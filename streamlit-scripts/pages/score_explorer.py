"""
Score Explorer — Explore matchmaking scoring breakdowns per user.

Load detailed_scores JSON → search user → see top-K unidirectional matches
with full component breakdown + photos + physical pref paragraphs.
Toggle to overlay actual distributed matches.
"""

import streamlit as st
import json
import base64
import os
import sys
from glob import glob
from pathlib import Path
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor

import psycopg2
import psycopg2.extras
from google.cloud import storage
from google.oauth2 import service_account
from dotenv import load_dotenv

# --- Setup paths & env ---
current_dir = os.path.dirname(__file__)
scripts_dir = os.path.abspath(os.path.join(current_dir, ".."))
parent_dir = os.path.abspath(os.path.join(scripts_dir, ".."))
sys.path.insert(0, parent_dir)

load_dotenv(os.path.join(parent_dir, ".env"))

DB_HOST = os.getenv("DB_HOST", "")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "")
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "")
GCS_PROJECT_ID = os.getenv("GCS_PROJECT_ID", "")
GCS_CREDENTIALS_BASE64 = os.getenv("GCS_CREDENTIALS_BASE64", "")

SIGNED_URL_EXPIRY = 3600

RESULTS_DIR = str(
    Path(__file__).resolve().parents[3]
    / "wavelength-backend"
    / "api"
    / "services"
    / "matchmaking"
    / "results"
)


# =============================================================================
# DB + GCS helpers (same pattern as match_review.py)
# =============================================================================

def _new_db_conn():
    if not DB_HOST or not DB_NAME:
        st.error("Missing DB_HOST or DB_NAME in .env")
        st.stop()
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASSWORD,
    )


_conn_holder = {"conn": None}


def get_db_conn():
    conn = _conn_holder["conn"]
    if conn is None or conn.closed:
        _conn_holder["conn"] = _new_db_conn()
    return _conn_holder["conn"]


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


@st.cache_resource
def get_gcs_bucket():
    if GCS_CREDENTIALS_BASE64:
        sa_info = json.loads(base64.b64decode(GCS_CREDENTIALS_BASE64))
        creds = service_account.Credentials.from_service_account_info(sa_info)
        client = storage.Client(project=GCS_PROJECT_ID, credentials=creds)
    else:
        client = storage.Client(project=GCS_PROJECT_ID)
    return client.bucket(GCS_BUCKET_NAME)


def _gcs_sign_urls_batch(paths):
    if not paths:
        return {}
    bucket = get_gcs_bucket()
    signed_map = {}
    for path in paths:
        try:
            blob = bucket.blob(path)
            signed_map[path] = blob.generate_signed_url(
                version="v4", expiration=timedelta(seconds=SIGNED_URL_EXPIRY), method="GET",
            )
        except Exception:
            pass
    return signed_map


# =============================================================================
# Fetchers (batched, cached)
# =============================================================================


@st.cache_data(ttl=300, show_spinner=False)
def fetch_user_metadata_batch(user_ids_tuple: tuple) -> dict:
    user_ids = list(user_ids_tuple)
    if not user_ids:
        return {}
    rows = _db_query(
        "SELECT user_id, full_name, gender, age, height, city, religion "
        "FROM user_profile_data WHERE user_id = ANY(%s::uuid[])",
        (user_ids,),
    )
    return {r["user_id"]: dict(r) for r in rows}


@st.cache_data(ttl=300, show_spinner=False)
def fetch_pref_summaries_batch(user_ids_tuple: tuple) -> dict:
    user_ids = list(user_ids_tuple)
    if not user_ids:
        return {}
    rows = _db_query(
        "SELECT user_id, summary_text FROM user_pref_vectors WHERE user_id = ANY(%s::uuid[])",
        (user_ids,),
    )
    return {r["user_id"]: r.get("summary_text", "") for r in rows}


@st.cache_data(ttl=300, show_spinner=False)
def fetch_user_photos_batch(user_ids_tuple: tuple) -> dict:
    user_ids = list(user_ids_tuple)
    if not user_ids:
        return {}
    rows = _db_query(
        "SELECT user_id, url, position FROM user_photos "
        "WHERE user_id = ANY(%s::uuid[]) ORDER BY position ASC",
        (user_ids,),
    )
    all_photos = [dict(r) for r in rows]
    if not all_photos:
        return {uid: [] for uid in user_ids}

    all_paths = [p["url"] for p in all_photos if p.get("url")]
    signed_map = _gcs_sign_urls_batch(all_paths)

    user_photos: dict[str, list[str]] = {}
    for p in all_photos:
        signed = signed_map.get(p.get("url", ""), "")
        if signed:
            user_photos.setdefault(p["user_id"], []).append(signed)

    return {uid: user_photos.get(uid, []) for uid in user_ids}


# =============================================================================
# Helpers
# =============================================================================


def _color(val, lo=0.3, hi=0.8):
    """Return CSS color: red if low, green if high, grey if None."""
    if val is None:
        return "color: grey"
    if val >= hi:
        return "color: #4caf50; font-weight: 600"
    if val <= lo:
        return "color: #e53935; font-weight: 600"
    return ""


def _fmt(val, decimals=3):
    if val is None:
        return "—"
    return f"{val:.{decimals}f}"


def _score_cell(val):
    """Colored score span."""
    return f"<span style='{_color(val)}'>{_fmt(val)}</span>"


# =============================================================================
# Render functions
# =============================================================================


def render_user_card(user_id: str, meta: dict | None, photos: list | None, phys_pref: str | None = None):
    """Compact user card with photos + key info."""
    if not meta:
        st.caption(f"`{user_id[:12]}…` (no metadata)")
        return

    name = meta.get("full_name") or user_id[:12]
    age = meta.get("age", "?")
    gender = meta.get("gender", "?")
    city = meta.get("city", "?")
    height = meta.get("height")
    religion = meta.get("religion")
    tier = meta.get("prof_tier")

    gender_color = "#e91e63" if gender == "female" else "#2196f3" if gender == "male" else "#9e9e9e"

    st.markdown(
        f"<h4 style='color:{gender_color}; margin:0 0 6px 0; border-bottom:2px solid {gender_color}; "
        f"padding-bottom:4px;'>{name}, {age}</h4>",
        unsafe_allow_html=True,
    )

    info_parts = [f"**Gender:** {gender}", f"**City:** {city}"]
    if height:
        info_parts.append(f"**Height:** {height}")
    if religion:
        info_parts.append(f"**Religion:** {religion}")
    if tier is not None:
        tier_colors = {0: "#ffeb3b", 1: "#4caf50", 2: "#2196f3", 3: "#9c27b0"}
        tc = tier_colors.get(tier, "#9e9e9e")
        info_parts.append(
            f"**Tier:** <span style='background:{tc};color:white;padding:1px 6px;"
            f"border-radius:4px;font-size:12px;'>T{tier}</span>"
        )
    st.markdown(" · ".join(info_parts), unsafe_allow_html=True)

    # photos
    if photos:
        cols = st.columns(min(len(photos), 4))
        for i, url in enumerate(photos[:4]):
            if url:
                with cols[i]:
                    st.image(url, width=130)

    # physical pref paragraph
    if phys_pref:
        st.markdown(
            f"<div style='background:rgba(100,100,100,0.12);border-left:3px solid #9c27b0;"
            f"border-radius:6px;padding:8px 12px;margin:6px 0;font-size:13px;'>"
            f"<b>Physical Pref:</b> {phys_pref}</div>",
            unsafe_allow_html=True,
        )

    st.code(user_id, language=None)


def render_scores_table(candidates: list, distribution_set: set | None):
    """Render the top-K scores table with full breakdown."""

    header = (
        "<tr>"
        "<th>#</th>"
        "<th>Candidate</th>"
        "<th>Attr Compat</th>"
        "<th>Img Sim<br><small>i→them / them→me</small></th>"
        "<th>Img Score<br><small>i→them / them→me / mutual</small></th>"
        "<th>Feature<br><small>i→them / them→me / mutual</small></th>"
        "<th>Combined<br><small>i→them / them→me / mutual</small></th>"
        "<th>Source</th>"
        "</tr>"
    )

    rows = []
    for i, c in enumerate(candidates, 1):
        bd = c.get("breakdown", {})
        is_matched = distribution_set and c["candidate_id"] in distribution_set

        row_style = "background:rgba(76,175,80,0.12);" if is_matched else ""
        badge = " <span style='background:#4caf50;color:white;padding:1px 5px;border-radius:3px;font-size:10px;'>MATCHED</span>" if is_matched else ""

        img_sim = bd.get("image_sim", {})
        img_sc = bd.get("image_score", {})
        feat = bd.get("feature_score", {})
        comb = bd.get("combined", {})

        rows.append(
            f"<tr style='{row_style}'>"
            f"<td>{i}</td>"
            f"<td><code>{c['candidate_id'][:12]}…</code>{badge}</td>"
            f"<td>{_score_cell(bd.get('attractiveness_compat'))}</td>"
            f"<td>{_score_cell(img_sim.get('i_to_them'))} / {_score_cell(img_sim.get('them_to_me'))}</td>"
            f"<td>{_score_cell(img_sc.get('i_to_them'))} / {_score_cell(img_sc.get('them_to_me'))} / {_score_cell(img_sc.get('mutual'))}</td>"
            f"<td>{_score_cell(feat.get('i_to_them'))} / {_score_cell(feat.get('them_to_me'))} / {_score_cell(feat.get('mutual'))}</td>"
            f"<td>{_score_cell(comb.get('i_to_them'))} / {_score_cell(comb.get('them_to_me'))} / {_score_cell(comb.get('mutual'))}</td>"
            f"<td>{c.get('source', '?')}</td>"
            f"</tr>"
        )

    table_html = (
        "<style>"
        "table.score-tbl { width:100%; border-collapse:collapse; font-size:13px; }"
        "table.score-tbl th { background:#1a1a2e; padding:8px 6px; text-align:center; border-bottom:2px solid #444; }"
        "table.score-tbl td { padding:6px; text-align:center; border-bottom:1px solid #333; }"
        "table.score-tbl tr:hover { background:rgba(255,255,255,0.04); }"
        "</style>"
        f"<table class='score-tbl'><thead>{header}</thead><tbody>{''.join(rows)}</tbody></table>"
    )
    st.markdown(table_html, unsafe_allow_html=True)


def render_quick_stats(candidates: list):
    """Quick aggregate stats for the searched user."""
    if not candidates:
        return

    def avg(key_path):
        vals = []
        for c in candidates:
            obj = c
            for k in key_path:
                obj = obj.get(k, {}) if isinstance(obj, dict) else None
                if obj is None:
                    break
            if obj is not None and isinstance(obj, (int, float)):
                vals.append(obj)
        return sum(vals) / len(vals) if vals else None

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        v = avg(["breakdown", "attractiveness_compat"])
        st.metric("Avg Attractiveness Compat", _fmt(v))
    with col2:
        v = avg(["breakdown", "image_score", "i_to_them"])
        st.metric("Avg Image Score (i→them)", _fmt(v))
    with col3:
        v = avg(["breakdown", "feature_score", "i_to_them"])
        st.metric("Avg Feature Score (i→them)", _fmt(v))
    with col4:
        v = avg(["breakdown", "combined", "i_to_them"])
        st.metric("Avg Combined (i→them)", _fmt(v))
    with col5:
        sources = {}
        for c in candidates:
            s = c.get("source", "?")
            sources[s] = sources.get(s, 0) + 1
        st.metric("Coverage", ", ".join(f"{k}:{v}" for k, v in sources.items()))


# =============================================================================
# Main page
# =============================================================================

st.title("Score Explorer")

# ── Step 1: pick JSON files ──────────────────────────────────────────────

available_detailed = sorted(glob(os.path.join(RESULTS_DIR, "detailed_scores_*.json")), reverse=True)
available_mutual = sorted(glob(os.path.join(RESULTS_DIR, "mutual_matches_*.json")), reverse=True)

if not available_detailed:
    st.warning(f"No detailed_scores JSON found in `{RESULTS_DIR}`")
    st.stop()

col_file1, col_file2 = st.columns(2)
with col_file1:
    detailed_file = st.selectbox(
        "Detailed Scores JSON",
        available_detailed,
        format_func=lambda p: Path(p).name,
    )
with col_file2:
    mutual_file = st.selectbox(
        "Mutual Matches JSON (for distribution overlay)",
        ["None"] + available_mutual,
        format_func=lambda p: Path(p).name if p != "None" else "— none —",
    )


# ── Load data ────────────────────────────────────────────────────────────

@st.cache_data
def load_json(path: str):
    with open(path) as f:
        return json.load(f)


detailed = load_json(detailed_file)
uni_data = detailed.get("unidirectional_by_user", {})
stats = detailed.get("stats", {})

mutual_data: dict | None = None
if mutual_file != "None":
    mutual_data = load_json(mutual_file).get("matches_by_user", {})

# ── Stats header ─────────────────────────────────────────────────────────

st.divider()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Eligible Users", stats.get("total_eligible_users", "?"))
c2.metric("Scored Pairs", stats.get("total_scored_pairs", "?"))
c3.metric("Users w/ Scores", stats.get("total_users_with_scores", "?"))
cov = stats.get("coverage", {})
c4.metric("Both / Img / Feat", f"{cov.get('both_scores', 0)} / {cov.get('image_only', 0)} / {cov.get('feature_only', 0)}")

# ── Pipeline Config Reference ────────────────────────────────────────────

with st.expander("Pipeline Config", expanded=False):

    st.markdown("### Combined Score")
    st.markdown("`combined = 0.8 × image_score + 0.2 × feature_score`")
    cfg_html = """
<table style='width:100%;font-size:14px;border-collapse:collapse;'>
<tr><th style='padding:6px 10px;text-align:left;border-bottom:2px solid #444;'>Setting</th>
    <th style='padding:6px 10px;text-align:left;border-bottom:2px solid #444;'>Value</th>
    <th style='padding:6px 10px;text-align:left;border-bottom:2px solid #444;'>Meaning</th></tr>
<tr><td style='padding:5px 10px;'>w_image</td><td><b>0.8</b></td><td>Weight for image score in combined</td></tr>
<tr><td style='padding:5px 10px;'>w_feature</td><td><b>0.2</b></td><td>Weight for feature score in combined</td></tr>
<tr><td style='padding:5px 10px;'>solo_penalty</td><td><b>0.8×</b></td><td>Multiplier when only one score source exists</td></tr>
</table>"""
    st.markdown(cfg_html, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### Image Score")
    st.markdown("`image_score = w × image_sim + (1-w) × attractiveness_compat`")
    st.markdown("`w = max_w_image × confidence`")
    img_html = """
<table style='width:100%;font-size:14px;border-collapse:collapse;'>
<tr><th style='padding:6px 10px;text-align:left;border-bottom:2px solid #444;'>Setting</th>
    <th style='padding:6px 10px;text-align:left;border-bottom:2px solid #444;'>Value</th>
    <th style='padding:6px 10px;text-align:left;border-bottom:2px solid #444;'>Meaning</th></tr>
<tr><td style='padding:5px 10px;'>max_w_image</td><td><b>0.5</b></td><td>Max weight for phy pref (at full confidence)</td></tr>
<tr><td style='padding:5px 10px;'>confidence_threshold</td><td><b>50 swipes</b></td><td>Swipes needed for full confidence</td></tr>
<tr><td style='padding:5px 10px;'>default_attractiveness</td><td><b>5.0</b></td><td>Fallback when attractiveness missing</td></tr>
<tr><td style='padding:5px 10px;'>attractiveness_compat</td><td colspan='2'><code>1 - |attr_a - attr_b| / 10</code></td></tr>
<tr><td style='padding:5px 10px;'>image_sim</td><td colspan='2'><code>max(0, max(dot(pref_vec, photo_i)))</code> — best photo match</td></tr>
</table>"""
    st.markdown(img_html, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### Pref Vector (how image_sim is built)")
    st.markdown("`pref_vec = w_likes×avg_likes + w_dislikes×avg_dislikes + w_passed×avg_passed + w_summary×summary_emb`")
    pref_html = """
<table style='width:100%;font-size:14px;border-collapse:collapse;'>
<tr><th style='padding:6px 10px;text-align:left;border-bottom:2px solid #444;'>Signal</th>
    <th style='padding:6px 10px;text-align:left;border-bottom:2px solid #444;'>Weight</th>
    <th style='padding:6px 10px;text-align:left;border-bottom:2px solid #444;'>Source</th></tr>
<tr><td style='padding:5px 10px;'>Likes</td><td><b>+1.0</b></td><td>Photos user swiped right on</td></tr>
<tr><td style='padding:5px 10px;'>Dislikes</td><td><b>-0.5</b></td><td>Photos user swiped left on</td></tr>
<tr><td style='padding:5px 10px;'>Passed</td><td><b>-0.2</b></td><td>Photos user passed</td></tr>
<tr><td style='padding:5px 10px;'>Summary</td><td><b>+1.0</b></td><td>LLM-extracted physical pref → embedding</td></tr>
</table>"""
    st.markdown(pref_html, unsafe_allow_html=True)
    st.markdown("Result is **unit-normalized**. Confidence = `min(1.0, total_interactions / 50)`")

    st.markdown("---")
    st.markdown("### Feature Score (Persona)")
    st.markdown("`score = Σ(W_i × S_i) / Σ(W_i)` — weighted avg of per-attribute Gaussian similarity")
    feat_html = """
<table style='width:100%;font-size:14px;border-collapse:collapse;'>
<tr><th style='padding:6px 10px;text-align:left;border-bottom:2px solid #444;'>Setting</th>
    <th style='padding:6px 10px;text-align:left;border-bottom:2px solid #444;'>Value</th></tr>
<tr><td style='padding:5px 10px;'>Per-attribute similarity</td><td><code>exp(-(pref - self)² / (2 × tolerance²))</code></td></tr>
<tr><td style='padding:5px 10px;'>Weight (tol &lt; 0.15)</td><td><b>10.0</b> — very strict</td></tr>
<tr><td style='padding:5px 10px;'>Weight (tol &lt; 0.25)</td><td><b>7.0</b> — strict</td></tr>
<tr><td style='padding:5px 10px;'>Weight (tol &lt; 0.35)</td><td><b>5.0</b> — moderate</td></tr>
<tr><td style='padding:5px 10px;'>Weight (tol &lt; 0.50)</td><td><b>3.0</b> — flexible</td></tr>
<tr><td style='padding:5px 10px;'>Weight (tol ≥ 0.50)</td><td><b>1.0</b> — very flexible</td></tr>
<tr><td style='padding:5px 10px;'>Confidence scaling</td><td><code>base_weight × √(pref_conf × self_conf)</code></td></tr>
<tr><td style='padding:5px 10px;'>Dealbreakers</td><td><b>Disabled</b></td></tr>
</table>"""
    st.markdown(feat_html, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### Mutual Score")
    st.markdown("`mutual = 2 × a_to_b × b_to_a / (a_to_b + b_to_a)` — harmonic mean, applied once at the end (Method 2)")

st.divider()

# ── Step 2: User search ─────────────────────────────────────────────────

all_user_ids = sorted(uni_data.keys())

search_col, k_col = st.columns([3, 1])
with search_col:
    search_input = st.text_input("Search User ID", placeholder="Paste or type user ID...", key="user_search")
    # filter matching IDs
    if search_input:
        matches = [uid for uid in all_user_ids if search_input.lower() in uid.lower()]
        if len(matches) == 1:
            selected_user = matches[0]
        elif matches:
            selected_user = st.selectbox("Matching users", matches, key="user_match_select")
        else:
            selected_user = ""
            st.warning("No matching user found.")
    else:
        selected_user = ""
with k_col:
    top_k = st.selectbox("Top-K", [5, 10, 20, 50], index=1)

if not selected_user:
    st.info("Select a user to explore their scoring breakdown.")
    st.stop()

candidates = uni_data.get(selected_user, [])
if not candidates:
    st.warning("No scored candidates for this user.")
    st.stop()

candidates_trimmed = candidates[:top_k]

# ── Fetch metadata + photos for all relevant users ───────────────────────

all_ids = [selected_user] + [c["candidate_id"] for c in candidates_trimmed]
all_ids_tuple = tuple(sorted(set(all_ids)))

with st.spinner("Loading user data..."):
    meta_cache = fetch_user_metadata_batch(all_ids_tuple)
    photo_cache = fetch_user_photos_batch(all_ids_tuple)
    pref_cache = fetch_pref_summaries_batch(all_ids_tuple)

# ── Show distribution toggle ─────────────────────────────────────────────

show_distribution = False
distribution_set: set | None = None
if mutual_data is not None:
    show_distribution = st.toggle("Overlay distributed matches", value=True)
    if show_distribution:
        matched_ids = mutual_data.get(selected_user, [])
        distribution_set = {m["matched_user_id"] for m in matched_ids}

# ── User card ────────────────────────────────────────────────────────────

st.subheader("User Profile")
render_user_card(selected_user, meta_cache.get(selected_user), photo_cache.get(selected_user), pref_cache.get(selected_user))

# ── Quick stats ──────────────────────────────────────────────────────────

st.subheader(f"Quick Stats (over {len(candidates)} total candidates)")
render_quick_stats(candidates)

# ── Scores table ─────────────────────────────────────────────────────────

st.divider()
st.subheader(f"Top-{top_k} Unidirectional Matches")
render_scores_table(candidates_trimmed, distribution_set)

# ── Expandable candidate cards ───────────────────────────────────────────

st.divider()
st.subheader("Candidate Details")

for i, c in enumerate(candidates_trimmed):
    cid = c["candidate_id"]
    is_matched = distribution_set and cid in distribution_set
    label = f"#{i+1} — {cid[:16]}…"
    if is_matched:
        label += "  ✅ MATCHED"

    with st.expander(label):
        col_user, col_cand = st.columns(2)
        with col_user:
            st.markdown("### Viewer")
            render_user_card(selected_user, meta_cache.get(selected_user), photo_cache.get(selected_user), pref_cache.get(selected_user))
        with col_cand:
            st.markdown("### Candidate")
            render_user_card(cid, meta_cache.get(cid), photo_cache.get(cid), pref_cache.get(cid))

        # physical pref comparison
        viewer_pref = pref_cache.get(selected_user)
        cand_pref = pref_cache.get(cid)
        if viewer_pref or cand_pref:
            st.markdown("---")
            st.markdown("**Physical Preference Paragraphs**")
            pc1, pc2 = st.columns(2)
            with pc1:
                viewer_name = (meta_cache.get(selected_user) or {}).get("full_name", selected_user[:12])
                st.markdown(
                    f"<div style='background:rgba(33,150,243,0.08);border-left:3px solid #2196f3;"
                    f"border-radius:6px;padding:10px 14px;font-size:13px;'>"
                    f"<b>{viewer_name}'s type:</b><br>{viewer_pref or '<i>No data</i>'}</div>",
                    unsafe_allow_html=True,
                )
            with pc2:
                cand_name = (meta_cache.get(cid) or {}).get("full_name", cid[:12])
                st.markdown(
                    f"<div style='background:rgba(233,30,99,0.08);border-left:3px solid #e91e63;"
                    f"border-radius:6px;padding:10px 14px;font-size:13px;'>"
                    f"<b>{cand_name}'s type:</b><br>{cand_pref or '<i>No data</i>'}</div>",
                    unsafe_allow_html=True,
                )

        # score breakdown for this pair
        bd = c.get("breakdown", {})
        st.markdown("---")
        st.markdown("**Score Breakdown**")

        bc1, bc2, bc3, bc4, bc5 = st.columns(5)
        with bc1:
            st.metric("Attr Compat", _fmt(bd.get("attractiveness_compat")))
        with bc2:
            img_sim = bd.get("image_sim", {})
            st.metric("Img Sim (i→them)", _fmt(img_sim.get("i_to_them")))
            st.metric("Img Sim (them→me)", _fmt(img_sim.get("them_to_me")))
        with bc3:
            img_sc = bd.get("image_score", {})
            st.metric("Img Score (i→them)", _fmt(img_sc.get("i_to_them")))
            st.metric("Img Score (them→me)", _fmt(img_sc.get("them_to_me")))
            st.metric("Img Score (mutual)", _fmt(img_sc.get("mutual")))
        with bc4:
            feat = bd.get("feature_score", {})
            st.metric("Feature (i→them)", _fmt(feat.get("i_to_them")))
            st.metric("Feature (them→me)", _fmt(feat.get("them_to_me")))
            st.metric("Feature (mutual)", _fmt(feat.get("mutual")))
        with bc5:
            comb = bd.get("combined", {})
            st.metric("Combined (i→them)", _fmt(comb.get("i_to_them")))
            st.metric("Combined (them→me)", _fmt(comb.get("them_to_me")))
            st.metric("Combined (mutual)", _fmt(comb.get("mutual")))

        if is_matched:
            # show distribution metadata
            match_row = next((m for m in mutual_data.get(selected_user, []) if m["matched_user_id"] == cid), None)
            if match_row:
                st.success(
                    f"**Distributed Match** — Rank: {match_row['rank']} · "
                    f"Phase: {match_row['origin_phase']} · "
                    f"Mutual: {_fmt(match_row.get('mutual_score'))} · "
                    f"Viewer→Cand: {_fmt(match_row.get('viewer_scores_candidate'))} · "
                    f"Cand→Viewer: {_fmt(match_row.get('candidate_scores_viewer'))}"
                )
