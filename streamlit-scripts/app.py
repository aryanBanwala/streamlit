"""
Lambda Admin Dashboard - Main Entry Point
All admin tools accessible from one place.
"""
import streamlit as st

# --- Page Config (must be first) ---
st.set_page_config(
    page_title="Lambda Admin Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom CSS for Better UI ---
st.markdown("""
<style>
    /* Main container styling */
    .main {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 0;
    }

    /* Content area */
    .block-container {
        background: #ffffff;
        border-radius: 15px;
        padding: 2rem !important;
        margin-top: 1rem;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
    }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #2d3748 0%, #1a202c 100%);
    }

    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {
        color: #ffffff;
    }

    /* Navigation buttons */
    .stButton button {
        border-radius: 10px;
        font-weight: 600;
        transition: all 0.3s ease;
    }

    .stButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    }

    /* Headers */
    h1 {
        color: #2d3748;
        font-weight: 800;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }

    h2, h3 {
        color: #4a5568;
        font-weight: 700;
    }

    /* Metrics */
    [data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: 800;
        color: #667eea;
    }

    /* Cards and containers */
    .element-container {
        transition: all 0.3s ease;
    }

    /* Dividers */
    hr {
        margin: 2rem 0;
        border: none;
        height: 2px;
        background: linear-gradient(90deg, transparent, #667eea, transparent);
    }
</style>
""", unsafe_allow_html=True)

# --- Define all pages ---
home_page = st.Page("pages/home.py", title="Home", icon="🏠", default=True)
waitlist_page = st.Page("pages/waitlist.py", title="Waitlist Review", icon="📋")
human_approval_page = st.Page("pages/human_approval.py", title="Human Approval", icon="✅")
chat_viewer_page = st.Page("pages/chat_viewer.py", title="Chat Viewer", icon="💬")
remove_users_page = st.Page("pages/remove_users.py", title="Remove Users", icon="🗑️")
image_manager_page = st.Page("pages/image_manager.py", title="Image Manager", icon="🖼️")
match_status_page = st.Page("pages/match_status.py", title="Match Status", icon="💑")
physical_compat_page = st.Page("pages/physical_compatibility.py", title="Physical Compatibility", icon="💪")

# --- Navigation ---
pg = st.navigation(
    {
        "Dashboard": [home_page],
        "User Management": [waitlist_page, human_approval_page, remove_users_page, image_manager_page, match_status_page, physical_compat_page],
        "Analytics": [chat_viewer_page],
    }
)

# --- Run selected page ---
pg.run()
