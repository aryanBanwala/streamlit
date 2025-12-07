"""
Human-in-the-Loop Approval Panel for Profile Status Workflow
Approve or undo profile matches before they are processed by Temporal.
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

# --- Supabase Connection ---
try:
    supabase = get_supabase_client()
except Exception as e:
    st.error(f"Supabase connection failed: {e}")
    st.stop()

# --- Constants ---
STATUS_PENDING = 'female_null-male_null-msg_human_approval_required'
STATUS_APPROVED = 'female_null-male_null-msg_human_approved'


# --- Data Fetch Functions ---
@st.cache_data(ttl=10)
def fetch_pending_profiles():
    """Fetch profiles awaiting human approval."""
    try:
        res = supabase.table('profiles').select('*').eq(
            'profile_status', STATUS_PENDING
        ).order('created_at', desc=True).execute()
        return res.data if res.data else []
    except Exception as e:
        st.error(f"Error fetching pending profiles: {e}")
        return []


@st.cache_data(ttl=10)
def fetch_approved_profiles():
    """Fetch profiles approved but not yet processed by Temporal."""
    try:
        res = supabase.table('profiles').select('*').eq(
            'profile_status', STATUS_APPROVED
        ).order('created_at', desc=True).execute()
        return res.data if res.data else []
    except Exception as e:
        st.error(f"Error fetching approved profiles: {e}")
        return []


@st.cache_data(ttl=30)
def fetch_user_metadata(user_id: str):
    """Fetch user metadata for display."""
    try:
        res = supabase.table('user_metadata').select(
            'user_id, name, age, height, religion, city, work_exp, education, '
            'profile_images, instagram_images, dating_preferences, gender'
        ).eq('user_id', user_id).maybe_single().execute()
        return res.data if res.data else {}
    except Exception as e:
        st.warning(f"Error fetching user {user_id}: {e}")
        return {}


def get_user_name(user_id: str) -> str:
    """Get user name from metadata."""
    meta = fetch_user_metadata(user_id)
    return meta.get('name', 'Unknown') if meta else 'Unknown'


# --- Status Update Functions ---
def approve_profile(profiles_id: str):
    """Update status from pending to approved."""
    try:
        supabase.table('profiles').update({
            'profile_status': STATUS_APPROVED
        }).eq('profiles_id', profiles_id).execute()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Failed to approve: {e}")
        return False


def undo_approval(profiles_id: str):
    """Undo approval - move back to pending."""
    try:
        supabase.table('profiles').update({
            'profile_status': STATUS_PENDING
        }).eq('profiles_id', profiles_id).execute()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Failed to undo: {e}")
        return False


# --- UI Helper Functions ---
def get_initiator_badge(profile: dict) -> str:
    """Return badge based on who initiated."""
    if profile.get('female_response'):
        return "💜 Liked by Female → If approved, female's profile will be sent to male"
    elif profile.get('male_response'):
        return "💙 Liked by Male → If approved, male's profile will be sent to female"
    return "❓ Unknown"


def display_user_card(meta: dict, label: str):
    """Display user info card."""
    st.markdown(f"**{label}**")

    if not meta:
        st.warning("No data found")
        return

    # Photos
    photos = meta.get('profile_images') or meta.get('instagram_images') or []
    if photos and isinstance(photos, list):
        display_photos = photos[:4]
        cols = st.columns(min(len(display_photos), 4))
        for idx, url in enumerate(display_photos):
            with cols[idx]:
                try:
                    st.image(url, use_container_width=True)
                except Exception:
                    st.caption("Image error")

    # Info table
    dating_prefs = meta.get('dating_preferences') or {}
    age_pref = dating_prefs.get('age_preference', 'N/A') if dating_prefs else 'N/A'

    info = {
        "Name": meta.get('name', 'N/A'),
        "Age": meta.get('age', 'N/A'),
        "Height": meta.get('height', 'N/A'),
        "Religion": meta.get('religion', 'N/A'),
        "City": meta.get('city', 'N/A'),
        "Age Preference": age_pref,
        "Work": meta.get('work_exp', 'N/A'),
        "Education": meta.get('education', 'N/A'),
    }

    for key, value in info.items():
        st.markdown(f"**{key}:** {value}")


# --- Initialize Session State ---
if 'selected_profile' not in st.session_state:
    st.session_state.selected_profile = None

# Check if redirected from Match Status page with a profile to select
if 'human_approval_select_profile' in st.session_state and st.session_state.human_approval_select_profile:
    st.session_state.selected_profile = st.session_state.human_approval_select_profile
    st.session_state.human_approval_select_profile = None  # Clear after use


# --- Fetch Data ---
pending_profiles = fetch_pending_profiles()
approved_profiles = fetch_approved_profiles()


# --- Sidebar ---
st.sidebar.title("Human Approval Panel")
st.sidebar.divider()

st.sidebar.metric("Pending Approval", len(pending_profiles))
st.sidebar.metric("Approved (Awaiting Temporal)", len(approved_profiles))

st.sidebar.divider()

# Approved profiles with undo option
if approved_profiles:
    st.sidebar.subheader("Approved (Undo Available)")
    st.sidebar.caption("These haven't been processed by Temporal yet, so you can undo.")

    for profile in approved_profiles:
        f_name = get_user_name(profile['female_user_id'])
        m_name = get_user_name(profile['male_user_id'])

        col1, col2 = st.sidebar.columns([3, 1])
        with col1:
            st.caption(f"{f_name} × {m_name}")
        with col2:
            if st.button("↩️", key=f"undo_{profile['profiles_id']}", help="Undo approval"):
                st.session_state[f"confirm_undo_{profile['profiles_id']}"] = True

        # Confirmation dialog for undo
        if st.session_state.get(f"confirm_undo_{profile['profiles_id']}"):
            st.sidebar.warning(f"Undo approval for {f_name} × {m_name}?")
            c1, c2 = st.sidebar.columns(2)
            with c1:
                if st.button("Yes", key=f"yes_undo_{profile['profiles_id']}"):
                    if undo_approval(profile['profiles_id']):
                        st.sidebar.success("Undone!")
                        st.session_state[f"confirm_undo_{profile['profiles_id']}"] = False
                        st.rerun()
            with c2:
                if st.button("No", key=f"no_undo_{profile['profiles_id']}"):
                    st.session_state[f"confirm_undo_{profile['profiles_id']}"] = False
                    st.rerun()
else:
    st.sidebar.info("No approved profiles awaiting Temporal.")


# --- Main Content ---
col_title, col_refresh = st.columns([4, 1])
with col_title:
    st.title("Human Approval Queue")
with col_refresh:
    if st.button("🔄 Refresh", use_container_width=True, type="primary"):
        st.cache_data.clear()
        st.rerun()

if not pending_profiles:
    st.info("No profiles pending approval. All caught up!")
    st.stop()

# Two column layout
left_col, right_col = st.columns([1, 2])

# --- Left Panel: Pending Profiles List ---
with left_col:
    st.subheader(f"Pending ({len(pending_profiles)})")

    for idx, profile in enumerate(pending_profiles):
        f_name = get_user_name(profile['female_user_id'])
        m_name = get_user_name(profile['male_user_id'])
        badge = get_initiator_badge(profile)
        created = profile.get('created_at', '')[:10] if profile.get('created_at') else ''

        # Card button
        card_label = f"**{f_name} × {m_name}**\n\n{badge}\n\n{created}"

        if st.button(
            f"{f_name} × {m_name}",
            key=f"select_{profile['profiles_id']}",
            use_container_width=True,
            type="secondary" if st.session_state.selected_profile != profile['profiles_id'] else "primary"
        ):
            st.session_state.selected_profile = profile['profiles_id']
            st.rerun()

        st.caption(f"{badge} | {created}")
        st.divider()

# --- Right Panel: Profile Details ---
with right_col:
    if st.session_state.selected_profile:
        # Find selected profile
        selected = next(
            (p for p in pending_profiles if p['profiles_id'] == st.session_state.selected_profile),
            None
        )

        if selected:
            st.subheader("Profile Details")

            # Initiator badge
            badge = get_initiator_badge(selected)
            st.info(f"**Initiator:** {badge}")

            # Two columns for female and male
            f_col, m_col = st.columns(2)

            with f_col:
                f_meta = fetch_user_metadata(selected['female_user_id'])
                display_user_card(f_meta, "👩 Female")
                st.caption(f"ID: {selected['female_user_id']}")

            with m_col:
                m_meta = fetch_user_metadata(selected['male_user_id'])
                display_user_card(m_meta, "👨 Male")
                st.caption(f"ID: {selected['male_user_id']}")

            st.divider()

            # Approve button
            if st.session_state.get(f"confirm_approve_{selected['profiles_id']}"):
                st.warning("Are you sure you want to approve this match?")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Yes, Approve", key="yes_approve", type="primary"):
                        if approve_profile(selected['profiles_id']):
                            st.success("Approved! Profile will be processed by Temporal.")
                            st.session_state.selected_profile = None
                            st.session_state[f"confirm_approve_{selected['profiles_id']}"] = False
                            st.rerun()
                with c2:
                    if st.button("Cancel", key="cancel_approve"):
                        st.session_state[f"confirm_approve_{selected['profiles_id']}"] = False
                        st.rerun()
            else:
                if st.button("Approve Match", key="approve_btn", type="primary", use_container_width=True):
                    st.session_state[f"confirm_approve_{selected['profiles_id']}"] = True
                    st.rerun()
        else:
            st.warning("Profile not found. It may have been processed.")
            st.session_state.selected_profile = None
    else:
        st.info("👈 Select a profile from the left panel to view details.")
