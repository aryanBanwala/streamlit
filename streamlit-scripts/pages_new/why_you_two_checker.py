"""
Why You Two Checker — Ghibli Edition
Upload evals JSON, view old vs new 'Why You Two' text, extracted traits, user photos, and Ghibli images.
"""
import json
import base64
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


# =========== SUPABASE FETCHERS ===========

@st.cache_data(ttl=300, show_spinner=False)
def fetch_profiles_batch(user_ids_tuple):
    user_ids = list(user_ids_tuple)
    if not user_ids:
        return {}
    sb = get_client()
    all_results = {}
    for i in range(0, len(user_ids), 50):
        chunk = user_ids[i:i + 50]
        resp = sb.from_("user_profile_data").select(
            "user_id, full_name, gender, age"
        ).in_("user_id", chunk).execute()
        for r in (resp.data or []):
            all_results[r["user_id"]] = r
    return all_results


@st.cache_data(ttl=300, show_spinner=False)
def fetch_photos_batch(user_ids_tuple):
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
    ids_tuple = tuple(user_ids)
    with ThreadPoolExecutor(max_workers=2) as executor:
        profile_future = executor.submit(fetch_profiles_batch, ids_tuple)
        photo_future = executor.submit(fetch_photos_batch, ids_tuple)
        return profile_future.result(), photo_future.result()


# =========== RENDER HELPERS ===========

def render_user_photos(photos, photo_scale):
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

st.markdown("#### Why You Two Checker — Ghibli Edition")

# --- Sidebar ---
st.sidebar.markdown("### Upload")
uploaded_file = st.sidebar.file_uploader("Upload evals JSON", type=["json"])

if not uploaded_file:
    st.info("Upload an `evals_*.json` file to get started.")
    st.stop()

raw = json.loads(uploaded_file.read())
results = raw.get("results", [])
evaluated_at = raw.get("evaluated_at", "N/A")

if not results:
    st.warning("No results found in JSON.")
    st.stop()

st.sidebar.markdown(f"**Evaluated at:** {evaluated_at}")
st.sidebar.markdown(f"**Total pairs:** {len(results)}")

photo_scale = st.sidebar.slider("Photo Size (%)", min_value=20, max_value=100, value=60, step=10)
PAIRS_PER_PAGE = st.sidebar.number_input("Pairs per page", min_value=1, max_value=20, value=3)

if st.sidebar.button("Clear Cache"):
    st.cache_data.clear()
    st.rerun()

total = len(results)

# --- Pagination ---
total_pages = (total + PAIRS_PER_PAGE - 1) // PAIRS_PER_PAGE
if "wyt_page" not in st.session_state:
    st.session_state.wyt_page = 1
if st.session_state.wyt_page > total_pages:
    st.session_state.wyt_page = total_pages


def _go_prev():
    st.session_state.wyt_page = max(1, st.session_state.wyt_page - 1)


def _go_next():
    st.session_state.wyt_page = min(total_pages, st.session_state.wyt_page + 1)


def render_pagination(suffix):
    col_prev, col_info, col_next = st.columns([1, 3, 1])
    with col_prev:
        st.button("← Prev", disabled=st.session_state.wyt_page <= 1,
                  use_container_width=True, key=f"wyt_prev_{suffix}", on_click=_go_prev)
    with col_info:
        st.markdown(
            f"<p style='text-align:center; margin:8px 0; color:grey;'>"
            f"Page {st.session_state.wyt_page} / {total_pages} &nbsp;&middot;&nbsp; {total} pairs</p>",
            unsafe_allow_html=True,
        )
    with col_next:
        st.button("Next →", disabled=st.session_state.wyt_page >= total_pages,
                  use_container_width=True, key=f"wyt_next_{suffix}", on_click=_go_next)


render_pagination("top")

start = (st.session_state.wyt_page - 1) * PAIRS_PER_PAGE
page_results = results[start:start + PAIRS_PER_PAGE]

# Fetch user data
page_user_ids = list(set(
    uid for r in page_results for uid in [r["user_1_id"], r["user_2_id"]]
))

with st.spinner("Loading profiles & photos..."):
    profiles, photos = fetch_page_data(page_user_ids)

# --- Render each pair ---
for idx, result in enumerate(page_results):
    u1 = result["user_1_id"]
    u2 = result["user_2_id"]
    old_wyt = result.get("old", "")
    new_wyt = result.get("new", "")
    intermediate = result.get("intermediate_step_results", {})
    traits = intermediate.get("extracted_traits", [])
    extract_prompt = intermediate.get("extract_prompt_used", "?")
    generate_prompt = intermediate.get("generate_prompt_used", "?")
    ghibli_b64 = result.get("ghibli_image", "")

    profile_1 = profiles.get(u1, {})
    profile_2 = profiles.get(u2, {})
    name_1 = profile_1.get("full_name") or u1[:8]
    name_2 = profile_2.get("full_name") or u2[:8]
    gender_1 = profile_1.get("gender", "?")
    gender_2 = profile_2.get("gender", "?")
    age_1 = profile_1.get("age", "?")
    age_2 = profile_2.get("age", "?")

    st.markdown("---")
    st.markdown(
        f"##### Pair #{start + idx + 1}: {name_1} & {name_2}",
        unsafe_allow_html=True,
    )

    # Old vs New Why You Two
    wyt_col1, wyt_col2 = st.columns(2)
    with wyt_col1:
        st.markdown(
            f'<div style="background:#1e1e2e; border-radius:12px; padding:14px 20px; margin:8px 0;">'
            f'<p style="color:#ff9800; font-size:11px; text-transform:uppercase; letter-spacing:1px; margin:0 0 6px 0;">Old Why You Two</p>'
            f'<p style="color:#e0e0e8; font-size:15px; line-height:1.5; margin:0;">{old_wyt}</p>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with wyt_col2:
        st.markdown(
            f'<div style="background:linear-gradient(135deg, #6366f1 0%, #ec4899 100%); border-radius:12px; padding:14px 20px; margin:8px 0;">'
            f'<p style="color:rgba(255,255,255,0.7); font-size:11px; text-transform:uppercase; letter-spacing:1px; margin:0 0 6px 0;">New Why You Two</p>'
            f'<p style="color:#ffffff; font-size:15px; font-weight:500; line-height:1.5; margin:0;">{new_wyt}</p>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # Prompts used
    st.caption(f"Extract prompt: `{extract_prompt}` · Generate prompt: `{generate_prompt}`")

    # Extracted Traits
    if traits:
        with st.expander(f"Extracted Traits ({len(traits)})", expanded=True):
            for t_idx, trait in enumerate(traits):
                trait_name = trait.get("trait", "")
                ev_a = trait.get("person_a_evidence", "")
                ev_b = trait.get("person_b_evidence", "")
                st.markdown(
                    f'<div style="background:#1e1e2e; border-radius:10px; padding:12px 16px; margin-bottom:10px;">'
                    f'<p style="color:#a78bfa; font-size:14px; font-weight:600; margin:0 0 8px 0;">🔗 {trait_name}</p>'
                    f'<p style="color:#93c5fd; font-size:12px; margin:0 0 4px 0;"><b>{name_1}:</b> {ev_a}</p>'
                    f'<p style="color:#f9a8d4; font-size:12px; margin:0;"><b>{name_2}:</b> {ev_b}</p>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # Ghibli image + User photos side by side
    col_u1, col_ghibli, col_u2 = st.columns([1, 1.5, 1])

    with col_u1:
        g1_color = "#1976d2" if gender_1 == "male" else "#e91e63" if gender_1 == "female" else "#9e9e9e"
        st.markdown(
            f"**{name_1}**, {age_1} "
            f'<span style="color:{g1_color}; font-weight:600;">({gender_1})</span>',
            unsafe_allow_html=True,
        )
        st.code(u1, language=None)
        render_user_photos(photos.get(u1, []), photo_scale)

    with col_ghibli:
        st.markdown("**Ghibli Image**")
        if ghibli_b64:
            st.markdown(
                f'<div style="border-radius:12px; overflow:hidden; margin-bottom:8px;">'
                f'<img src="data:image/png;base64,{ghibli_b64}" style="width:100%; border-radius:12px;" />'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.info("No Ghibli image available")

    with col_u2:
        g2_color = "#1976d2" if gender_2 == "male" else "#e91e63" if gender_2 == "female" else "#9e9e9e"
        st.markdown(
            f"**{name_2}**, {age_2} "
            f'<span style="color:{g2_color}; font-weight:600;">({gender_2})</span>',
            unsafe_allow_html=True,
        )
        st.code(u2, language=None)
        render_user_photos(photos.get(u2, []), photo_scale)

st.markdown("---")
render_pagination("bottom")
