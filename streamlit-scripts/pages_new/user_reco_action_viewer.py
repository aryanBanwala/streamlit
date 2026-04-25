"""
User Reco Action Viewer
Input a user_id → view their basic profile + all recos grouped by run (oldest first),
with expandable cards showing the display_data (what the viewer saw) and their action.
"""
import json
import base64
from datetime import timedelta
import streamlit as st
import os
import sys
from collections import OrderedDict
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
    signed = {}
    for p in paths:
        try:
            signed[p] = _gcs_sign_url(p)
        except Exception:
            pass
    return signed


# ============ Fetchers ============

@st.cache_data(ttl=300, show_spinner=False)
def fetch_target_user(user_id: str):
    rows = _db_query(
        """
        SELECT
          upd.user_id, upd.full_name, upd.age, upd.gender, upd.height,
          upd.city, upd.work, upd.education, upd.work_tag, upd.education_tag,
          upd.religion, upd.orientation,
          mus.prof_tier, mus.prof_tier_reason,
          aps.attractiveness_score, aps.attractiveness_reasoning
        FROM user_profile_data upd
        LEFT JOIN matchmaking_user_state mus ON mus.user_id = upd.user_id
        LEFT JOIN ai_processing_state   aps ON aps.user_id = upd.user_id
        WHERE upd.user_id = %s::uuid
        """,
        (user_id,),
    )
    return dict(rows[0]) if rows else None


@st.cache_data(ttl=300, show_spinner=False)
def fetch_photos(user_ids_tuple: tuple):
    user_ids = list(user_ids_tuple)
    if not user_ids:
        return {}
    rows = _db_query(
        "SELECT user_id, url, category, position, is_display_photo "
        "FROM user_photos WHERE user_id = ANY(%s::uuid[]) ORDER BY position ASC",
        (user_ids,),
    )
    photos = [dict(r) for r in rows]
    paths = [p["url"] for p in photos if p.get("url")]
    signed = _gcs_sign_urls_batch(paths)
    for p in photos:
        p["signed_url"] = signed.get(p.get("url", ""), "")

    out = {}
    for p in photos:
        out.setdefault(str(p["user_id"]), []).append(p)
    return out


@st.cache_data(ttl=180, show_spinner=False)
def fetch_recos(user_id: str):
    rows = _db_query(
        """
        SELECT
          um.id, um.current_user_id, um.matched_user_id,
          um.mutual_score, um.viewer_scores_candidate, um.candidate_scores_viewer,
          um.rank, um.run_id, um.origin_phase, um.origin_method, um.origin_metadata,
          um.is_viewed, um.is_mutual, um.is_active, um.user_action,
          um.liked_at, um.created_at, um.updated_at, um.know_more_count,
          cand.full_name AS cand_name, cand.age AS cand_age, cand.gender AS cand_gender,
          mdm.user_id_1, mdm.user_id_2,
          mdm.display_data_of_user_1, mdm.display_data_of_user_2,
          mdm.section_tags
        FROM user_matches um
        LEFT JOIN user_profile_data cand
               ON cand.user_id::text = um.matched_user_id
        LEFT JOIN matches_display_metadata mdm
               ON mdm.id = um.display_data
        WHERE um.current_user_id = %s
        ORDER BY um.created_at ASC
        """,
        (user_id,),
    )
    return [dict(r) for r in rows]


# ============ Helpers ============

def _action_badge(action):
    if not action:
        return '<span style="background:#e0e0e0; color:#555; padding:2px 8px; border-radius:4px; font-size:11px;">no-action</span>'
    colors = {"shortlisted": "#4caf50", "rejected": "#f44336", "passed": "#9e9e9e"}
    c = colors.get(action, "#607d8b")
    return f'<span style="background:{c}; color:white; padding:2px 8px; border-radius:4px; font-size:11px; font-weight:600;">{action}</span>'


def _origin_badge(phase):
    if not phase:
        return ""
    colors = {
        "GREEDY_STRICT": "#4caf50",
        "RELAXED_L1": "#8bc34a",
        "RELAXED_L2": "#ff9800",
        "RELAXED_L3": "#f44336",
        "EXPLORATION": "#9c27b0",
        "EXPLORATION_UNIDIRECTIONAL": "#673ab7",
        "INBOUND_STRICT": "#00bcd4",
        "INBOUND_RELAXED": "#03a9f4",
    }
    c = colors.get(phase, "#607d8b")
    return f'<span style="background:{c}; color:white; padding:2px 8px; border-radius:4px; font-size:11px; font-weight:600;">{phase}</span>'


def _tier_badge(tier):
    if not tier:
        return "—"
    colors = {"S": "#4caf50", "A": "#8bc34a", "B": "#ff9800", "C": "#f44336", "D": "#9e9e9e"}
    c = colors.get(str(tier).upper()[:1], "#607d8b")
    return f'<span style="background:{c}; color:white; padding:1px 6px; border-radius:4px; font-size:12px; font-weight:600;">{tier}</span>'


def _render_photo_grid(photos, cols=3):
    valid = [p for p in (photos or []) if p.get("signed_url")]
    if not valid:
        st.caption("No photos")
        return
    for i in range(0, len(valid), cols):
        row = valid[i:i + cols]
        cols_ui = st.columns(cols)
        for j, p in enumerate(row):
            with cols_ui[j]:
                star = "⭐ " if p.get("is_display_photo") else ""
                cap = f"{star}pos:{p.get('position', '?')}"
                st.markdown(
                    f'<img src="{p["signed_url"]}" style="width:100%; border-radius:8px;" />'
                    f'<p style="font-size:10px; color:grey; text-align:center; margin-top:2px;">{cap}</p>',
                    unsafe_allow_html=True,
                )


def _render_display_data(elements, tags_for_viewer=None):
    if not elements:
        st.caption("No display_data")
        return
    if isinstance(elements, str):
        try:
            elements = json.loads(elements)
        except Exception:
            st.caption(f"Raw: {elements[:200]}")
            return

    elements_sorted = sorted(elements, key=lambda e: e.get("order", 0))
    tags_for_viewer = tags_for_viewer or {}

    for el in elements_sorted:
        etype = el.get("type")
        title = el.get("title", "")
        content = el.get("content")
        order = el.get("order")
        tag = ""
        t = tags_for_viewer.get(str(order))
        if t:
            tag = f' <span style="background:#eee; color:#555; padding:1px 6px; border-radius:3px; font-size:10px;">{t}</span>'

        if etype == "paragraph":
            st.markdown(f"**{title}**{tag}", unsafe_allow_html=True)
            st.write(content or "")

        elif etype == "display_picture":
            st.markdown(f"**{title}**{tag}", unsafe_allow_html=True)
            if content:
                try:
                    url = _gcs_sign_url(content)
                    st.markdown(
                        f'<img src="{url}" style="max-width:320px; border-radius:8px;" />',
                        unsafe_allow_html=True,
                    )
                except Exception:
                    st.caption(f"(sign failed) {content}")

        elif etype == "profile_card":
            c = content or {}
            st.markdown(f"**{title}**{tag}", unsafe_allow_html=True)
            tf = c.get("titleField", {}) or {}
            sf = c.get("subtitleField", {}) or {}
            st.markdown(f"**{tf.get('value', '')}** · {sf.get('value', '')}")
            fields = c.get("fields") or []
            if fields:
                pairs = [
                    f"{f.get('emoji', '')} **{f.get('label')}**: {f.get('value')}"
                    for f in fields
                ]
                st.markdown(" &nbsp;·&nbsp; ".join(pairs), unsafe_allow_html=True)

        elif etype == "timeline":
            st.markdown(f"**{title}**{tag}", unsafe_allow_html=True)
            if isinstance(content, list):
                for pt in content:
                    st.markdown(f"- {pt}")

        else:
            st.caption(f"unknown element: {etype}")

        st.markdown("<hr style='margin:8px 0;'/>", unsafe_allow_html=True)


# ============ UI ============

st.title("👤 User Reco Action Viewer")
st.caption("Enter a user_id to see their profile + every reco they've received (oldest run first), with the exact card shown to them and their action.")

user_id_input = st.text_input("User ID", placeholder="uuid")

if not user_id_input:
    st.info("Enter a user_id to begin.")
    st.stop()

user_id = user_id_input.strip()

with st.spinner("Fetching target user…"):
    target = fetch_target_user(user_id)

if not target:
    st.error("User not found in user_profile_data")
    st.stop()

photo_map = fetch_photos((user_id,))
target_photos = photo_map.get(user_id, [])

# ---- TARGET USER CARD ----
col_info, col_photos = st.columns([1, 1])

with col_info:
    name = target.get("full_name") or "?"
    age = target.get("age") or "?"
    gender = target.get("gender") or "?"
    height = target.get("height") or "?"
    gender_color = "#1976d2" if gender == "male" else "#e91e63" if gender == "female" else "#9e9e9e"

    st.markdown(
        f"### {name}, {age} "
        f'<span style="color:{gender_color}; font-weight:600;">({gender})</span>',
        unsafe_allow_html=True,
    )
    st.caption(f"{target.get('city') or '?'}  ·  {height}  ·  {target.get('religion') or '?'}")
    st.markdown(f"**Work:** {target.get('work_tag') or target.get('work') or '—'}")
    st.markdown(f"**Education:** {target.get('education_tag') or target.get('education') or '—'}")

    tier = target.get("prof_tier")
    attr = target.get("attractiveness_score")
    st.markdown(
        f'**Prof Tier:** {_tier_badge(tier)} &nbsp;&nbsp; '
        f'**Attractiveness:** **{round(attr, 2) if attr is not None else "—"}**',
        unsafe_allow_html=True,
    )

    st.code(str(target["user_id"]), language=None)

    with st.expander("Reasoning", expanded=False):
        if target.get("attractiveness_reasoning"):
            st.markdown("**Attractiveness:**")
            st.write(target["attractiveness_reasoning"])
        if target.get("prof_tier_reason"):
            st.markdown("**Prof Tier:**")
            st.write(target["prof_tier_reason"])
        if not target.get("attractiveness_reasoning") and not target.get("prof_tier_reason"):
            st.caption("no reasoning available")

with col_photos:
    _render_photo_grid(target_photos, cols=3)

st.markdown("---")

# ---- Recos ----

with st.spinner("Fetching recos…"):
    recos = fetch_recos(user_id)

if not recos:
    st.info("No recos in user_matches for this user.")
    st.stop()

# Batch-sign candidate photos
candidate_ids = list({r["matched_user_id"] for r in recos if r.get("matched_user_id")})
cand_photo_map = fetch_photos(tuple(candidate_ids)) if candidate_ids else {}

# Filters
st.subheader(f"Recos ({len(recos)})")
fc = st.columns(4)
with fc[0]:
    show_short = st.checkbox("shortlisted", value=True)
with fc[1]:
    show_reject = st.checkbox("rejected", value=True)
with fc[2]:
    show_pass = st.checkbox("passed", value=True)
with fc[3]:
    show_none = st.checkbox("no-action", value=True)


def _keep(r):
    a = r.get("user_action")
    if a == "shortlisted":
        return show_short
    if a == "rejected":
        return show_reject
    if a == "passed":
        return show_pass
    return show_none


filtered = [r for r in recos if _keep(r)]
st.caption(f"Showing {len(filtered)} / {len(recos)}")

# Group by run_id, preserving created_at ASC order
groups = OrderedDict()
for r in filtered:
    rid = str(r.get("run_id") or "no-run")
    groups.setdefault(rid, []).append(r)

for rid, items in groups.items():
    first_created = items[0].get("created_at")
    created_s = first_created.strftime("%Y-%m-%d %H:%M") if hasattr(first_created, "strftime") else str(first_created)
    rid_short = rid if rid == "no-run" else f"{rid[:8]}…"
    st.markdown(f"### Run · `{rid_short}` · {created_s} · {len(items)} recos")

    for r in items:
        cand_id = r["matched_user_id"]
        cand_name = r.get("cand_name") or "?"
        cand_age = r.get("cand_age") or "?"
        cand_gender = r.get("cand_gender") or "?"
        action = r.get("user_action")
        phase = r.get("origin_phase")
        rank = r.get("rank")
        mutual = r.get("mutual_score")

        label_parts = []
        if rank is not None:
            label_parts.append(f"#{rank}")
        label_parts.append(f"{cand_name}, {cand_age} ({cand_gender})")
        label_parts.append(f"m={round(mutual, 3) if mutual is not None else '—'}")
        if phase:
            label_parts.append(phase)
        label_parts.append(action or "no-action")
        label = "  ·  ".join(label_parts)

        with st.expander(label, expanded=False):
            top = st.columns([3, 2])
            with top[0]:
                st.markdown(
                    f'{_action_badge(action)} &nbsp; {_origin_badge(phase)}',
                    unsafe_allow_html=True,
                )
                st.caption(f"candidate_id: `{cand_id}`")
                st.caption(f"match_id: `{r['id']}`")

                vs = r.get("viewer_scores_candidate")
                cs = r.get("candidate_scores_viewer")
                st.markdown(
                    f"**mutual**: {round(mutual, 4) if mutual is not None else '—'}  ·  "
                    f"**viewer→cand**: {round(vs, 4) if vs is not None else '—'}  ·  "
                    f"**cand→viewer**: {round(cs, 4) if cs is not None else '—'}"
                )

                flags = []
                if r.get("is_viewed"): flags.append("viewed")
                if r.get("is_mutual"): flags.append("mutual")
                if r.get("is_active"): flags.append("active")
                st.caption("flags: " + (", ".join(flags) if flags else "—"))

                if r.get("liked_at"):
                    st.caption(f"liked_at: {r['liked_at']}")
                st.caption(f"know_more_count: {r.get('know_more_count', 0)}")
                if r.get("origin_metadata"):
                    with st.expander("origin_metadata", expanded=False):
                        st.json(r["origin_metadata"])

            with top[1]:
                _render_photo_grid(cand_photo_map.get(cand_id, []), cols=3)

            st.markdown("---")

            # display_data_of_user_X describes user X themselves →
            # viewer (input user_id) sees the OTHER user's card
            dd = None
            tags_for_card = None
            u1 = str(r.get("user_id_1") or "")
            u2 = str(r.get("user_id_2") or "")
            section_tags = r.get("section_tags") or {}
            if u1 == user_id:
                dd = r.get("display_data_of_user_2")
                tags_for_card = section_tags.get(u2)
            elif u2 == user_id:
                dd = r.get("display_data_of_user_1")
                tags_for_card = section_tags.get(u1)

            if dd:
                st.markdown("**Candidate's display card (shown to viewer)**")
                _render_display_data(dd, tags_for_card)
            else:
                st.caption("No display_data linked to this reco")
