"""
Cohort CSV Explorer
Upload a CSV (e.g. males who passed quality but are outside the matchmaking cohort)
and inspect each user_id with their verdicts, reasoning, attractiveness, tier, and
photos. Filters by tier / attractiveness band / verdicts / user_id search.

Expected CSV columns:
    user_id, user_photos, prof_tier, attractiveness_score,
    chat_verdict, chat_reasoning, pic_verdict, pic_reasoning, final_verdict
`user_photos` is a comma-separated list of GCS object paths.
"""
import base64
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from google.cloud import storage
from google.oauth2 import service_account

# --- Setup paths & env ---
current_dir = os.path.dirname(__file__)
scripts_dir = os.path.abspath(os.path.join(current_dir, ".."))
parent_dir = os.path.abspath(os.path.join(scripts_dir, ".."))
sys.path.insert(0, parent_dir)

dotenv_path = os.path.join(parent_dir, ".env")
load_dotenv(dotenv_path)

GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "")
GCS_PROJECT_ID = os.getenv("GCS_PROJECT_ID", "")
GCS_CREDENTIALS_BASE64 = os.getenv("GCS_CREDENTIALS_BASE64", "")

SIGNED_URL_EXPIRY = 3600
USERS_PER_PAGE = 5


# =========== GCS HELPERS ===========

@st.cache_resource
def get_gcs_bucket():
    if GCS_CREDENTIALS_BASE64:
        sa_info = json.loads(base64.b64decode(GCS_CREDENTIALS_BASE64))
        creds = service_account.Credentials.from_service_account_info(sa_info)
        client = storage.Client(project=GCS_PROJECT_ID, credentials=creds)
    else:
        client = storage.Client(project=GCS_PROJECT_ID)
    return client.bucket(GCS_BUCKET_NAME)


def _check_and_sign(path):
    """One HEAD request per blob (exists) + local signing if present.
    Returns (path, signed_url_or_empty, exists)."""
    try:
        bucket = get_gcs_bucket()
        blob = bucket.blob(path)
        if not blob.exists():
            return path, "", False
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=SIGNED_URL_EXPIRY),
            method="GET",
        )
        return path, url, True
    except Exception:
        return path, "", False


@st.cache_data(ttl=SIGNED_URL_EXPIRY - 60, show_spinner=False)
def _gcs_sign_urls_batch(paths_tuple):
    """Returns {path: {"url": str, "exists": bool}} for all paths.
    Parallel HEAD requests + local signing; cached so repeats are free."""
    paths = list(dict.fromkeys(paths_tuple))  # dedupe, preserve order
    if not paths:
        return {}
    out = {}
    with ThreadPoolExecutor(max_workers=16) as executor:
        for path, url, exists in executor.map(_check_and_sign, paths):
            out[path] = {"url": url, "exists": exists}
    return out


# =========== CSV PARSING ===========

def _split_photos(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return []
    s = str(val).strip()
    if not s:
        return []
    return [p.strip() for p in s.split(",") if p.strip()]


def _parse_bool(v):
    if isinstance(v, bool):
        return v
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip().lower()
    if s in ("true", "t", "1", "yes"):
        return True
    if s in ("false", "f", "0", "no"):
        return False
    return None


def _band(att):
    if att is None or pd.isna(att):
        return "NULL_ATT"
    try:
        a = float(att)
    except (TypeError, ValueError):
        return "NULL_ATT"
    if a >= 7:
        return "HIGH"
    if a >= 4:
        return "MID"
    return "LOW"


@st.cache_data(show_spinner=False)
def parse_csv(file_bytes: bytes, name: str) -> pd.DataFrame:
    import io
    df = pd.read_csv(io.BytesIO(file_bytes))
    # Normalize column names (case-insensitive)
    df.columns = [c.strip() for c in df.columns]
    expected = {
        "user_id", "user_photos", "prof_tier", "attractiveness_score",
        "chat_verdict", "chat_reasoning", "pic_verdict", "pic_reasoning", "final_verdict",
    }
    missing = expected - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    df["user_id"] = df["user_id"].astype(str)
    df["photos_list"] = df["user_photos"].apply(_split_photos)
    df["prof_tier"] = df["prof_tier"].astype(str).str.strip()
    df["attractiveness_score"] = pd.to_numeric(df["attractiveness_score"], errors="coerce")
    df["chat_verdict_b"] = df["chat_verdict"].apply(_parse_bool)
    df["pic_verdict_b"] = df["pic_verdict"].apply(_parse_bool)
    df["final_verdict_b"] = df["final_verdict"].apply(_parse_bool)
    df["band"] = df["attractiveness_score"].apply(_band)
    return df


# =========== UI ===========

st.markdown("#### Cohort CSV Explorer")
st.caption("Upload a CSV of users (with verdicts + photos) and explore each user_id with filters.")

uploaded = st.file_uploader(
    "Upload CSV",
    type=["csv"],
    help="Required columns: user_id, user_photos, prof_tier, attractiveness_score, "
         "chat_verdict, chat_reasoning, pic_verdict, pic_reasoning, final_verdict",
)

if not uploaded:
    st.info("Upload a CSV to get started.")
    st.stop()

try:
    df = parse_csv(uploaded.getvalue(), uploaded.name)
except Exception as e:
    st.error(f"Could not parse CSV: {e}")
    st.stop()

st.success(f"Loaded **{len(df):,}** rows from `{uploaded.name}`.")

# Compact summary by tier
summary = (
    df.groupby("prof_tier", dropna=False)
    .size()
    .reset_index(name="count")
    .sort_values("prof_tier")
)
with st.expander("Quick summary (by tier)", expanded=False):
    st.dataframe(summary, use_container_width=True, hide_index=True)

# --- Sidebar filters ---
st.sidebar.markdown("### Search")
search_uid = st.sidebar.text_input("Search by user_id", placeholder="paste user_id (or prefix)")

st.sidebar.markdown("### Filters")

tier_options = sorted(df["prof_tier"].dropna().unique().tolist())
selected_tiers = st.sidebar.multiselect("Profile Tier", tier_options, default=tier_options)

band_options = ["HIGH", "MID", "LOW", "NULL_ATT"]
present_bands = [b for b in band_options if b in df["band"].unique()]
selected_bands = st.sidebar.multiselect("Attractiveness Band", present_bands, default=present_bands)

att_valid = df["attractiveness_score"].dropna()
if len(att_valid) > 0:
    att_min, att_max = int(att_valid.min()), int(att_valid.max())
else:
    att_min, att_max = 0, 10
if att_min == att_max:
    att_max = att_min + 1
att_range = st.sidebar.slider(
    "Attractiveness Score Range", min_value=att_min, max_value=att_max,
    value=(att_min, att_max),
)
include_null_att = st.sidebar.checkbox("Include rows with NULL attractiveness", value=True)

verdict_options = {"All": None, "Pass": True, "Fail": False}
chat_filter = st.sidebar.radio("Chat Verdict", list(verdict_options.keys()), index=0, horizontal=True)
pic_filter = st.sidebar.radio("Pic Verdict", list(verdict_options.keys()), index=0, horizontal=True)
final_filter = st.sidebar.radio("Final Verdict", list(verdict_options.keys()), index=0, horizontal=True)

if st.sidebar.button("Reset filters", use_container_width=True):
    for k in list(st.session_state.keys()):
        if k.startswith("cohort_csv_"):
            del st.session_state[k]
    st.rerun()

# --- Apply filters ---
filt = df.copy()
if selected_tiers:
    filt = filt[filt["prof_tier"].isin(selected_tiers)]
if selected_bands:
    filt = filt[filt["band"].isin(selected_bands)]
att_mask = (
    (filt["attractiveness_score"] >= att_range[0])
    & (filt["attractiveness_score"] <= att_range[1])
)
if include_null_att:
    att_mask = att_mask | filt["attractiveness_score"].isna()
filt = filt[att_mask]
if verdict_options[chat_filter] is not None:
    filt = filt[filt["chat_verdict_b"] == verdict_options[chat_filter]]
if verdict_options[pic_filter] is not None:
    filt = filt[filt["pic_verdict_b"] == verdict_options[pic_filter]]
if verdict_options[final_filter] is not None:
    filt = filt[filt["final_verdict_b"] == verdict_options[final_filter]]
if search_uid.strip():
    q = search_uid.strip().lower()
    filt = filt[filt["user_id"].str.lower().str.contains(q, na=False)]

filt = filt.sort_values(
    ["prof_tier", "attractiveness_score"], ascending=[True, False], na_position="last"
).reset_index(drop=True)

total = len(filt)
st.sidebar.markdown(f"**Showing: {total:,} / {len(df):,}**")

if total == 0:
    st.warning("No rows match the current filters.")
    st.stop()

# --- Pagination ---
total_pages = (total + USERS_PER_PAGE - 1) // USERS_PER_PAGE
if "cohort_csv_page" not in st.session_state:
    st.session_state.cohort_csv_page = 1
if st.session_state.cohort_csv_page > total_pages:
    st.session_state.cohort_csv_page = total_pages

col_prev, col_info, col_next = st.columns([1, 3, 1])
with col_prev:
    if st.button("←", disabled=st.session_state.cohort_csv_page <= 1, use_container_width=True):
        st.session_state.cohort_csv_page -= 1
        st.rerun()
with col_info:
    st.markdown(
        f"<p style='text-align:center; margin:8px 0; color: grey;'>"
        f"Page {st.session_state.cohort_csv_page} / {total_pages} "
        f"&nbsp;&middot;&nbsp; {total:,} users</p>",
        unsafe_allow_html=True,
    )
with col_next:
    if st.button("→", disabled=st.session_state.cohort_csv_page >= total_pages, use_container_width=True):
        st.session_state.cohort_csv_page += 1
        st.rerun()

start = (st.session_state.cohort_csv_page - 1) * USERS_PER_PAGE
page_rows = filt.iloc[start:start + USERS_PER_PAGE]

# --- Pre-sign all photos for this page in one batch ---
all_paths = []
for _, row in page_rows.iterrows():
    all_paths.extend(row["photos_list"])
signed_map = _gcs_sign_urls_batch(tuple(all_paths)) if all_paths else {}


def _verdict_pill(label, val):
    if val is True:
        st.success(f"{label}: Pass", icon="✅")
    elif val is False:
        st.error(f"{label}: Fail", icon="❌")
    else:
        st.info(f"{label}: —")


for _, row in page_rows.iterrows():
    uid = row["user_id"]
    tier = row["prof_tier"] or "—"
    att = row["attractiveness_score"]
    att_str = f"{int(att)}" if pd.notna(att) else "—"
    band = row["band"]
    final_v = row["final_verdict_b"]
    icon = "✅" if final_v else ("❌" if final_v is False else "⏳")

    header = f"{icon}  {uid[:8]}…  ·  Tier {tier}  ·  Att {att_str} ({band})"
    with st.expander(header, expanded=False):
        # Identity row
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1:
            st.code(uid, language=None)
        with c2:
            st.metric("Tier", tier)
        with c3:
            st.metric("Att Score", att_str)

        # Verdict pills
        v1, v2, v3 = st.columns(3)
        with v1:
            _verdict_pill("Chat", row["chat_verdict_b"])
        with v2:
            _verdict_pill("Pic", row["pic_verdict_b"])
        with v3:
            _verdict_pill("Final", final_v)

        # Reasoning
        r1, r2 = st.columns(2)
        with r1:
            st.markdown("**Chat Reasoning**")
            st.info(row.get("chat_reasoning") or "—")
        with r2:
            st.markdown("**Pic Reasoning**")
            st.info(row.get("pic_reasoning") or "—")

        # Photos
        photos = row["photos_list"]
        missing_count = sum(1 for p in photos if not signed_map.get(p, {}).get("exists"))
        st.markdown(f"**Photos** ({len(photos)} total"
                    + (f", {missing_count} not found in bucket" if missing_count else "")
                    + ")")
        if not photos:
            st.warning("No photos in CSV for this user.")
        else:
            cols_per_row = 4
            for i in range(0, len(photos), cols_per_row):
                row_slice = photos[i:i + cols_per_row]
                cols = st.columns(cols_per_row)
                for j, path in enumerate(row_slice):
                    with cols[j]:
                        info = signed_map.get(path, {"url": "", "exists": False})
                        if info["exists"] and info["url"]:
                            st.image(info["url"], use_container_width=True, caption=f"#{i + j + 1}")
                        else:
                            st.markdown(
                                f"""
                                <div style="height:200px;border-radius:10px;
                                    border:1px dashed rgba(220,53,69,0.4);
                                    background:rgba(220,53,69,0.06);
                                    display:flex;align-items:center;justify-content:center;
                                    flex-direction:column;color:rgba(220,53,69,0.85);
                                    font-size:0.85rem;text-align:center;padding:0.5rem;">
                                    <div style="font-size:1.6rem;">🚫</div>
                                    <div style="margin-top:6px;font-weight:600;">Not found in bucket</div>
                                    <div style="font-size:0.7rem;opacity:0.7;margin-top:4px;">#{i + j + 1}</div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )
                            with st.popover(f"path #{i + j + 1}", use_container_width=True):
                                st.code(path, language=None)
