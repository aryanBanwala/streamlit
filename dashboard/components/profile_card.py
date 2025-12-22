"""
Profile card components for displaying user information.
"""
import streamlit as st
from typing import Optional, List


def profile_card(
    user: dict,
    show_contact: bool = False,
    show_actions: bool = False,
    key_prefix: str = ""
) -> Optional[bool]:
    """
    Display a full user profile card.

    Args:
        user: User data dict
        show_contact: Whether to show contact info
        show_actions: Whether to show action buttons
        key_prefix: Unique key prefix for buttons

    Returns:
        True if action button clicked, None otherwise
    """
    name = user.get('name', 'Unknown')
    age = user.get('age', '')
    gender = user.get('gender', '')
    city = user.get('city', '')
    area = user.get('area', '')

    # Header
    st.markdown(f"### {name}")

    # Location
    location = ', '.join(filter(None, [area, city]))

    # Info grid
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Age:** {age or 'N/A'}")
        st.markdown(f"**Gender:** {gender or 'N/A'}")
    with col2:
        st.markdown(f"**Location:** {location or 'N/A'}")
        st.markdown(f"**Religion:** {user.get('religion', 'N/A')}")

    # Additional info
    if user.get('work_exp') or user.get('education'):
        st.markdown(f"**Work:** {user.get('work_exp', 'N/A')}")
        st.markdown(f"**Education:** {user.get('education', 'N/A')}")

    if user.get('attractiveness'):
        st.markdown(f"**Attractiveness:** {user.get('attractiveness')}")

    if user.get('professional_tier'):
        st.markdown(f"**Professional Tier:** {user.get('professional_tier')}")

    # Contact info
    if show_contact:
        st.divider()
        st.markdown(f"**Phone:** {user.get('phone_num', 'N/A')}")
        st.markdown(f"**Email:** {user.get('email', 'N/A')}")

    # Images
    photos = user.get('profile_images') or user.get('instagram_images') or user.get('collage_images') or []
    if photos:
        user_images_gallery(photos)

    # Actions
    if show_actions:
        st.divider()
        return st.button("View Details", key=f"{key_prefix}_view", use_container_width=True)

    return None


def profile_card_mini(
    user: dict,
    show_image: bool = True,
    image_width: int = 100
) -> None:
    """
    Display a compact user profile card.

    Args:
        user: User data dict
        show_image: Whether to show profile image
        image_width: Width of profile image
    """
    name = user.get('name', 'Unknown')
    age = user.get('age', '')
    gender = user.get('gender', '')
    city = user.get('city', '')

    # Image
    if show_image:
        photos = user.get('profile_images') or user.get('instagram_images') or []
        if photos:
            try:
                st.image(photos[0], width=image_width)
            except Exception:
                st.markdown("No photo")
        else:
            st.markdown("No photo")

    # Basic info
    st.markdown(f"**{name}**, {age}")
    if gender:
        gender_icon = "M" if gender == 'male' else "F" if gender == 'female' else "?"
        st.caption(f"{gender_icon} | {city or 'N/A'}")


def user_images_gallery(
    photos: List[str],
    height: int = 300,
    max_images: int = 10
) -> None:
    """
    Display user photos in a horizontal scrollable gallery.

    Args:
        photos: List of image URLs
        height: Height of images
        max_images: Maximum number of images to show
    """
    if not photos or not isinstance(photos, list):
        st.markdown("""
        <div style="height: 150px; background: #2d2d2d; border-radius: 8px;
                    display: flex; align-items: center; justify-content: center; color: #888;">
            No images available
        </div>
        """, unsafe_allow_html=True)
        return

    images_html = ""
    for url in photos[:max_images]:
        images_html += f'''
        <img src="{url}"
             style="height: {height}px; width: auto; object-fit: cover;
                    border-radius: 8px; flex-shrink: 0;"
             loading="lazy">
        '''

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


def profile_comparison(
    user1: dict,
    user2: dict,
    label1: str = "User 1",
    label2: str = "User 2"
) -> None:
    """
    Display two profiles side by side for comparison.

    Args:
        user1: First user data
        user2: Second user data
        label1: Label for first user
        label2: Label for second user
    """
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"#### {label1}")
        profile_card(user1)

    with col2:
        st.markdown(f"#### {label2}")
        profile_card(user2)
