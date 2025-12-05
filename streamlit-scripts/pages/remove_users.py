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
    from dependencies import get_supabase_client
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

def fetch_users_to_review():
    """Fetch users where hasAppropriatePhotos is true or null (not false)."""
    try:
        # Fetch all users and filter in Python since Supabase doesn't support OR with NULL easily
        res = supabase.table('user_metadata').select(
            'user_id, name, city, area, work_exp, education, interesting_facts, religion, '
            'profile_images, collage_images, instagram_images, "shouldBeRemoved", "hasAppropriatePhotos"'
        ).execute()

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

# --- Session State Initialization ---
if 'remove_current_index' not in st.session_state:
    st.session_state.remove_current_index = 0
if 'remove_users_list' not in st.session_state:
    st.session_state.remove_users_list = []
if 'remove_refresh_trigger' not in st.session_state:
    st.session_state.remove_refresh_trigger = 0

# --- Load Users ---
# Reload when refresh_trigger changes
users = fetch_users_to_review()
st.session_state.remove_users_list = users

# --- Left Sidebar: Removed Users List ---
st.sidebar.header("Removed Users")
st.sidebar.divider()

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
                st.success(f"Undo: {current_user.get('name', 'User')} restored!")
                st.session_state.remove_refresh_trigger += 1
                st.rerun()
    else:
        if st.button("Remove This Person", key="remove_btn", type="primary", use_container_width=True):
            if update_should_be_removed(user_id, True):
                st.warning(f"{current_user.get('name', 'User')} marked for removal!")
                st.session_state.remove_refresh_trigger += 1
                st.rerun()

st.divider()

# --- User Profile Display ---
# Name
st.header(current_user.get('name') or 'Unknown Name')

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
