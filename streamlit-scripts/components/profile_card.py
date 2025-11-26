import streamlit as st

def render_profile_card(profile: dict, on_click_key: str = None):
    """
    Render a single profile card (similar to ProfileCard.tsx)

    Args:
        profile: Dict with keys like name, age, collage_image, location, religion, work, short_intro, etc.
        on_click_key: Unique key for the "tell me more" button

    Returns:
        bool: True if "tell me more" was clicked
    """
    metadata = profile.get('metadata', profile)

    # Handle collage_image (can be string or list)
    collage_image = metadata.get('collage_image')
    if isinstance(collage_image, list) and len(collage_image) > 0:
        image_url = collage_image[0]
    elif isinstance(collage_image, str):
        image_url = collage_image
    else:
        image_url = None

    # Collect badges
    badges = []
    if metadata.get('location', '').strip():
        badges.append(('📍', metadata['location']))
    if metadata.get('religion', '').strip():
        badges.append(('🙏', metadata['religion']))
    if metadata.get('work', '').strip():
        badges.append(('💼', metadata['work']))
    badges = badges[:3]  # Max 3 badges

    # Bio text
    bio_text = metadata.get('short_intro') or metadata.get('vibe_check') or 'No bio available'

    # Card container
    with st.container():
        # Use columns for card-like appearance
        st.markdown("""
        <style>
        .profile-card {
            background: white;
            border-radius: 16px;
            padding: 12px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            width: 240px;
            min-height: 400px;
        }
        .profile-badge {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 2px 8px;
            background: #f3f4f6;
            border-radius: 12px;
            font-size: 10px;
            color: #374151;
            margin-right: 4px;
            margin-bottom: 4px;
        }
        </style>
        """, unsafe_allow_html=True)

        # Image
        if image_url:
            try:
                st.image(image_url, use_container_width=True)
            except:
                st.info("📷 No photo")
        else:
            st.info("📷 No photo")

        # Name & Age
        name = metadata.get('name', 'Unknown')
        age = metadata.get('age', '?')
        st.markdown(f"**{name}, {age}**")

        # Badges
        if badges:
            badge_html = ""
            for icon, text in badges:
                badge_html += f'<span class="profile-badge">{icon} {text}</span>'
            st.markdown(badge_html, unsafe_allow_html=True)

        # Bio (truncated)
        if len(bio_text) > 150:
            bio_text = bio_text[:150] + "..."
        st.caption(bio_text)

        # Tell me more button
        clicked = False
        if on_click_key:
            clicked = st.button("tell me more →", key=on_click_key, use_container_width=True)

        return clicked


def render_profile_card_compact(profile: dict, position: int = 1):
    """
    Render a compact version of profile card for horizontal display
    """
    metadata = profile.get('metadata', profile)

    # Handle collage_image
    collage_image = metadata.get('collage_image')
    if isinstance(collage_image, list) and len(collage_image) > 0:
        image_url = collage_image[0]
    elif isinstance(collage_image, str):
        image_url = collage_image
    else:
        image_url = None

    name = metadata.get('name', 'Unknown')
    age = metadata.get('age', '?')
    location = metadata.get('location', '')

    # Simple card
    if image_url:
        try:
            st.image(image_url, use_container_width=True)
        except:
            st.info("📷")

    st.markdown(f"**{name}, {age}**")
    if location:
        st.caption(f"📍 {location}")
