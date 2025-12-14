"""
Attractiveness Rating - Rate user attractiveness from 1-10.
Browse users one at a time, filter by gender, search by user_id.
"""
import streamlit as st
import os
import sys
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

# --- Supabase Connection ---
try:
    supabase = get_supabase_client()
except Exception as e:
    st.error(f"Supabase connection failed: {e}")
    st.stop()


# --- Data Loading Functions ---
@st.cache_data(ttl=60)
def fetch_users(gender_filter: str = "all", rating_filter: str = "all"):
    """Fetch users from user_metadata with optional gender and rating filters."""
    try:
        query = supabase.table('user_metadata').select(
            'user_id, name, gender, age, profile_images, instagram_images, attractiveness'
        )

        if gender_filter and gender_filter != "all":
            query = query.eq('gender', gender_filter)

        if rating_filter == "not rated":
            query = query.is_('attractiveness', 'null')
        elif rating_filter == "rated":
            query = query.not_.is_('attractiveness', 'null')

        # Order by attractiveness null first (unrated users first), then by user_id
        res = query.order('attractiveness', desc=False, nullsfirst=True).order('user_id').execute()
        return res.data if res.data else []
    except Exception as e:
        st.error(f"Error fetching users: {e}")
        return []


def fetch_user_by_id(user_id: str):
    """Fetch a specific user by user_id."""
    try:
        res = supabase.table('user_metadata').select(
            'user_id, name, gender, age, profile_images, instagram_images, attractiveness'
        ).eq('user_id', user_id).maybe_single().execute()
        return res.data
    except Exception as e:
        st.error(f"Error fetching user: {e}")
        return None


def update_attractiveness(user_id: str, score: int) -> bool:
    """Update attractiveness score for a user."""
    try:
        supabase.table('user_metadata').update({
            'attractiveness': score
        }).eq('user_id', user_id).execute()
        return True
    except Exception as e:
        st.error(f"Failed to update attractiveness: {e}")
        return False


def display_user_images(user_data: dict):
    """Display user photos in a horizontal scrollable container."""
    photos = user_data.get('profile_images') or user_data.get('instagram_images') or []

    if photos and isinstance(photos, list):
        images_html = ""
        for url in photos:
            images_html += f'<img src="{url}" style="height: 400px; width: auto; object-fit: cover; border-radius: 8px; flex-shrink: 0;">'

        st.markdown(f"""
        <div style="
            display: flex;
            gap: 12px;
            overflow-x: auto;
            padding: 12px 0;
            scrollbar-width: thin;
        ">
            {images_html}
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="height: 300px; background: #2d2d2d; border-radius: 8px; display: flex; align-items: center; justify-content: center; color: #888;">
            No images available
        </div>
        """, unsafe_allow_html=True)


# --- Initialize Session State ---
if 'ar_current_index' not in st.session_state:
    st.session_state.ar_current_index = 0
if 'ar_gender_filter' not in st.session_state:
    st.session_state.ar_gender_filter = "all"
if 'ar_search_user_id' not in st.session_state:
    st.session_state.ar_search_user_id = None
if 'ar_search_mode' not in st.session_state:
    st.session_state.ar_search_mode = False
if 'ar_rating_filter' not in st.session_state:
    st.session_state.ar_rating_filter = "not rated"


# --- Sidebar ---
st.sidebar.header("Filters")

# Gender filter
gender_options = ["all", "male", "female"]
selected_gender = st.sidebar.selectbox(
    "Gender",
    options=gender_options,
    index=gender_options.index(st.session_state.ar_gender_filter)
)

# Handle gender filter change
if selected_gender != st.session_state.ar_gender_filter:
    st.session_state.ar_gender_filter = selected_gender
    st.session_state.ar_current_index = 0
    st.session_state.ar_search_mode = False
    st.session_state.ar_search_user_id = None
    st.cache_data.clear()
    st.rerun()

# Rating status filter
rating_options = ["not rated", "rated"]
selected_rating = st.sidebar.selectbox(
    "Rating Status",
    options=rating_options,
    index=rating_options.index(st.session_state.ar_rating_filter)
)

# Handle rating filter change
if selected_rating != st.session_state.ar_rating_filter:
    st.session_state.ar_rating_filter = selected_rating
    st.session_state.ar_current_index = 0
    st.session_state.ar_search_mode = False
    st.session_state.ar_search_user_id = None
    st.cache_data.clear()
    st.rerun()

st.sidebar.divider()

# Search by user_id
st.sidebar.subheader("Search User")
search_input = st.sidebar.text_input("User ID", placeholder="Enter user_id...")
if st.sidebar.button("Search", type="primary", use_container_width=True):
    if search_input.strip():
        st.session_state.ar_search_user_id = search_input.strip()
        st.session_state.ar_search_mode = True
        st.rerun()

if st.session_state.ar_search_mode:
    if st.sidebar.button("Clear Search", use_container_width=True):
        st.session_state.ar_search_mode = False
        st.session_state.ar_search_user_id = None
        st.rerun()

st.sidebar.divider()

# Fetch users based on filters
users = fetch_users(st.session_state.ar_gender_filter, st.session_state.ar_rating_filter)

# Stats
st.sidebar.subheader("Stats")
total_users = len(users)
rated_users = sum(1 for u in users if u.get('attractiveness') is not None)
unrated_users = total_users - rated_users

st.sidebar.metric("Total Users", total_users)
col1, col2 = st.sidebar.columns(2)
with col1:
    st.metric("Rated", rated_users)
with col2:
    st.metric("Unrated", unrated_users)

if total_users > 0:
    progress = rated_users / total_users
    st.sidebar.progress(progress, text=f"{int(progress * 100)}% rated")


# --- Main Content ---
col_title, col_refresh = st.columns([4, 1])
with col_title:
    st.title("Attractiveness Rating")
with col_refresh:
    if st.button("Refresh", use_container_width=True, type="primary"):
        st.cache_data.clear()
        st.rerun()

# Handle search mode vs browse mode
if st.session_state.ar_search_mode and st.session_state.ar_search_user_id:
    # Search mode - show specific user
    user_data = fetch_user_by_id(st.session_state.ar_search_user_id)

    if not user_data:
        st.error(f"User not found: {st.session_state.ar_search_user_id}")
        st.stop()

    st.info(f"Showing search result for: **{st.session_state.ar_search_user_id}**")

else:
    # Browse mode - show users one by one
    if not users:
        st.warning("No users found with current filter.")
        st.stop()

    # Ensure index is valid
    if st.session_state.ar_current_index >= len(users):
        st.session_state.ar_current_index = 0

    user_data = users[st.session_state.ar_current_index]

    # Navigation info
    st.info(f"User {st.session_state.ar_current_index + 1} of {len(users)} | Gender: {st.session_state.ar_gender_filter} | Status: {st.session_state.ar_rating_filter}")

# Display current user
if user_data:
    user_id = user_data.get('user_id')
    name = user_data.get('name', 'Unknown')
    gender = user_data.get('gender', 'Unknown')
    age = user_data.get('age', '')
    current_score = user_data.get('attractiveness')

    # User header
    st.markdown(f"### {name}")
    score_text = f"Current rating: **{current_score}/10**" if current_score else "Not rated yet"
    st.markdown(f"**User ID:** `{user_id}` | **Gender:** {gender} | **Age:** {age if age else 'N/A'} | {score_text}")

    st.divider()

    # Display images
    display_user_images(user_data)

    st.divider()

    # Rating buttons (1-10)
    st.markdown("#### Rate Attractiveness")

    @st.fragment
    def rating_buttons():
        local_score = st.session_state.get(f"ar_local_score_{user_id}") or user_data.get('attractiveness')

        # Two rows of 5 buttons each
        row1 = st.columns(5)
        for i in range(5):
            with row1[i]:
                score_val = i + 1
                btn_type = "primary" if local_score == score_val else "secondary"
                if st.button(str(score_val), key=f"rate_{user_id}_{score_val}", type=btn_type, use_container_width=True):
                    st.session_state[f"ar_local_score_{user_id}"] = score_val
                    update_attractiveness(user_id, score_val)
                    st.cache_data.clear()
                    st.rerun(scope="fragment")

        row2 = st.columns(5)
        for i in range(5):
            with row2[i]:
                score_val = i + 6
                btn_type = "primary" if local_score == score_val else "secondary"
                if st.button(str(score_val), key=f"rate_{user_id}_{score_val}", type=btn_type, use_container_width=True):
                    st.session_state[f"ar_local_score_{user_id}"] = score_val
                    update_attractiveness(user_id, score_val)
                    st.cache_data.clear()
                    st.rerun(scope="fragment")

    rating_buttons()

    st.divider()

    # Navigation buttons (only in browse mode)
    if not st.session_state.ar_search_mode:
        col_prev, col_next = st.columns(2)

        with col_prev:
            if st.button("< Previous", use_container_width=True, disabled=st.session_state.ar_current_index == 0):
                st.session_state.ar_current_index -= 1
                st.rerun()

        with col_next:
            if st.button("Next >", use_container_width=True, disabled=st.session_state.ar_current_index >= len(users) - 1):
                st.session_state.ar_current_index += 1
                st.rerun()
