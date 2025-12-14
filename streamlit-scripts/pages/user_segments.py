"""
User Segments - View CSV exports of user segments with reset capability.
"""
import streamlit as st
import pandas as pd
import os
import sys
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load environment
current_dir = os.path.dirname(__file__)
scripts_dir = os.path.abspath(os.path.join(current_dir, '..'))
parent_dir = os.path.abspath(os.path.join(scripts_dir, '..'))
sys.path.insert(0, parent_dir)
dotenv_path = os.path.join(parent_dir, '.env')
load_dotenv(dotenv_path)

try:
    from dependencies import get_supabase_client
    supabase = get_supabase_client()
except ImportError:
    st.error("Error: 'dependencies.py' not found.")
    st.stop()
except Exception as e:
    st.error(f"Supabase connection failed: {e}")
    st.stop()

# --- Constants ---
DATA_DIR = Path(__file__).parent.parent / "data"
API_URL = "https://staging.heywavelength.com/api/user/fullreset"

# Load API key from environment
API_KEY = os.getenv("API_KEY_HEADER", "")

def get_csv_files():
    """Get all CSV files from data directory."""
    if not DATA_DIR.exists():
        return []
    return sorted([f for f in DATA_DIR.glob("*.csv")])

def load_csv(file_path: Path) -> pd.DataFrame:
    """Load CSV file into DataFrame."""
    try:
        return pd.read_csv(file_path)
    except Exception as e:
        st.error(f"Error loading {file_path.name}: {e}")
        return pd.DataFrame()

def reset_user(user_id: str) -> tuple[bool, str]:
    """Call the fullreset API for a user."""
    if not API_KEY:
        return False, "API key not configured. Set WAVE_API_KEY environment variable."

    try:
        response = requests.post(
            API_URL,
            headers={
                "Content-Type": "application/json",
                "x-api-key": API_KEY
            },
            json={"user_id": user_id},
            timeout=30
        )
        if response.status_code == 200:
            return True, "User reset successfully"
        else:
            return False, f"API error: {response.status_code} - {response.text}"
    except requests.exceptions.RequestException as e:
        return False, f"Request failed: {str(e)}"

def format_filename(filename: str) -> str:
    """Format filename for display."""
    name = filename.replace(".csv", "").replace("_", " ").title()
    return name

def check_user_exists(user_id: str) -> bool:
    """Check if a single user exists in user_data table."""
    try:
        res = supabase.table('user_data').select('user_id').eq('user_id', user_id).maybe_single().execute()
        return res.data is not None
    except Exception:
        return True  # Assume exists on error

@st.cache_data(ttl=600)
def get_deleted_users(user_ids: tuple) -> set:
    """Initial check for which users from CSV are already deleted. Cached for 10 min."""
    if not user_ids:
        return set()
    try:
        res = supabase.table('user_data').select('user_id').in_('user_id', list(user_ids)).execute()
        existing_ids = {row['user_id'] for row in res.data} if res.data else set()
        return set(user_ids) - existing_ids  # Return users NOT in db (deleted)
    except Exception:
        return set()  # On error, assume none are deleted

# --- Page Content ---
st.title("User Segments")
st.caption("View exported user segments and reset users if needed")

# API Key input in sidebar
with st.sidebar:
    st.subheader("API Configuration")
    api_key_input = st.text_input(
        "API Key",
        value=API_KEY,
        type="password",
        help="Enter the API key for user reset endpoint"
    )
    if api_key_input:
        API_KEY = api_key_input

# Get CSV files
csv_files = get_csv_files()

if not csv_files:
    st.warning(f"No CSV files found in {DATA_DIR}")
    st.stop()

# File selector
file_options = {format_filename(f.name): f for f in csv_files}
selected_name = st.selectbox("Select Segment", options=list(file_options.keys()))
selected_file = file_options[selected_name]

# Load data
df = load_csv(selected_file)

if df.empty:
    st.warning("No data in this file")
    st.stop()

# Stats
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Users", len(df))
with col2:
    if "status" in df.columns:
        st.metric("Statuses", df["status"].nunique())
with col3:
    if "next_steps_sent" in df.columns:
        st.metric("Next Steps Sent", df["next_steps_sent"].value_counts().get("true", 0))

st.divider()

# Initialize session state for dialog and deleted users tracking
if "show_reset_dialog" not in st.session_state:
    st.session_state.show_reset_dialog = False
    st.session_state.reset_user_id = None
    st.session_state.reset_user_info = None
if "deleted_users" not in st.session_state:
    st.session_state.deleted_users = set()

# Reset confirmation dialog
@st.dialog("Confirm User Reset")
def reset_dialog():
    user_id = st.session_state.reset_user_id
    user_info = st.session_state.reset_user_info

    st.warning(f"Are you sure you want to completely reset this user?")
    st.markdown(f"**User ID:** `{user_id}`")

    if user_info:
        if "user_email" in user_info:
            st.markdown(f"**Email:** {user_info.get('user_email', 'N/A')}")
        if "user_phone" in user_info:
            st.markdown(f"**Phone:** {user_info.get('user_phone', 'N/A')}")

    st.error("This action cannot be undone!")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Cancel", use_container_width=True):
            st.session_state.show_reset_dialog = False
            st.session_state.reset_user_id = None
            st.session_state.reset_user_info = None
            st.rerun()
    with col2:
        if st.button("Reset User", type="primary", use_container_width=True):
            success, message = reset_user(user_id)
            if success:
                st.success(message)
                # Check if user was actually deleted from db
                if not check_user_exists(user_id):
                    st.session_state.deleted_users.add(user_id)
                st.session_state.show_reset_dialog = False
                st.session_state.reset_user_id = None
                st.session_state.reset_user_info = None
                st.rerun()
            else:
                st.error(message)

# Show dialog if triggered
if st.session_state.show_reset_dialog:
    reset_dialog()

# Display data with reset buttons
st.subheader(f"{selected_name} ({len(df)} users)")

# Add search/filter
search = st.text_input("Search by user_id, email, or phone", "")
if search:
    mask = df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)
    df = df[mask]
    st.caption(f"Showing {len(df)} matching users")

# Initial check: get users already deleted from db (cached)
all_user_ids = tuple(df["user_id"].dropna().unique().tolist()) if "user_id" in df.columns else ()
initially_deleted = get_deleted_users(all_user_ids)

# Display each row with delete button
for idx, row in df.iterrows():
    user_id = row.get("user_id", "")
    # Check if user was deleted: either initially or during this session
    is_deleted = user_id in initially_deleted or user_id in st.session_state.deleted_users

    with st.container():
        cols = st.columns([4, 1])

        with cols[0]:
            # Display row data
            display_cols = [c for c in df.columns if c != "user_id"]
            info_parts = []

            if "user_email" in row:
                info_parts.append(f"**Email:** {row.get('user_email', 'N/A')}")
            if "user_phone" in row:
                info_parts.append(f"**Phone:** {row.get('user_phone', 'N/A')}")
            if "status" in row:
                info_parts.append(f"**Status:** {row.get('status', 'N/A')}")
            if "message_count" in row:
                info_parts.append(f"**Messages:** {row.get('message_count', 'N/A')}")
            if "next_steps_sent" in row:
                info_parts.append(f"**Next Steps:** {row.get('next_steps_sent', 'N/A')}")

            st.markdown(f"`{user_id}`")
            st.caption(" | ".join(info_parts) if info_parts else "No additional info")

        with cols[1]:
            if is_deleted:
                st.markdown(
                    f'<div style="background-color: #ff4b4b; color: white; padding: 0.5rem 1rem; '
                    f'border-radius: 0.5rem; text-align: center; font-weight: 500;">Deleted</div>',
                    unsafe_allow_html=True
                )
            else:
                if st.button("Reset", key=f"reset_{idx}_{user_id}", type="secondary", use_container_width=True):
                    st.session_state.show_reset_dialog = True
                    st.session_state.reset_user_id = user_id
                    st.session_state.reset_user_info = row.to_dict()
                    st.rerun()

        st.divider()
