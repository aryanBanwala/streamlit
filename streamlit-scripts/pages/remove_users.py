"""
Remove Unnecessary Users - Review users and mark them for removal
"""
import streamlit as st
import os
import sys
from dotenv import load_dotenv

# Setup paths (pages folder ke andar se 2 levels up)
current_dir = os.path.dirname(__file__)
scripts_dir = os.path.abspath(os.path.join(current_dir, '..'))
parent_dir = os.path.abspath(os.path.join(scripts_dir, '..'))
sys.path.insert(0, parent_dir)
sys.path.insert(0, scripts_dir)

try:
    from dependencies import get_supabase_client, get_pinecone_client, get_pinecone_index_name
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

# Custom CSS for animations
st.markdown("""
<style>
@keyframes slideIn {
    from {
        opacity: 0;
        transform: translateX(-20px);
    }
    to {
        opacity: 1;
        transform: translateX(0);
    }
}

.removed-user-item {
    animation: slideIn 0.3s ease-out;
    padding: 10px 14px;
    margin: 6px 0;
    background-color: #2d2d2d;
    border-radius: 8px;
    border-left: 4px solid #ff6b6b;
    cursor: pointer;
    transition: background-color 0.2s ease;
}

.removed-user-item:hover {
    background-color: #3d3d3d;
}

.removed-user-name {
    font-weight: 500;
    color: #ff6b6b;
}

.photo-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 10px;
}
</style>
""", unsafe_allow_html=True)

# Title
st.title("Remove Unnecessary Users")
st.caption("Review users and mark them for removal")

# --- Data Fetching Functions ---

def fetch_users_to_review(after_date=None):
    """Fetch users where hasAppropriatePhotos is true or null (not false)."""
    try:
        # Fetch all users and filter in Python since Supabase doesn't support OR with NULL easily
        query = supabase.table('user_metadata').select(
            'user_id, name, city, area, work_exp, education, interesting_facts, religion, '
            'profile_images, collage_images, instagram_images, "shouldBeRemoved", "hasAppropriatePhotos", created_at, '
            'gender, professional_tier, attractiveness, age'
        )

        # Add date filter if provided
        if after_date:
            query = query.gte('created_at', after_date.isoformat())

        res = query.execute()

        if not res.data:
            return []

        # Filter: hasAppropriatePhotos != false (i.e., true or null)
        filtered = [u for u in res.data if u.get('hasAppropriatePhotos') != False]
        return filtered
    except Exception as e:
        st.error(f"Error fetching users: {e}")
        return []

def fetch_removed_users():
    """Fetch users where shouldBeRemoved = true."""
    try:
        res = supabase.table('user_metadata').select(
            'user_id, name'
        ).eq('shouldBeRemoved', True).execute()
        return res.data if res.data else []
    except Exception as e:
        st.error(f"Error fetching removed users: {e}")
        return []

def update_should_be_removed(user_id: str, value):
    """Update shouldBeRemoved field for a user."""
    try:
        supabase.table('user_metadata').update(
            {'shouldBeRemoved': value}
        ).eq('user_id', user_id).execute()
        return True
    except Exception as e:
        st.error(f"Error updating user: {e}")
        return False

def update_pinecone_should_be_removed(user_id: str, value: bool):
    """Update shouldBeRemoved in Pinecone for all 4 namespaces."""
    namespaces = ["lifestyle", "__default__", "work_edu", "personality"]
    pc = get_pinecone_client()
    if not pc:
        st.warning("Pinecone client not available")
        return False

    index_name = get_pinecone_index_name()
    index = pc.Index(index_name)

    for ns in namespaces:
        try:
            # Fetch existing record to get current metadata
            result = index.fetch(ids=[user_id], namespace=ns)
            if user_id in result.vectors:
                existing = result.vectors[user_id]
                metadata = existing.metadata or {}
                metadata["shouldBeRemoved"] = value
                # Update with existing vector and new metadata
                index.upsert(
                    vectors=[{
                        "id": user_id,
                        "values": existing.values,
                        "metadata": metadata
                    }],
                    namespace=ns
                )
        except Exception as e:
            st.error(f"Error updating Pinecone namespace {ns}: {e}")
            return False
    return True

# --- Session State Initialization ---
if 'remove_current_index' not in st.session_state:
    st.session_state.remove_current_index = 0
if 'remove_users_list' not in st.session_state:
    st.session_state.remove_users_list = []
if 'remove_refresh_trigger' not in st.session_state:
    st.session_state.remove_refresh_trigger = 0

# --- Filters ---
st.sidebar.header("Filters")

# Date filter
filter_date = st.sidebar.date_input(
    "Created on or after",
    value=None,
    key="filter_date"
)

# Gender filter
gender_options = ["All", "male", "female"]
filter_gender = st.sidebar.selectbox(
    "Gender",
    options=gender_options,
    key="filter_gender"
)

# Professional tier filter
tier_options = ["All", "1", "2", "3", "Not Set"]
filter_tier = st.sidebar.selectbox(
    "Professional Tier",
    options=tier_options,
    key="filter_tier"
)

# Attractiveness score filter
attractiveness_options = ["All", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "Not Rated"]
filter_attractiveness = st.sidebar.selectbox(
    "Attractiveness Score",
    options=attractiveness_options,
    key="filter_attractiveness"
)

# Location filter (city) - will be populated dynamically
# First fetch all users to get unique cities
all_users_for_cities = fetch_users_to_review(after_date=filter_date)
unique_cities = sorted(set(u.get('city') for u in all_users_for_cities if u.get('city')))
city_options = ["All"] + unique_cities
filter_city = st.sidebar.selectbox(
    "City",
    options=city_options,
    key="filter_city"
)

# Age filter
col_age1, col_age2 = st.sidebar.columns(2)
with col_age1:
    filter_age_min = st.number_input("Min Age", min_value=18, max_value=100, value=18, key="filter_age_min")
with col_age2:
    filter_age_max = st.number_input("Max Age", min_value=18, max_value=100, value=100, key="filter_age_max")

st.sidebar.divider()

# --- Load Users ---
# Reload when refresh_trigger changes
users = fetch_users_to_review(after_date=filter_date)

# Apply filters
if filter_gender != "All":
    users = [u for u in users if u.get('gender') == filter_gender]

if filter_tier != "All":
    if filter_tier == "Not Set":
        users = [u for u in users if u.get('professional_tier') is None]
    else:
        users = [u for u in users if u.get('professional_tier') == int(filter_tier)]

if filter_attractiveness != "All":
    if filter_attractiveness == "Not Rated":
        users = [u for u in users if u.get('attractiveness') is None]
    else:
        users = [u for u in users if u.get('attractiveness') == int(filter_attractiveness)]

if filter_city != "All":
    users = [u for u in users if u.get('city') == filter_city]

# Age filter
users = [u for u in users if u.get('age') is None or (filter_age_min <= (u.get('age') or 0) <= filter_age_max)]

st.session_state.remove_users_list = users

# --- Search by User ID ---
st.sidebar.header("Search by User ID")
search_user_id = st.sidebar.text_input("Enter User ID", key="search_user_id", placeholder="e.g., 6097cfc5-32f6-...")

if st.sidebar.button("Search", key="search_btn"):
    if search_user_id:
        # Find user index in the list
        found_index = None
        for idx, user in enumerate(users):
            if user.get('user_id') == search_user_id.strip():
                found_index = idx
                break

        if found_index is not None:
            st.session_state.remove_current_index = found_index
            st.rerun()
        else:
            st.sidebar.error("User not found")

st.sidebar.divider()

# --- Left Sidebar: Removed Users List ---
st.sidebar.header("Removed Users")

removed_users = fetch_removed_users()

if removed_users:
    st.sidebar.markdown(f"**{len(removed_users)} user(s) marked for removal**")
    for idx, removed_user in enumerate(removed_users):
        name = removed_user.get('name') or 'Unknown'
        removed_user_id = removed_user.get('user_id')

        # Find the index of this user in the main users list
        user_index = None
        for i, u in enumerate(users):
            if u.get('user_id') == removed_user_id:
                user_index = i
                break

        if user_index is not None:
            if st.sidebar.button(f"{name} - removed", key=f"removed_{idx}", use_container_width=True):
                st.session_state.remove_current_index = user_index
                st.rerun()
        else:
            st.sidebar.markdown(
                f'<div class="removed-user-item"><span class="removed-user-name">{name}</span> - removed</div>',
                unsafe_allow_html=True
            )
else:
    st.sidebar.info("No users marked for removal yet.")

st.sidebar.divider()
st.sidebar.markdown(f"**Total users to review:** {len(users)}")

# --- All Users List in Sidebar ---
st.sidebar.divider()
st.sidebar.header("All Users")
with st.sidebar.expander(f"Browse all {len(users)} users", expanded=False):
    for idx, user in enumerate(users):
        name = user.get('name') or 'Unknown'
        is_user_removed = user.get('shouldBeRemoved') == True
        label = f"{'❌ ' if is_user_removed else ''}{name}"
        if st.button(label, key=f"all_user_{idx}", use_container_width=True):
            st.session_state.remove_current_index = idx
            st.rerun()

# --- Main Content ---
if not users:
    st.warning("No users found to review.")
    st.stop()

# Ensure current_index is within bounds
if st.session_state.remove_current_index >= len(users):
    st.session_state.remove_current_index = len(users) - 1
if st.session_state.remove_current_index < 0:
    st.session_state.remove_current_index = 0

current_user = users[st.session_state.remove_current_index]
user_id = current_user.get('user_id')
is_removed = current_user.get('shouldBeRemoved') == True

# Progress indicator
st.markdown(f"**User {st.session_state.remove_current_index + 1} of {len(users)}**")
st.progress((st.session_state.remove_current_index + 1) / len(users))

# --- Remove/Undo Button (TOP) ---
col_action1, col_action2, col_action3 = st.columns([1, 2, 1])
with col_action2:
    if is_removed:
        if st.button("Undo Removal", key="undo_btn", type="secondary", use_container_width=True):
            if update_should_be_removed(user_id, None):
                update_pinecone_should_be_removed(user_id, False)
                st.success(f"Undo: {current_user.get('name', 'User')} restored!")
                st.session_state.remove_refresh_trigger += 1
                st.rerun()
    else:
        if st.button("Remove This Person", key="remove_btn", type="primary", use_container_width=True):
            if update_should_be_removed(user_id, True):
                update_pinecone_should_be_removed(user_id, True)
                st.warning(f"{current_user.get('name', 'User')} marked for removal!")
                st.session_state.remove_refresh_trigger += 1
                st.rerun()

st.divider()

# --- User Profile Display ---
# Name and basic info
st.header(current_user.get('name') or 'Unknown Name')

# Display key info in a row
gender = current_user.get('gender') or 'N/A'
age = current_user.get('age')
tier = current_user.get('professional_tier')
attractiveness = current_user.get('attractiveness')

info_parts = []
if gender != 'N/A':
    info_parts.append(f"**Gender:** {gender}")
if age:
    info_parts.append(f"**Age:** {age}")
if tier:
    info_parts.append(f"**Tier:** {tier}")
if attractiveness:
    info_parts.append(f"**Attractiveness:** {attractiveness}/10")

if info_parts:
    st.markdown(" | ".join(info_parts))

if is_removed:
    st.error("This user is marked for removal")

# Photos
photos = []
if current_user.get('profile_images'):
    photos.extend(current_user['profile_images'])
if current_user.get('collage_images'):
    photos.extend(current_user['collage_images'])
if current_user.get('instagram_images'):
    photos.extend(current_user['instagram_images'])

if photos:
    st.subheader("Photos")
    # Show spinner while loading, then display photos
    with st.spinner("Loading photos..."):
        # Display photos in a grid (max 6)
        photo_cols = st.columns(min(len(photos), 3))
        for idx, photo_url in enumerate(photos[:6]):
            with photo_cols[idx % 3]:
                try:
                    st.image(photo_url, use_container_width=True)
                except Exception:
                    st.error("Failed to load image")
else:
    st.info("No photos available")

st.divider()

# Profile Info in two columns
col1, col2 = st.columns(2)

with col1:
    st.subheader("Location")
    city = current_user.get('city') or 'N/A'
    area = current_user.get('area') or 'N/A'
    st.markdown(f"**City:** {city}")
    st.markdown(f"**Area:** {area}")

    st.subheader("Religion")
    religion = current_user.get('religion') or 'N/A'
    st.markdown(f"{religion}")

with col2:
    st.subheader("Work")
    work = current_user.get('work_exp') or 'N/A'
    st.markdown(f"{work}")

    st.subheader("Education")
    education = current_user.get('education') or 'N/A'
    st.markdown(f"{education}")

# Interesting Facts
st.subheader("Interesting Facts")
facts = current_user.get('interesting_facts') or []
if facts:
    for fact in facts:
        st.markdown(f"- {fact}")
else:
    st.markdown("No interesting facts available")

st.divider()

# --- Navigation Buttons (BOTTOM) ---
col_prev, col_spacer, col_next = st.columns([1, 2, 1])

with col_prev:
    if st.button("< Previous", key="prev_btn", use_container_width=True, disabled=(st.session_state.remove_current_index == 0)):
        st.session_state.remove_current_index -= 1
        st.rerun()

with col_next:
    if st.button("Next >", key="next_btn", use_container_width=True, disabled=(st.session_state.remove_current_index >= len(users) - 1)):
        st.session_state.remove_current_index += 1
        st.rerun()
