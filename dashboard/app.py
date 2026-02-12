"""
Lambda Admin Dashboard - Main Entry Point
"""
import streamlit as st

# --- Page Config (must be first Streamlit command) ---
st.set_page_config(
    page_title="Lambda Admin",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Define Pages ---
growth_dashboard = st.Page(
    "pages/1_growth_dashboard.py",
    title="Growth Dashboard",
    default=True
)
demographics = st.Page(
    "pages/2_demographics.py",
    title="Demographics",
)
profile_360 = st.Page(
    "pages/3_profile_360.py",
    title="360 Profile View",
)
funnel = st.Page(
    "pages/4_funnel.py",
    title="Funnel",
)
human_review = st.Page(
    "pages/5_human_review.py",
    title="Human Review",
)
matchmaking_stats = st.Page(
    "pages/6_matchmaking_stats.py",
    title="Matchmaking Stats",
)
slotting_review = st.Page(
    "pages/7_slotting_review.py",
    title="Slotting Review",
)
spirit_animal_tracker = st.Page(
    "pages/8_spirit_animal_tracker.py",
    title="Spirit Animal Tracker",
)

# --- Navigation ---
pg = st.navigation(
    {
        "Overview": [growth_dashboard, demographics],
        "Users": [profile_360],
        "Analytics": [funnel, matchmaking_stats, slotting_review],
        "Conversion": [spirit_animal_tracker],
        "Operations": [human_review],
    }
)

# --- Run ---
pg.run()
