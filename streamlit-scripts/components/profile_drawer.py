import streamlit as st

def render_profile_drawer(profile: dict):
    """
    Render detailed profile view (similar to ProfileDrawer.tsx)
    Shows: Why you both, Vibe check, You should know, Image, Interesting things, Journey, Others

    Args:
        profile: Dict with metadata containing all profile fields
    """
    metadata = profile.get('metadata', profile)
    name = metadata.get('name', 'Unknown')
    gender = metadata.get('gender', '').lower()

    # Header
    st.markdown(f"## Meet {name}")

    # Handle collage_image
    collage_image = metadata.get('collage_image')
    if isinstance(collage_image, list) and len(collage_image) > 0:
        image_url = collage_image[0]
    elif isinstance(collage_image, str):
        image_url = collage_image
    else:
        image_url = None

    # Why You Both Section
    why_you_both = metadata.get('why_you_both')
    if why_you_both:
        with st.container():
            st.markdown("### 👫 Why you both?")
            st.write(why_you_both)

    # Vibe Check Section
    vibe_check = metadata.get('vibe_check')
    if vibe_check:
        with st.container():
            st.markdown("### ✨ Vibe check")
            st.write(vibe_check)

    # You Should Know Section
    you_should_know = metadata.get('you_should_know')
    if you_should_know:
        with st.container():
            st.markdown("### 💡 You should know")
            st.write(you_should_know)

    st.divider()

    # Image
    if image_url:
        try:
            st.image(image_url, use_container_width=True)
        except:
            pass

    # Interesting Things Section
    interesting_things = metadata.get('interesting_things', [])
    if interesting_things:
        st.markdown("### You might find this interesting")
        icons = ['🎯', '⚡', '🎯']
        for idx, item in enumerate(interesting_things):
            icon = icons[idx % len(icons)]
            subject = item.get('subject', '')
            mssg = item.get('mssg', '')
            with st.container():
                st.markdown(f"**{icon} {subject}**")
                st.write(mssg)

    # Journey Section
    journey = metadata.get('journey', [])
    if journey:
        pronoun = "Her" if gender == 'female' else "His"
        st.markdown(f"### {pronoun} journey so far")
        for idx, step in enumerate(journey):
            st.markdown(f"🔶 {step}")

    # Others Section
    others = metadata.get('others', [])
    if others:
        st.markdown("### Other things that might matter")
        for item in others:
            key = item.get('key', '')
            val = item.get('val', '')
            st.markdown(f"**{key}:** {val}")


def render_profile_expander(profile: dict, expanded: bool = False):
    """
    Render profile details inside an expander

    Args:
        profile: Dict with metadata
        expanded: Whether expander should be open by default
    """
    metadata = profile.get('metadata', profile)
    name = metadata.get('name', 'Unknown')
    age = metadata.get('age', '?')

    with st.expander(f"📋 {name}'s Full Profile", expanded=expanded):
        render_profile_drawer(profile)


def render_profile_modal(profile: dict, key_prefix: str = "profile"):
    """
    Render profile as a dialog/modal (using Streamlit's dialog feature if available)
    Falls back to expander if dialog not available

    Args:
        profile: Dict with metadata
        key_prefix: Unique key prefix for dialog
    """
    # Check if dialog is available (Streamlit 1.30+)
    if hasattr(st, 'dialog'):
        @st.dialog(f"Profile Details")
        def show_profile():
            render_profile_drawer(profile)

        if st.button("View Full Profile", key=f"{key_prefix}_btn"):
            show_profile()
    else:
        # Fallback to expander
        render_profile_expander(profile, expanded=False)
