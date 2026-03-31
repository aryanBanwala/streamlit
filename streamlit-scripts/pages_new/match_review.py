"""
Match Review Dashboard
Upload mutual_matches JSON from matchmaking pipeline, then review each pair side by side with photos and metadata.
"""
import json
import base64
from datetime import datetime, timedelta, timezone
import streamlit as st
import os
import sys
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
import psycopg2
import psycopg2.extras
from google.cloud import storage
from google.oauth2 import service_account

# --- Setup paths & env ---
current_dir = os.path.dirname(__file__)
scripts_dir = os.path.abspath(os.path.join(current_dir, '..'))
parent_dir = os.path.abspath(os.path.join(scripts_dir, '..'))
sys.path.insert(0, parent_dir)

dotenv_path = os.path.join(parent_dir, '.env')
load_dotenv(dotenv_path)

DB_HOST = os.getenv("DB_HOST", "")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "")
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "")
GCS_PROJECT_ID = os.getenv("GCS_PROJECT_ID", "")
GCS_CREDENTIALS_BASE64 = os.getenv("GCS_CREDENTIALS_BASE64", "")

SIGNED_URL_EXPIRY = 3600


def _new_db_conn():
    if not DB_HOST or not DB_NAME:
        st.error("Missing DB_HOST or DB_NAME in .env")
        st.stop()
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


_conn_holder = {"conn": None}


def get_db_conn():
    conn = _conn_holder["conn"]
    if conn is None or conn.closed:
        _conn_holder["conn"] = _new_db_conn()
    return _conn_holder["conn"]


@st.cache_resource
def get_gcs_bucket():
    if GCS_CREDENTIALS_BASE64:
        sa_info = json.loads(base64.b64decode(GCS_CREDENTIALS_BASE64))
        creds = service_account.Credentials.from_service_account_info(sa_info)
        client = storage.Client(project=GCS_PROJECT_ID, credentials=creds)
    else:
        client = storage.Client(project=GCS_PROJECT_ID)
    return client.bucket(GCS_BUCKET_NAME)


def _db_query(sql, params=None):
    """Run a read query and return list of dicts."""
    try:
        conn = get_db_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    except (psycopg2.InterfaceError, psycopg2.OperationalError):
        _conn_holder["conn"] = None
        conn = get_db_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def _db_execute(sql, params=None):
    """Run a write query (INSERT/UPDATE)."""
    try:
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()
    except (psycopg2.InterfaceError, psycopg2.OperationalError):
        _conn_holder["conn"] = None
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()


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

def _gcs_sign_url(path):
    """Generate a signed URL for a GCS object."""
    bucket = get_gcs_bucket()
    blob = bucket.blob(path)
    return blob.generate_signed_url(
        version="v4",
        expiration=timedelta(seconds=SIGNED_URL_EXPIRY),
        method="GET",
    )


def _gcs_sign_urls_batch(paths):
    """Sign multiple GCS paths, return {path: signed_url}."""
    if not paths:
        return {}
    signed_map = {}
    for path in paths:
        try:
            signed_map[path] = _gcs_sign_url(path)
        except Exception:
            pass
    return signed_map


@st.cache_data(ttl=300, show_spinner=False)
def fetch_genders_batch(user_ids_tuple):
    """Fetch only user_id + gender for all users (lightweight)."""
    user_ids = list(user_ids_tuple)
    if not user_ids:
        return {}
    rows = _db_query(
        "SELECT user_id, gender FROM user_profile_data WHERE user_id = ANY(%s::uuid[])",
        (user_ids,)
    )
    return {r["user_id"]: r.get("gender") or "unknown" for r in rows}


@st.cache_data(ttl=300, show_spinner=False)
def fetch_ai_processing_batch(user_ids_tuple):
    """Fetch attractiveness_score and attractiveness_reasoning from ai_processing_state."""
    user_ids = list(user_ids_tuple)
    if not user_ids:
        return {}
    rows = _db_query(
        "SELECT user_id, attractiveness_score, attractiveness_reasoning FROM ai_processing_state WHERE user_id = ANY(%s::uuid[])",
        (user_ids,)
    )
    return {r["user_id"]: dict(r) for r in rows}


@st.cache_data(ttl=300, show_spinner=False)
def fetch_matchmaking_state_batch(user_ids_tuple):
    """Fetch prof_tier and prof_tier_reason from matchmaking_user_state."""
    user_ids = list(user_ids_tuple)
    if not user_ids:
        return {}
    rows = _db_query(
        "SELECT user_id, prof_tier, prof_tier_reason FROM matchmaking_user_state WHERE user_id = ANY(%s::uuid[])",
        (user_ids,)
    )
    return {r["user_id"]: dict(r) for r in rows}


@st.cache_data(ttl=300, show_spinner=False)
def fetch_profiles_batch(user_ids_tuple):
    """Fetch user_profile_data for a batch of user_ids."""
    user_ids = list(user_ids_tuple)
    if not user_ids:
        return {}
    rows = _db_query(
        "SELECT user_id, full_name, gender, age, height, city, area, work, education, "
        "work_tag, education_tag, religion, orientation "
        "FROM user_profile_data WHERE user_id = ANY(%s::uuid[])",
        (user_ids,)
    )
    return {r["user_id"]: dict(r) for r in rows}


@st.cache_data(ttl=300, show_spinner=False)
def fetch_photos_batch(user_ids_tuple):
    """Fetch photos + batch sign URLs for user_ids."""
    user_ids = list(user_ids_tuple)
    if not user_ids:
        return {}

    rows = _db_query(
        "SELECT user_id, url, category, position, is_display_photo "
        "FROM user_photos WHERE user_id = ANY(%s::uuid[]) ORDER BY position ASC",
        (user_ids,)
    )
    all_photos = [dict(r) for r in rows]

    if not all_photos:
        return {uid: [] for uid in user_ids}

    # Batch sign all URLs via GCS
    all_paths = [p["url"] for p in all_photos if p.get("url")]
    signed_map = _gcs_sign_urls_batch(all_paths)

    for p in all_photos:
        p["signed_url"] = signed_map.get(p.get("url", ""), "")

    user_photos = {}
    for p in all_photos:
        user_photos.setdefault(p["user_id"], []).append(p)

    return {uid: user_photos.get(uid, []) for uid in user_ids}


def fetch_page_data(user_ids):
    """Fetch profiles, photos, AI processing state, and matchmaking state in parallel."""
    ids_tuple = tuple(user_ids)
    with ThreadPoolExecutor(max_workers=4) as executor:
        profile_future = executor.submit(fetch_profiles_batch, ids_tuple)
        photo_future = executor.submit(fetch_photos_batch, ids_tuple)
        ai_future = executor.submit(fetch_ai_processing_batch, ids_tuple)
        mm_future = executor.submit(fetch_matchmaking_state_batch, ids_tuple)
        return (
            profile_future.result(),
            photo_future.result(),
            ai_future.result(),
            mm_future.result(),
        )


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


def render_user_card(profile, photos, photo_scale, ai_state=None, mm_state=None):
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

    # Attractiveness & Prof Tier
    ai = ai_state or {}
    mm = mm_state or {}
    attr_score = ai.get("attractiveness_score")
    prof_tier = mm.get("prof_tier", "?")
    tier_colors = {"S": "#4caf50", "A": "#8bc34a", "B": "#ff9800", "C": "#f44336", "D": "#9e9e9e"}
    tier_color = tier_colors.get(str(prof_tier).upper()[:1], "#607d8b")
    st.markdown(
        f'Attractiveness: **{round(attr_score, 2) if attr_score is not None else "N/A"}** &nbsp;&nbsp; '
        f'Prof Tier: <span style="background:{tier_color}; color:white; padding:1px 6px; border-radius:4px; font-size:12px; font-weight:600;">{prof_tier}</span>',
        unsafe_allow_html=True,
    )
    attr_reason = ai.get("attractiveness_reasoning")
    tier_reason = mm.get("prof_tier_reason")
    if attr_reason or tier_reason:
        with st.expander("Reasoning", expanded=False):
            if attr_reason:
                st.markdown(f"**Attractiveness:** {attr_reason}")
            if tier_reason:
                st.markdown(f"**Prof Tier:** {tier_reason}")

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


def parse_display_metadata(data):
    """Parse display_metadata_samples into a lookup dict keyed by sorted pair tuple."""
    samples = data.get("display_metadata_samples", [])
    lookup = {}
    for sample in samples:
        u1 = sample.get("user_1_id", "")
        u2 = sample.get("user_2_id", "")
        if not u1 or not u2:
            continue
        pair_key = tuple(sorted([u1, u2]))
        lookup[pair_key] = sample
    return lookup


def parse_why_you_two(data):
    """Parse why_you_two_results into a lookup dict keyed by sorted pair tuple."""
    results = data.get("why_you_two_results", [])
    lookup = {}
    for item in results:
        u1 = item.get("user_1_id", "")
        u2 = item.get("user_2_id", "")
        if not u1 or not u2:
            continue
        pair_key = tuple(sorted([u1, u2]))
        lookup[pair_key] = item
    return lookup


def sign_storage_paths(paths):
    """Sign a list of storage paths and return {path: signed_url}."""
    if not paths:
        return {}
    signed_map = {}
    try:
        signed_map = _gcs_sign_urls_batch(paths)
    except Exception as e:
        st.warning(f"Failed to sign storage paths: {e}")
    return signed_map


def render_display_section(section, signed_urls):
    """Render a single display data section as a styled card."""
    sec_type = section.get("type", "")
    title = section.get("title", "")
    content = section.get("content", "")

    if sec_type == "paragraph":
        st.markdown(
            f'<div style="background:#1e1e2e; border-radius:12px; padding:16px 20px; margin-bottom:12px;">'
            f'<p style="color:#a0a0b8; font-size:11px; text-transform:uppercase; letter-spacing:1px; margin:0 0 6px 0;">{title}</p>'
            f'<p style="color:#e0e0e8; font-size:14px; line-height:1.6; margin:0;">{content}</p>'
            f'</div>',
            unsafe_allow_html=True,
        )

    elif sec_type == "display_picture":
        url = signed_urls.get(content, "")
        if url:
            st.markdown(
                f'<div style="border-radius:12px; overflow:hidden; margin-bottom:12px;">'
                f'<img src="{url}" style="width:100%; border-radius:12px;" />'
                f'</div>',
                unsafe_allow_html=True,
            )

    elif sec_type == "profile_card":
        fields = content.get("fields", []) if isinstance(content, dict) else []
        title_field = content.get("titleField", {}) if isinstance(content, dict) else {}
        subtitle_field = content.get("subtitleField", {}) if isinstance(content, dict) else {}

        name_val = title_field.get("value", "?")
        age_val = subtitle_field.get("value", "?")

        card_fields_html = ""
        for f in fields:
            if f.get("show_on_card") or f.get("show_in_drawer"):
                emoji = f.get("emoji", "")
                label = f.get("label", "")
                value = f.get("value", "")
                card_fields_html += (
                    f'<div style="display:inline-block; background:#2a2a3e; border-radius:8px; padding:6px 12px; margin:4px; font-size:13px;">'
                    f'{emoji} <span style="color:#8888a0;">{label}:</span> <span style="color:#e0e0e8;">{value}</span>'
                    f'</div>'
                )

        st.markdown(
            f'<div style="background:#1e1e2e; border-radius:12px; padding:20px; margin-bottom:12px;">'
            f'<p style="color:#ffffff; font-size:20px; font-weight:700; margin:0 0 2px 0;">{name_val}</p>'
            f'<p style="color:#a0a0b8; font-size:14px; margin:0 0 12px 0;">Age: {age_val}</p>'
            f'<div style="display:flex; flex-wrap:wrap; gap:4px;">{card_fields_html}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    elif sec_type == "timeline":
        items = content if isinstance(content, list) else []
        timeline_html = ""
        for i, item in enumerate(items):
            timeline_html += (
                f'<div style="display:flex; gap:12px; margin-bottom:12px;">'
                f'<div style="display:flex; flex-direction:column; align-items:center;">'
                f'<div style="width:10px; height:10px; border-radius:50%; background:#6366f1; margin-top:5px;"></div>'
                f'{"<div style=\"width:2px; flex:1; background:#333;\"></div>" if i < len(items) - 1 else ""}'
                f'</div>'
                f'<p style="color:#e0e0e8; font-size:13px; line-height:1.5; margin:0; padding-bottom:4px;">{item}</p>'
                f'</div>'
            )
        st.markdown(
            f'<div style="background:#1e1e2e; border-radius:12px; padding:16px 20px; margin-bottom:12px;">'
            f'<p style="color:#a0a0b8; font-size:11px; text-transform:uppercase; letter-spacing:1px; margin:0 0 12px 0;">{title}</p>'
            f'{timeline_html}'
            f'</div>',
            unsafe_allow_html=True,
        )

    elif sec_type == "photos":
        photos_list = content if isinstance(content, list) else []
        photos_html = ""
        for p in photos_list:
            path = p.get("path", "")
            url = signed_urls.get(path, "")
            if url:
                photos_html += (
                    f'<div style="width:48%; border-radius:8px; overflow:hidden; margin-bottom:8px;">'
                    f'<img src="{url}" style="width:100%; border-radius:8px;" />'
                    f'</div>'
                )
        if photos_html:
            st.markdown(
                f'<div style="background:#1e1e2e; border-radius:12px; padding:16px 20px; margin-bottom:12px;">'
                f'<p style="color:#a0a0b8; font-size:11px; text-transform:uppercase; letter-spacing:1px; margin:0 0 12px 0;">{title}</p>'
                f'<div style="display:flex; flex-wrap:wrap; gap:8px; justify-content:flex-start;">{photos_html}</div>'
                f'</div>',
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
display_lookup = parse_display_metadata(raw)
why_you_two_lookup = parse_why_you_two(raw)
match_lookup = {tuple(sorted([m["user_a"], m["user_b"]])): m for m in all_matches}

# --- Sidebar filters ---
st.sidebar.markdown("### Filters")

# Search by user_id
_search_input = st.sidebar.text_input("Search User ID", placeholder="Paste a user_id to filter matches...")
_search_clicked = st.sidebar.button("Search", use_container_width=True)
if _search_clicked and _search_input:
    st.session_state["search_user_id"] = _search_input.strip()
elif _search_clicked and not _search_input:
    st.session_state.pop("search_user_id", None)
search_user_id = st.session_state.get("search_user_id", "")

# Origin phase filter
available_phases = sorted(set(m["origin_phase"] for m in all_matches))
phase_filter = st.sidebar.selectbox("Origin Phase", ["All"] + available_phases)

# Gender sort — detect available genders from data
_all_uids_for_gender = list(set(uid for m in all_matches for uid in [m["user_a"], m["user_b"]]))
_gender_map_preview = fetch_genders_batch(tuple(sorted(_all_uids_for_gender)))
_available_genders = sorted(set(_gender_map_preview.values()) - {"unknown"})
gender_sort = st.sidebar.selectbox("Group by Gender", ["None"] + _available_genders)

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

# Apply user_id search — show only matches listed under that user in matches_by_user
if search_user_id:
    search_term = search_user_id.strip()
    user_matched_ids = set()
    for m in (raw.get("matches_by_user", {}).get(search_term, [])):
        user_matched_ids.add(m["matched_user_id"])
    if user_matched_ids:
        all_matches = [m for m in all_matches
                       if (m["user_a"] == search_term and m["user_b"] in user_matched_ids)
                       or (m["user_b"] == search_term and m["user_a"] in user_matched_ids)]
    else:
        all_matches = []

# Apply gender grouping
if gender_sort != "None":
    gender_map = _gender_map_preview

    # For each match, find the user(s) matching the selected gender
    # Group: { user_id -> [matches] } for users of the selected gender
    grouped = OrderedDict()
    ungrouped = []
    for m in all_matches:
        a_gender = gender_map.get(m["user_a"], "unknown")
        b_gender = gender_map.get(m["user_b"], "unknown")
        if a_gender == gender_sort:
            grouped.setdefault(m["user_a"], []).append(m)
        elif b_gender == gender_sort:
            grouped.setdefault(m["user_b"], []).append(m)
        else:
            ungrouped.append(m)

    # Rebuild all_matches: each group's matches sorted by score, then ungrouped at the end
    all_matches = []
    for uid, matches in grouped.items():
        matches.sort(key=lambda x: x.get("mutual_score") or 0, reverse=True)
        all_matches.extend(matches)
    all_matches.extend(ungrouped)

total = len(all_matches)

# --- Stats bar ---
phase_counts = run_stats.get("phase_counts", {})
if not phase_counts:
    phase_counts = {}
    for m in all_matches:
        p = m.get("origin_phase", "unknown")
        phase_counts[p] = phase_counts.get(p, 0) + 1

unique_users = set(uid for m in all_matches for uid in [m["user_a"], m["user_b"]])
stats_cols = st.columns(min(len(phase_counts) + 2, 7))
with stats_cols[0]:
    st.metric("Total Pairs", run_stats.get("total_pairs", total))
with stats_cols[1]:
    st.metric("Unique Users", len(unique_users))
for i, (phase, count) in enumerate(sorted(phase_counts.items())):
    if i + 2 < len(stats_cols):
        with stats_cols[i + 2]:
            st.metric(phase, count)

if total == 0:
    st.info("No matches found for this filter.")
    st.stop()

# --- Tabs ---
tab_review, tab_display = st.tabs(["Match Review", "Display Data"])

# ===================== TAB 1: MATCH REVIEW =====================
with tab_review:
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

    page_user_ids = list(set(
        uid for m in page_matches for uid in [m["user_a"], m["user_b"]]
    ))

    with st.spinner("Loading profiles & photos..."):
        profiles, photos, ai_states, mm_states = fetch_page_data(page_user_ids)

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

        st.markdown("---")
        st.markdown(
            f"##### Match #{start + idx + 1}: {name_a} & {name_b} &nbsp;&nbsp; "
            f'<span style="font-size:14px;">Score: <b>{round(score, 4)}</b></span> &nbsp; '
            f'{origin_badge(phase)}',
            unsafe_allow_html=True,
        )

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

        # Why You Two
        pair_key = tuple(sorted([user_a, user_b]))
        wyt = why_you_two_lookup.get(pair_key)
        if wyt and wyt.get("success") and wyt.get("why_you_two"):
            wyt_content = wyt["why_you_two"].get("content", "")
            if wyt_content:
                st.markdown(
                    f'<div style="background:linear-gradient(135deg, #6366f1 0%, #ec4899 100%); border-radius:12px; padding:14px 20px; margin:8px 0;">'
                    f'<p style="color:rgba(255,255,255,0.7); font-size:11px; text-transform:uppercase; letter-spacing:1px; margin:0 0 4px 0;">Why You Two</p>'
                    f'<p style="color:#ffffff; font-size:15px; font-weight:500; line-height:1.5; margin:0;">{wyt_content}</p>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        match_key = f"{user_a}_{user_b}"
        reject_key = f"reject_{match_key}"
        rejected_key = f"rejected_{match_key}"
        is_rejected = match.get("rejected") or st.session_state.get(rejected_key)

        if is_rejected:
            st.error("**Rejected** — 1-week cooldown active for this pair.")
        else:
            if st.button("Reject Match", key=f"btn_reject_{match_key}_top", type="primary", use_container_width=True):
                st.session_state[reject_key] = True

            if st.session_state.get(reject_key):
                st.warning(f"**Reject {name_a} & {name_b}?** This will add a 1-week cooldown.")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Yes, reject", key=f"btn_yes_{match_key}", type="primary", use_container_width=True):
                        try:
                            sorted_pair = sorted([user_a, user_b])
                            expires = datetime.now(timezone.utc) + timedelta(weeks=1)
                            _db_execute(
                                'INSERT INTO match_cooldowns (user_a_id, user_b_id, "type", expires_at) '
                                "VALUES (%s, %s, %s, %s) "
                                'ON CONFLICT (user_a_id, user_b_id, "type") DO UPDATE SET expires_at = EXCLUDED.expires_at',
                                (sorted_pair[0], sorted_pair[1], "manual_rejection", expires)
                            )
                            st.session_state.pop(reject_key, None)
                            st.session_state[rejected_key] = True
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed: {e}")
                with c2:
                    if st.button("Cancel", key=f"btn_cancel_{match_key}", use_container_width=True):
                        st.session_state.pop(reject_key, None)
                        st.rerun()

        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**User A**")
            render_user_card(profile_a, photos.get(user_a, []), photo_scale,
                             ai_states.get(user_a), mm_states.get(user_a))
        with col_b:
            st.markdown("**User B**")
            render_user_card(profile_b, photos.get(user_b, []), photo_scale,
                             ai_states.get(user_b), mm_states.get(user_b))

        if not is_rejected:
            if st.button("Reject Match", key=f"btn_reject_{match_key}_bottom", type="primary", use_container_width=True):
                st.session_state[reject_key] = True

        # Inline display data preview if available
        pair_key_dd = tuple(sorted([user_a, user_b]))
        dd_sample = display_lookup.get(pair_key_dd)
        if dd_sample:
            with st.expander("View Display Data", expanded=False):
                # Collect and sign paths for this pair
                dd_paths = []
                for dd_key in ("display_data_of_user_1", "display_data_of_user_2"):
                    for section in dd_sample.get(dd_key, []):
                        if section.get("type") == "display_picture":
                            dd_paths.append(section.get("content", ""))
                        elif section.get("type") == "photos":
                            for p in (section.get("content", []) if isinstance(section.get("content"), list) else []):
                                dd_paths.append(p.get("path", ""))
                dd_paths = [p for p in dd_paths if p]
                dd_signed = sign_storage_paths(dd_paths)

                dd_name_1 = profiles.get(dd_sample.get("user_1_id", ""), {}).get("full_name") or dd_sample.get("user_1_id", "")[:8]
                dd_name_2 = profiles.get(dd_sample.get("user_2_id", ""), {}).get("full_name") or dd_sample.get("user_2_id", "")[:8]

                dd_col1, dd_col2 = st.columns(2)
                with dd_col1:
                    st.markdown(
                        f'<p style="color:#6366f1; font-weight:700; font-size:15px; margin-bottom:8px;">'
                        f'What {dd_name_1} sees about {dd_name_2}</p>',
                        unsafe_allow_html=True,
                    )
                    for section in sorted(dd_sample.get("display_data_of_user_1", []), key=lambda x: x.get("order", 0)):
                        render_display_section(section, dd_signed)
                with dd_col2:
                    st.markdown(
                        f'<p style="color:#ec4899; font-weight:700; font-size:15px; margin-bottom:8px;">'
                        f'What {dd_name_2} sees about {dd_name_1}</p>',
                        unsafe_allow_html=True,
                    )
                    for section in sorted(dd_sample.get("display_data_of_user_2", []), key=lambda x: x.get("order", 0)):
                        render_display_section(section, dd_signed)

    st.markdown("---")
    render_pagination("bottom")

# ===================== TAB 2: DISPLAY DATA =====================
with tab_display:
    display_samples = raw.get("display_metadata_samples", [])

    # Apply user_id search filter to display tab too
    if search_user_id:
        search_term = search_user_id.strip().lower()
        display_samples = [s for s in display_samples
                           if s.get("user_1_id", "").lower() == search_term
                           or s.get("user_2_id", "").lower() == search_term]

    if not display_samples:
        st.info("No display data found in this JSON.")
    else:
        st.markdown(f"**{len(display_samples)} display data samples available**")

        # Pagination for display tab
        DISPLAY_PER_PAGE = MATCHES_PER_PAGE
        display_total = len(display_samples)
        display_total_pages = (display_total + DISPLAY_PER_PAGE - 1) // DISPLAY_PER_PAGE

        if "dd_page" not in st.session_state:
            st.session_state.dd_page = 1
        if st.session_state.dd_page > display_total_pages:
            st.session_state.dd_page = display_total_pages

        def _dd_prev():
            st.session_state.dd_page = max(1, st.session_state.dd_page - 1)

        def _dd_next():
            st.session_state.dd_page = min(display_total_pages, st.session_state.dd_page + 1)

        def render_dd_pagination(suffix):
            col_prev, col_info, col_next = st.columns([1, 3, 1])
            with col_prev:
                st.button("← Prev", disabled=st.session_state.dd_page <= 1,
                          use_container_width=True, key=f"dd_prev_{suffix}", on_click=_dd_prev)
            with col_info:
                st.markdown(
                    f"<p style='text-align:center; margin:8px 0; color:grey;'>"
                    f"Page {st.session_state.dd_page} / {display_total_pages} &nbsp;&middot;&nbsp; {display_total} samples</p>",
                    unsafe_allow_html=True,
                )
            with col_next:
                st.button("Next →", disabled=st.session_state.dd_page >= display_total_pages,
                          use_container_width=True, key=f"dd_next_{suffix}", on_click=_dd_next)

        render_dd_pagination("top")

        dd_start = (st.session_state.dd_page - 1) * DISPLAY_PER_PAGE
        page_display = display_samples[dd_start:dd_start + DISPLAY_PER_PAGE]

        # Sign only current page's display paths
        all_display_paths = []
        for sample in page_display:
            for key in ("display_data_of_user_1", "display_data_of_user_2"):
                for section in sample.get(key, []):
                    if section.get("type") == "display_picture":
                        all_display_paths.append(section.get("content", ""))
                    elif section.get("type") == "photos":
                        for p in (section.get("content", []) if isinstance(section.get("content"), list) else []):
                            all_display_paths.append(p.get("path", ""))
        all_display_paths = [p for p in all_display_paths if p]

        with st.spinner("Signing display URLs..."):
            display_signed_urls = sign_storage_paths(all_display_paths)

        # Fetch names for display pairs
        dd_user_ids = list(set(
            uid for s in page_display for uid in [s.get("user_1_id", ""), s.get("user_2_id", "")] if uid
        ))
        dd_profiles = fetch_profiles_batch(tuple(sorted(dd_user_ids)))

        for idx, sample in enumerate(page_display):
            u1 = sample.get("user_1_id", "")
            u2 = sample.get("user_2_id", "")
            success = sample.get("success", False)
            name_1 = dd_profiles.get(u1, {}).get("full_name") or u1[:8]
            name_2 = dd_profiles.get(u2, {}).get("full_name") or u2[:8]

            st.markdown("---")
            status_color = "#4caf50" if success else "#f44336"
            st.markdown(
                f"##### Pair #{dd_start + idx + 1}: {name_1} & {name_2} &nbsp;&nbsp; "
                f'<span style="background:{status_color}; color:white; padding:2px 8px; border-radius:4px; font-size:12px;">{"Success" if success else "Failed"}</span>',
                unsafe_allow_html=True,
            )
            id_col1, id_col2 = st.columns(2)
            with id_col1:
                st.code(u1, language=None)
            with id_col2:
                st.code(u2, language=None)

            # Two columns: what user_1 sees (about user_2) | what user_2 sees (about user_1)
            col_1, col_2 = st.columns(2)

            with col_1:
                st.markdown(
                    f'<p style="color:#6366f1; font-weight:700; font-size:15px; margin-bottom:8px;">'
                    f'What {name_1} sees about {name_2}</p>',
                    unsafe_allow_html=True,
                )
                sections_1 = sorted(sample.get("display_data_of_user_1", []),
                                    key=lambda x: x.get("order", 0))
                for section in sections_1:
                    render_display_section(section, display_signed_urls)

            with col_2:
                st.markdown(
                    f'<p style="color:#ec4899; font-weight:700; font-size:15px; margin-bottom:8px;">'
                    f'What {name_2} sees about {name_1}</p>',
                    unsafe_allow_html=True,
                )
                sections_2 = sorted(sample.get("display_data_of_user_2", []),
                                    key=lambda x: x.get("order", 0))
                for section in sections_2:
                    render_display_section(section, display_signed_urls)

            # Inline match review if available
            dd_pair_key = tuple(sorted([u1, u2]))
            dd_match = match_lookup.get(dd_pair_key)
            if dd_match:
                with st.expander("View Match Review", expanded=False):
                    dd_ua = dd_match["user_a"]
                    dd_ub = dd_match["user_b"]
                    dd_score = dd_match.get("mutual_score") or 0
                    dd_phase = dd_match.get("origin_phase", "?")
                    dd_method = dd_match.get("origin_method", "?")

                    st.markdown(
                        f'Score: **{round(dd_score, 4)}** &nbsp; {origin_badge(dd_phase)} &nbsp; Method: **{dd_method}**',
                        unsafe_allow_html=True,
                    )
                    mr_cols = st.columns(4)
                    with mr_cols[0]:
                        st.caption(f"Mutual: **{round(dd_score, 4)}**")
                    with mr_cols[1]:
                        a_s = dd_match.get("a_scores_b")
                        st.caption(f"A→B: **{round(a_s, 4) if a_s is not None else 'N/A'}**")
                    with mr_cols[2]:
                        b_s = dd_match.get("b_scores_a")
                        st.caption(f"B→A: **{round(b_s, 4) if b_s is not None else 'N/A'}**")
                    with mr_cols[3]:
                        st.caption(f"Rank: **{dd_match.get('rank', '?')}**")

                    # Why You Two
                    dd_wyt = why_you_two_lookup.get(dd_pair_key)
                    if dd_wyt and dd_wyt.get("success") and dd_wyt.get("why_you_two"):
                        wyt_c = dd_wyt["why_you_two"].get("content", "")
                        if wyt_c:
                            st.markdown(
                                f'<div style="background:linear-gradient(135deg, #6366f1 0%, #ec4899 100%); border-radius:12px; padding:14px 20px; margin:8px 0;">'
                                f'<p style="color:rgba(255,255,255,0.7); font-size:11px; text-transform:uppercase; letter-spacing:1px; margin:0 0 4px 0;">Why You Two</p>'
                                f'<p style="color:#ffffff; font-size:15px; font-weight:500; line-height:1.5; margin:0;">{wyt_c}</p>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )

                    # Profiles + photos
                    mr_ids = [dd_ua, dd_ub]
                    mr_profiles, mr_photos, mr_ai, mr_mm = fetch_page_data(mr_ids)
                    mr_col_a, mr_col_b = st.columns(2)
                    with mr_col_a:
                        st.markdown("**User A**")
                        render_user_card(mr_profiles.get(dd_ua, {}), mr_photos.get(dd_ua, []), 60,
                                         mr_ai.get(dd_ua), mr_mm.get(dd_ua))
                    with mr_col_b:
                        st.markdown("**User B**")
                        render_user_card(mr_profiles.get(dd_ub, {}), mr_photos.get(dd_ub, []), 60,
                                         mr_ai.get(dd_ub), mr_mm.get(dd_ub))

        st.markdown("---")
        render_dd_pagination("bottom")
