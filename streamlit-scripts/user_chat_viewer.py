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

try:
    from dependencies import get_supabase_client
except ImportError:
    st.error("Error: 'dependencies.py' not found.")
    st.stop()

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
st.caption("Search users and view their onboarding chat messages")

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
def fetch_onboarding_chats(user_id: str):
    """Fetch onboarding chat sessions and messages for a user."""
    sessions = []
    messages = []
    try:
        # Fetch only onboarding chat sessions
        session_res = supabase.table('chat_sessions').select('*').eq('user_id', user_id).eq('chat_type', 'onboarding').order('created_at', desc=True).execute()
        sessions = session_res.data if session_res.data else []

        if sessions:
            session_ids = [s['id'] for s in sessions]
            message_res = supabase.table('chat_messages').select('*').in_('session_id', session_ids).order('created_at', desc=False).execute()
            messages = message_res.data if message_res.data else []
    except Exception as e:
        st.error(f"Error fetching chat data: {e}")

    return sessions, messages

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

# Apply filters
filtered_df = df_users.copy()

if search_query:
    search_lower = search_query.lower()
    filtered_df = filtered_df[
        filtered_df['name'].fillna('').str.lower().str.contains(search_lower) |
        filtered_df['email'].fillna('').str.lower().str.contains(search_lower)
    ]

if selected_gender != 'All':
    filtered_df = filtered_df[filtered_df['gender'] == selected_gender]

# --- Main Content ---
col1, col2 = st.columns([1, 2])

# Left column: User list
with col1:
    st.subheader(f"Users ({len(filtered_df)})")

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
    st.subheader("Onboarding Chat Messages")

    if not selected_user_id:
        st.info("Select a user from the list to view their onboarding chats.")
    else:
        # Get selected user info
        selected_user = filtered_df[filtered_df['user_id'] == selected_user_id].iloc[0]

        st.markdown(f"**Name:** {selected_user['name'] or 'N/A'}")
        st.markdown(f"**Email:** {selected_user['email'] or 'N/A'}")
        st.markdown(f"**Gender:** {selected_user['gender'] or 'N/A'}")
        st.divider()

        # Fetch chat data
        with st.spinner("Loading chat messages..."):
            sessions, messages = fetch_onboarding_chats(selected_user_id)

        if not sessions:
            st.info("No onboarding chat sessions found for this user.")
        else:
            st.success(f"Found {len(sessions)} onboarding session(s)")

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
                        for msg in session_messages:
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

                                # Show metadata if present and non-empty
                                if msg_metadata and msg_metadata != {}:
                                    with st.expander("View Message Metadata"):
                                        st.json(msg_metadata)

# Footer
st.divider()
st.caption("User Chat Viewer - Onboarding Conversations")
