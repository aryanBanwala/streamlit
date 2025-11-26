import streamlit as st
from .profile_card import render_profile_card_compact
from .profile_drawer import render_profile_drawer

def render_profile_batch(profiles: list, batch_id: str = "batch"):
    """
    Render multiple profile cards in a horizontal layout (similar to ProfileBatch.tsx)

    Args:
        profiles: List of profile dicts with position, userId, resultId, metadata
        batch_id: Unique identifier for this batch (for keys)
    """
    if not profiles or len(profiles) == 0:
        st.info("No profiles to display")
        return

    # Sort by position
    sorted_profiles = sorted(profiles, key=lambda p: int(p.get('position', 0)))

    # Header
    st.caption(f"{len(profiles)} profile{'s' if len(profiles) > 1 else ''}")

    # Use columns for horizontal layout
    cols = st.columns(min(len(sorted_profiles), 3))

    # Track which profile to show details for
    selected_profile_key = f"{batch_id}_selected_profile"
    if selected_profile_key not in st.session_state:
        st.session_state[selected_profile_key] = None

    for idx, profile in enumerate(sorted_profiles):
        col_idx = idx % 3
        with cols[col_idx]:
            render_single_profile_in_batch(profile, f"{batch_id}_{idx}")

            # "Tell me more" button
            if st.button("tell me more →", key=f"{batch_id}_{idx}_more", use_container_width=True):
                st.session_state[selected_profile_key] = profile

    # Show profile drawer if one is selected
    if st.session_state[selected_profile_key] is not None:
        profile = st.session_state[selected_profile_key]
        metadata = profile.get('metadata', profile)
        name = metadata.get('name', 'Profile')

        st.divider()
        with st.expander(f"📋 {name}'s Full Profile", expanded=True):
            render_profile_drawer(profile)

            if st.button("Close", key=f"{batch_id}_close"):
                st.session_state[selected_profile_key] = None
                st.rerun()


def render_single_profile_in_batch(profile: dict, key_prefix: str):
    """
    Render a single profile card within a batch

    Args:
        profile: Profile dict with metadata
        key_prefix: Unique key prefix
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
    religion = metadata.get('religion', '')
    work = metadata.get('work', '')
    bio_text = metadata.get('short_intro') or metadata.get('vibe_check') or ''

    # Card container
    with st.container():
        # Image
        if image_url:
            try:
                st.image(image_url, use_container_width=True)
            except:
                st.info("📷 No photo")
        else:
            st.info("📷 No photo")

        # Name & Age
        st.markdown(f"**{name}, {age}**")

        # Badges (compact)
        badges = []
        if location:
            badges.append(f"📍 {location}")
        if religion:
            badges.append(f"🙏 {religion}")
        if work:
            badges.append(f"💼 {work}")

        if badges:
            st.caption(" | ".join(badges[:2]))  # Show max 2 badges

        # Bio (short)
        if bio_text:
            display_bio = bio_text[:100] + "..." if len(bio_text) > 100 else bio_text
            st.caption(display_bio)


def render_profile_batch_readonly(profiles: list, batch_id: str = "batch"):
    """
    Render profile batch in read-only mode (no interactive buttons)
    Good for viewing past chat history

    Args:
        profiles: List of profile dicts
        batch_id: Unique identifier for this batch
    """
    if not profiles or len(profiles) == 0:
        st.info("No profiles to display")
        return

    # Sort by position
    sorted_profiles = sorted(profiles, key=lambda p: int(p.get('position', 0)))

    # Header
    st.caption(f"🔍 {len(profiles)} profile{'s' if len(profiles) > 1 else ''} shown")

    # Use columns
    cols = st.columns(min(len(sorted_profiles), 3))

    for idx, profile in enumerate(sorted_profiles):
        col_idx = idx % 3
        metadata = profile.get('metadata', profile)

        with cols[col_idx]:
            # Handle collage_image
            collage_image = metadata.get('collage_image')
            if isinstance(collage_image, list) and len(collage_image) > 0:
                image_url = collage_image[0]
            elif isinstance(collage_image, str):
                image_url = collage_image
            else:
                image_url = None

            # Show image
            if image_url:
                try:
                    st.image(image_url, use_container_width=True)
                except:
                    pass

            # Name & Age
            name = metadata.get('name', 'Unknown')
            age = metadata.get('age', '?')
            st.markdown(f"**{name}, {age}**")

            # Location
            location = metadata.get('location', '')
            if location:
                st.caption(f"📍 {location}")

            # Show expander for more details
            with st.expander("View details"):
                render_profile_drawer(profile)
