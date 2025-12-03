import streamlit as st
import os
import sys
from dotenv import load_dotenv

# Configuration
st.set_page_config(page_title="Waitlist Review", layout="wide")

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

# Load environment
dotenv_path = os.path.join(parent_dir, '.env')
load_dotenv(dotenv_path)

try:
    supabase = get_supabase_client()
    st.sidebar.success("Supabase connected!")
except Exception as e:
    st.sidebar.error(f"Supabase connection failed: {e}")
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

.user-card {
    animation: slideIn 0.3s ease-out;
    padding: 16px;
    margin: 8px 0;
    background-color: #1e1e1e;
    border-radius: 10px;
    border-left: 4px solid #4CAF50;
}

.user-card.removed {
    border-left-color: #ff6b6b;
    opacity: 0.7;
}

.stat-box {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 20px;
    border-radius: 10px;
    text-align: center;
    color: white;
}

.filter-section {
    background-color: #262626;
    padding: 15px;
    border-radius: 8px;
    margin-bottom: 20px;
}
</style>
""", unsafe_allow_html=True)

# Title
st.title("Waitlist Review")
st.caption("Review waitlist users and mark them for removal")

# --- Data Fetching Functions ---

@st.cache_data(ttl=60)
def fetch_all_waitlist_users():
    """Fetch all users from waitlist_metadata."""
    try:
        res = supabase.table('waitlist_metadata').select(
            'user_id, full_name, whatsapp_number, gender, city, area, '
            'relationship_type, relationship_why, interesting_fact, '
            'additional_context, should_be_removed, created_at, qualified, professional_tier'
        ).order('created_at', desc=True).execute()
        return res.data if res.data else []
    except Exception as e:
        st.error(f"Error fetching users: {e}")
        return []

def fetch_removed_count():
    """Fetch count of removed users."""
    try:
        res = supabase.table('waitlist_metadata').select(
            'user_id', count='exact'
        ).eq('should_be_removed', True).execute()
        return res.count if res.count else 0
    except Exception as e:
        return 0

def update_should_be_removed(user_id: str, value):
    """Update should_be_removed field for a user."""
    try:
        supabase.table('waitlist_metadata').update(
            {'should_be_removed': value}
        ).eq('user_id', user_id).execute()
        return True
    except Exception as e:
        st.error(f"Error updating user: {e}")
        return False

# --- Session State Initialization ---
if 'current_page' not in st.session_state:
    st.session_state.current_page = 1
if 'users_per_page' not in st.session_state:
    st.session_state.users_per_page = 10
if 'view_mode' not in st.session_state:
    st.session_state.view_mode = 'cards'  # 'cards' or 'detail'
if 'selected_user_id' not in st.session_state:
    st.session_state.selected_user_id = None

# --- Load Users ---
all_users = fetch_all_waitlist_users()

# --- Sidebar Stats ---
st.sidebar.header("Statistics")
st.sidebar.divider()

total_users = len(all_users)
removed_count = len([u for u in all_users if u.get('should_be_removed') == True])
female_count = len([u for u in all_users if u.get('gender', '').lower() == 'female'])
male_count = len([u for u in all_users if u.get('gender', '').lower() == 'male'])

st.sidebar.metric("Total Users", total_users)
st.sidebar.metric("Removed", removed_count)
st.sidebar.metric("Females", female_count)
st.sidebar.metric("Males", male_count)

st.sidebar.divider()

# --- Filters ---
st.sidebar.header("Filters")

# Gender filter
gender_filter = st.sidebar.radio(
    "Gender",
    ["All", "Females only", "Males only"],
    horizontal=True
)

# --- Apply Filters ---
filtered_users = all_users.copy()

if gender_filter == "Females only":
    filtered_users = [u for u in filtered_users if u.get('gender', '').lower() == 'female']
elif gender_filter == "Males only":
    filtered_users = [u for u in filtered_users if u.get('gender', '').lower() == 'male']

# --- Pagination ---
st.sidebar.divider()
st.sidebar.header("Pagination")
users_per_page = st.sidebar.selectbox(
    "Users per page",
    [5, 10, 20, 50],
    index=1
)
st.session_state.users_per_page = users_per_page

total_filtered = len(filtered_users)
total_pages = max(1, (total_filtered + users_per_page - 1) // users_per_page)

# Ensure current page is within bounds
if st.session_state.current_page > total_pages:
    st.session_state.current_page = total_pages

# Page selector
st.sidebar.number_input(
    f"Page (1-{total_pages})",
    min_value=1,
    max_value=total_pages,
    value=st.session_state.current_page,
    key='page_input',
    on_change=lambda: setattr(st.session_state, 'current_page', st.session_state.page_input)
)

# --- Clear Cache Button ---
st.sidebar.divider()
if st.sidebar.button("Refresh Data", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

# --- Main Content ---
st.divider()

# Results header
col_results, col_view = st.columns([3, 1])
with col_results:
    st.subheader(f"Showing {total_filtered} users (Page {st.session_state.current_page}/{total_pages})")

# Calculate slice for current page
start_idx = (st.session_state.current_page - 1) * users_per_page
end_idx = start_idx + users_per_page
page_users = filtered_users[start_idx:end_idx]

# --- Display Users ---
if not page_users:
    st.warning("No users found with current filters.")
else:
    for idx, user in enumerate(page_users):
        user_id = user.get('user_id')
        is_removed = user.get('should_be_removed') == True

        # Create expandable card for each user
        with st.expander(
            f"{'❌ ' if is_removed else ''}{user.get('full_name') or 'Unknown'} - {user.get('city') or 'N/A'} ({user.get('gender') or 'N/A'})",
            expanded=False
        ):
            # Action buttons at top
            col_action1, col_action2, col_spacer = st.columns([1, 1, 2])
            with col_action1:
                if is_removed:
                    if st.button("Undo Removal", key=f"undo_{user_id}", type="secondary"):
                        if update_should_be_removed(user_id, None):
                            st.success("Restored!")
                            st.cache_data.clear()
                            st.rerun()
                else:
                    if st.button("Remove", key=f"remove_{user_id}", type="primary"):
                        if update_should_be_removed(user_id, True):
                            st.warning("Marked for removal!")
                            st.cache_data.clear()
                            st.rerun()

            if is_removed:
                st.error("This user is marked for removal")

            st.divider()

            # User details in columns
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Basic Info**")
                st.markdown(f"- **Name:** {user.get('full_name') or 'N/A'}")
                st.markdown(f"- **WhatsApp:** {user.get('whatsapp_number') or 'N/A'}")
                st.markdown(f"- **Gender:** {user.get('gender') or 'N/A'}")
                st.markdown(f"- **City:** {user.get('city') or 'N/A'}")
                st.markdown(f"- **Area:** {user.get('area') or 'N/A'}")

            with col2:
                st.markdown("**Status**")
                tier = user.get('professional_tier')
                tier_display = f"Tier {tier}" if tier else "Not Set"
                qualified = user.get('qualified')
                qualified_display = "Yes" if qualified == True else ("No" if qualified == False else "Not Set")
                st.markdown(f"- **Professional Tier:** {tier_display}")
                st.markdown(f"- **Qualified:** {qualified_display}")
                st.markdown(f"- **Created:** {user.get('created_at', 'N/A')[:10] if user.get('created_at') else 'N/A'}")

            st.divider()

            # Relationship info
            st.markdown("**Relationship**")
            st.markdown(f"- **Type:** {user.get('relationship_type') or 'N/A'}")
            st.markdown(f"- **Why:** {user.get('relationship_why') or 'N/A'}")

            st.divider()

            # Additional info
            st.markdown("**Additional Info**")
            st.markdown(f"**Interesting Fact:** {user.get('interesting_fact') or 'N/A'}")
            st.markdown(f"**Additional Context:** {user.get('additional_context') or 'N/A'}")

# --- Pagination Controls at Bottom ---
st.divider()
col_prev, col_info, col_next = st.columns([1, 2, 1])

with col_prev:
    if st.button("< Previous", disabled=(st.session_state.current_page <= 1), use_container_width=True):
        st.session_state.current_page -= 1
        st.rerun()

with col_info:
    st.markdown(f"<center>Page {st.session_state.current_page} of {total_pages}</center>", unsafe_allow_html=True)

with col_next:
    if st.button("Next >", disabled=(st.session_state.current_page >= total_pages), use_container_width=True):
        st.session_state.current_page += 1
        st.rerun()

# Footer
st.divider()
st.caption("Waitlist Review - Review and manage waitlist users")
