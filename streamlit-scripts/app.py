"""
Lambda Admin Dashboard - Main Entry Point
All admin tools accessible from one place.
"""
import streamlit as st
from streamlit_oauth import OAuth2Component
import extra_streamlit_components as stx

# --- Page Config (must be first) ---
st.set_page_config(
    page_title="Lambda Admin",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Cookie Manager for persistent auth ---
cookie_manager = stx.CookieManager(key="auth_cookies")

# --- Google OAuth Configuration (from .streamlit/secrets.toml) ---
GOOGLE_CLIENT_ID = st.secrets["auth"]["google"]["client_id"]
GOOGLE_CLIENT_SECRET = st.secrets["auth"]["google"]["client_secret"]
REDIRECT_URI = st.secrets["auth"]["redirect_uri"]

# Allowed domains (e.g., "heywavelength.com") - from secrets.toml
ALLOWED_DOMAINS = [d.lower() for d in st.secrets.get("auth", {}).get("allowed_domains", [])]

def check_access(email: str) -> bool:
    """Check if email domain is allowed."""
    if not ALLOWED_DOMAINS:
        return True  # If no allowlist configured, allow all authenticated users
    email_domain = email.lower().split("@")[-1]
    return email_domain in ALLOWED_DOMAINS

# --- Authentication ---
# Try to get email from cookie first
user_email = cookie_manager.get("user_email")

if user_email is None:
    # Hide sidebar when not logged in
    st.markdown("""
        <style>
            [data-testid="stSidebar"] {display: none;}
            [data-testid="stSidebarNav"] {display: none;}
        </style>
    """, unsafe_allow_html=True)

    st.title("Lambda Admin Login")
    st.write("Please sign in with your Google account to continue.")

    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        st.error("Google OAuth not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables.")
        st.stop()

    oauth2 = OAuth2Component(
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        authorize_endpoint="https://accounts.google.com/o/oauth2/v2/auth",
        token_endpoint="https://oauth2.googleapis.com/token",
    )

    result = oauth2.authorize_button(
        name="Sign in with Google",
        redirect_uri=REDIRECT_URI,
        scope="openid email profile",
        key="google_oauth",
        use_container_width=True,
        extras_params={"prompt": "select_account"},
        pkce="S256",
    )

    if result and "token" in result:
        import requests
        # Get user info from Google
        access_token = result["token"]["access_token"]
        user_info = requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        ).json()
        email = user_info.get("email")
        # Store in cookie (expires in 7 days)
        cookie_manager.set("user_email", email, max_age=60*60*24*7)
        st.rerun()

    st.stop()

# Check if user's email is allowed
if not check_access(user_email):
    # Hide sidebar for unauthorized users
    st.markdown("""
        <style>
            [data-testid="stSidebar"] {display: none;}
            [data-testid="stSidebarNav"] {display: none;}
        </style>
    """, unsafe_allow_html=True)

    st.error(f"Access denied. Your email ({user_email}) is not authorized.")
    st.write("Please contact an administrator to request access.")
    if st.button("Sign out"):
        cookie_manager.delete("user_email")
        st.rerun()
    st.stop()

# Show logged in user in sidebar
with st.sidebar:
    st.write(f"Logged in as: **{user_email}**")
    if st.button("Sign out"):
        cookie_manager.delete("user_email")
        st.rerun()

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
email_batch_page = st.Page("pages/email_batch_generator.py", title="Email Batch Generator", icon="📧")
marked_ghosted_page = st.Page("pages/marked_ghosted.py", title="Marked Ghosted", icon="👻")
match_analytics_page = st.Page("pages/match_analytics.py", title="Match Analytics", icon="📊")

# --- Navigation ---
pg = st.navigation(
    {
        "Dashboard": [home_page],
        "User Management": [waitlist_page, human_approval_page, remove_users_page, image_manager_page, match_status_page, physical_compat_page, attractiveness_page, user_segments_page, marked_ghosted_page],
        "Analytics": [chat_viewer_page, match_stats_page, match_analytics_page, slotting_viewer_page, bidirectional_viewer_page],
        "Tools": [email_batch_page],
    }
)

# --- Run selected page ---
pg.run()
