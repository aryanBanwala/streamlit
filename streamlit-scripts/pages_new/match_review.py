"""
Match Review Dashboard
Upload mutual_matches JSON from matchmaking pipeline, then review each pair side by side with photos and metadata.
"""
import json
from datetime import datetime, timedelta, timezone
import streamlit as st
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from supabase import create_client

# --- Setup paths & env ---
current_dir = os.path.dirname(__file__)
scripts_dir = os.path.abspath(os.path.join(current_dir, '..'))
parent_dir = os.path.abspath(os.path.join(scripts_dir, '..'))
sys.path.insert(0, parent_dir)

dotenv_path = os.path.join(parent_dir, '.env')
load_dotenv(dotenv_path)

SUPABASE_URL_APP = os.getenv("SUPABASE_URL_APP_PROD", "")
SUPABASE_KEY_APP = os.getenv("SUPABASE_SERVICE_ROLE_KEY_APP_PROD", "")

SIGNED_URL_EXPIRY = 3600


@st.cache_resource
def get_client():
    if not SUPABASE_URL_APP or not SUPABASE_KEY_APP:
        st.error("Missing SUPABASE_URL_APP_PROD or SUPABASE_SERVICE_ROLE_KEY_APP_PROD in .env")
        st.stop()
    return create_client(SUPABASE_URL_APP, SUPABASE_KEY_APP)


# =========== JSON PARSING ===========

def parse_matches_json(data):
    """
    Parse uploaded mutual_matches JSON into deduplicated unique pairs.
    JSON format: { matches_by_user: { user_id: [ {matched_user_id, rank, mutual_score, ...} ] }, stats: {...} }
    """
    matches_by_user = data.get("matches_by_user", {})
    stats = data.get("stats", {})

    seen_pairs = set()
    unique_pairs = []

    for user_id, matches in matches_by_user.items():
        for m in matches:
            matched_id = m["matched_user_id"]
            pair_key = tuple(sorted([user_id, matched_id]))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            # Normalize: user_a is the one from pair_key[0]
            if user_id == pair_key[0]:
                unique_pairs.append({
                    "user_a": user_id,
                    "user_b": matched_id,
                    "mutual_score": m.get("mutual_score", 0),
                    "a_scores_b": m.get("viewer_scores_candidate"),
                    "b_scores_a": m.get("candidate_scores_viewer"),
                    "rank": m.get("rank"),
                    "origin_phase": m.get("origin_phase", "?"),
                    "origin_method": m.get("origin_method", "?"),
                    "origin_metadata": m.get("origin_metadata"),
                    "is_mutual": m.get("is_mutual"),
                })
            else:
                unique_pairs.append({
                    "user_a": matched_id,
                    "user_b": user_id,
                    "mutual_score": m.get("mutual_score", 0),
                    "a_scores_b": m.get("candidate_scores_viewer"),
                    "b_scores_a": m.get("viewer_scores_candidate"),
                    "rank": m.get("rank"),
                    "origin_phase": m.get("origin_phase", "?"),
                    "origin_method": m.get("origin_method", "?"),
                    "origin_metadata": m.get("origin_metadata"),
                    "is_mutual": m.get("is_mutual"),
                })

    unique_pairs.sort(key=lambda x: x.get("mutual_score") or 0, reverse=True)
    return unique_pairs, stats


# =========== SUPABASE FETCHERS (profiles + photos) ===========

@st.cache_data(ttl=300, show_spinner=False)
def fetch_profiles_batch(user_ids_tuple):
    """Fetch user_profile_data for a batch of user_ids."""
    user_ids = list(user_ids_tuple)
    if not user_ids:
        return {}
    sb = get_client()
    # Supabase IN has a limit, batch in chunks of 50
    all_results = {}
    for i in range(0, len(user_ids), 50):
        chunk = user_ids[i:i + 50]
        resp = sb.from_("user_profile_data").select(
            "user_id, full_name, gender, age, height, city, area, work, education, "
            "work_tag, education_tag, religion, orientation"
        ).in_("user_id", chunk).execute()
        for r in (resp.data or []):
            all_results[r["user_id"]] = r
    return all_results


@st.cache_data(ttl=300, show_spinner=False)
def fetch_photos_batch(user_ids_tuple):
    """Fetch photos + batch sign URLs for user_ids."""
    user_ids = list(user_ids_tuple)
    if not user_ids:
        return {}
    sb = get_client()

    all_photos = []
    for i in range(0, len(user_ids), 50):
        chunk = user_ids[i:i + 50]
        resp = sb.from_("user_photos").select(
            "user_id, url, category, position, is_display_photo"
        ).in_("user_id", chunk).order("position", desc=False).execute()
        all_photos.extend(resp.data or [])

    if not all_photos:
        return {uid: [] for uid in user_ids}

    # Batch sign all URLs
    all_paths = [p["url"] for p in all_photos if p.get("url")]
    signed_map = {}
    if all_paths:
        try:
            signed_results = sb.storage.from_("media").create_signed_urls(all_paths, SIGNED_URL_EXPIRY)
            for item in signed_results:
                path = item.get("path", "")
                url = item.get("signedURL") or item.get("signedUrl", "")
                if path:
                    signed_map[path] = url
        except Exception:
            pass

    for p in all_photos:
        p["signed_url"] = signed_map.get(p.get("url", ""), "")

    user_photos = {}
    for p in all_photos:
        user_photos.setdefault(p["user_id"], []).append(p)

    return {uid: user_photos.get(uid, []) for uid in user_ids}


def fetch_page_data(user_ids):
    """Fetch profiles and photos in parallel."""
    ids_tuple = tuple(user_ids)
    with ThreadPoolExecutor(max_workers=2) as executor:
        profile_future = executor.submit(fetch_profiles_batch, ids_tuple)
        photo_future = executor.submit(fetch_photos_batch, ids_tuple)
        return profile_future.result(), photo_future.result()


# =========== HELPERS ===========

def origin_badge(phase):
    """Return colored badge for origin phase."""
    if not phase:
        return ""
    colors = {
        "GREEDY_STRICT": "#4caf50",
        "RELAXED_L1": "#8bc34a",
        "RELAXED_L2": "#ff9800",
        "RELAXED_L3": "#f44336",
        "EXPLORATION": "#9c27b0",
        "dummy_seed": "#607d8b",
    }
    color = colors.get(phase, "#9e9e9e")
    return f'<span style="background:{color}; color:white; padding:2px 8px; border-radius:4px; font-size:12px; font-weight:600;">{phase}</span>'


def render_user_card(profile, photos, photo_scale):
    """Render a user's info + photos."""
    if not profile:
        st.warning("Profile not found")
        return

    name = profile.get("full_name", "N/A")
    age = profile.get("age", "?")
    gender = profile.get("gender", "?")
    city = profile.get("city", "?")
    work = profile.get("work_tag") or profile.get("work") or "N/A"
    edu = profile.get("education_tag") or profile.get("education") or "N/A"
    height = profile.get("height", "?")
    religion = profile.get("religion", "?")

    gender_color = "#1976d2" if gender == "male" else "#e91e63" if gender == "female" else "#9e9e9e"

    st.markdown(
        f"**{name}**, {age} "
        f'<span style="color:{gender_color}; font-weight:600;">({gender})</span>',
        unsafe_allow_html=True,
    )
    st.caption(f"{city} · {height}\" · {religion}")
    st.caption(f"Work: {work}")
    st.caption(f"Edu: {edu}")
    st.code(profile.get("user_id", ""), language=None)

    # Photos
    if not photos:
        st.warning("No photos")
        return

    for photo in photos:
        url = photo.get("signed_url", "")
        if url:
            is_display = photo.get("is_display_photo", False)
            caption = f"{'⭐ Display · ' if is_display else ''}pos:{photo.get('position', '?')}"
            st.markdown(
                f'<div style="width:{photo_scale}%; border-radius:8px; margin-bottom:8px;">'
                f'<img src="{url}" style="width:100%; border-radius:8px;" />'
                f'</div>'
                f'<p style="font-size:11px; color:grey; margin-top:-4px;">{caption}</p>',
                unsafe_allow_html=True,
            )


# ============== UI ==============

st.markdown("#### Match Review")

# --- Sidebar ---
st.sidebar.markdown("### Upload")
uploaded_file = st.sidebar.file_uploader("Upload mutual_matches JSON", type=["json"])

if not uploaded_file:
    st.info("Upload a `mutual_matches_*.json` file from the matchmaking pipeline to get started.")
    st.stop()

# Parse JSON
raw = json.loads(uploaded_file.read())
all_matches, run_stats = parse_matches_json(raw)

# --- Sidebar filters ---
st.sidebar.markdown("### Filters")

# Origin phase filter
available_phases = sorted(set(m["origin_phase"] for m in all_matches))
phase_filter = st.sidebar.selectbox("Origin Phase", ["All"] + available_phases)

# Photo scale
photo_scale = st.sidebar.slider("Photo Size (%)", min_value=20, max_value=100, value=60, step=10,
                                 help="Scale photos on screen")

MATCHES_PER_PAGE = st.sidebar.number_input("Matches per page", min_value=1, max_value=20, value=5)

if st.sidebar.button("Clear Cache"):
    st.cache_data.clear()
    st.rerun()

# --- Run stats ---
st.sidebar.markdown("---")
st.sidebar.markdown("### Run Stats")
st.sidebar.markdown(f"**Generated:** {raw.get('generated_at', 'N/A')}")
st.sidebar.markdown(f"**Total users:** {run_stats.get('total_users', '?')}")
st.sidebar.markdown(f"**Fully filled:** {run_stats.get('users_fully_filled', '?')}")
st.sidebar.markdown(f"**Partially filled:** {run_stats.get('users_partially_filled', '?')}")
st.sidebar.markdown(f"**Zero matches:** {run_stats.get('users_with_zero', '?')}")

# Apply phase filter
if phase_filter != "All":
    all_matches = [m for m in all_matches if m["origin_phase"] == phase_filter]

total = len(all_matches)

# --- Stats bar ---
phase_counts = run_stats.get("phase_counts", {})
if not phase_counts:
    phase_counts = {}
    for m in all_matches:
        p = m.get("origin_phase", "unknown")
        phase_counts[p] = phase_counts.get(p, 0) + 1

stats_cols = st.columns(min(len(phase_counts) + 1, 6))
with stats_cols[0]:
    st.metric("Total Pairs", run_stats.get("total_pairs", total))
for i, (phase, count) in enumerate(sorted(phase_counts.items())):
    if i + 1 < len(stats_cols):
        with stats_cols[i + 1]:
            st.metric(phase, count)

if total == 0:
    st.info("No matches found for this filter.")
    st.stop()

# --- Pagination ---
total_pages = (total + MATCHES_PER_PAGE - 1) // MATCHES_PER_PAGE
if "mr_page" not in st.session_state:
    st.session_state.mr_page = 1
if st.session_state.mr_page > total_pages:
    st.session_state.mr_page = total_pages


def _go_prev():
    st.session_state.mr_page = max(1, st.session_state.mr_page - 1)

def _go_next():
    st.session_state.mr_page = min(total_pages, st.session_state.mr_page + 1)

def render_pagination(suffix):
    """Render pagination controls. suffix differentiates top/bottom widget keys."""
    col_prev, col_info, col_next = st.columns([1, 3, 1])
    with col_prev:
        st.button("← Prev", disabled=st.session_state.mr_page <= 1,
                  use_container_width=True, key=f"mr_prev_{suffix}", on_click=_go_prev)
    with col_info:
        st.markdown(
            f"<p style='text-align:center; margin:8px 0; color:grey;'>"
            f"Page {st.session_state.mr_page} / {total_pages} &nbsp;&middot;&nbsp; {total} pairs</p>",
            unsafe_allow_html=True,
        )
    with col_next:
        st.button("Next →", disabled=st.session_state.mr_page >= total_pages,
                  use_container_width=True, key=f"mr_next_{suffix}", on_click=_go_next)


render_pagination("top")

start = (st.session_state.mr_page - 1) * MATCHES_PER_PAGE
page_matches = all_matches[start:start + MATCHES_PER_PAGE]

# Collect all user_ids for this page
page_user_ids = list(set(
    uid for m in page_matches for uid in [m["user_a"], m["user_b"]]
))

# --- Batch fetch profiles + photos from Supabase ---
with st.spinner("Loading profiles & photos..."):
    profiles, photos = fetch_page_data(page_user_ids)

# --- Render each match pair ---
for idx, match in enumerate(page_matches):
    user_a = match["user_a"]
    user_b = match["user_b"]
    score = match.get("mutual_score") or 0
    phase = match.get("origin_phase", "?")
    method = match.get("origin_method", "?")

    profile_a = profiles.get(user_a, {})
    profile_b = profiles.get(user_b, {})
    name_a = profile_a.get("full_name") or "?"
    name_b = profile_b.get("full_name") or "?"

    # Header
    st.markdown("---")
    st.markdown(
        f"##### Match #{start + idx + 1}: {name_a} & {name_b} &nbsp;&nbsp; "
        f'<span style="font-size:14px;">Score: <b>{round(score, 4)}</b></span> &nbsp; '
        f'{origin_badge(phase)}',
        unsafe_allow_html=True,
    )

    # Match metadata row
    meta_cols = st.columns(5)
    with meta_cols[0]:
        st.caption(f"Mutual: **{round(score, 4)}**")
    with meta_cols[1]:
        a_score = match.get("a_scores_b")
        st.caption(f"A→B: **{round(a_score, 4) if a_score is not None else 'N/A'}**")
    with meta_cols[2]:
        b_score = match.get("b_scores_a")
        st.caption(f"B→A: **{round(b_score, 4) if b_score is not None else 'N/A'}**")
    with meta_cols[3]:
        st.caption(f"Rank: **{match.get('rank', '?')}**")
    with meta_cols[4]:
        st.caption(f"Method: **{method}**")

    if match.get("origin_metadata"):
        with st.expander("Origin Metadata", expanded=False):
            st.json(match["origin_metadata"])

    # --- Reject logic ---
    match_key = f"{user_a}_{user_b}"
    reject_key = f"reject_{match_key}"
    rejected_key = f"rejected_{match_key}"
    is_rejected = match.get("rejected") or st.session_state.get(rejected_key)

    if is_rejected:
        st.error("**Rejected** — 1-week cooldown active for this pair.")
    else:
        # Top reject button
        if st.button("Reject Match", key=f"btn_reject_{match_key}_top", type="primary", use_container_width=True):
            st.session_state[reject_key] = True

        if st.session_state.get(reject_key):
            st.warning(f"**Reject {name_a} & {name_b}?** This will add a 1-week cooldown.")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Yes, reject", key=f"btn_yes_{match_key}", type="primary", use_container_width=True):
                    try:
                        sb = get_client()
                        expires = (datetime.now(timezone.utc) + timedelta(weeks=1)).isoformat()
                        sb.rpc("upsert_match_cooldown", {
                            "p_user_a": user_a,
                            "p_user_b": user_b,
                            "p_type": "manual_rejection",
                            "p_expires_at": expires,
                        }).execute()
                        st.session_state.pop(reject_key, None)
                        st.session_state[rejected_key] = True
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")
            with c2:
                if st.button("Cancel", key=f"btn_cancel_{match_key}", use_container_width=True):
                    st.session_state.pop(reject_key, None)
                    st.rerun()

    # Side by side: User A | User B
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("**User A**")
        render_user_card(profile_a, photos.get(user_a, []), photo_scale)

    with col_b:
        st.markdown("**User B**")
        render_user_card(profile_b, photos.get(user_b, []), photo_scale)

    # Bottom reject button
    if not is_rejected:
        if st.button("Reject Match", key=f"btn_reject_{match_key}_bottom", type="primary", use_container_width=True):
            st.session_state[reject_key] = True

# --- Bottom pagination ---
st.markdown("---")
render_pagination("bottom")
