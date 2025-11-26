import streamlit as st
import pandas as pd
import os
import sys
from dotenv import load_dotenv

# Configuration
st.set_page_config(page_title="User Chat Viewer", layout="wide")

# Setup paths
current_dir = os.path.dirname(__file__)
parent_dir = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.insert(0, parent_dir)
sys.path.insert(0, current_dir)

try:
    from dependencies import get_supabase_client
except ImportError:
    st.error("Error: 'dependencies.py' not found.")
    st.stop()

# Import components
try:
    from components import (
        render_profile_batch_readonly,
        render_profile_drawer,
        render_intro_confirmation_readonly
    )
except ImportError as e:
    st.warning(f"Components not loaded: {e}")
    render_profile_batch_readonly = None
    render_profile_drawer = None
    render_intro_confirmation_readonly = None

# Load environment
dotenv_path = os.path.join(parent_dir, '.env')
load_dotenv(dotenv_path)

try:
    supabase = get_supabase_client()
    st.sidebar.success("Supabase connected!")
except Exception as e:
    st.sidebar.error(f"Supabase connection failed: {e}")
    st.stop()

# Title
st.title("User Chat Viewer")
st.caption("Search users and view their chat messages")

# --- Data Fetching Functions ---

@st.cache_data(ttl=60)
def fetch_all_users():
    """Fetch users from user_metadata (name, gender) and user_data (email).
    Only returns users whose user_id exists in user_metadata.
    """
    try:
        # Fetch from user_metadata (name, gender)
        metadata_res = supabase.table('user_metadata').select('user_id, name, gender').execute()
        metadata_list = metadata_res.data if metadata_res.data else []

        if not metadata_list:
            return []

        # Get all user_ids from metadata
        user_ids = [u['user_id'] for u in metadata_list]

        # Fetch emails from user_data for these user_ids
        user_data_res = supabase.table('user_data').select('user_id, user_email').in_('user_id', user_ids).execute()
        user_data_list = user_data_res.data if user_data_res.data else []

        # Create email lookup map
        email_map = {u['user_id']: u['user_email'] for u in user_data_list}

        # Merge data
        users = []
        for user in metadata_list:
            users.append({
                'user_id': user['user_id'],
                'name': user.get('name'),
                'gender': user.get('gender'),
                'email': email_map.get(user['user_id'])
            })

        return users
    except Exception as e:
        st.error(f"Error fetching users: {e}")
        return []

@st.cache_data(ttl=30)
def fetch_chats_by_type(user_id: str, chat_type: str):
    """Fetch chat sessions and messages for a user by chat type."""
    sessions = []
    messages = []
    try:
        # Fetch chat sessions by type
        session_res = supabase.table('chat_sessions').select('*').eq('user_id', user_id).eq('chat_type', chat_type).order('created_at', desc=True).execute()
        sessions = session_res.data if session_res.data else []

        if sessions:
            session_ids = [s['id'] for s in sessions]
            message_res = supabase.table('chat_messages').select('*').in_('session_id', session_ids).order('created_at', desc=False).execute()
            messages = message_res.data if message_res.data else []
    except Exception as e:
        st.error(f"Error fetching chat data: {e}")

    return sessions, messages

@st.cache_data(ttl=60)
def fetch_users_with_chat_type(chat_type: str):
    """Fetch user_ids that have at least one session of the given chat_type."""
    try:
        # Get distinct user_ids from chat_sessions with the given chat_type
        res = supabase.table('chat_sessions').select('user_id').eq('chat_type', chat_type).execute()
        if res.data:
            return list(set([s['user_id'] for s in res.data]))
        return []
    except Exception as e:
        st.error(f"Error fetching users with {chat_type} chats: {e}")
        return []


def render_search_message_metadata(metadata: dict, msg_type: str, key_prefix: str):
    """
    Render special components for search chat messages based on metadata.

    Args:
        metadata: Message metadata dict
        msg_type: Message type (e.g., 'text', 'profile_batch', 'intro_confirmation')
        key_prefix: Unique key prefix for components
    """
    # Check for profiles in metadata (ProfileBatch)
    profiles = metadata.get('profiles', [])
    if profiles and len(profiles) > 0:
        st.divider()
        if render_profile_batch_readonly:
            render_profile_batch_readonly(profiles, batch_id=key_prefix)
        else:
            # Fallback: show profiles as cards
            st.caption(f"🔍 {len(profiles)} profiles")
            cols = st.columns(min(len(profiles), 3))
            for p_idx, profile in enumerate(profiles):
                with cols[p_idx % 3]:
                    p_meta = profile.get('metadata', profile)
                    name = p_meta.get('name', 'Unknown')
                    age = p_meta.get('age', '?')
                    location = p_meta.get('location', '')

                    # Image
                    img = p_meta.get('collage_image')
                    if isinstance(img, list) and img:
                        img = img[0]
                    if img:
                        try:
                            st.image(img, use_container_width=True)
                        except:
                            pass

                    st.markdown(f"**{name}, {age}**")
                    if location:
                        st.caption(f"📍 {location}")

                    # Expander for details
                    with st.expander("Details"):
                        st.json(p_meta)

    # Check for intro confirmation in metadata
    intro_message = metadata.get('intro_message') or metadata.get('message')
    intro_profile = metadata.get('intro_profile') or metadata.get('profile')
    selected_button = metadata.get('selected_button') or metadata.get('user_choice')

    if intro_profile:
        st.divider()
        if render_intro_confirmation_readonly:
            render_intro_confirmation_readonly(
                message=intro_message or "Would you like to connect?",
                profile=intro_profile,
                selected_button=selected_button
            )
        else:
            # Fallback
            st.markdown(intro_message or "Would you like to connect?")
            p_name = intro_profile.get('name', 'Unknown')
            p_age = intro_profile.get('age', '?')
            st.markdown(f"**{p_name}, {p_age}**")

            if selected_button == 'yes':
                st.success("✓ User selected: Yes")
            elif selected_button == 'no':
                st.error("User selected: No")

    # Check for single profile view
    single_profile = metadata.get('profile_detail') or metadata.get('selected_profile')
    if single_profile and render_profile_drawer:
        st.divider()
        with st.expander("📋 Profile Details", expanded=False):
            render_profile_drawer(single_profile)

    # Show raw metadata option (for debugging/inspection)
    if metadata and (not profiles) and (not intro_profile) and (not single_profile):
        with st.expander("View Raw Metadata"):
            st.json(metadata)


# --- Load Users ---
with st.spinner("Loading users..."):
    all_users = fetch_all_users()

if not all_users:
    st.warning("No users found in the database.")
    st.stop()

# Convert to DataFrame
df_users = pd.DataFrame(all_users)

# --- Sidebar: Filters & Search ---
st.sidebar.header("Search & Filter")

# Search bar
search_query = st.sidebar.text_input("Search by name or email:", placeholder="Type to search...")

# Gender filter
gender_options = ['All'] + sorted([g for g in df_users['gender'].dropna().unique() if g])
selected_gender = st.sidebar.selectbox("Filter by gender:", gender_options)

# Chat type selector
st.sidebar.divider()
st.sidebar.header("Chat Type")
chat_type = st.sidebar.radio(
    "Select chat type:",
    options=['onboarding', 'search'],
    format_func=lambda x: '🎯 Onboarding' if x == 'onboarding' else '🔍 Search',
    horizontal=True
)

# Apply filters
filtered_df = df_users.copy()

# Filter by chat type - only show users who have chats of the selected type
with st.spinner(f"Filtering users with {chat_type} chats..."):
    users_with_chat_type = fetch_users_with_chat_type(chat_type)

if users_with_chat_type:
    filtered_df = filtered_df[filtered_df['user_id'].isin(users_with_chat_type)]
else:
    filtered_df = pd.DataFrame()  # Empty if no users have this chat type

if not filtered_df.empty and search_query:
    search_lower = search_query.lower()
    filtered_df = filtered_df[
        filtered_df['name'].fillna('').str.lower().str.contains(search_lower) |
        filtered_df['email'].fillna('').str.lower().str.contains(search_lower)
    ]

if not filtered_df.empty and selected_gender != 'All':
    filtered_df = filtered_df[filtered_df['gender'] == selected_gender]

# --- Main Content ---
col1, col2 = st.columns([1, 2])

# Left column: User list
with col1:
    chat_type_label = "Onboarding" if chat_type == "onboarding" else "Search"
    st.subheader(f"Users with {chat_type_label} Chats ({len(filtered_df)})")

    if filtered_df.empty:
        st.info("No users match your search criteria.")
        selected_user_id = None
    else:
        # Create display dataframe without user_id
        display_df = filtered_df[['name', 'email', 'gender']].copy()
        display_df.index = range(1, len(display_df) + 1)

        # Show user list
        st.dataframe(
            display_df,
            use_container_width=True,
            height=400
        )

        # User selection dropdown (using name + email for display)
        filtered_df['display_label'] = filtered_df.apply(
            lambda r: f"{r['name'] or 'No Name'} ({r['email'] or 'No Email'})",
            axis=1
        )

        # Create mapping of display label to user_id
        label_to_id = dict(zip(filtered_df['display_label'], filtered_df['user_id']))

        selected_label = st.selectbox(
            "Select a user to view chats:",
            options=[''] + list(filtered_df['display_label']),
            index=0,
            placeholder="Choose a user..."
        )

        selected_user_id = label_to_id.get(selected_label) if selected_label else None

# Right column: Chat messages
with col2:
    chat_type_display = "Onboarding" if chat_type == "onboarding" else "Search"
    st.subheader(f"{chat_type_display} Chat Messages")

    if not selected_user_id:
        st.info(f"Select a user from the list to view their {chat_type} chats.")
    else:
        # Get selected user info
        selected_user = filtered_df[filtered_df['user_id'] == selected_user_id].iloc[0]

        st.markdown(f"**Name:** {selected_user['name'] or 'N/A'}")
        st.markdown(f"**Email:** {selected_user['email'] or 'N/A'}")
        st.markdown(f"**Gender:** {selected_user['gender'] or 'N/A'}")
        st.divider()

        # Fetch chat data based on selected type
        with st.spinner(f"Loading {chat_type} chat messages..."):
            sessions, messages = fetch_chats_by_type(selected_user_id, chat_type)

        if not sessions:
            st.info(f"No {chat_type} chat sessions found for this user.")
        else:
            st.success(f"Found {len(sessions)} {chat_type} session(s)")

            # Sort sessions by created_at (most recent first)
            sorted_sessions = sorted(sessions, key=lambda s: s['created_at'], reverse=True)

            for idx, session in enumerate(sorted_sessions):
                session_id = session['id']
                session_created = session.get('created_at', 'Unknown')
                session_summary = session.get('summary', '')
                has_summary = session.get('has_summary', False)

                # Get messages for this session
                session_messages = [msg for msg in messages if msg['session_id'] == session_id]

                with st.expander(
                    f"Session: {session_created[:19] if session_created else 'Unknown'} | {len(session_messages)} messages",
                    expanded=(idx == 0)  # Expand first session by default
                ):
                    if has_summary and session_summary:
                        st.info(f"Summary: {session_summary}")

                    if not session_messages:
                        st.warning("No messages in this session.")
                    else:
                        for msg_idx, msg in enumerate(session_messages):
                            role = msg.get('role', 'unknown')
                            content = msg.get('message', '')
                            image_urls = msg.get('image_urls', [])
                            msg_metadata = msg.get('metadata', {})
                            msg_type = msg.get('message_type', 'text')

                            with st.chat_message(name=role):
                                st.markdown(content)

                                # Show images if present
                                if image_urls and isinstance(image_urls, list):
                                    img_cols = st.columns(min(len(image_urls), 3))
                                    for img_idx, img_url in enumerate(image_urls):
                                        with img_cols[img_idx % 3]:
                                            try:
                                                st.image(img_url, use_container_width=True)
                                            except Exception:
                                                st.error("Failed to load image")

                                # Handle special message types for search chats
                                if chat_type == 'search' and msg_metadata:
                                    render_search_message_metadata(
                                        msg_metadata,
                                        msg_type,
                                        key_prefix=f"s{idx}_m{msg_idx}"
                                    )
                                elif msg_metadata and msg_metadata != {}:
                                    # Show raw metadata for onboarding chats
                                    with st.expander("View Message Metadata"):
                                        st.json(msg_metadata)


# Footer
st.divider()
st.caption("User Chat Viewer - View Onboarding & Search Conversations")
