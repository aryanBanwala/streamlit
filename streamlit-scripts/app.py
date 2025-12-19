"""
Lambda Admin Dashboard - Main Entry Point
All admin tools accessible from one place.
"""
import streamlit as st

# --- Page Config (must be first) ---
st.set_page_config(
    page_title="Lambda Admin",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Define all pages ---
home_page = st.Page("pages/home.py", title="Home", icon="🏠", default=True)
waitlist_page = st.Page("pages/waitlist.py", title="Waitlist Review", icon="📋")
human_approval_page = st.Page("pages/human_approval.py", title="Human Approval", icon="✅")
chat_viewer_page = st.Page("pages/chat_viewer.py", title="Chat Viewer", icon="💬")
remove_users_page = st.Page("pages/remove_users.py", title="Remove Users", icon="🗑️")
image_manager_page = st.Page("pages/image_manager.py", title="Image Manager", icon="🖼️")
match_status_page = st.Page("pages/match_status.py", title="Match Status", icon="💑")
physical_compat_page = st.Page("pages/physical_compatibility.py", title="Physical Compatibility", icon="💪")
attractiveness_page = st.Page("pages/attractiveness_rating.py", title="Attractiveness Rating", icon="⭐")
user_segments_page = st.Page("pages/user_segments.py", title="User Segments", icon="📊")
match_stats_page = st.Page("pages/match_stats.py", title="Match Stats", icon="📈")
slotting_viewer_page = st.Page("pages/slotting_viewer.py", title="Slotting Viewer", icon="🎰")
email_batch_page = st.Page("pages/email_batch_generator.py", title="Email Batch Generator", icon="📧")

# --- Navigation ---
pg = st.navigation(
    {
        "Dashboard": [home_page],
        "User Management": [waitlist_page, human_approval_page, remove_users_page, image_manager_page, match_status_page, physical_compat_page, attractiveness_page, user_segments_page],
        "Analytics": [chat_viewer_page, match_stats_page, slotting_viewer_page],
        "Tools": [email_batch_page],
    }
)

# --- Run selected page ---
pg.run()
