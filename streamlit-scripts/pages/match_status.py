"""
Match Status - View the journey of user matches through the system.
"""
import streamlit as st
import os
import sys
from datetime import datetime, date
from dotenv import load_dotenv

# Setup paths (pages folder ke andar se 2 levels up)
current_dir = os.path.dirname(__file__)
scripts_dir = os.path.abspath(os.path.join(current_dir, '..'))
parent_dir = os.path.abspath(os.path.join(scripts_dir, '..'))
sys.path.insert(0, parent_dir)
sys.path.insert(0, scripts_dir)

try:
    from dependencies import get_supabase_client
except ImportError:
    st.error("Error: 'dependencies.py' not found.")
    st.stop()

# Load environment
dotenv_path = os.path.join(parent_dir, '.env')
load_dotenv(dotenv_path)

# --- Supabase Connection ---
try:
    supabase = get_supabase_client()
except Exception as e:
    st.error(f"Supabase connection failed: {e}")
    st.stop()

# --- Status Stage Definitions ---
STAGE_LABELS = [
    "Created",
    "Awaiting Approval",
    "Approved",
    "Notified",
    "Both Yes",
    "Connected"
]


# --- Data Fetching Functions ---
@st.cache_data(ttl=30)
def fetch_all_profiles():
    """Fetch all profiles from the profiles table."""
    try:
        res = supabase.table('profiles').select('*').order('created_at', desc=True).execute()
        return res.data if res.data else []
    except Exception as e:
        st.error(f"Error fetching profiles: {e}")
        return []


@st.cache_data(ttl=30)
def fetch_user_metadata(user_id: str):
    """Fetch user metadata for display."""
    try:
        res = supabase.table('user_metadata').select(
            'user_id, name, age, height, religion, city, work_exp, education, '
            'profile_images, instagram_images, dating_preferences, gender'
        ).eq('user_id', user_id).maybe_single().execute()
        return res.data if res.data else {}
    except Exception as e:
        st.warning(f"Error fetching user {user_id}: {e}")
        return {}


@st.cache_data(ttl=30)
def fetch_user_data(user_id: str):
    """Fetch user data (email, phone) from user_data table."""
    try:
        res = supabase.table('user_data').select(
            'user_id, user_email, user_phone'
        ).eq('user_id', user_id).maybe_single().execute()
        return res.data if res.data else {}
    except Exception as e:
        st.warning(f"Error fetching user data {user_id}: {e}")
        return {}


def get_user_name(user_id: str) -> str:
    """Get user name from metadata."""
    meta = fetch_user_metadata(user_id)
    return meta.get('name', 'Unknown') if meta else 'Unknown'


@st.cache_data(ttl=30)
def fetch_search_chat(user_id: str):
    """Fetch search chat sessions and messages for a user."""
    sessions = []
    messages = []
    try:
        session_res = supabase.table('chat_sessions').select('*').eq(
            'user_id', user_id
        ).eq('chat_type', 'search').order('created_at', desc=True).execute()
        sessions = session_res.data if session_res.data else []

        if sessions:
            session_ids = [s['id'] for s in sessions]
            message_res = supabase.table('chat_messages').select('*').in_(
                'session_id', session_ids
            ).order('created_at', desc=False).execute()
            messages = message_res.data if message_res.data else []
    except Exception as e:
        st.error(f"Error fetching chat data: {e}")

    return sessions, messages


# --- Helper Functions ---
def get_stage_index(profile: dict) -> int:
    """Return stage index (0-5) based on profile_status."""
    status = profile.get('profile_status', '')

    # Stage 5: Connected (both yes and processed)
    if 'female_yes-male_yes_msg_match' in status:
        return 5

    # Stage 4: Both Yes (waiting for final processing)
    if 'female_yes-male_yes-msg_null' in status:
        return 4

    # Stage 3: Notified (message sent to one party)
    if 'msg_ms' in status or 'msg_fs' in status:
        return 3

    # Stage 2: Approved (human approved, waiting for temporal)
    if 'msg_human_approved' in status:
        return 2

    # Stage 1: Awaiting Approval
    if 'msg_human_approval_required' in status:
        return 1

    # Stage 0: Created (initial state)
    return 0


def is_rejected(profile: dict) -> bool:
    """Check if match was rejected after notification."""
    status = profile.get('profile_status', '')

    # Male rejected after female's profile was sent to him
    if 'msg_ms' in status and profile.get('male_response') is False:
        return True

    # Female rejected after male's profile was sent to her
    if 'msg_fs' in status and profile.get('female_response') is False:
        return True

    return False


def get_human_readable_status(profile: dict) -> str:
    """Convert profile status to human-readable text."""
    if is_rejected(profile):
        return "Rejected"

    stage = get_stage_index(profile)
    return STAGE_LABELS[stage]


def get_initiator_badge(profile: dict) -> str:
    """Return who initiated the match."""
    if profile.get('female_response'):
        return "Female"
    elif profile.get('male_response'):
        return "Male"
    return "Unknown"


def get_status_category(profile: dict) -> str:
    """Categorize profile for filtering."""
    if is_rejected(profile):
        return "Rejected"

    stage = get_stage_index(profile)
    if stage <= 2:
        return "Pending"
    elif stage <= 4:
        return "In Progress"
    else:
        return "Connected"


# --- UI Components ---
def render_mini_card(meta: dict, user_data: dict, user_id: str, color: str):
    """Render a horizontal profile card with photo on left, info on right."""
    if not meta:
        st.warning("No user data")
        return

    name = meta.get('name', 'Unknown')
    email = user_data.get('user_email', '-')
    phone = user_data.get('user_phone', '-')

    # Get first photo
    photos = meta.get('profile_images') or meta.get('instagram_images') or []
    photo_url = photos[0] if photos and isinstance(photos, list) else None

    border_color = "#9333ea" if color == "purple" else "#3b82f6"  # purple or blue

    st.markdown(f"""
    <div style="
        border: 2px solid {border_color};
        border-radius: 12px;
        padding: 16px;
        background: #1e1e1e;
        display: flex;
        align-items: center;
        gap: 16px;
    ">
        <div style="
            width: 80px;
            height: 80px;
            min-width: 80px;
            border-radius: 50%;
            overflow: hidden;
            background: #374151;
        ">
            {'<img src="' + photo_url + '" style="width:100%;height:100%;object-fit:cover;">' if photo_url else '<div style="padding-top:30px;color:#9ca3af;text-align:center;">No Photo</div>'}
        </div>
        <div style="flex: 1; min-width: 0;">
            <div style="font-weight: 600; font-size: 16px; margin-bottom: 6px; color: #ffffff;">{name}</div>
            <div style="font-size: 12px; color: #d1d5db; margin-bottom: 3px;">{email if email else '-'}</div>
            <div style="font-size: 12px; color: #d1d5db; margin-bottom: 3px;">{phone if phone else '-'}</div>
            <div style="font-size: 10px; color: #9ca3af; font-family: monospace; word-break: break-all;">{user_id}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_progress_bar(stage_index: int, rejected: bool = False):
    """Render a horizontal progress bar with 6 stages."""

    # Define colors
    completed_color = "#ef4444" if rejected else "#10b981"  # red if rejected, green otherwise
    current_color = "#ef4444" if rejected else "#3b82f6"  # red if rejected, blue otherwise
    pending_color = "#d1d5db"  # gray

    nodes = []
    for i, label in enumerate(STAGE_LABELS):
        if rejected and i == stage_index:
            node_color = "#ef4444"
            text_color = "#ef4444"
        elif i < stage_index:
            node_color = completed_color
            text_color = "#374151"
        elif i == stage_index:
            node_color = current_color
            text_color = current_color
        else:
            node_color = pending_color
            text_color = "#9ca3af"

        # Line before node (except first)
        if i > 0:
            line_color = completed_color if i <= stage_index else pending_color
            if rejected and i > stage_index:
                line_color = pending_color
            nodes.append(f'<div style="flex:1;height:3px;background:{line_color};margin-top:10px;"></div>')

        nodes.append(
            f'<div style="display:flex;flex-direction:column;align-items:center;min-width:60px;">'
            f'<div style="width:20px;height:20px;border-radius:50%;background:{node_color};"></div>'
            f'<div style="font-size:10px;color:{text_color};margin-top:4px;text-align:center;">{label}</div>'
            f'</div>'
        )

    html = '<div style="display:flex;align-items:flex-start;justify-content:center;padding:16px 0;">' + ''.join(nodes) + '</div>'
    st.markdown(html, unsafe_allow_html=True)


@st.dialog("Search Chat", width="large")
def show_search_chat_dialog(user_id: str, user_name: str):
    """Display search chat in a dialog popup."""
    st.subheader(f"Search Chat - {user_name}")
    st.caption(f"User ID: {user_id}")
    st.divider()

    sessions, messages = fetch_search_chat(user_id)

    if not sessions:
        st.info("No search chat sessions found for this user.")
        return

    st.success(f"Found {len(sessions)} search session(s)")

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
            expanded=(idx == 0)
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

                        # Show metadata if present
                        if msg_metadata and msg_metadata != {}:
                            with st.expander("View Message Metadata"):
                                st.json(msg_metadata)


# --- Initialize Session State ---
if 'match_status_selected' not in st.session_state:
    st.session_state.match_status_selected = None


# --- Fetch Data ---
all_profiles = fetch_all_profiles()


# --- Sidebar ---
st.sidebar.header("Filters")

status_filter = st.sidebar.selectbox(
    "Status",
    ["All", "Male Initiated", "Female Initiated", "Pending Human Approval", "Human Approved", "Notified", "Both Yes", "Connected", "Rejected"]
)

search_id = st.sidebar.text_input("Search by User ID")

date_filter = st.sidebar.date_input("Show matches after", value=date(2025, 12, 3))

st.sidebar.divider()

# Stats
st.sidebar.subheader("Statistics")
total_count = len(all_profiles)
pending_count = len([p for p in all_profiles if get_status_category(p) == "Pending"])
in_progress_count = len([p for p in all_profiles if get_status_category(p) == "In Progress"])
connected_count = len([p for p in all_profiles if get_status_category(p) == "Connected"])
rejected_count = len([p for p in all_profiles if is_rejected(p)])

st.sidebar.metric("Total", total_count)
col1, col2 = st.sidebar.columns(2)
with col1:
    st.metric("Pending", pending_count)
    st.metric("Connected", connected_count)
with col2:
    st.metric("In Progress", in_progress_count)
    st.metric("Rejected", rejected_count)


# --- Apply Filters ---
filtered_profiles = all_profiles

if status_filter != "All":
    if status_filter == "Rejected":
        filtered_profiles = [p for p in filtered_profiles if is_rejected(p)]
    elif status_filter == "Male Initiated":
        # Male said yes first (male_response = true)
        filtered_profiles = [p for p in filtered_profiles if p.get('male_response') == True and p.get('female_response') != True]
    elif status_filter == "Female Initiated":
        # Female said yes first (female_response = true)
        filtered_profiles = [p for p in filtered_profiles if p.get('female_response') == True and p.get('male_response') != True]
    elif status_filter == "Pending Human Approval":
        filtered_profiles = [p for p in filtered_profiles if 'msg_human_approval_required' in p.get('profile_status', '')]
    elif status_filter == "Human Approved":
        filtered_profiles = [p for p in filtered_profiles if 'msg_human_approved' in p.get('profile_status', '')]
    elif status_filter == "Notified":
        # Message sent to one party (msg_ms or msg_fs)
        filtered_profiles = [p for p in filtered_profiles if ('msg_ms' in p.get('profile_status', '') or 'msg_fs' in p.get('profile_status', '')) and not is_rejected(p)]
    elif status_filter == "Both Yes":
        filtered_profiles = [p for p in filtered_profiles if 'female_yes-male_yes' in p.get('profile_status', '') and 'msg_null' in p.get('profile_status', '')]
    elif status_filter == "Connected":
        filtered_profiles = [p for p in filtered_profiles if 'female_yes-male_yes' in p.get('profile_status', '') and 'msg_null' not in p.get('profile_status', '')]

if search_id:
    filtered_profiles = [
        p for p in filtered_profiles
        if search_id.lower() in p.get('female_user_id', '').lower()
        or search_id.lower() in p.get('male_user_id', '').lower()
    ]

if date_filter:
    filtered_profiles = [
        p for p in filtered_profiles
        if p.get('created_at') and datetime.fromisoformat(p['created_at'].replace('Z', '+00:00')).date() >= date_filter
    ]


# --- Filter Descriptions ---
FILTER_DESCRIPTIONS = {
    "All": "Showing all matches regardless of status",
    "Male Initiated": "Matches where the male liked the female first (male_response = true)",
    "Female Initiated": "Matches where the female liked the male first (female_response = true)",
    "Pending Human Approval": "Matches awaiting human review before profile is sent to the other party",
    "Human Approved": "Matches approved by human, waiting for Temporal to send the profile",
    "Notified": "Profile has been sent to one party, waiting for their response",
    "Both Yes": "Both users said yes, waiting for final connection processing",
    "Connected": "Successfully connected matches - both users have been notified",
    "Rejected": "Matches where one party rejected after seeing the profile",
}

# --- Main Content ---
col_title, col_refresh = st.columns([4, 1])
with col_title:
    st.title("Match Status")
with col_refresh:
    if st.button("Refresh", use_container_width=True, type="primary"):
        st.cache_data.clear()
        st.rerun()

# Show filter description
if status_filter in FILTER_DESCRIPTIONS:
    st.info(f"**{status_filter}:** {FILTER_DESCRIPTIONS[status_filter]}")


# --- Top Section: Selected Match Details ---
if st.session_state.match_status_selected:
    selected = next(
        (p for p in all_profiles if p['profiles_id'] == st.session_state.match_status_selected),
        None
    )

    if selected:
        st.subheader("Match Details")

        # Who initiated badge
        initiator = get_initiator_badge(selected)
        badge_color = "#9333ea" if initiator == "Female" else "#3b82f6"
        st.markdown(f"""
        <div style="
            display:inline-block;
            padding:4px 12px;
            background:{badge_color};
            color:white;
            border-radius:12px;
            font-size:12px;
            margin-bottom:12px;
        ">
            Initiated by: {initiator}
        </div>
        """, unsafe_allow_html=True)

        # Two column layout: Female Card | Male Card
        col1, col2 = st.columns(2)

        with col1:
            f_meta = fetch_user_metadata(selected['female_user_id'])
            f_data = fetch_user_data(selected['female_user_id'])
            render_mini_card(f_meta, f_data, selected['female_user_id'], "purple")
            if st.button("🔍 Show Search Chat", key="chat_female", use_container_width=True):
                show_search_chat_dialog(
                    selected['female_user_id'],
                    f_meta.get('name', 'Unknown')
                )

        with col2:
            m_meta = fetch_user_metadata(selected['male_user_id'])
            m_data = fetch_user_data(selected['male_user_id'])
            render_mini_card(m_meta, m_data, selected['male_user_id'], "blue")
            if st.button("🔍 Show Search Chat", key="chat_male", use_container_width=True):
                show_search_chat_dialog(
                    selected['male_user_id'],
                    m_meta.get('name', 'Unknown')
                )

        # Progress bar below the cards
        st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
        render_progress_bar(get_stage_index(selected), is_rejected(selected))

        # Show rejection message if applicable
        if is_rejected(selected):
            st.error("This match was rejected")

        # Show "Go to Human Approval" button if status is awaiting approval
        if 'msg_human_approval_required' in selected.get('profile_status', ''):
            st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
            if st.button("Go to Human Approval", type="primary", use_container_width=True):
                # Store the profile ID to be selected on the Human Approval page
                st.session_state.human_approval_select_profile = selected['profiles_id']
                st.switch_page("pages/human_approval.py")

        st.divider()
    else:
        st.session_state.match_status_selected = None


# --- Bottom Section: Match List ---
st.subheader(f"Matches ({len(filtered_profiles)})")

if not filtered_profiles:
    st.info("No matches found with the current filters.")
else:
    for profile in filtered_profiles:
        f_name = get_user_name(profile['female_user_id'])
        m_name = get_user_name(profile['male_user_id'])
        status_text = get_human_readable_status(profile)
        created = profile.get('created_at', '')[:10] if profile.get('created_at') else ''
        initiator = get_initiator_badge(profile)
        is_selected = st.session_state.match_status_selected == profile['profiles_id']

        # Status color
        #
        if is_rejected(profile):
            status_color = "#ef4444"
        elif status_text == "Connected":
            status_color = "#10b981"
        else:
            status_color = "#6b7280"

        col1, col2, col3, col4, col5 = st.columns([2, 2, 1.5, 1.5, 1])

        with col1:
            st.markdown(f"**{f_name}**")
        with col2:
            st.markdown(f"**{m_name}**")
        with col3:
            st.markdown(f"<span style='color:{status_color};'>{status_text}</span>", unsafe_allow_html=True)
        with col4:
            st.caption(created)
        with col5:
            if st.button(
                "View" if not is_selected else "Selected",
                key=f"select_{profile['profiles_id']}",
                type="primary" if is_selected else "secondary",
                use_container_width=True
            ):
                st.session_state.match_status_selected = profile['profiles_id']
                st.rerun()

        st.divider()
