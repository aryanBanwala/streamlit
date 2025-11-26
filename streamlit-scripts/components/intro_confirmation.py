import streamlit as st

def render_intro_confirmation(
    message: str,
    profile: dict,
    selected_button: str = None,
    key_prefix: str = "intro"
):
    """
    Render intro confirmation card with Yes/No buttons (similar to IntroConfirmation.tsx)

    Args:
        message: The confirmation message to display
        profile: Dict with name, age, work, location, religion
        selected_button: 'yes', 'no', or None if not yet selected
        key_prefix: Unique key prefix for buttons

    Returns:
        str or None: 'yes' if yes clicked, 'no' if no clicked, None otherwise
    """
    name = profile.get('name', 'Unknown')
    age = profile.get('age', '?')
    work = profile.get('work', '')
    location = profile.get('location', '')
    religion = profile.get('religion', '')

    # Container with styling
    with st.container():
        # Message
        st.write(message)

        # Profile Card (simplified)
        with st.container():
            st.markdown(
                f"""
                <div style="background: rgba(0,0,0,0.05); border-radius: 12px; padding: 12px; margin: 8px 0;">
                    <h4 style="margin: 0 0 8px 0;">{name}, {age}</h4>
                    <div style="display: flex; flex-wrap: wrap; gap: 8px;">
                """,
                unsafe_allow_html=True
            )

            # Badges
            badges_html = ""
            if location:
                badges_html += f'<span style="background: rgba(255,255,255,0.8); padding: 4px 10px; border-radius: 20px; font-size: 12px;">📍 {location}</span>'
            if religion:
                badges_html += f'<span style="background: rgba(255,255,255,0.8); padding: 4px 10px; border-radius: 20px; font-size: 12px;">🙏 {religion}</span>'
            if work:
                badges_html += f'<span style="background: rgba(255,255,255,0.8); padding: 4px 10px; border-radius: 20px; font-size: 12px;">💼 {work}</span>'

            st.markdown(
                f"""
                    {badges_html}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

        # Buttons
        result = None

        if selected_button is None:
            # Show clickable buttons
            col1, col2 = st.columns(2)
            with col1:
                if st.button("no", key=f"{key_prefix}_no", use_container_width=True):
                    result = 'no'
            with col2:
                if st.button("✓ yes", key=f"{key_prefix}_yes", use_container_width=True):
                    result = 'yes'
        else:
            # Show selected state (disabled buttons)
            col1, col2 = st.columns(2)
            with col1:
                if selected_button == 'no':
                    st.markdown(
                        '<div style="background: rgba(0,0,0,0.1); padding: 8px; border-radius: 8px; text-align: center; font-weight: 500;">no</div>',
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        '<div style="background: white; padding: 8px; border-radius: 8px; text-align: center; color: #9ca3af; opacity: 0.5;">no</div>',
                        unsafe_allow_html=True
                    )
            with col2:
                if selected_button == 'yes':
                    st.markdown(
                        '<div style="background: rgba(0,0,0,0.1); padding: 8px; border-radius: 8px; text-align: center; font-weight: 500;">✓ yes</div>',
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        '<div style="background: white; padding: 8px; border-radius: 8px; text-align: center; color: #9ca3af; opacity: 0.5;">✓ yes</div>',
                        unsafe_allow_html=True
                    )

        return result


def render_intro_confirmation_readonly(
    message: str,
    profile: dict,
    selected_button: str = None
):
    """
    Render intro confirmation in read-only mode (for viewing past chats)
    No interactive buttons, just displays the state

    Args:
        message: The confirmation message
        profile: Dict with name, age, work, location, religion
        selected_button: 'yes', 'no', or None
    """
    name = profile.get('name', 'Unknown')
    age = profile.get('age', '?')
    work = profile.get('work', '')
    location = profile.get('location', '')
    religion = profile.get('religion', '')

    with st.container():
        # Card container
        st.markdown(
            """
            <div style="background: white; border-radius: 12px; padding: 12px 16px; border: 1px solid rgba(0,0,0,0.1); margin: 8px 0;">
            """,
            unsafe_allow_html=True
        )

        # Message
        st.write(message)

        # Profile info
        st.markdown(f"**{name}, {age}**")

        badges = []
        if location:
            badges.append(f"📍 {location}")
        if religion:
            badges.append(f"🙏 {religion}")
        if work:
            badges.append(f"💼 {work}")

        if badges:
            st.caption(" • ".join(badges))

        # Show selection result
        if selected_button == 'yes':
            st.success("✓ User selected: Yes")
        elif selected_button == 'no':
            st.error("User selected: No")
        else:
            st.info("No selection made")

        st.markdown("</div>", unsafe_allow_html=True)
