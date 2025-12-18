"""
User Image Manager - Manage user profile and collage images
Search by user_id, view/delete/add profile images, view/delete/replace collage image
"""
import streamlit as st
import os
import sys
import random
import string
import time
from datetime import datetime
from dotenv import load_dotenv

# Setup paths
current_dir = os.path.dirname(__file__)
scripts_dir = os.path.abspath(os.path.join(current_dir, '..'))
parent_dir = os.path.abspath(os.path.join(scripts_dir, '..'))
sys.path.insert(0, parent_dir)
sys.path.insert(0, scripts_dir)

from dependencies import get_supabase_client

# Load environment
dotenv_path = os.path.join(parent_dir, '.env')
load_dotenv(dotenv_path)

# Initialize Supabase
try:
    supabase = get_supabase_client()
except Exception as e:
    st.error(f"Supabase connection failed: {e}")
    st.stop()

# Constants
STORAGE_BUCKET = "chat-images"


# --- Helper Functions ---

def generate_profile_filename(user_id: str, index: int) -> str:
    """Generate filename for profile images: {user_id}-{timestamp_ms}-{index}-{random}.jpeg"""
    timestamp = int(time.time() * 1000)
    random_str = ''.join(random.choices(string.ascii_lowercase, k=6))
    return f"{user_id}-{timestamp}-{index}-{random_str}.jpeg"


def generate_collage_path(user_id: str) -> str:
    """Generate path for collage images: collage_creation/{user_id}/collage_{YYYYMMDD_HHMMSS}.jpg"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"collage_creation/{user_id}/collage_{timestamp}.jpg"


def extract_storage_path(url: str) -> str:
    """Extract storage path from full URL"""
    # URL: https://xxx.supabase.co/storage/v1/object/public/chat-images/public/file.jpeg
    # Returns: public/file.jpeg
    parts = url.split('/chat-images/')
    return parts[1] if len(parts) > 1 else None


def fetch_user_by_id(user_id: str):
    """Fetch user data from user_metadata by user_id"""
    try:
        res = supabase.table('user_metadata').select(
            'user_id, name, gender, age, profile_images, collage_images'
        ).eq('user_id', user_id).maybe_single().execute()
        return res.data
    except Exception as e:
        st.error(f"Error fetching user: {e}")
        return None


def delete_from_storage(url: str) -> bool:
    """Delete file from Supabase storage"""
    try:
        path = extract_storage_path(url)
        if path:
            supabase.storage.from_(STORAGE_BUCKET).remove([path])
            return True
        return False
    except Exception as e:
        st.warning(f"Could not delete from storage: {e}")
        return False


def upload_to_storage(file_bytes: bytes, file_path: str, content_type: str = "image/jpeg") -> str:
    """Upload file to Supabase storage and return public URL"""
    try:
        supabase.storage.from_(STORAGE_BUCKET).upload(
            path=file_path,
            file=file_bytes,
            file_options={"content-type": content_type}
        )
        return supabase.storage.from_(STORAGE_BUCKET).get_public_url(file_path)
    except Exception as e:
        st.error(f"Upload failed: {e}")
        return None


def update_profile_images(user_id: str, images: list) -> bool:
    """Update profile_images array in database"""
    try:
        supabase.table('user_metadata').update({
            'profile_images': images
        }).eq('user_id', user_id).execute()
        return True
    except Exception as e:
        st.error(f"Failed to update profile images: {e}")
        return False


def update_collage_images(user_id: str, images: list, clear_status: bool = False) -> bool:
    """Update collage_images array in database. If clear_status=True, also clears collage_creation_status and message."""
    try:
        update_data = {'collage_images': images}
        if clear_status:
            update_data['collage_creation_status'] = None
            update_data['collage_creation_message'] = None
        supabase.table('user_metadata').update(update_data).eq('user_id', user_id).execute()
        return True
    except Exception as e:
        st.error(f"Failed to update collage images: {e}")
        return False


# --- Page Content ---

st.title("User Image Manager")
st.markdown("Search by user_id to view and manage profile/collage images")

st.divider()

# --- Search Section ---
col_search, col_btn = st.columns([3, 1])
with col_search:
    search_user_id = st.text_input("Enter User ID", key="search_user_id_input", label_visibility="collapsed", placeholder="Enter user_id...")
with col_btn:
    search_clicked = st.button("Search", type="primary", use_container_width=True)

# Initialize session state
if 'image_manager_user_data' not in st.session_state:
    st.session_state.image_manager_user_data = None

# Handle search
if search_clicked and search_user_id:
    user_data = fetch_user_by_id(search_user_id.strip())
    if user_data:
        st.session_state.image_manager_user_data = user_data
        st.success(f"Found user: {user_data.get('name', 'Unknown')}")
    else:
        st.session_state.image_manager_user_data = None
        st.error("User not found")

# --- Display User Data ---
user_data = st.session_state.image_manager_user_data

if user_data:
    st.divider()

    # User Info Header
    user_id = user_data.get('user_id')
    name = user_data.get('name', 'Unknown')
    gender = user_data.get('gender', 'Unknown')
    age = user_data.get('age', 'Unknown')

    st.markdown(f"### {name}")
    st.markdown(f"**User ID:** `{user_id}` | **Gender:** {gender} | **Age:** {age}")

    st.divider()

    # --- Profile Images Section ---
    profile_images = user_data.get('profile_images') or []

    col_header, col_add = st.columns([3, 1])
    with col_header:
        st.subheader(f"Profile Images ({len(profile_images)})")
    with col_add:
        add_profile_img = st.button("+ Add Image", key="add_profile_btn", use_container_width=True)

    # Add profile image uploader (multiple files)
    if add_profile_img or st.session_state.get('show_profile_uploader'):
        st.session_state.show_profile_uploader = True
        uploaded_files = st.file_uploader(
            "Upload profile images",
            type=['jpg', 'jpeg', 'png'],
            key="profile_uploader",
            accept_multiple_files=True
        )
        if uploaded_files:
            with st.spinner(f"Uploading {len(uploaded_files)} image(s)..."):
                success_count = 0
                for i, uploaded_file in enumerate(uploaded_files):
                    # Generate filename and upload
                    index = len(profile_images) + i
                    filename = generate_profile_filename(user_id, index)
                    file_path = f"public/{filename}"

                    url = upload_to_storage(uploaded_file.getvalue(), file_path)
                    if url:
                        profile_images.append(url)
                        success_count += 1

                # Update DB once with all new images
                if success_count > 0 and update_profile_images(user_id, profile_images):
                    st.success(f"{success_count} image(s) uploaded successfully!")
                    st.session_state.show_profile_uploader = False
                    # Refresh user data
                    st.session_state.image_manager_user_data = fetch_user_by_id(user_id)
                    st.rerun()

    # Display profile images in grid (fixed width ~200px per image)
    if profile_images:
        cols = st.columns(4)  # 4 columns for smaller images
        for idx, url in enumerate(profile_images):
            with cols[idx % 4]:
                try:
                    st.image(url, width=200)
                except Exception:
                    st.error("Failed to load")

                if st.button("Delete", key=f"del_profile_{idx}"):
                    with st.spinner("Deleting..."):
                        # Delete from storage
                        delete_from_storage(url)
                        # Remove from array
                        updated_images = [img for i, img in enumerate(profile_images) if i != idx]
                        if update_profile_images(user_id, updated_images):
                            st.success("Deleted!")
                            st.session_state.image_manager_user_data = fetch_user_by_id(user_id)
                            st.rerun()
    else:
        st.info("No profile images")

    st.divider()

    # --- Collage Images Section ---
    collage_images = user_data.get('collage_images') or []
    current_collage = collage_images[0] if collage_images else None

    col_header2, col_replace = st.columns([3, 1])
    with col_header2:
        st.subheader("Collage Image (1 max)")
    with col_replace:
        btn_label = "Replace" if current_collage else "Upload"
        replace_collage = st.button(btn_label, key="replace_collage_btn", use_container_width=True)

    # Replace/Upload collage uploader
    if replace_collage or st.session_state.get('show_collage_uploader'):
        st.session_state.show_collage_uploader = True
        uploaded_collage = st.file_uploader(
            "Upload collage image",
            type=['jpg', 'jpeg', 'png'],
            key="collage_uploader"
        )
        if uploaded_collage:
            with st.spinner("Uploading..."):
                # Delete old collage if exists
                if current_collage:
                    delete_from_storage(current_collage)

                # Generate path and upload
                file_path = generate_collage_path(user_id)
                url = upload_to_storage(uploaded_collage.getvalue(), file_path)

                if url:
                    # Replace array with single URL
                    if update_collage_images(user_id, [url]):
                        st.success("Collage uploaded successfully!")
                        st.session_state.show_collage_uploader = False
                        st.session_state.image_manager_user_data = fetch_user_by_id(user_id)
                        st.rerun()

    # Display collage image (fixed width 300px)
    if current_collage:
        col_img, col_spacer = st.columns([1, 2])
        with col_img:
            try:
                st.image(current_collage, width=300)
            except Exception:
                st.error("Failed to load collage")

            if st.button("Delete Collage", key="del_collage"):
                with st.spinner("Deleting..."):
                    delete_from_storage(current_collage)
                    if update_collage_images(user_id, [], clear_status=True):
                        st.success("Collage deleted!")
                        st.session_state.image_manager_user_data = fetch_user_by_id(user_id)
                        st.rerun()
    else:
        st.info("No collage image")

else:
    st.info("Enter a user_id and click Search to view/manage images")
