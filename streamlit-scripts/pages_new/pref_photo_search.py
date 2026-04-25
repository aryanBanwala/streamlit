"""
Pref → Photo Vector Search
Input a user_id → load their pref summary embedding from user_pref_vectors,
run pgvector nearest-neighbor against user_photos_analysis, render photos.
"""
import streamlit as st
import os
import sys
import json
import base64
from datetime import timedelta

import psycopg2
import psycopg2.extras
from google.cloud import storage
from google.oauth2 import service_account
from dotenv import load_dotenv

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


# ============ DB ============

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


# ============ GCS ============

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
    out = {}
    for path in paths:
        try:
            blob = bucket.blob(path)
            out[path] = blob.generate_signed_url(
                version="v4", expiration=timedelta(seconds=SIGNED_URL_EXPIRY), method="GET",
            )
        except Exception:
            pass
    return out


# ============ Fetchers ============

@st.cache_data(ttl=300, show_spinner=False)
def fetch_pref(user_id: str):
    rows = _db_query(
        """
        SELECT user_id, type, summary_text, summary_update_count,
               (summary_embedding IS NOT NULL) AS has_embedding
        FROM user_pref_vectors
        WHERE user_id = %s::uuid AND type = 'image'
        LIMIT 1
        """,
        (user_id,),
    )
    return rows[0] if rows else None


@st.cache_data(ttl=300, show_spinner=False)
def fetch_topk_photos(user_id: str, k: int):
    """pgvector nearest neighbor: pref.summary_embedding vs user_photos_analysis.embedding."""
    return _db_query(
        """
        WITH q AS (
            SELECT summary_embedding
            FROM user_pref_vectors
            WHERE user_id = %s::uuid AND type = 'image'
            LIMIT 1
        )
        SELECT
            upa.photo_id,
            upa.user_id,
            upa.description,
            1 - (upa.embedding <=> q.summary_embedding) AS similarity
        FROM user_photos_analysis upa, q
        WHERE upa.embedding IS NOT NULL
        ORDER BY upa.embedding <=> q.summary_embedding
        LIMIT %s
        """,
        (user_id, k),
    )


@st.cache_data(ttl=300, show_spinner=False)
def fetch_photo_urls(photo_ids_tuple: tuple):
    if not photo_ids_tuple:
        return {}
    rows = _db_query(
        "SELECT id, url FROM user_photos WHERE id = ANY(%s::uuid[])",
        (list(photo_ids_tuple),),
    )
    path_by_id = {str(r["id"]): r["url"] for r in rows if r.get("url")}
    signed = _gcs_sign_urls_batch(list({p for p in path_by_id.values()}))
    return {pid: signed.get(path, "") for pid, path in path_by_id.items()}


# ============ UI ============

st.title("🔎 Pref → Photo Vector Search")
st.caption("Input a user_id, load their pref summary embedding, and find the closest photos across user_photos_analysis.")

c1, c2, c3 = st.columns([3, 1, 1])
with c1:
    user_id = st.text_input("User ID", placeholder="uuid…").strip()
with c2:
    top_k = st.number_input("Top K", min_value=1, max_value=200, value=12)
with c3:
    st.write("")
    st.write("")
    run = st.button("Search", type="primary", use_container_width=True)

if not user_id:
    st.info("Enter a user_id to begin.")
    st.stop()

if not run and "last_query" not in st.session_state:
    st.stop()

if run:
    st.session_state["last_query"] = (user_id, int(top_k))

q_uid, q_k = st.session_state["last_query"]

pref = fetch_pref(q_uid)
if not pref:
    st.error(f"No pref row found for user_id `{q_uid}` (type=image).")
    st.stop()

if not pref.get("has_embedding"):
    st.error(f"Pref row exists but summary_embedding is NULL for `{q_uid}`.")
    st.stop()

with st.expander("📝 Pref summary text", expanded=True):
    st.write(pref.get("summary_text") or "_(empty)_")
    st.caption(f"update count: {pref.get('summary_update_count')}")

with st.spinner("Searching nearest photos…"):
    results = fetch_topk_photos(q_uid, q_k)

if not results:
    st.warning("No matches.")
    st.stop()

top_photo_ids = tuple(str(r["photo_id"]) for r in results)
url_map = fetch_photo_urls(top_photo_ids)

st.subheader(f"Top {len(results)} matches")

cols_per_row = 3
for row_start in range(0, len(results), cols_per_row):
    cols = st.columns(cols_per_row)
    for col, r in zip(cols, results[row_start : row_start + cols_per_row]):
        pid = str(r["photo_id"])
        uid = str(r["user_id"])
        score = float(r["similarity"]) if r.get("similarity") is not None else 0.0
        url = url_map.get(pid, "")
        with col:
            if url:
                st.image(url, use_container_width=True)
            else:
                st.markdown("_(no url)_")
            st.markdown(f"**score:** `{score:.4f}`")
            st.markdown(f"**user_id:** `{uid}`")
            st.markdown(f"**photo_id:** `{pid}`")
            with st.expander("description"):
                st.write(r.get("description") or "_(empty)_")
