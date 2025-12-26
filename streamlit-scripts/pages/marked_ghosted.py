"""
Marked Ghosted - Search users and mark them as ghosted
"""
import streamlit as st
import os
import sys
from datetime import datetime
import pytz
from dotenv import load_dotenv

# Setup paths
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

try:
    supabase = get_supabase_client()
except Exception as e:
    st.error(f"Supabase connection failed: {e}")
    st.stop()

# Custom CSS
st.markdown("""
<style>
@keyframes slideIn {
    from {
        opacity: 0;
        transform: translateY(-10px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.ghost-card {
    animation: slideIn 0.3s ease-out;
    padding: 16px;
    margin: 8px 0;
    background-color: #2d2d2d;
    border-radius: 10px;
    border-left: 4px solid #ff9800;
}

.ghost-card-ghosted {
    border-left-color: #f44336;
}

.user-name {
    font-size: 1.2em;
    font-weight: 600;
    color: #ffffff;
}

.user-info {
    color: #b0b0b0;
    font-size: 0.9em;
    margin-top: 4px;
}

.ghost-badge {
    display: inline-block;
    background-color: #f44336;
    color: white;
    padding: 4px 12px;
    border-radius: 16px;
    font-size: 0.85em;
    font-weight: 500;
    margin-left: 8px;
}

.ghosted-list-item {
    padding: 12px 16px;
    margin: 6px 0;
    background-color: #1e1e1e;
    border-radius: 8px;
    border-left: 4px solid #f44336;
}

.ghosted-date {
    color: #888;
    font-size: 0.8em;
}
</style>
""", unsafe_allow_html=True)

# Title
st.title("Marked Ghosted")
st.caption("Search users by name or ID and mark them as ghosted")

# --- Data Fetching Functions ---

def search_users(query: str):
    """Search users by name or user_id."""
    try:
        query = query.strip()
        if not query:
            return []

        # Search by user_id (exact match)
        res_id = supabase.table('user_metadata').select(
            'user_id, name, gender, age, city, profile_images, ghost_status'
        ).eq('user_id', query).execute()

        if res_id.data:
            return res_id.data

        # Search by name (case-insensitive, partial match)
        res_name = supabase.table('user_metadata').select(
            'user_id, name, gender, age, city, profile_images, ghost_status'
        ).ilike('name', f'%{query}%').limit(20).execute()

        return res_name.data if res_name.data else []
    except Exception as e:
        st.error(f"Error searching users: {e}")
        return []


def fetch_ghosted_users():
    """Fetch all users marked as ghosted."""
    try:
        # Fetch users where ghost_status has is_ghost = true
        res = supabase.table('user_metadata').select(
            'user_id, name, gender, age, city, ghost_status'
        ).neq('ghost_status', {}).execute()

        if not res.data:
            return []

        # Filter to only include users where is_ghost is true
        ghosted = [
            u for u in res.data
            if u.get('ghost_status') and u['ghost_status'].get('is_ghost') == True
        ]

        # Sort by ghosted_at date (most recent first)
        ghosted.sort(
            key=lambda x: x.get('ghost_status', {}).get('ghosted_at', ''),
            reverse=True
        )

        return ghosted
    except Exception as e:
        st.error(f"Error fetching ghosted users: {e}")
        return []


def mark_user_as_ghost(user_id: str, reason: str = "no_response_after_match"):
    """Mark a user as ghosted."""
    try:
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist).isoformat()

        ghost_status = {
            "is_ghost": True,
            "ghosted_at": now,
            "reason": reason
        }

        supabase.table('user_metadata').update(
            {'ghost_status': ghost_status}
        ).eq('user_id', user_id).execute()

        return True
    except Exception as e:
        st.error(f"Error marking user as ghost: {e}")
        return False


def unmark_user_as_ghost(user_id: str):
    """Remove ghost status from a user."""
    try:
        supabase.table('user_metadata').update(
            {'ghost_status': {}}
        ).eq('user_id', user_id).execute()

        return True
    except Exception as e:
        st.error(f"Error unmarking ghost status: {e}")
        return False


# --- Session State ---
if 'ghost_search_query' not in st.session_state:
    st.session_state.ghost_search_query = ""
if 'ghost_search_results' not in st.session_state:
    st.session_state.ghost_search_results = []

# --- Search Section ---
st.subheader("Search User")

col_search, col_btn = st.columns([4, 1])

with col_search:
    search_input = st.text_input(
        "Search by name or user ID",
        placeholder="Enter name or user_id...",
        key="ghost_search_input",
        label_visibility="collapsed"
    )

with col_btn:
    search_clicked = st.button("Search", type="primary", use_container_width=True)

if search_clicked and search_input:
    st.session_state.ghost_search_query = search_input
    st.session_state.ghost_search_results = search_users(search_input)

# --- Search Results ---
if st.session_state.ghost_search_results:
    st.markdown("---")
    st.subheader(f"Search Results ({len(st.session_state.ghost_search_results)})")

    for user in st.session_state.ghost_search_results:
        user_id = user.get('user_id')
        name = user.get('name') or 'Unknown'
        gender = user.get('gender') or 'N/A'
        age = user.get('age') or 'N/A'
        city = user.get('city') or 'N/A'
        ghost_status = user.get('ghost_status') or {}
        is_ghosted = ghost_status.get('is_ghost', False)

        card_class = "ghost-card ghost-card-ghosted" if is_ghosted else "ghost-card"

        with st.container():
            col1, col2, col3 = st.columns([1, 3, 2])

            # Profile image
            with col1:
                profile_images = user.get('profile_images') or []
                if profile_images:
                    try:
                        st.image(profile_images[0], width=80)
                    except:
                        st.markdown("📷")
                else:
                    st.markdown("📷")

            # User info
            with col2:
                ghost_badge = '<span class="ghost-badge">GHOSTED</span>' if is_ghosted else ''
                st.markdown(
                    f'<div class="user-name">{name}{ghost_badge}</div>',
                    unsafe_allow_html=True
                )
                st.markdown(
                    f'<div class="user-info">{gender} • {age} yrs • {city}</div>',
                    unsafe_allow_html=True
                )
                st.caption(f"ID: {user_id}")

                if is_ghosted:
                    ghosted_at = ghost_status.get('ghosted_at', 'N/A')
                    reason = ghost_status.get('reason', 'N/A')
                    if ghosted_at != 'N/A':
                        try:
                            dt = datetime.fromisoformat(ghosted_at)
                            ghosted_at = dt.strftime('%d %b %Y, %I:%M %p')
                        except:
                            pass
                    st.markdown(f'<div class="ghosted-date">Ghosted: {ghosted_at} | Reason: {reason}</div>', unsafe_allow_html=True)

            # Action button
            with col3:
                if is_ghosted:
                    if st.button("Remove Ghost Status", key=f"unghost_{user_id}", type="secondary"):
                        if unmark_user_as_ghost(user_id):
                            st.success(f"Removed ghost status from {name}")
                            st.session_state.ghost_search_results = search_users(st.session_state.ghost_search_query)
                            st.rerun()
                else:
                    # Reason selector
                    reason = st.selectbox(
                        "Reason",
                        options=[
                            "no_response_after_match",
                            "stopped_replying",
                            "unresponsive",
                            "other"
                        ],
                        key=f"reason_{user_id}",
                        label_visibility="collapsed"
                    )
                    if st.button("Mark as Ghost", key=f"ghost_{user_id}", type="primary"):
                        if mark_user_as_ghost(user_id, reason):
                            st.warning(f"Marked {name} as ghosted")
                            st.session_state.ghost_search_results = search_users(st.session_state.ghost_search_query)
                            st.rerun()

            st.markdown("---")

elif st.session_state.ghost_search_query and not st.session_state.ghost_search_results:
    st.info("No users found matching your search.")

# --- Ghosted Users List ---
st.markdown("---")
st.subheader("Ghosted Users")

ghosted_users = fetch_ghosted_users()

if ghosted_users:
    st.markdown(f"**{len(ghosted_users)} user(s) marked as ghosted**")

    for user in ghosted_users:
        user_id = user.get('user_id')
        name = user.get('name') or 'Unknown'
        gender = user.get('gender') or 'N/A'
        age = user.get('age') or 'N/A'
        city = user.get('city') or 'N/A'
        ghost_status = user.get('ghost_status', {})
        ghosted_at = ghost_status.get('ghosted_at', 'N/A')
        reason = ghost_status.get('reason', 'N/A')

        # Format date
        if ghosted_at != 'N/A':
            try:
                dt = datetime.fromisoformat(ghosted_at)
                ghosted_at = dt.strftime('%d %b %Y, %I:%M %p')
            except:
                pass

        with st.expander(f"{name} - {city}", expanded=False):
            col1, col2 = st.columns([3, 1])

            with col1:
                st.markdown(f"**User ID:** {user_id}")
                st.markdown(f"**Gender:** {gender} | **Age:** {age}")
                st.markdown(f"**City:** {city}")
                st.markdown(f"**Ghosted At:** {ghosted_at}")
                st.markdown(f"**Reason:** {reason}")

            with col2:
                if st.button("Remove Ghost Status", key=f"list_unghost_{user_id}"):
                    if unmark_user_as_ghost(user_id):
                        st.success(f"Removed ghost status from {name}")
                        st.rerun()
else:
    st.info("No users marked as ghosted yet.")
