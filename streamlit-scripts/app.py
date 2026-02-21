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
bidirectional_viewer_page = st.Page("pages/bidirectional_viewer.py", title="Bidirectional Viewer", icon="🔄")
pair_scoring_page = st.Page("pages/pair_scoring.py", title="Pair Scoring", icon="🎯")
email_batch_page = st.Page("pages/email_batch_generator.py", title="Email Batch Generator", icon="📧")
poker_finaliser_page = st.Page("pages/poker_finaliser.py", title="Poker Finaliser", icon="🃏")
marked_ghosted_page = st.Page("pages/marked_ghosted.py", title="Marked Ghosted", icon="👻")
match_analytics_page = st.Page("pages/match_analytics.py", title="Match Analytics", icon="📊")
spirit_animal_page = st.Page("pages/spirit_animal_tracker.py", title="Spirit Animal Tracker", icon="🐾")

# --- Navigation ---
pg = st.navigation(
    {
        "Dashboard": [home_page],
        "User Management": [waitlist_page, human_approval_page, remove_users_page, image_manager_page, match_status_page, physical_compat_page, attractiveness_page, user_segments_page, marked_ghosted_page],
        "Analytics": [chat_viewer_page, match_stats_page, match_analytics_page, slotting_viewer_page, bidirectional_viewer_page, pair_scoring_page],
        "Conversion": [spirit_animal_page],
        "Tools": [email_batch_page, poker_finaliser_page],
    }
)

# --- Run selected page ---
pg.run()
