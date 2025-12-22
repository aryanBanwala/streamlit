"""
360 Profile View - Complete user profile with image manager, matches, and chat viewer.
"""
import streamlit as st
import pandas as pd
from datetime import datetime
import random
import string
import time

# Import services
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.users import UserService
from services.matches import MatchService
from services.supabase import supabase
from config import CACHE_TTL_SHORT, STORAGE_BUCKET


# --- Helper Functions ---

def format_number(n: int) -> str:
    """Format number with commas."""
    return f"{n:,}"


def generate_profile_filename(user_id: str, index: int) -> str:
    """Generate filename for profile images."""
    timestamp = int(time.time() * 1000)
    random_str = ''.join(random.choices(string.ascii_lowercase, k=6))
    return f"{user_id}-{timestamp}-{index}-{random_str}.jpeg"


def generate_collage_path(user_id: str) -> str:
    """Generate path for collage images."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"collage_creation/{user_id}/collage_{timestamp}.jpg"


def extract_storage_path(url: str) -> str:
    """Extract storage path from full URL."""
    parts = url.split('/chat-images/')
    return parts[1] if len(parts) > 1 else None


@st.cache_data(ttl=CACHE_TTL_SHORT)
def fetch_user_chats(user_id: str, chat_type: str) -> tuple:
    """Fetch chat sessions and messages for a user."""
    try:
        session_res = supabase.table('chat_sessions').select('*').eq(
            'user_id', user_id
        ).eq('chat_type', chat_type).order('created_at', desc=True).execute()
        sessions = session_res.data or []

        messages = []
        if sessions:
            session_ids = [s['id'] for s in sessions]
            message_res = supabase.table('chat_messages').select('*').in_(
                'session_id', session_ids
            ).order('created_at', desc=False).execute()
            messages = message_res.data or []

        return sessions, messages
    except Exception:
        return [], []


# --- Page Header ---

st.title("360 Profile View")
st.caption("Complete user view with profile, images, matches, and chat history")


# --- Search Section ---

st.markdown("---")

search_col1, search_col2, search_col3 = st.columns([2, 1, 1])

with search_col1:
    search_query = st.text_input(
        "Search",
        placeholder="Enter name, email, or user_id...",
        label_visibility="collapsed"
    )

with search_col2:
    gender_filter = st.selectbox(
        "Gender",
        options=['All', 'male', 'female'],
        label_visibility="collapsed"
    )

with search_col3:
    search_btn = st.button("Search", type="primary", use_container_width=True)

# Initialize session state
if 'profile_360_user' not in st.session_state:
    st.session_state.profile_360_user = None
if 'profile_360_search_results' not in st.session_state:
    st.session_state.profile_360_search_results = None


# --- Search Results ---

if search_btn and search_query:
    query = search_query.strip()

    # Check if it's a user_id (UUID format)
    if len(query) == 36 and '-' in query:
        user = UserService.get_user_by_id(query)
        if user:
            st.session_state.profile_360_user = user
            st.session_state.profile_360_search_results = None
        else:
            st.error("User not found with that ID")
            st.session_state.profile_360_user = None
            st.session_state.profile_360_search_results = None
    else:
        # Search by name
        gender = gender_filter if gender_filter != 'All' else None
        results = UserService.search_users(query, gender=gender)

        if not results:
            st.warning("No users found matching your search.")
            st.session_state.profile_360_user = None
            st.session_state.profile_360_search_results = None
        elif len(results) == 1:
            # Single result - load directly
            st.session_state.profile_360_user = UserService.get_user_by_id(results[0]['user_id'])
            st.session_state.profile_360_search_results = None
        else:
            # Multiple results - store in session state
            st.session_state.profile_360_search_results = results
            st.session_state.profile_360_user = None

# Show search results if available
if st.session_state.profile_360_search_results:
    results = st.session_state.profile_360_search_results
    st.markdown(f"**Found {len(results)} users:**")

    for idx, user in enumerate(results[:10]):
        col_info, col_btn = st.columns([4, 1])
        with col_info:
            name = user.get('name', 'Unknown')
            age = user.get('age', '')
            u_gender = user.get('gender', '')
            city = user.get('city', '')
            st.markdown(f"**{name}**, {age} | {u_gender} | {city}")
        with col_btn:
            if st.button("View", key=f"view_{idx}", use_container_width=True):
                st.session_state.profile_360_user = UserService.get_user_by_id(user['user_id'])
                st.session_state.profile_360_search_results = None
                st.rerun()


# --- Display User Profile ---

user = st.session_state.profile_360_user

if user:
    st.markdown("---")

    user_id = user.get('user_id')
    name = user.get('name', 'Unknown')
    age = user.get('age', '')
    gender = user.get('gender', '')

    # Header with user info
    header_col1, header_col2 = st.columns([3, 1])

    with header_col1:
        st.markdown(f"## {name}")
        st.markdown(f"**{age}** | **{gender.capitalize() if gender else 'N/A'}** | {user.get('city', 'N/A')}")

    with header_col2:
        if st.button("Clear", use_container_width=True):
            st.session_state.profile_360_user = None
            st.rerun()

    # Tabs for different sections
    tab_profile, tab_images, tab_matches, tab_chats = st.tabs([
        "Profile", "Images", "Matches", "Chats"
    ])

    # --- Profile Tab ---
    with tab_profile:
        # Get contact info
        contact = UserService.get_user_contact(user_id)

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### Basic Info")
            st.markdown(f"**User ID:** `{user_id}`")
            st.markdown(f"**Name:** {name}")
            st.markdown(f"**Age:** {age or 'N/A'}")
            st.markdown(f"**Gender:** {gender or 'N/A'}")
            st.markdown(f"**Height:** {user.get('height', 'N/A')}")
            st.markdown(f"**Religion:** {user.get('religion', 'N/A')}")

        with col2:
            st.markdown("#### Contact & Location")
            st.markdown(f"**City:** {user.get('city', 'N/A')}")
            st.markdown(f"**Area:** {user.get('area', 'N/A')}")
            st.markdown(f"**Phone:** {user.get('phone_num') or contact.get('user_phone', 'N/A')}")
            st.markdown(f"**Email:** {contact.get('user_email', 'N/A')}")

        st.markdown("---")

        col3, col4 = st.columns(2)

        with col3:
            st.markdown("#### Professional")
            st.markdown(f"**Education:** {user.get('education', 'N/A')}")
            st.markdown(f"**Work Experience:** {user.get('work_exp', 'N/A')}")

            tier = user.get('professional_tier')
            if tier is not None:
                tier_str = "Unassigned" if tier < 0 else f"Tier {tier}"
                st.markdown(f"**Professional Tier:** {tier_str}")

        with col4:
            st.markdown("#### Scores & Status")
            st.markdown(f"**Attractiveness:** {user.get('attractiveness', 'N/A')}")
            st.markdown(f"**Should Be Removed:** {user.get('shouldBeRemoved', False)}")
            st.markdown(f"**Has Appropriate Photos:** {user.get('hasAppropriatePhotos', 'N/A')}")

        # Dating Preferences
        prefs = user.get('dating_preferences')
        if prefs:
            st.markdown("---")
            st.markdown("#### Dating Preferences")
            if isinstance(prefs, dict):
                for key, value in prefs.items():
                    st.markdown(f"**{key}:** {value}")
            else:
                st.json(prefs)

        # Created At
        created_at = user.get('created_at')
        if created_at:
            st.markdown("---")
            st.caption(f"Created: {created_at[:19] if created_at else 'Unknown'}")


    # --- Images Tab ---
    with tab_images:
        # Profile Images Section
        profile_images = user.get('profile_images') or []

        col_header, col_add = st.columns([3, 1])
        with col_header:
            st.markdown(f"#### Profile Images ({len(profile_images)})")
        with col_add:
            if st.button("+ Add", key="add_profile_btn", use_container_width=True):
                st.session_state.show_profile_uploader = True

        # Add profile image uploader
        if st.session_state.get('show_profile_uploader'):
            uploaded_files = st.file_uploader(
                "Upload profile images",
                type=['jpg', 'jpeg', 'png'],
                key="profile_uploader",
                accept_multiple_files=True
            )
            if uploaded_files:
                with st.spinner(f"Uploading {len(uploaded_files)} image(s)..."):
                    success_count = 0
                    new_images = list(profile_images)

                    for i, uploaded_file in enumerate(uploaded_files):
                        index = len(new_images)
                        filename = generate_profile_filename(user_id, index)
                        file_path = f"public/{filename}"

                        url = UserService.upload_image(
                            uploaded_file.getvalue(),
                            file_path
                        )
                        if url:
                            new_images.append(url)
                            success_count += 1

                    if success_count > 0 and UserService.update_user_images(user_id, profile_images=new_images):
                        st.success(f"{success_count} image(s) uploaded!")
                        st.session_state.show_profile_uploader = False
                        UserService.get_user_by_id.clear()
                        st.session_state.profile_360_user = UserService.get_user_by_id(user_id)
                        st.rerun()

        # Display profile images
        if profile_images:
            cols = st.columns(4)
            for idx, url in enumerate(profile_images):
                with cols[idx % 4]:
                    try:
                        st.image(url, use_container_width=True)
                    except Exception:
                        st.error("Failed")

                    if st.button("Delete", key=f"del_profile_{idx}"):
                        with st.spinner("Deleting..."):
                            UserService.delete_image(url)
                            updated = [img for i, img in enumerate(profile_images) if i != idx]
                            if UserService.update_user_images(user_id, profile_images=updated):
                                UserService.get_user_by_id.clear()
                                st.session_state.profile_360_user = UserService.get_user_by_id(user_id)
                                st.rerun()
        else:
            st.info("No profile images")

        st.markdown("---")

        # Collage Images Section
        collage_images = user.get('collage_images') or []
        current_collage = collage_images[0] if collage_images else None

        col_header2, col_replace = st.columns([3, 1])
        with col_header2:
            st.markdown("#### Collage Image")
        with col_replace:
            btn_label = "Replace" if current_collage else "Upload"
            if st.button(btn_label, key="replace_collage_btn", use_container_width=True):
                st.session_state.show_collage_uploader = True

        # Collage uploader
        if st.session_state.get('show_collage_uploader'):
            uploaded_collage = st.file_uploader(
                "Upload collage image",
                type=['jpg', 'jpeg', 'png'],
                key="collage_uploader"
            )
            if uploaded_collage:
                with st.spinner("Uploading..."):
                    if current_collage:
                        UserService.delete_image(current_collage)

                    file_path = generate_collage_path(user_id)
                    url = UserService.upload_image(uploaded_collage.getvalue(), file_path)

                    if url and UserService.update_user_images(user_id, collage_images=[url]):
                        st.success("Collage uploaded!")
                        st.session_state.show_collage_uploader = False
                        UserService.get_user_by_id.clear()
                        st.session_state.profile_360_user = UserService.get_user_by_id(user_id)
                        st.rerun()

        # Display collage
        if current_collage:
            col_img, col_spacer = st.columns([1, 2])
            with col_img:
                try:
                    st.image(current_collage, use_container_width=True)
                except Exception:
                    st.error("Failed to load collage")

                if st.button("Delete Collage", key="del_collage"):
                    with st.spinner("Deleting..."):
                        UserService.delete_image(current_collage)
                        if UserService.update_user_images(user_id, collage_images=[]):
                            UserService.get_user_by_id.clear()
                            st.session_state.profile_360_user = UserService.get_user_by_id(user_id)
                            st.rerun()
        else:
            st.info("No collage image")

        # Instagram Images (read-only)
        instagram_images = user.get('instagram_images') or []
        if instagram_images:
            st.markdown("---")
            st.markdown(f"#### Instagram Images ({len(instagram_images)})")
            cols = st.columns(4)
            for idx, url in enumerate(instagram_images[:8]):
                with cols[idx % 4]:
                    try:
                        st.image(url, use_container_width=True)
                    except Exception:
                        pass


    # --- Matches Tab ---
    with tab_matches:
        with st.spinner("Loading matches..."):
            outbound, inbound = MatchService.get_user_matches(user_id)

        # Summary metrics
        metric_cols = st.columns(4)
        with metric_cols[0]:
            st.metric("Outbound", len(outbound))
        with metric_cols[1]:
            st.metric("Inbound", len(inbound))
        with metric_cols[2]:
            mutual_out = sum(1 for m in outbound if m.get('is_mutual'))
            st.metric("Mutual", mutual_out)
        with metric_cols[3]:
            liked_out = sum(1 for m in outbound if m.get('is_liked'))
            st.metric("Liked", liked_out)

        st.markdown("---")

        # Match tabs
        match_tab_out, match_tab_in = st.tabs(["Outbound Matches", "Inbound Matches"])

        with match_tab_out:
            if outbound:
                # Get matched user info
                matched_ids = tuple(m.get('matched_user_id') for m in outbound if m.get('matched_user_id'))
                matched_users = UserService.get_users_batch(matched_ids)

                for match in outbound[:20]:
                    matched_id = match.get('matched_user_id')
                    matched_user = matched_users.get(matched_id, {})

                    col1, col2, col3 = st.columns([2, 2, 1])

                    with col1:
                        matched_name = matched_user.get('name', 'Unknown')
                        matched_age = matched_user.get('age', '')
                        st.markdown(f"**{matched_name}**, {matched_age}")
                        st.caption(f"{matched_user.get('city', 'N/A')}")

                    with col2:
                        is_liked = "Liked" if match.get('is_liked') else "Not Liked"
                        is_mutual = "Mutual" if match.get('is_mutual') else ""
                        is_viewed = "Viewed" if match.get('is_viewed') else "Not Viewed"
                        st.caption(f"{is_liked} | {is_mutual} | {is_viewed}")
                        st.caption(f"Score: {match.get('mutual_score', 'N/A')}")

                    with col3:
                        if st.button("View", key=f"view_out_{matched_id}"):
                            full_user = UserService.get_user_by_id(matched_id)
                            if full_user:
                                st.session_state.profile_360_user = full_user
                                st.rerun()

                    st.markdown("---")
            else:
                st.info("No outbound matches")

        with match_tab_in:
            if inbound:
                # Get current user info
                current_ids = tuple(m.get('current_user_id') for m in inbound if m.get('current_user_id'))
                current_users = UserService.get_users_batch(current_ids)

                for match in inbound[:20]:
                    current_id = match.get('current_user_id')
                    current_user = current_users.get(current_id, {})

                    col1, col2, col3 = st.columns([2, 2, 1])

                    with col1:
                        current_name = current_user.get('name', 'Unknown')
                        current_age = current_user.get('age', '')
                        st.markdown(f"**{current_name}**, {current_age}")
                        st.caption(f"{current_user.get('city', 'N/A')}")

                    with col2:
                        is_liked = "Liked" if match.get('is_liked') else "Not Liked"
                        is_mutual = "Mutual" if match.get('is_mutual') else ""
                        is_viewed = "Viewed" if match.get('is_viewed') else "Not Viewed"
                        st.caption(f"{is_liked} | {is_mutual} | {is_viewed}")
                        st.caption(f"Score: {match.get('mutual_score', 'N/A')}")

                    with col3:
                        if st.button("View", key=f"view_in_{current_id}"):
                            full_user = UserService.get_user_by_id(current_id)
                            if full_user:
                                st.session_state.profile_360_user = full_user
                                st.rerun()

                    st.markdown("---")
            else:
                st.info("No inbound matches")


    # --- Chats Tab ---
    with tab_chats:
        chat_type = st.radio(
            "Chat Type",
            options=['onboarding', 'search'],
            format_func=lambda x: 'Onboarding' if x == 'onboarding' else 'Search',
            horizontal=True
        )

        with st.spinner(f"Loading {chat_type} chats..."):
            sessions, messages = fetch_user_chats(user_id, chat_type)

        if not sessions:
            st.info(f"No {chat_type} chat sessions found")
        else:
            st.success(f"Found {len(sessions)} session(s)")

            for idx, session in enumerate(sessions[:10]):
                session_id = session['id']
                session_created = session.get('created_at', 'Unknown')
                session_summary = session.get('summary', '')

                session_messages = [msg for msg in messages if msg['session_id'] == session_id]

                with st.expander(
                    f"Session: {session_created[:19] if session_created else 'Unknown'} | {len(session_messages)} messages",
                    expanded=(idx == 0)
                ):
                    if session_summary:
                        st.info(f"Summary: {session_summary}")

                    if not session_messages:
                        st.warning("No messages in this session")
                    else:
                        for msg in session_messages:
                            role = msg.get('role', 'unknown')
                            content = msg.get('message', '')
                            image_urls = msg.get('image_urls', [])
                            msg_time = msg.get('created_at', '')[:16] if msg.get('created_at') else ''

                            with st.chat_message(name=role):
                                st.markdown(content)

                                # Show images
                                if image_urls and isinstance(image_urls, list):
                                    img_cols = st.columns(min(len(image_urls), 3))
                                    for img_idx, img_url in enumerate(image_urls):
                                        with img_cols[img_idx % 3]:
                                            try:
                                                st.image(img_url, use_container_width=True)
                                            except Exception:
                                                pass

                                # Show time
                                if msg_time:
                                    st.caption(msg_time[11:16])


else:
    st.info("Search for a user by name, email, or user_id to view their complete profile.")
