"""
Quality Filtering Dashboard
Review quality-filtered users from actual-prod: onboarding chats + photos.
"""
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


@st.cache_resource
def get_app_prod_client():
    if not SUPABASE_URL_APP or not SUPABASE_KEY_APP:
        st.error("Missing SUPABASE_URL_APP_PROD or SUPABASE_SERVICE_ROLE_KEY_APP_PROD in .env")
        st.stop()
    return create_client(SUPABASE_URL_APP, SUPABASE_KEY_APP)


USERS_PER_PAGE = 5

# Storage base for constructing public-style signed URLs
# We'll use create_signed_urls (batch) for speed
SIGNED_URL_EXPIRY = 3600


# =========== BATCH FETCHERS ===========

@st.cache_data(ttl=300, show_spinner=False)
def fetch_all_quality_users():
    """Fetch ALL quality_filtering rows joined with user_data + profile. Cached 5 min."""
    sb = get_app_prod_client()
    resp = sb.from_("quality_filtering").select(
        "user_id, chat_verdict, pic_verdict, final_verdict, "
        "chat_reasoning, pic_reasoning, created_at, "
        "user_data!inner(user_id, user_phone, user_email, user_code, deleted_at, "
        "user_profile_data!user_profile_data_user_id_fkey(full_name, gender))"
    ).is_("user_data.deleted_at", "null").order("created_at", desc=True).limit(999).execute()
    return resp.data or []


@st.cache_data(ttl=300, show_spinner=False)
def fetch_conversations_for_page(user_ids_tuple):
    """Fetch onboarding conversations + messages for user_ids. Cached 5 min."""
    user_ids = list(user_ids_tuple)
    sb = get_app_prod_client()

    # 1) Get all onboarding conversations in one call
    conv_resp = sb.from_("conversations").select(
        "id, participant_a"
    ).in_("participant_a", user_ids).eq("type", "ai").eq("ai_agent_type", "onboarding").execute()

    convs = conv_resp.data or []
    if not convs:
        return {uid: [] for uid in user_ids}

    user_conv_map = {}
    for c in convs:
        user_conv_map[c["participant_a"]] = c["id"]

    # 2) Fetch messages per conversation in parallel (each can have 300+ msgs)
    def fetch_msgs_for_conv(conv_id):
        resp = sb.from_("messages").select(
            "conversation_id, sender_type, text, created_at"
        ).eq("conversation_id", conv_id).order("created_at", desc=False).limit(999).execute()
        return conv_id, resp.data or []

    conv_msgs = {}
    conv_ids = list(user_conv_map.values())
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(fetch_msgs_for_conv, cid) for cid in conv_ids]
        for f in futures:
            cid, msgs = f.result()
            conv_msgs[cid] = msgs

    return {uid: conv_msgs.get(user_conv_map.get(uid, ""), []) for uid in user_ids}


@st.cache_data(ttl=300, show_spinner=False)
def fetch_photos_for_page(user_ids_tuple):
    """Fetch photos + batch sign URLs for user_ids. Cached 5 min."""
    user_ids = list(user_ids_tuple)
    sb = get_app_prod_client()

    photo_resp = sb.from_("user_photos").select(
        "user_id, url, category, position, is_display_photo"
    ).in_("user_id", user_ids).order("position", desc=False).execute()

    all_photos = photo_resp.data or []
    if not all_photos:
        return {uid: [] for uid in user_ids}

    # Batch sign all URLs in ONE call
    all_paths = [p["url"] for p in all_photos]
    try:
        signed_results = sb.storage.from_("media").create_signed_urls(all_paths, SIGNED_URL_EXPIRY)
        signed_map = {}
        for item in signed_results:
            path = item.get("path", "")
            url = item.get("signedURL") or item.get("signedUrl", "")
            if path:
                signed_map[path] = url
    except Exception:
        # Fallback: no signed URLs
        signed_map = {}

    for p in all_photos:
        p["signed_url"] = signed_map.get(p["url"], "")

    user_photos = {}
    for p in all_photos:
        user_photos.setdefault(p["user_id"], []).append(p)

    return {uid: user_photos.get(uid, []) for uid in user_ids}


def fetch_page_data(page_user_ids):
    """Fetch conversations and photos in parallel. Results are cached."""
    ids_tuple = tuple(page_user_ids)
    with ThreadPoolExecutor(max_workers=2) as executor:
        conv_future = executor.submit(fetch_conversations_for_page, ids_tuple)
        photo_future = executor.submit(fetch_photos_for_page, ids_tuple)
        return conv_future.result(), photo_future.result()


# ============== UI ==============

st.markdown("#### Quality Filtering Review")

# --- Sidebar search ---
st.sidebar.markdown("### Search")
search_user_id = st.sidebar.text_input("Search by User ID", placeholder="paste user_id here...")

# --- Sidebar filters ---
st.sidebar.markdown("### Filters")

verdict_options = {"All": None, "Pass (True)": True, "Fail (False)": False}

chat_filter = st.sidebar.radio("Chat Verdict", list(verdict_options.keys()), index=0, horizontal=True)
pic_filter = st.sidebar.radio("Pic Verdict", list(verdict_options.keys()), index=0, horizontal=True)
final_filter = st.sidebar.radio("Final Verdict", list(verdict_options.keys()), index=0, horizontal=True)

gender_options = ["All", "male", "female"]
gender_filter = st.sidebar.radio("Gender", gender_options, index=0, horizontal=True)

chat_val = verdict_options[chat_filter]
pic_val = verdict_options[pic_filter]
final_val = verdict_options[final_filter]

if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

# --- Fetch ALL users upfront (cached) ---
all_users = fetch_all_quality_users()

# --- Apply filters in-memory ---
filtered_users = all_users
if search_user_id.strip():
    filtered_users = [u for u in filtered_users if search_user_id.strip().lower() in u["user_id"].lower()]
if chat_val is not None:
    filtered_users = [u for u in filtered_users if u["chat_verdict"] == chat_val]
if pic_val is not None:
    filtered_users = [u for u in filtered_users if u["pic_verdict"] == pic_val]
if final_val is not None:
    filtered_users = [u for u in filtered_users if u["final_verdict"] == final_val]
if gender_filter != "All":
    filtered_users = [u for u in filtered_users if ((u.get("user_data") or {}).get("user_profile_data") or {}).get("gender") == gender_filter]

total = len(filtered_users)
st.sidebar.markdown(f"**Total users: {total}**")

if total == 0:
    st.info("No users found with the selected filters.")
    st.stop()

# --- Pagination ---
total_pages = (total + USERS_PER_PAGE - 1) // USERS_PER_PAGE
if "qf_page" not in st.session_state:
    st.session_state.qf_page = 1
if st.session_state.qf_page > total_pages:
    st.session_state.qf_page = total_pages

col_prev, col_info, col_next = st.columns([1, 3, 1])
with col_prev:
    if st.button("←", disabled=st.session_state.qf_page <= 1, use_container_width=True):
        st.session_state.qf_page -= 1
        st.rerun()
with col_info:
    st.markdown(
        f"<p style='text-align:center; margin:8px 0; color: grey;'>"
        f"{st.session_state.qf_page} / {total_pages} &nbsp;&middot;&nbsp; {total} users</p>",
        unsafe_allow_html=True,
    )
with col_next:
    if st.button("→", disabled=st.session_state.qf_page >= total_pages, use_container_width=True):
        st.session_state.qf_page += 1
        st.rerun()

start = (st.session_state.qf_page - 1) * USERS_PER_PAGE
page_users = filtered_users[start:start + USERS_PER_PAGE]
page_user_ids = [u["user_id"] for u in page_users]

# --- Batch fetch (parallel + cached) ---
with st.spinner("Loading..."):
    conversations, photos = fetch_page_data(page_user_ids)


# --- Render ---
def badge(val):
    if val is True:
        return "✅ Pass"
    elif val is False:
        return "❌ Fail"
    return "⏳ Pending"


for user in page_users:
    uid = user["user_id"]
    ud = user.get("user_data", {})
    upd = ud.get("user_profile_data") or {}
    phone = ud.get("user_phone", "N/A")
    email = ud.get("user_email", "N/A")
    code = ud.get("user_code", "N/A")
    name = upd.get("full_name", "N/A")
    gender = upd.get("gender", "N/A")

    chat_v = user["chat_verdict"]
    pic_v = user["pic_verdict"]
    final_v = user["final_verdict"]

    verdict_icon = "✅" if final_v else "❌"
    with st.expander(f"{verdict_icon} {name} ({gender})", expanded=False):
        # --- User info as a clean table ---
        info_col1, info_col2 = st.columns(2)
        with info_col1:
            st.code(uid, language=None)
        with info_col2:
            if phone and phone != "N/A":
                st.code(phone, language=None)

        st.markdown("")

        # --- Verdict pills ---
        v_col1, v_col2, v_col3 = st.columns(3)
        with v_col1:
            if chat_v:
                st.success("Chat: Pass", icon="✅")
            else:
                st.error("Chat: Fail", icon="❌")
        with v_col2:
            if pic_v:
                st.success("Pic: Pass", icon="✅")
            else:
                st.error("Pic: Fail", icon="❌")
        with v_col3:
            if final_v:
                st.success("Final: Pass", icon="✅")
            else:
                st.error("Final: Fail", icon="❌")

        st.markdown("")

        # --- Reasoning ---
        col_cr, col_pr = st.columns(2)
        with col_cr:
            st.markdown("**Chat Reasoning**")
            st.info(user.get("chat_reasoning") or "N/A")
        with col_pr:
            st.markdown("**Pic Reasoning**")
            st.info(user.get("pic_reasoning") or "N/A")

        # --- Edit verdict ---
        edit_key = f"edit_{uid}"
        confirm_key = f"confirm_{uid}"

        if st.button("✏️ Edit Verdicts", key=f"btn_edit_{uid}"):
            st.session_state[edit_key] = True
            st.session_state.pop(confirm_key, None)

        if st.session_state.get(edit_key):
            st.markdown("---")
            ec1, ec2, ec3 = st.columns(3)
            with ec1:
                new_chat = st.toggle("Chat Verdict", value=bool(chat_v), key=f"tog_chat_{uid}")
            with ec2:
                new_pic = st.toggle("Pic Verdict", value=bool(pic_v), key=f"tog_pic_{uid}")
            with ec3:
                new_final = new_chat or new_pic
                if new_final:
                    st.success(f"Final: Pass", icon="✅")
                else:
                    st.error(f"Final: Fail", icon="❌")

            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                if st.button("Submit", key=f"btn_submit_{uid}", type="primary", use_container_width=True):
                    st.session_state[confirm_key] = {
                        "chat": new_chat, "pic": new_pic, "final": new_final
                    }
            with btn_col2:
                if st.button("Cancel", key=f"btn_cancel_{uid}", use_container_width=True):
                    st.session_state.pop(edit_key, None)
                    st.session_state.pop(confirm_key, None)
                    st.rerun()

            if st.session_state.get(confirm_key):
                vals = st.session_state[confirm_key]
                st.warning(
                    f"**Update {name}?**\n\n"
                    f"- Chat: {badge(chat_v)} → {'✅ Pass' if vals['chat'] else '❌ Fail'}\n"
                    f"- Pic: {badge(pic_v)} → {'✅ Pass' if vals['pic'] else '❌ Fail'}\n"
                    f"- Final: {badge(final_v)} → {'✅ Pass' if vals['final'] else '❌ Fail'}"
                )
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Yes, update", key=f"btn_yes_{uid}", type="primary", use_container_width=True):
                        sb = get_app_prod_client()
                        sb.from_("quality_filtering").update({
                            "chat_verdict": vals["chat"],
                            "pic_verdict": vals["pic"],
                            "final_verdict": vals["final"],
                        }).eq("user_id", uid).execute()
                        st.session_state.pop(edit_key, None)
                        st.session_state.pop(confirm_key, None)
                        st.cache_data.clear()
                        st.success("Updated!")
                        st.rerun()
                with c2:
                    if st.button("No, go back", key=f"btn_no_{uid}", use_container_width=True):
                        st.session_state.pop(confirm_key, None)
                        st.rerun()

        st.markdown("")

        # --- Tabs ---
        tab_chat, tab_photos = st.tabs(["💬 Onboarding Chat", "📸 Photos"])

        with tab_chat:
            msgs = conversations.get(uid, [])
            if not msgs:
                st.warning("No onboarding conversation found.")
            else:
                for msg in msgs:
                    sender = msg["sender_type"]
                    text = msg.get("text", "")
                    if not text:
                        continue
                    if sender == "ai":
                        with st.chat_message("assistant"):
                            st.markdown(text)
                    elif sender == "user":
                        with st.chat_message("user"):
                            st.markdown(text)
                    else:
                        st.caption(f"[{sender}] {text}")

        with tab_photos:
            user_photos = photos.get(uid, [])
            if not user_photos:
                st.warning("No photos found.")
            else:
                cols = st.columns(min(len(user_photos), 4))
                for i, photo in enumerate(user_photos):
                    with cols[i % 4]:
                        url = photo.get("signed_url", "")
                        if url:
                            st.image(url, use_container_width=True,
                                     caption=f"{'⭐ Display' if photo.get('is_display_photo') else ''} pos:{photo.get('position')}")
                        else:
                            st.warning(f"Could not load photo {i+1}")
