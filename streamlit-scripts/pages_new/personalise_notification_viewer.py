"""
Personalise Notification Viewer
Input a run_id → for each user with a generated personalised push copy in
matchmaking_personalise_notification, show the title/body + every match's
display_data they saw in that run, in collapsible cards.
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


@st.cache_data(ttl=1800, show_spinner=False)
def _sign_urls_batch_cached(paths_tuple: tuple) -> dict:
    """Batch sign GCS paths. Cached for 30min so repeated renders don't re-sign."""
    if not paths_tuple:
        return {}
    bucket = get_gcs_bucket()
    out: dict = {}
    for p in paths_tuple:
        if not p:
            continue
        try:
            blob = bucket.blob(p)
            out[p] = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(seconds=SIGNED_URL_EXPIRY),
                method="GET",
            )
        except Exception:
            pass
    return out


# ============ Fetchers ============

@st.cache_data(ttl=300, show_spinner=False)
def fetch_personalised_rows(run_id: str):
    """All (user_id, title, body, ...) for this run from matchmaking_personalise_notification."""
    rows = _db_query(
        """
        SELECT
          mpn.user_id, mpn.run_id, mpn.message_type,
          mpn.title, mpn.body, mpn.metadata,
          mpn.generated_at, mpn.created_at,
          upd.full_name, upd.age, upd.gender, upd.city
        FROM matchmaking_personalise_notification mpn
        LEFT JOIN user_profile_data upd
               ON upd.user_id::text = mpn.user_id
        WHERE mpn.run_id = %s::uuid
        ORDER BY mpn.generated_at ASC
        """,
        (run_id,),
    )
    return [dict(r) for r in rows]


@st.cache_data(ttl=300, show_spinner=False)
def fetch_matches_in_run(run_id: str, user_ids_tuple: tuple):
    """All user_matches in this run for the given viewer user_ids, joined with display_data."""
    user_ids = list(user_ids_tuple)
    if not user_ids:
        return []
    rows = _db_query(
        """
        SELECT
          um.id, um.current_user_id, um.matched_user_id,
          um.mutual_score, um.viewer_scores_candidate, um.candidate_scores_viewer,
          um.rank, um.origin_phase, um.origin_method,
          um.is_active, um.is_mutual, um.is_viewed, um.user_action,
          um.created_at,
          cand.full_name AS cand_name, cand.age AS cand_age, cand.gender AS cand_gender,
          mdm.user_id_1, mdm.user_id_2,
          mdm.display_data_of_user_1, mdm.display_data_of_user_2,
          mdm.section_tags
        FROM user_matches um
        LEFT JOIN user_profile_data cand
               ON cand.user_id::text = um.matched_user_id
        LEFT JOIN matches_display_metadata mdm
               ON mdm.id = um.display_data
        WHERE um.run_id = %s::uuid
          AND um.current_user_id = ANY(%s)
        ORDER BY um.current_user_id, um.rank NULLS LAST, um.created_at
        """,
        (run_id, user_ids),
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


def _msg_type_badge(mt):
    if not mt:
        return ""
    colors = {"instant_match": "#1976d2", "weekly_match": "#7b1fa2"}
    c = colors.get(mt, "#455a64")
    return f'<span style="background:{c}; color:white; padding:2px 8px; border-radius:4px; font-size:11px; font-weight:600;">{mt}</span>'


def _collect_gcs_paths(elements) -> list:
    """Walk display_data elements and collect every GCS path that needs signing."""
    if not elements:
        return []
    if isinstance(elements, str):
        try:
            elements = json.loads(elements)
        except Exception:
            return []
    paths = []
    for el in elements:
        etype = el.get("type")
        content = el.get("content")
        if etype == "display_picture" and isinstance(content, str):
            paths.append(content)
        elif etype == "photos" and isinstance(content, list):
            for p in content:
                if isinstance(p, str):
                    paths.append(p)
                elif isinstance(p, dict) and p.get("url"):
                    paths.append(p["url"])
    return paths


def _render_display_data(elements, tags_for_viewer, signed_map):
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
            url = signed_map.get(content) if content else None
            if url:
                st.markdown(
                    f'<img src="{url}" style="max-width:280px; border-radius:8px;" />',
                    unsafe_allow_html=True,
                )
            elif content:
                st.caption(f"(sign failed) {content}")

        elif etype == "photos":
            st.markdown(f"**{title}**{tag}", unsafe_allow_html=True)
            items = content or []
            cols = st.columns(min(3, max(1, len(items))))
            for j, p in enumerate(items):
                path = p if isinstance(p, str) else (p.get("url") if isinstance(p, dict) else None)
                url = signed_map.get(path) if path else None
                if url:
                    with cols[j % len(cols)]:
                        st.markdown(
                            f'<img src="{url}" style="width:100%; border-radius:8px;" />',
                            unsafe_allow_html=True,
                        )

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
            st.caption(f"unknown element: {etype} → {content}")

        st.markdown("<hr style='margin:8px 0;'/>", unsafe_allow_html=True)


def _viewer_side_display(row, viewer_id):
    """Return (display_data_for_viewer, section_tags_for_candidate) given a user_matches row.

    Viewer reads display_data of the OTHER user (the candidate's card).
    """
    u1 = str(row.get("user_id_1") or "")
    u2 = str(row.get("user_id_2") or "")
    section_tags = row.get("section_tags") or {}
    if u1 == viewer_id:
        return row.get("display_data_of_user_2"), section_tags.get(u2)
    if u2 == viewer_id:
        return row.get("display_data_of_user_1"), section_tags.get(u1)
    return None, None


# ============ UI ============

st.title("🔔 Personalise Notification Viewer")
st.caption("Enter a run_id to see every personalised push copy generated for that run + the display_data each viewer saw.")

rc = st.columns([5, 1])
with rc[0]:
    run_id_input = st.text_input("Run ID", placeholder="uuid of matchmaking run")
with rc[1]:
    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
    if st.button("🔄 Refetch", use_container_width=True, help="Bypass cache and re-query DB"):
        fetch_personalised_rows.clear()
        fetch_matches_in_run.clear()
        st.rerun()

if not run_id_input:
    st.info("Enter a run_id to begin.")
    st.stop()

run_id = run_id_input.strip()

with st.spinner("Fetching personalised rows…"):
    rows = fetch_personalised_rows(run_id)

if not rows:
    st.error("No rows in matchmaking_personalise_notification for this run_id.")
    st.stop()

# ---- Summary header ----
total = len(rows)
msg_types = sorted({r.get("message_type") for r in rows if r.get("message_type")})
first_gen = min((r["generated_at"] for r in rows if r.get("generated_at")), default=None)
last_gen = max((r["generated_at"] for r in rows if r.get("generated_at")), default=None)

mc = st.columns(4)
mc[0].metric("users with copy", total)
mc[1].metric("message_types", ", ".join(msg_types) or "—")
mc[2].metric("first generated", first_gen.strftime("%H:%M:%S") if first_gen else "—")
mc[3].metric("last generated", last_gen.strftime("%H:%M:%S") if last_gen else "—")

st.markdown("---")

# ---- Filters ----
fc = st.columns([2, 2, 1.2, 1])
with fc[0]:
    search_q = st.text_input("Search (name or user_id)", placeholder="substring match")
with fc[1]:
    msg_filter = st.multiselect("message_type", options=msg_types, default=msg_types)
with fc[2]:
    gender_filter = st.radio(
        "gender",
        options=["all", "female", "male"],
        index=0,
        horizontal=True,
        key="pnv_gender",
    )
with fc[3]:
    show_raw = st.checkbox("show metadata", value=False)


def _keep(r):
    if msg_filter and r.get("message_type") not in msg_filter:
        return False
    if gender_filter != "all":
        g = (r.get("gender") or "").lower()
        if g != gender_filter:
            return False
    if search_q:
        q = search_q.lower().strip()
        name = (r.get("full_name") or "").lower()
        uid = str(r.get("user_id") or "").lower()
        if q not in name and q not in uid:
            return False
    return True


filtered = [r for r in rows if _keep(r)]

if not filtered:
    st.caption(f"Showing 0 / {total}")
    st.stop()

# ---- Pagination ----
pc = st.columns([1, 1, 3])
with pc[0]:
    page_size = st.selectbox("page size", [5, 10, 20, 50], index=1, key="pnv_page_size")
total_pages = max(1, (len(filtered) + page_size - 1) // page_size)

# Reset page if filters shrunk the result below current page (runs BEFORE widget instantiation)
if "pnv_page" not in st.session_state:
    st.session_state["pnv_page"] = 1
if st.session_state["pnv_page"] > total_pages:
    st.session_state["pnv_page"] = 1

with pc[1]:
    page_num = st.number_input(
        f"page (1–{total_pages})",
        min_value=1, max_value=total_pages,
        step=1, key="pnv_page",
    )
with pc[2]:
    start = (page_num - 1) * page_size
    end = min(start + page_size, len(filtered))
    st.markdown(
        f"<div style='padding-top:28px; color:#555;'>"
        f"Showing <b>{start + 1}–{end}</b> of <b>{len(filtered)}</b> "
        f"(filtered from {total})</div>",
        unsafe_allow_html=True,
    )

page_rows = filtered[start:end]

# ---- Batch fetch matches + sign GCS paths ONLY for current page ----
viewer_ids = [r["user_id"] for r in page_rows]

with st.spinner(f"Fetching matches + display_data for {len(viewer_ids)} users…"):
    match_rows = fetch_matches_in_run(run_id, tuple(viewer_ids))

matches_by_viewer: dict = {}
for m in match_rows:
    matches_by_viewer.setdefault(str(m["current_user_id"]), []).append(m)

all_paths = set()
for vid, ms in matches_by_viewer.items():
    for m in ms:
        dd, _ = _viewer_side_display(m, vid)
        all_paths.update(_collect_gcs_paths(dd))

with st.spinner(f"Signing {len(all_paths)} image URLs…"):
    signed_map = _sign_urls_batch_cached(tuple(sorted(all_paths)))

st.markdown("---")


# ---- Render per-user (current page only) ----
for r in page_rows:
    uid = r["user_id"]
    name = r.get("full_name") or "?"
    age = r.get("age") or "?"
    gender = r.get("gender") or "?"
    city = r.get("city") or "?"
    mt = r.get("message_type")
    title_copy = r.get("title") or ""
    body_copy = r.get("body") or ""
    gen_at = r.get("generated_at")
    gen_s = gen_at.strftime("%Y-%m-%d %H:%M:%S") if hasattr(gen_at, "strftime") else str(gen_at)

    viewer_matches = matches_by_viewer.get(str(uid), [])
    header = f"{name}, {age} ({gender}) · {city} · {len(viewer_matches)} matches · {gen_s}"

    with st.expander(header, expanded=False):
        # Top row: badges + ids
        st.markdown(
            f'{_msg_type_badge(mt)} &nbsp; '
            f'<span style="color:#888; font-size:12px;">user_id:</span> '
            f'<code style="font-size:11px;">{uid}</code>',
            unsafe_allow_html=True,
        )

        # Notification preview card
        st.markdown(
            f"""
            <div style="
                background: linear-gradient(180deg, #fafafa 0%, #f0f0f0 100%);
                border: 1px solid #ddd; border-radius: 12px;
                padding: 14px 18px; margin: 10px 0 14px 0;
                box-shadow: 0 1px 3px rgba(0,0,0,0.06);
            ">
                <div style="display:flex; align-items:center; gap:8px; margin-bottom:6px;">
                    <div style="width:24px; height:24px; background:#000; border-radius:6px;
                                display:flex; align-items:center; justify-content:center;
                                color:white; font-weight:700; font-size:13px;">W</div>
                    <span style="font-weight:600; font-size:13px; color:#333;">Wavelength</span>
                    <span style="color:#888; font-size:11px; margin-left:auto;">now</span>
                </div>
                <div style="font-weight:700; font-size:15px; color:#111; margin-bottom:2px;">
                    {title_copy or "<i>(no title)</i>"}
                </div>
                <div style="font-size:14px; color:#333; line-height:1.35;">
                    {body_copy or "<i>(no body)</i>"}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if show_raw and r.get("metadata"):
            with st.expander("metadata", expanded=False):
                st.json(r["metadata"])

        if not viewer_matches:
            st.caption("No user_matches rows in this run for this viewer.")
            continue

        st.markdown(f"##### Matches shown to this viewer ({len(viewer_matches)})")

        for m in viewer_matches:
            cand_id = m["matched_user_id"]
            cand_name = m.get("cand_name") or "?"
            cand_age = m.get("cand_age") or "?"
            cand_gender = m.get("cand_gender") or "?"
            action = m.get("user_action")
            phase = m.get("origin_phase")
            rank = m.get("rank")
            mutual = m.get("mutual_score")

            parts = []
            if rank is not None:
                parts.append(f"#{rank}")
            parts.append(f"{cand_name}, {cand_age} ({cand_gender})")
            parts.append(f"m={round(mutual, 3) if mutual is not None else '—'}")
            if phase:
                parts.append(phase)
            parts.append(action or "no-action")
            sub_label = "  ·  ".join(parts)

            with st.expander(sub_label, expanded=False):
                st.markdown(
                    f'{_action_badge(action)} &nbsp; {_origin_badge(phase)}',
                    unsafe_allow_html=True,
                )
                st.caption(f"candidate_id: `{cand_id}` · match_id: `{m['id']}`")

                vs = m.get("viewer_scores_candidate")
                cs = m.get("candidate_scores_viewer")
                st.markdown(
                    f"**mutual**: {round(mutual, 4) if mutual is not None else '—'}  ·  "
                    f"**viewer→cand**: {round(vs, 4) if vs is not None else '—'}  ·  "
                    f"**cand→viewer**: {round(cs, 4) if cs is not None else '—'}"
                )

                flags = []
                if m.get("is_viewed"): flags.append("viewed")
                if m.get("is_mutual"): flags.append("mutual")
                if m.get("is_active"): flags.append("active")
                st.caption("flags: " + (", ".join(flags) if flags else "—"))

                st.markdown("---")

                dd, tags_for_card = _viewer_side_display(m, uid)
                if dd:
                    _render_display_data(dd, tags_for_card, signed_map)
                else:
                    st.caption("No display_data linked to this reco")

# ---- Bottom pagination controls (prev / next) ----
def _goto_page(p):
    # Callback runs BEFORE next rerun → safe to set widget-keyed state
    st.session_state["pnv_page"] = p

st.markdown("---")
bp = st.columns([1, 1, 3, 1, 1])
with bp[0]:
    st.button("⏮ first", disabled=page_num <= 1, use_container_width=True,
              key="pnv_btn_first", on_click=_goto_page, args=(1,))
with bp[1]:
    st.button("← prev", disabled=page_num <= 1, use_container_width=True,
              key="pnv_btn_prev", on_click=_goto_page, args=(max(1, page_num - 1),))
with bp[2]:
    st.markdown(
        f"<div style='text-align:center; padding-top:8px; color:#555;'>"
        f"page <b>{page_num}</b> / <b>{total_pages}</b></div>",
        unsafe_allow_html=True,
    )
with bp[3]:
    st.button("next →", disabled=page_num >= total_pages, use_container_width=True,
              key="pnv_btn_next", on_click=_goto_page, args=(min(total_pages, page_num + 1),))
with bp[4]:
    st.button("last ⏭", disabled=page_num >= total_pages, use_container_width=True,
              key="pnv_btn_last", on_click=_goto_page, args=(total_pages,))
