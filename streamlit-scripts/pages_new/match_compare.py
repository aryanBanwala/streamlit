"""
Match Compare Dashboard
Upload multiple mutual_matches JSONs (each from a different weightage config),
search by user_id, then browse that user's matches per config — view one config
at a time, or split-screen 2 configs side-by-side to see how weightage choice
changes who shows up in the user's feed.
"""
import json
import base64
from datetime import timedelta
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


# =========== DB + GCS HELPERS ===========

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


def _gcs_sign_url(path):
    bucket = get_gcs_bucket()
    blob = bucket.blob(path)
    return blob.generate_signed_url(
        version="v4",
        expiration=timedelta(seconds=SIGNED_URL_EXPIRY),
        method="GET",
    )


def _gcs_sign_urls_batch(paths):
    if not paths:
        return {}
    signed_map = {}
    for path in paths:
        try:
            signed_map[path] = _gcs_sign_url(path)
        except Exception:
            pass
    return signed_map


# =========== PROFILE FETCHERS ===========

@st.cache_data(ttl=300, show_spinner=False)
def fetch_ai_processing_batch(user_ids_tuple):
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

    all_paths = [p["url"] for p in all_photos if p.get("url")]
    signed_map = _gcs_sign_urls_batch(all_paths)
    for p in all_photos:
        p["signed_url"] = signed_map.get(p.get("url", ""), "")

    user_photos = {}
    for p in all_photos:
        user_photos.setdefault(p["user_id"], []).append(p)
    return {uid: user_photos.get(uid, []) for uid in user_ids}


def fetch_users_data(user_ids):
    """Fetch profiles, photos, AI processing state, and matchmaking state in parallel."""
    ids_tuple = tuple(sorted(set(user_ids)))
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


# =========== JSON PARSING ===========

def parse_matches_json(data):
    """
    Parse one mutual_matches JSON. Keep the per-viewer feed structure verbatim
    so the page can scope to either:
      - CURRENT mode: a user's own feed (viewer_id is the searched user)
      - MUTUAL mode:  every row where the searched user appears as a matched candidate
    """
    return data.get("matches_by_user", {})


# =========== HELPERS ===========

def origin_badge(phase):
    if not phase:
        return ""
    colors = {
        "GREEDY_STRICT": "#4caf50",
        "RELAXED_L1": "#8bc34a",
        "RELAXED_L2": "#ff9800",
        "RELAXED_L3": "#f44336",
        "INBOUND": "#2196f3",
        "EXPLORATION": "#9c27b0",
        "EXPLORATION_UNIDIRECTIONAL": "#673ab7",
        "dummy_seed": "#607d8b",
    }
    color = colors.get(phase, "#9e9e9e")
    return f'<span style="background:{color}; color:white; padding:2px 8px; border-radius:4px; font-size:11px; font-weight:600;">{phase}</span>'


def _fmt(v, d=4):
    if v is None:
        return "—"
    try:
        return f"{round(float(v), d)}"
    except Exception:
        return str(v)


def render_user_card(profile, photos, photo_scale, ai_state=None, mm_state=None):
    """Render a user's info + photos. Same shape as match_review.py's render."""
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


# =========== COMPARATOR LOGIC ===========

SEARCH_MODE_CURRENT = "current"
SEARCH_MODE_MUTUAL = "mutual"


def matches_for_user_in_config(matches_by_user, user_id, mode):
    """Return list of normalized match dicts for the searched user in this config.

    Each returned item is a "card" with two sides:
      - viewer_id      → the user_matches.current_user_id of the row
      - candidate_id   → the user_matches.matched_user_id of the row
      - viewer_to_candidate / candidate_to_viewer → directional scores from the row

    In CURRENT mode: viewer_id == user_id, candidate_id is each match in user_id's feed.
    In MUTUAL mode:  candidate_id == user_id, viewer_id is each user who has user_id in
                     their feed as a matched candidate.

    Sorted by mutual_score DESC. Pure scope — no cross-direction merge — so counts
    line up with the actual user_matches rows the pipeline produced.
    """
    out = []

    if mode == SEARCH_MODE_CURRENT:
        for m in matches_by_user.get(user_id, []) or []:
            out.append({
                "viewer_id": user_id,
                "candidate_id": m["matched_user_id"],
                "mutual_score": m.get("mutual_score"),
                "viewer_to_candidate": m.get("viewer_scores_candidate"),
                "candidate_to_viewer": m.get("candidate_scores_viewer"),
                "rank": m.get("rank"),
                "origin_phase": m.get("origin_phase"),
                "origin_method": m.get("origin_method"),
                "origin_metadata": m.get("origin_metadata"),
                "is_mutual": m.get("is_mutual"),
            })
    elif mode == SEARCH_MODE_MUTUAL:
        for viewer, ms in matches_by_user.items():
            if viewer == user_id:
                continue
            for m in ms or []:
                if m.get("matched_user_id") != user_id:
                    continue
                out.append({
                    "viewer_id": viewer,
                    "candidate_id": user_id,
                    "mutual_score": m.get("mutual_score"),
                    "viewer_to_candidate": m.get("viewer_scores_candidate"),
                    "candidate_to_viewer": m.get("candidate_scores_viewer"),
                    "rank": m.get("rank"),
                    "origin_phase": m.get("origin_phase"),
                    "origin_method": m.get("origin_method"),
                    "origin_metadata": m.get("origin_metadata"),
                    "is_mutual": m.get("is_mutual"),
                })

    out.sort(key=lambda x: (x.get("mutual_score") or 0), reverse=True)
    return out


def _other_side_id(match, mode, searched_user):
    """Return the id of the OTHER user in this match (not the searched one).
    Used to build cross-config lookups for the badge."""
    if mode == SEARCH_MODE_CURRENT:
        return match["candidate_id"]
    return match["viewer_id"]


def render_match_card(idx, match, page_user_data, photo_scale,
                      other_config_label=None, other_config_match_lookup=None,
                      other_lookup_key=None):
    """Render one match as a side-by-side pair card (viewer + candidate).

    `match` carries `viewer_id` + `candidate_id` and the scoring fields.
    `page_user_data` is the (profiles, photos, ai_states, mm_states) tuple for this page.
    `other_config_match_lookup` lets the header show this match's counterpart in the
    other selected config (keyed by `other_lookup_key`, which is whichever side is
    "the other user" for the current search mode).
    """
    profiles, photos, ai_states, mm_states = page_user_data
    viewer_id = match["viewer_id"]
    candidate_id = match["candidate_id"]
    score = match.get("mutual_score") or 0
    phase = match.get("origin_phase", "?")

    viewer_profile = profiles.get(viewer_id) or {}
    candidate_profile = profiles.get(candidate_id) or {}
    name_v = viewer_profile.get("full_name") or viewer_id[:8]
    name_c = candidate_profile.get("full_name") or candidate_id[:8]

    overlap_badge = ""
    if other_config_match_lookup is not None and other_lookup_key is not None:
        other_match = other_config_match_lookup.get(other_lookup_key)
        cfg_label_html = f' in <i>{other_config_label}</i>' if other_config_label else ''
        if other_match is not None:
            other_rank = other_match.get("rank", "?")
            other_score = other_match.get("mutual_score")
            other_score_txt = _fmt(other_score)
            delta = (score - (other_score or 0)) if other_score is not None else None
            delta_txt = ""
            if delta is not None:
                arrow = "↑" if delta > 0 else ("↓" if delta < 0 else "=")
                delta_color = "#4caf50" if delta > 0 else ("#f44336" if delta < 0 else "#9e9e9e")
                delta_txt = f' <span style="color:{delta_color};">{arrow}{abs(round(delta, 4))}</span>'
            overlap_badge = (
                f'<span style="background:#1e1e2e; border:1px solid #4caf50; color:#e0e0e8; '
                f'padding:2px 8px; border-radius:6px; font-size:11px; font-weight:500; margin-left:8px;">'
                f'↔ rank #{other_rank}{cfg_label_html} · mutual={other_score_txt}{delta_txt}'
                f'</span>'
            )
        else:
            overlap_badge = (
                f'<span style="background:#3a1f1f; border:1px solid #f44336; color:#ffb4b4; '
                f'padding:2px 8px; border-radius:6px; font-size:11px; font-weight:500; margin-left:8px;">'
                f'✗ not{cfg_label_html}'
                f'</span>'
            )

    st.markdown(
        f"##### #{idx + 1}: {name_v} → {name_c} &nbsp; "
        f'<span style="font-size:13px;">mutual=<b>{round(score, 4)}</b></span> &nbsp; '
        f'{origin_badge(phase)}{overlap_badge}',
        unsafe_allow_html=True,
    )

    meta_cols = st.columns(4)
    with meta_cols[0]:
        st.caption(f"Mutual: **{round(score, 4)}**")
    with meta_cols[1]:
        v = match.get("viewer_to_candidate")
        st.caption(f"Viewer→Candidate: **{round(v, 4) if v is not None else 'N/A'}**")
    with meta_cols[2]:
        o = match.get("candidate_to_viewer")
        st.caption(f"Candidate→Viewer: **{round(o, 4) if o is not None else 'N/A'}**")
    with meta_cols[3]:
        st.caption(f"Rank: **{match.get('rank', '?')}**")

    if match.get("origin_metadata"):
        with st.expander("Origin metadata", expanded=False):
            st.json(match["origin_metadata"])

    pair_cols = st.columns(2)
    with pair_cols[0]:
        st.markdown("**Viewer (current_user_id)**")
        render_user_card({**viewer_profile, "user_id": viewer_id},
                         photos.get(viewer_id, []), photo_scale,
                         ai_states.get(viewer_id), mm_states.get(viewer_id))
    with pair_cols[1]:
        st.markdown("**Candidate (matched_user_id)**")
        render_user_card({**candidate_profile, "user_id": candidate_id},
                         photos.get(candidate_id, []), photo_scale,
                         ai_states.get(candidate_id), mm_states.get(candidate_id))


def paginate_and_render(column_label, matches, configs_state_key,
                        photo_scale, per_page, mode,
                        other_config_label=None, other_config_match_lookup=None):
    """Render a paginated match list within the current column."""
    total = len(matches)
    if total == 0:
        st.info(f"No matches for this user in **{column_label}**.")
        return

    total_pages = (total + per_page - 1) // per_page
    page_state_key = f"page_{configs_state_key}"
    if page_state_key not in st.session_state:
        st.session_state[page_state_key] = 1
    page = max(1, min(st.session_state[page_state_key], total_pages))
    st.session_state[page_state_key] = page

    nav_cols = st.columns([1, 3, 1])
    with nav_cols[0]:
        if st.button("← Prev", key=f"prev_{configs_state_key}", disabled=page <= 1, use_container_width=True):
            st.session_state[page_state_key] = page - 1
            st.rerun()
    with nav_cols[1]:
        st.markdown(
            f"<p style='text-align:center; margin:8px 0; color:grey;'>"
            f"<b>{column_label}</b> &nbsp;·&nbsp; Page {page}/{total_pages} &nbsp;·&nbsp; {total} matches</p>",
            unsafe_allow_html=True,
        )
    with nav_cols[2]:
        if st.button("Next →", key=f"next_{configs_state_key}", disabled=page >= total_pages, use_container_width=True):
            st.session_state[page_state_key] = page + 1
            st.rerun()

    start = (page - 1) * per_page
    page_matches = matches[start:start + per_page]

    # Fetch viewer + candidate profiles for the visible page (cache hits across pages)
    needed_ids: list[str] = []
    for m in page_matches:
        needed_ids.append(m["viewer_id"])
        needed_ids.append(m["candidate_id"])
    page_user_data = fetch_users_data(needed_ids)

    for i, m in enumerate(page_matches):
        st.markdown("---")
        # The "other" side of this card depends on search mode — in CURRENT mode the
        # candidate is "the other", in MUTUAL mode the viewer is "the other".
        other_lookup_key = m["candidate_id"] if mode == SEARCH_MODE_CURRENT else m["viewer_id"]
        render_match_card(
            start + i, m, page_user_data, photo_scale,
            other_config_label=other_config_label,
            other_config_match_lookup=other_config_match_lookup,
            other_lookup_key=other_lookup_key,
        )


# ============== UI ==============

st.markdown("#### Match Compare")
st.caption("Search a user, browse their matches per weightage config — single view or split-screen for two configs.")

# --- Sidebar ---
st.sidebar.markdown("### Upload weightage outputs")
uploaded_files = st.sidebar.file_uploader(
    "Upload N mutual_matches JSONs (one per weightage config)",
    type=["json"],
    accept_multiple_files=True,
)

if not uploaded_files:
    st.info("Upload **2 or more** `mutual_matches_*.json` files in the sidebar to begin.")
    st.stop()

# Parse each file
configs: "OrderedDict[str, dict]" = OrderedDict()
for f in uploaded_files:
    try:
        raw = json.loads(f.read())
    except Exception as e:
        st.sidebar.error(f"Failed to parse {f.name}: {e}")
        continue
    cfg_name = f.name.replace(".json", "")
    configs[cfg_name] = parse_matches_json(raw)

if not configs:
    st.error("No valid configs parsed.")
    st.stop()

st.sidebar.markdown("### Loaded configs")
for cfg_name, lookup in configs.items():
    st.sidebar.markdown(f"- **{cfg_name}** &nbsp;·&nbsp; {len(lookup)} pairs")

photo_scale = st.sidebar.slider("Photo Size (%)", min_value=20, max_value=100, value=50, step=10)
per_page = st.sidebar.number_input("Matches per page", min_value=1, max_value=20, value=3)

if st.sidebar.button("Clear Cache"):
    st.cache_data.clear()
    st.rerun()

# --- Main: search mode + user_id ---
st.markdown("---")
search_cols = st.columns([2, 3])
with search_cols[0]:
    search_mode = st.radio(
        "Search mode",
        options=[SEARCH_MODE_CURRENT, SEARCH_MODE_MUTUAL],
        format_func=lambda v: {
            SEARCH_MODE_CURRENT: "Current — user's own feed (current_user_id)",
            SEARCH_MODE_MUTUAL: "Mutual — where user appears (matched_user_id)",
        }[v],
        key="mc_search_mode",
        horizontal=False,
    )
with search_cols[1]:
    search_user_id = st.text_input(
        "User ID",
        placeholder="Paste a user_id...",
        key="mc_search",
    ).strip()

if not search_user_id:
    st.info("Enter a user_id and pick a mode to find matches.")
    st.stop()

# --- Config picker (1 or 2) ---
config_names = list(configs.keys())
default_pick = config_names[:1]
selected_configs = st.multiselect(
    "Configs to view (pick 1 for full view, 2 for split-screen)",
    options=config_names,
    default=default_pick,
    max_selections=2,
    key="mc_config_pick",
)

if not selected_configs:
    st.warning("Pick at least one config.")
    st.stop()

# Build per-config matches list for the searched user
per_config_matches: dict[str, list[dict]] = {}
for cfg in selected_configs:
    per_config_matches[cfg] = matches_for_user_in_config(configs[cfg], search_user_id, search_mode)

total_across = sum(len(v) for v in per_config_matches.values())
if total_across == 0:
    st.warning(f"No matches found for user `{search_user_id}` in any selected config (mode: **{search_mode}**).")
    st.stop()

# Summary line
sum_parts = []
for cfg in selected_configs:
    sum_parts.append(f"**{cfg}**: {len(per_config_matches[cfg])} matches")
st.success(" &nbsp;·&nbsp; ".join(sum_parts))

st.markdown("---")

if len(selected_configs) == 1:
    cfg = selected_configs[0]
    paginate_and_render(
        column_label=cfg,
        matches=per_config_matches[cfg],
        configs_state_key=f"single_{cfg}_{search_mode}",
        photo_scale=photo_scale,
        per_page=per_page,
        mode=search_mode,
    )
else:
    cfg_a, cfg_b = selected_configs[0], selected_configs[1]
    matches_a = per_config_matches[cfg_a]
    matches_b = per_config_matches[cfg_b]
    # Build "other-side id → match dict" lookups for cross-referencing in the badges.
    # In CURRENT mode the "other" is the candidate; in MUTUAL mode it is the viewer.
    lookup_a_by_other = {_other_side_id(m, search_mode, search_user_id): m for m in matches_a}
    lookup_b_by_other = {_other_side_id(m, search_mode, search_user_id): m for m in matches_b}
    set_a = set(lookup_a_by_other.keys())
    set_b = set(lookup_b_by_other.keys())
    overlap = set_a & set_b

    other_label = "candidate" if search_mode == SEARCH_MODE_CURRENT else "viewer"
    st.markdown(
        f"<p style='color:grey;'>Overlap: <b>{len(overlap)}</b> {other_label}(s) appear in both configs &nbsp;·&nbsp; "
        f"{len(set_a - set_b)} only in <b>{cfg_a}</b> &nbsp;·&nbsp; "
        f"{len(set_b - set_a)} only in <b>{cfg_b}</b></p>",
        unsafe_allow_html=True,
    )

    col_a, col_b = st.columns(2, gap="medium")
    with col_a:
        paginate_and_render(
            column_label=cfg_a,
            matches=matches_a,
            configs_state_key=f"left_{cfg_a}_{search_mode}",
            photo_scale=photo_scale,
            per_page=per_page,
            mode=search_mode,
            other_config_label=cfg_b,
            other_config_match_lookup=lookup_b_by_other,
        )
    with col_b:
        paginate_and_render(
            column_label=cfg_b,
            matches=matches_b,
            configs_state_key=f"right_{cfg_b}_{search_mode}",
            photo_scale=photo_scale,
            per_page=per_page,
            mode=search_mode,
            other_config_label=cfg_a,
            other_config_match_lookup=lookup_a_by_other,
        )
