"""
Lambda Admin Dashboard - Main Entry Point
Choose between old (Website/Wavelength) and new (App/Wavelength) dashboards.
"""
import streamlit as st

# --- Page Config (must be first) ---
st.set_page_config(
    page_title="Lambda Admin",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- Session state for dashboard choice ---
if "dashboard" not in st.session_state:
    st.session_state.dashboard = None


# --- Chooser page (rendered as a st.Page callable) ---
def chooser_page():
    st.markdown(
        "<h1 style='text-align:center; margin-top: 80px;'>Lambda Admin Dashboard</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align:center; color: grey;'>Choose a dashboard to continue</p>",
        unsafe_allow_html=True,
    )

    col1, spacer, col2 = st.columns([1, 0.3, 1])

    with col1:
        st.markdown("---")
        st.markdown("### 🌐 Website — Wavelength (Old)")
        st.markdown("The original admin dashboard for the **website** version of Wavelength.")
        if st.button("Open Old Dashboard →", use_container_width=True, type="primary"):
            st.session_state.dashboard = "old"
            st.rerun()

    with col2:
        st.markdown("---")
        st.markdown("### 📱 App — Wavelength (New)")
        st.markdown("The new admin dashboard for the **app** version of Wavelength.")
        if st.button("Open New Dashboard →", use_container_width=True, type="primary"):
            st.session_state.dashboard = "new"
            st.rerun()


# --- Build navigation based on chosen dashboard ---
if st.session_state.dashboard == "old":
    # Back button in sidebar
    if st.sidebar.button("← Back to Chooser"):
        st.session_state.dashboard = None
        st.rerun()
    st.sidebar.markdown("---")

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

    pg = st.navigation(
        {
            "🌐 Old Dashboard": [home_page],
            "User Management": [waitlist_page, human_approval_page, remove_users_page, image_manager_page, match_status_page, physical_compat_page, attractiveness_page, user_segments_page, marked_ghosted_page],
            "Analytics": [chat_viewer_page, match_stats_page, match_analytics_page, slotting_viewer_page, bidirectional_viewer_page, pair_scoring_page],
            "Conversion": [spirit_animal_page],
            "Tools": [email_batch_page, poker_finaliser_page],
        }
    )
    pg.run()

elif st.session_state.dashboard == "new":
    if st.sidebar.button("← Back to Chooser"):
        st.session_state.dashboard = None
        st.rerun()
    st.sidebar.markdown("---")

    new_home_page = st.Page("pages_new/home.py", title="Home", icon="🏠", default=True)
    quality_filtering_page = st.Page("pages_new/quality_filtering.py", title="Quality Filtering", icon="🔍")
    match_review_page = st.Page("pages_new/match_review.py", title="Match Review", icon="💘")
    wyt_checker_page = st.Page("pages_new/why_you_two_checker.py", title="Why You Two Checker", icon="🎨")

    pg = st.navigation(
        {
            "📱 New Dashboard": [new_home_page],
            "Review": [quality_filtering_page, match_review_page, wyt_checker_page],
        }
    )
    pg.run()

else:
    # Chooser screen — register a single page to prevent auto-discovery of pages/
    pg = st.navigation([st.Page(chooser_page, title="Choose Dashboard", icon="🔧")])
    pg.run()
