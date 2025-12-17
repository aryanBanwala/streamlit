"""
Match Stats - Comprehensive analytics dashboard for user matches.
View overview metrics, search user match history, and analyze trends.
"""
import streamlit as st
import pandas as pd
import os
import sys
from datetime import datetime, date, timedelta
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


# --- Data Fetching Functions ---
def fetch_all_paginated(query_builder, page_size=1000):
    """Fetch all records using pagination to bypass 1000 row limit."""
    all_data = []
    offset = 0
    while True:
        res = query_builder.range(offset, offset + page_size - 1).execute()
        if not res.data:
            break
        all_data.extend(res.data)
        if len(res.data) < page_size:
            break
        offset += page_size
    return all_data


@st.cache_data(ttl=300)
def fetch_filter_options():
    """Fetch distinct run_ids and origin_phases for filter dropdowns."""
    try:
        # Get distinct run_ids - paginated
        run_data = fetch_all_paginated(supabase.table('user_matches').select('run_id'))
        run_ids = list(set(r['run_id'] for r in run_data if r.get('run_id')))

        # Get distinct origin_phases - paginated
        phase_data = fetch_all_paginated(supabase.table('user_matches').select('origin_phase'))
        phases = list(set(p['origin_phase'] for p in phase_data if p.get('origin_phase')))

        return sorted(run_ids), sorted(phases)
    except Exception as e:
        st.error(f"Error fetching filter options: {e}")
        return [], []


@st.cache_data(ttl=120)
def fetch_overview_stats(run_id=None, origin_phase=None, start_date=None, end_date=None):
    """Fetch matches with optional filters for overview stats."""
    try:
        query = supabase.table('user_matches').select(
            'match_id, current_user_id, matched_user_id, is_liked, is_viewed, is_mutual, mutual_score, know_more_count, origin_phase, created_at'
        )

        if run_id:
            query = query.eq('run_id', run_id)
        if origin_phase:
            query = query.eq('origin_phase', origin_phase)
        if start_date:
            query = query.gte('created_at', str(start_date))
        if end_date:
            query = query.lte('created_at', str(end_date))

        # Fetch all with pagination
        return fetch_all_paginated(query)
    except Exception as e:
        st.error(f"Error fetching overview stats: {e}")
        return []


@st.cache_data(ttl=120)
def fetch_user_genders(user_ids: list):
    """Fetch gender for a list of user_ids from user_metadata."""
    if not user_ids:
        return {}
    try:
        # Batch fetch in chunks of 500 to avoid query limits
        gender_map = {}
        for i in range(0, len(user_ids), 500):
            chunk = user_ids[i:i+500]
            res = supabase.table('user_metadata').select('user_id, gender').in_('user_id', chunk).execute()
            if res.data:
                for u in res.data:
                    gender_map[u['user_id']] = u.get('gender')
        return gender_map
    except Exception as e:
        return {}


@st.cache_data(ttl=60)
def fetch_user_matches(user_id: str):
    """Fetch all matches for a specific user (as current_user_id or matched_user_id)."""
    try:
        # As current user (outbound)
        outbound = supabase.table('user_matches').select(
            'match_id, matched_user_id, is_liked, is_viewed, is_mutual, mutual_score, '
            'viewer_scores_candidate, candidate_scores_viewer, rank, origin_phase, created_at, know_more_count'
        ).eq('current_user_id', user_id).order('created_at', desc=True).execute()

        # As matched user (inbound)
        inbound = supabase.table('user_matches').select(
            'match_id, current_user_id, is_liked, is_viewed, is_mutual, mutual_score, '
            'viewer_scores_candidate, candidate_scores_viewer, rank, origin_phase, created_at, know_more_count'
        ).eq('matched_user_id', user_id).order('created_at', desc=True).execute()

        return outbound.data or [], inbound.data or []
    except Exception as e:
        st.error(f"Error fetching user matches: {e}")
        return [], []


@st.cache_data(ttl=60)
def fetch_user_profile(user_id: str):
    """Fetch user profile from user_metadata."""
    try:
        res = supabase.table('user_metadata').select(
            'user_id, name, age, gender, city, area, phone_num, work_exp, education, '
            'profile_images, instagram_images, collage_images, attractiveness, religion'
        ).eq('user_id', user_id).maybe_single().execute()
        return res.data
    except Exception as e:
        return None


@st.cache_data(ttl=60)
def fetch_user_contact_batch(user_ids: list):
    """Batch fetch user emails and phones from user_data table."""
    if not user_ids:
        return {}, {}
    try:
        email_map = {}
        phone_map = {}
        for i in range(0, len(user_ids), 500):
            chunk = user_ids[i:i+500]
            res = supabase.table('user_data').select('user_id, user_email, user_phone').in_('user_id', chunk).execute()
            if res.data:
                for u in res.data:
                    email_map[u['user_id']] = u.get('user_email')
                    phone_map[u['user_id']] = u.get('user_phone')
        return email_map, phone_map
    except Exception as e:
        return {}, {}


@st.cache_data(ttl=60)
def fetch_user_profiles_batch(user_ids: list):
    """Batch fetch user profiles from user_metadata."""
    if not user_ids:
        return {}
    try:
        res = supabase.table('user_metadata').select(
            'user_id, name, age, gender, city, phone_num, profile_images, instagram_images'
        ).in_('user_id', user_ids).execute()
        return {u['user_id']: u for u in res.data} if res.data else {}
    except Exception as e:
        return {}


@st.cache_data(ttl=300)
def fetch_daily_stats(days=30, run_id=None, origin_phase=None):
    """Fetch matches for time-series trends."""
    try:
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        query = supabase.table('user_matches').select(
            'created_at, is_liked, is_viewed, is_mutual'
        ).gte('created_at', start_date)

        if run_id:
            query = query.eq('run_id', run_id)
        if origin_phase:
            query = query.eq('origin_phase', origin_phase)

        # Fetch all with pagination
        return fetch_all_paginated(query)
    except Exception as e:
        st.error(f"Error fetching daily stats: {e}")
        return []


def display_user_images(photos: list, height: int = 300):
    """Display user photos in a horizontal scrollable container."""
    if photos and isinstance(photos, list):
        images_html = ""
        for url in photos[:10]:  # Limit to 10 images
            images_html += f'<img src="{url}" style="height: {height}px; width: auto; object-fit: cover; border-radius: 8px; flex-shrink: 0;">'

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
        <div style="height: 150px; background: #2d2d2d; border-radius: 8px; display: flex; align-items: center; justify-content: center; color: #888;">
            No images available
        </div>
        """, unsafe_allow_html=True)


def display_profile_card(user_data: dict):
    """Display a user profile card with details."""
    if not user_data:
        st.warning("User profile not found")
        return

    name = user_data.get('name', 'Unknown')
    age = user_data.get('age', '')
    gender = user_data.get('gender', '')
    city = user_data.get('city', '')
    area = user_data.get('area', '')
    phone = user_data.get('phone_num', '')
    work = user_data.get('work_exp', '')
    education = user_data.get('education', '')
    attractiveness = user_data.get('attractiveness', '')
    religion = user_data.get('religion', '')

    # Build location string
    location = ', '.join(filter(None, [area, city]))

    st.markdown(f"### {name}")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"**Age:** {age if age else 'N/A'}")
        st.markdown(f"**Gender:** {gender if gender else 'N/A'}")
    with col2:
        st.markdown(f"**Location:** {location if location else 'N/A'}")
        st.markdown(f"**Religion:** {religion if religion else 'N/A'}")
    with col3:
        st.markdown(f"**Phone:** {phone if phone else 'N/A'}")
        st.markdown(f"**Attractiveness:** {attractiveness if attractiveness else 'N/A'}")

    if work or education:
        st.markdown(f"**Work:** {work if work else 'N/A'} | **Education:** {education if education else 'N/A'}")

    # Display images
    photos = user_data.get('profile_images') or user_data.get('instagram_images') or user_data.get('collage_images') or []
    display_user_images(photos, height=350)


# --- Session State Initialization ---
if 'ms_search_user_id' not in st.session_state:
    st.session_state.ms_search_user_id = ""
if 'ms_last_run_id' not in st.session_state:
    st.session_state.ms_last_run_id = None
if 'ms_last_phase' not in st.session_state:
    st.session_state.ms_last_phase = None


# --- Sidebar: Filters ---
st.sidebar.header("Filters")

# Fetch filter options
run_ids, origin_phases = fetch_filter_options()

# Run ID filter
run_options = ["All"] + run_ids
selected_run = st.sidebar.selectbox("Run ID", options=run_options, index=0)
run_id_filter = None if selected_run == "All" else selected_run

# Origin Phase filter
phase_options = ["All"] + origin_phases
selected_phase = st.sidebar.selectbox("Origin Phase", options=phase_options, index=0)
phase_filter = None if selected_phase == "All" else selected_phase

# Date Range filter
st.sidebar.subheader("Date Range")
col1, col2 = st.sidebar.columns(2)
with col1:
    start_date = st.date_input("From", value=date.today() - timedelta(days=30))
with col2:
    end_date = st.date_input("To", value=date.today())

st.sidebar.divider()

# Refresh button
if st.sidebar.button("Refresh Data", use_container_width=True, type="primary"):
    st.cache_data.clear()
    st.rerun()

# Handle filter changes - clear cache
if run_id_filter != st.session_state.ms_last_run_id or phase_filter != st.session_state.ms_last_phase:
    st.session_state.ms_last_run_id = run_id_filter
    st.session_state.ms_last_phase = phase_filter


# --- Main Content ---
st.title("Match Stats")

# Tabs
tab_overview, tab_user, tab_mutual, tab_male_likes, tab_female_likes, tab_trends = st.tabs(["Overview", "User Search", "Mutual Likes", "Male Likes", "Female Likes", "Trends"])


# --- Tab 1: Overview ---
with tab_overview:
    st.subheader("Match Overview")

    # Fetch data with filters
    matches_data = fetch_overview_stats(
        run_id=run_id_filter,
        origin_phase=phase_filter,
        start_date=start_date,
        end_date=end_date
    )

    if not matches_data:
        st.info("No matches found for the selected filters.")
    else:
        df = pd.DataFrame(matches_data)
        total_count = len(df)

        # Fetch gender data for all current_user_ids
        all_user_ids = list(set(df['current_user_id'].tolist()))
        with st.spinner("Loading gender data..."):
            gender_map = fetch_user_genders(all_user_ids)

        # Add gender column to dataframe
        df['sender_gender'] = df['current_user_id'].map(gender_map)

        # Split data by gender
        df_male = df[df['sender_gender'] == 'male']
        df_female = df[df['sender_gender'] == 'female']

        # Calculate all stats for combined, male, female
        def calc_stats(data):
            total = len(data)
            liked = len(data[data['is_liked'] == 'liked'])
            disliked = len(data[data['is_liked'] == 'disliked'])
            passed = len(data[data['is_liked'] == 'passed'])
            viewed = int(data['is_viewed'].sum()) if 'is_viewed' in data.columns else 0
            mutual = int(data['is_mutual'].sum()) if 'is_mutual' in data.columns else 0
            avg_mutual = data['mutual_score'].dropna().mean()
            avg_know = data['know_more_count'].dropna().mean()
            return {
                'total': total,
                'liked': liked,
                'disliked': disliked,
                'passed': passed,
                'viewed': viewed,
                'mutual': mutual,
                'avg_mutual': avg_mutual,
                'avg_know': avg_know,
                'like_rate': (liked / total * 100) if total > 0 else 0,
                'dislike_rate': (disliked / total * 100) if total > 0 else 0,
                'pass_rate': (passed / total * 100) if total > 0 else 0,
                'view_rate': (viewed / total * 100) if total > 0 else 0,
                'mutual_rate': (mutual / total * 100) if total > 0 else 0,
            }

        stats_combined = calc_stats(df)
        stats_male = calc_stats(df_male)
        stats_female = calc_stats(df_female)

        # Display metrics in 3 columns: Combined, Male, Female
        st.markdown("### Core Metrics")

        # Headers
        col_label, col_combined, col_male, col_female = st.columns([1.5, 1, 1, 1])
        with col_label:
            st.markdown("**Metric**")
        with col_combined:
            st.markdown("**Combined**")
        with col_male:
            st.markdown("**Male**")
        with col_female:
            st.markdown("**Female**")

        # Total Matches
        col_label, col_combined, col_male, col_female = st.columns([1.5, 1, 1, 1])
        with col_label:
            st.markdown("Total Matches")
        with col_combined:
            st.metric("", f"{stats_combined['total']:,}", label_visibility="collapsed")
        with col_male:
            st.metric("", f"{stats_male['total']:,}", label_visibility="collapsed")
        with col_female:
            st.metric("", f"{stats_female['total']:,}", label_visibility="collapsed")

        # Likes
        col_label, col_combined, col_male, col_female = st.columns([1.5, 1, 1, 1])
        with col_label:
            st.markdown("Likes")
        with col_combined:
            st.metric("", f"{stats_combined['liked']:,}", f"{stats_combined['like_rate']:.1f}%", label_visibility="collapsed")
        with col_male:
            st.metric("", f"{stats_male['liked']:,}", f"{stats_male['like_rate']:.1f}%", label_visibility="collapsed")
        with col_female:
            st.metric("", f"{stats_female['liked']:,}", f"{stats_female['like_rate']:.1f}%", label_visibility="collapsed")

        # Dislikes
        col_label, col_combined, col_male, col_female = st.columns([1.5, 1, 1, 1])
        with col_label:
            st.markdown("Dislikes")
        with col_combined:
            st.metric("", f"{stats_combined['disliked']:,}", f"{stats_combined['dislike_rate']:.1f}%", label_visibility="collapsed")
        with col_male:
            st.metric("", f"{stats_male['disliked']:,}", f"{stats_male['dislike_rate']:.1f}%", label_visibility="collapsed")
        with col_female:
            st.metric("", f"{stats_female['disliked']:,}", f"{stats_female['dislike_rate']:.1f}%", label_visibility="collapsed")

        # Passed
        col_label, col_combined, col_male, col_female = st.columns([1.5, 1, 1, 1])
        with col_label:
            st.markdown("Passed")
        with col_combined:
            st.metric("", f"{stats_combined['passed']:,}", f"{stats_combined['pass_rate']:.1f}%", label_visibility="collapsed")
        with col_male:
            st.metric("", f"{stats_male['passed']:,}", f"{stats_male['pass_rate']:.1f}%", label_visibility="collapsed")
        with col_female:
            st.metric("", f"{stats_female['passed']:,}", f"{stats_female['pass_rate']:.1f}%", label_visibility="collapsed")

        st.divider()
        st.markdown("### Engagement Metrics")

        # Headers
        col_label, col_combined, col_male, col_female = st.columns([1.5, 1, 1, 1])
        with col_label:
            st.markdown("**Metric**")
        with col_combined:
            st.markdown("**Combined**")
        with col_male:
            st.markdown("**Male**")
        with col_female:
            st.markdown("**Female**")

        # Viewed
        col_label, col_combined, col_male, col_female = st.columns([1.5, 1, 1, 1])
        with col_label:
            st.markdown("Viewed")
        with col_combined:
            st.metric("", f"{stats_combined['viewed']:,}", f"{stats_combined['view_rate']:.1f}%", label_visibility="collapsed")
        with col_male:
            st.metric("", f"{stats_male['viewed']:,}", f"{stats_male['view_rate']:.1f}%", label_visibility="collapsed")
        with col_female:
            st.metric("", f"{stats_female['viewed']:,}", f"{stats_female['view_rate']:.1f}%", label_visibility="collapsed")

        # Mutual Matches
        col_label, col_combined, col_male, col_female = st.columns([1.5, 1, 1, 1])
        with col_label:
            st.markdown("Mutual Matches")
        with col_combined:
            st.metric("", f"{stats_combined['mutual']:,}", f"{stats_combined['mutual_rate']:.1f}%", label_visibility="collapsed")
        with col_male:
            st.metric("", f"{stats_male['mutual']:,}", f"{stats_male['mutual_rate']:.1f}%", label_visibility="collapsed")
        with col_female:
            st.metric("", f"{stats_female['mutual']:,}", f"{stats_female['mutual_rate']:.1f}%", label_visibility="collapsed")

        # Avg Mutual Score
        col_label, col_combined, col_male, col_female = st.columns([1.5, 1, 1, 1])
        with col_label:
            st.markdown("Avg Mutual Score")
        with col_combined:
            st.metric("", f"{stats_combined['avg_mutual']:.2f}" if pd.notna(stats_combined['avg_mutual']) else "N/A", label_visibility="collapsed")
        with col_male:
            st.metric("", f"{stats_male['avg_mutual']:.2f}" if pd.notna(stats_male['avg_mutual']) else "N/A", label_visibility="collapsed")
        with col_female:
            st.metric("", f"{stats_female['avg_mutual']:.2f}" if pd.notna(stats_female['avg_mutual']) else "N/A", label_visibility="collapsed")

        # Avg Know More
        col_label, col_combined, col_male, col_female = st.columns([1.5, 1, 1, 1])
        with col_label:
            st.markdown("Avg Know More")
        with col_combined:
            st.metric("", f"{stats_combined['avg_know']:.1f}" if pd.notna(stats_combined['avg_know']) else "N/A", label_visibility="collapsed")
        with col_male:
            st.metric("", f"{stats_male['avg_know']:.1f}" if pd.notna(stats_male['avg_know']) else "N/A", label_visibility="collapsed")
        with col_female:
            st.metric("", f"{stats_female['avg_know']:.1f}" if pd.notna(stats_female['avg_know']) else "N/A", label_visibility="collapsed")

        st.divider()

        # Mutual Likes calculation (A liked B AND B liked A)
        st.markdown("### Mutual Likes Analysis")

        # Get all likes
        likes_df = df[df['is_liked'] == 'liked'][['current_user_id', 'matched_user_id']].copy()

        # Find mutual likes: where (A->B) exists AND (B->A) exists
        like_pairs = set(zip(likes_df['current_user_id'], likes_df['matched_user_id']))

        mutual_pairs = set()
        for curr, matched in like_pairs:
            if (matched, curr) in like_pairs:
                pair = tuple(sorted([curr, matched]))
                mutual_pairs.add(pair)

        mutual_like_count = len(mutual_pairs)
        liked_count = stats_combined['liked']

        col_ml1, col_ml2 = st.columns(2)
        with col_ml1:
            st.metric("Mutual Likes (Both Liked)", f"{mutual_like_count:,}")
        with col_ml2:
            mutual_like_rate = (mutual_like_count / (liked_count / 2) * 100) if liked_count > 0 else 0
            st.metric("Mutual Like Rate", f"{mutual_like_rate:.1f}%")

        st.divider()

        # Breakdown by origin_phase
        st.subheader("Breakdown by Origin Phase")

        phase_stats = df.groupby('origin_phase').agg({
            'match_id': 'count',
            'is_liked': lambda x: (x == 'liked').sum(),
            'is_viewed': 'sum',
            'mutual_score': 'mean'
        }).reset_index()
        phase_stats.columns = ['Origin Phase', 'Total', 'Likes', 'Views', 'Avg Score']
        phase_stats['Like Rate %'] = (phase_stats['Likes'] / phase_stats['Total'] * 100).round(1)
        phase_stats['Avg Score'] = phase_stats['Avg Score'].round(2)

        st.dataframe(
            phase_stats[['Origin Phase', 'Total', 'Likes', 'Like Rate %', 'Views', 'Avg Score']],
            use_container_width=True,
            hide_index=True
        )


# --- Tab 2: User Search ---
with tab_user:
    st.subheader("User Match History")

    # Search input
    search_col1, search_col2 = st.columns([4, 1])
    with search_col1:
        user_search = st.text_input(
            "Enter User ID",
            value=st.session_state.ms_search_user_id,
            placeholder="Paste user_id here...",
            label_visibility="collapsed"
        )
    with search_col2:
        search_clicked = st.button("Search", type="primary", use_container_width=True)

    if search_clicked and user_search.strip():
        st.session_state.ms_search_user_id = user_search.strip()
        st.rerun()

    if st.session_state.ms_search_user_id:
        user_id = st.session_state.ms_search_user_id

        # Fetch user profile
        with st.spinner("Loading user profile..."):
            user_profile = fetch_user_profile(user_id)

        if not user_profile:
            st.error(f"User not found: {user_id}")
        else:
            # Display profile card
            st.markdown(f"**User ID:** `{user_id}`")
            display_profile_card(user_profile)

            st.divider()

            # Fetch matches
            with st.spinner("Loading matches..."):
                outbound, inbound = fetch_user_matches(user_id)

            # Summary metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Outbound Matches", len(outbound))
            with col2:
                st.metric("Inbound Matches", len(inbound))
            with col3:
                liked_out = sum(1 for m in outbound if m.get('is_liked') == 'liked')
                st.metric("User's Likes", liked_out)
            with col4:
                liked_in = sum(1 for m in inbound if m.get('is_liked') == 'liked')
                st.metric("Liked by Others", liked_in)

            st.divider()

            # Sub-tabs for outbound/inbound
            user_tab1, user_tab2 = st.tabs([
                f"Outbound ({len(outbound)})",
                f"Inbound ({len(inbound)})"
            ])

            with user_tab1:
                if outbound:
                    # Get profiles for matched users
                    matched_ids = [m['matched_user_id'] for m in outbound]
                    profiles = fetch_user_profiles_batch(matched_ids)

                    for match in outbound:
                        matched_id = match['matched_user_id']
                        profile = profiles.get(matched_id, {})
                        name = profile.get('name', 'Unknown')
                        photos = profile.get('profile_images') or profile.get('instagram_images') or []
                        thumb = photos[0] if photos else None

                        with st.expander(f"{name} ({matched_id[:8]}...) - {match.get('is_liked', 'N/A')}"):
                            cols = st.columns([1, 3])
                            with cols[0]:
                                if thumb:
                                    st.image(thumb, width=100)
                                else:
                                    st.markdown("No photo")
                            with cols[1]:
                                st.markdown(f"**Status:** {match.get('is_liked', 'N/A')} | **Viewed:** {match.get('is_viewed', False)}")
                                st.markdown(f"**Mutual Score:** {match.get('mutual_score', 'N/A')} | **Rank:** {match.get('rank', 'N/A')}")
                                st.markdown(f"**Phase:** {match.get('origin_phase', 'N/A')} | **Date:** {match.get('created_at', 'N/A')}")
                                st.markdown(f"**Know More Count:** {match.get('know_more_count', 0)}")
                else:
                    st.info("No outbound matches found.")

            with user_tab2:
                if inbound:
                    # Get profiles for current users
                    current_ids = [m['current_user_id'] for m in inbound]
                    profiles = fetch_user_profiles_batch(current_ids)

                    for match in inbound:
                        current_id = match['current_user_id']
                        profile = profiles.get(current_id, {})
                        name = profile.get('name', 'Unknown')
                        photos = profile.get('profile_images') or profile.get('instagram_images') or []
                        thumb = photos[0] if photos else None

                        with st.expander(f"{name} ({current_id[:8]}...) - {match.get('is_liked', 'N/A')}"):
                            cols = st.columns([1, 3])
                            with cols[0]:
                                if thumb:
                                    st.image(thumb, width=100)
                                else:
                                    st.markdown("No photo")
                            with cols[1]:
                                st.markdown(f"**Status:** {match.get('is_liked', 'N/A')} | **Viewed:** {match.get('is_viewed', False)}")
                                st.markdown(f"**Mutual Score:** {match.get('mutual_score', 'N/A')} | **Rank:** {match.get('rank', 'N/A')}")
                                st.markdown(f"**Phase:** {match.get('origin_phase', 'N/A')} | **Date:** {match.get('created_at', 'N/A')}")
                                st.markdown(f"**Know More Count:** {match.get('know_more_count', 0)}")
                else:
                    st.info("No inbound matches found.")
    else:
        st.info("Enter a user ID above to view their match history.")


# --- Tab 3: Mutual Likes ---
with tab_mutual:
    st.subheader("Mutual Likes List")
    st.markdown("Pairs where **both users liked each other**")

    # Fetch data with filters
    mutual_matches_data = fetch_overview_stats(
        run_id=run_id_filter,
        origin_phase=phase_filter,
        start_date=start_date,
        end_date=end_date
    )

    if not mutual_matches_data:
        st.info("No matches found for the selected filters.")
    else:
        df_mutual = pd.DataFrame(mutual_matches_data)

        # Get all likes
        likes_df = df_mutual[df_mutual['is_liked'] == 'liked'][['current_user_id', 'matched_user_id', 'created_at', 'mutual_score', 'origin_phase']].copy()

        # Find mutual likes: where (A->B) exists AND (B->A) exists
        like_pairs = set(zip(likes_df['current_user_id'], likes_df['matched_user_id']))

        # Build list of mutual pairs with details
        mutual_pairs_list = []
        seen_pairs = set()

        for _, row in likes_df.iterrows():
            curr = row['current_user_id']
            matched = row['matched_user_id']
            if (matched, curr) in like_pairs:
                # This is a mutual like
                pair_key = tuple(sorted([curr, matched]))
                if pair_key not in seen_pairs:
                    seen_pairs.add(pair_key)
                    mutual_pairs_list.append({
                        'user_1': curr,
                        'user_2': matched,
                        'created_at': row['created_at'],
                        'mutual_score': row['mutual_score'],
                        'origin_phase': row['origin_phase']
                    })

        if not mutual_pairs_list:
            st.info("No mutual likes found in the selected date range.")
        else:
            st.metric("Total Mutual Likes", len(mutual_pairs_list))
            st.divider()

            # Get all user IDs for profile fetching
            all_mutual_user_ids = list(set(
                [p['user_1'] for p in mutual_pairs_list] +
                [p['user_2'] for p in mutual_pairs_list]
            ))

            with st.spinner("Loading user profiles..."):
                mutual_profiles = fetch_user_profiles_batch(all_mutual_user_ids)
                mutual_genders = fetch_user_genders(all_mutual_user_ids)
                mutual_emails, mutual_phones = fetch_user_contact_batch(all_mutual_user_ids)

            # Display each mutual pair
            for i, pair in enumerate(mutual_pairs_list):
                user1_id = pair['user_1']
                user2_id = pair['user_2']
                user1_profile = mutual_profiles.get(user1_id, {})
                user2_profile = mutual_profiles.get(user2_id, {})

                user1_name = user1_profile.get('name', 'Unknown')
                user2_name = user2_profile.get('name', 'Unknown')
                user1_gender = mutual_genders.get(user1_id, 'N/A')
                user2_gender = mutual_genders.get(user2_id, 'N/A')
                user1_email = mutual_emails.get(user1_id, 'N/A')
                user2_email = mutual_emails.get(user2_id, 'N/A')
                user1_phone = mutual_phones.get(user1_id, 'N/A')
                user2_phone = mutual_phones.get(user2_id, 'N/A')

                user1_photos = user1_profile.get('profile_images') or user1_profile.get('instagram_images') or []
                user2_photos = user2_profile.get('profile_images') or user2_profile.get('instagram_images') or []

                with st.expander(f"#{i+1}: {user1_name} ({user1_gender}) ❤️ {user2_name} ({user2_gender})"):
                    col1, col2 = st.columns(2)

                    with col1:
                        st.markdown(f"### {user1_name}")
                        st.markdown(f"**User ID:** `{user1_id}`")
                        st.markdown(f"**Gender:** {user1_gender}")
                        st.markdown(f"**Age:** {user1_profile.get('age', 'N/A')}")
                        st.markdown(f"**City:** {user1_profile.get('city', 'N/A')}")
                        st.markdown(f"**Phone:** {user1_phone}")
                        st.markdown(f"**Email:** {user1_email}")
                        if user1_photos:
                            st.image(user1_photos[0], width=200)

                    with col2:
                        st.markdown(f"### {user2_name}")
                        st.markdown(f"**User ID:** `{user2_id}`")
                        st.markdown(f"**Gender:** {user2_gender}")
                        st.markdown(f"**Age:** {user2_profile.get('age', 'N/A')}")
                        st.markdown(f"**City:** {user2_profile.get('city', 'N/A')}")
                        st.markdown(f"**Phone:** {user2_phone}")
                        st.markdown(f"**Email:** {user2_email}")
                        if user2_photos:
                            st.image(user2_photos[0], width=200)

                    st.divider()
                    st.markdown(f"**Mutual Score:** {pair['mutual_score']} | **Phase:** {pair['origin_phase']} | **Date:** {pair['created_at']}")


# --- Tab 4: Male Likes ---
with tab_male_likes:
    st.subheader("Males Who Received Likes")
    st.markdown("List of males sorted by number of likes received")

    # Fetch data with filters
    male_likes_data_raw = fetch_overview_stats(
        run_id=run_id_filter,
        origin_phase=phase_filter,
        start_date=start_date,
        end_date=end_date
    )

    if not male_likes_data_raw:
        st.info("No matches found for the selected filters.")
    else:
        df_male_likes = pd.DataFrame(male_likes_data_raw)

        # Get all likes where matched_user is male
        # matched_user_id is the person who RECEIVED the like
        likes_received = df_male_likes[df_male_likes['is_liked'] == 'liked'][['matched_user_id']].copy()

        if len(likes_received) > 0:
            # Count likes per matched_user
            likes_count = likes_received.groupby('matched_user_id').size().reset_index(name='likes_received')
            likes_count = likes_count.sort_values('likes_received', ascending=False)

            # Get all matched_user_ids
            matched_user_ids = likes_count['matched_user_id'].tolist()

            # Fetch gender for all matched users
            with st.spinner("Loading user data..."):
                matched_genders = fetch_user_genders(matched_user_ids)

            # Filter to only males
            male_user_ids = [uid for uid in matched_user_ids if matched_genders.get(uid) == 'male']

            if male_user_ids:
                # Fetch profiles and contact info for males
                male_profiles = fetch_user_profiles_batch(male_user_ids)
                male_emails, male_phones = fetch_user_contact_batch(male_user_ids)

                # Build display data
                male_likes_data = []
                for uid in male_user_ids:
                    like_count = likes_count[likes_count['matched_user_id'] == uid]['likes_received'].values[0]
                    profile = male_profiles.get(uid, {})
                    male_likes_data.append({
                        'user_id': uid,
                        'name': profile.get('name', 'Unknown'),
                        'likes': like_count,
                        'phone': male_phones.get(uid, 'N/A'),
                        'email': male_emails.get(uid, 'N/A'),
                        'photos': profile.get('profile_images') or profile.get('instagram_images') or []
                    })

                st.metric("Total Males with Likes", len(male_likes_data))
                st.divider()

                # Display each male with likes
                for i, male in enumerate(male_likes_data[:50]):  # Limit to top 50
                    with st.expander(f"#{i+1}: {male['name']} - {male['likes']} likes"):
                        col1, col2 = st.columns([1, 3])
                        with col1:
                            if male['photos']:
                                st.image(male['photos'][0], width=150)
                            else:
                                st.markdown("No photo")
                        with col2:
                            st.markdown(f"**Name:** {male['name']}")
                            st.markdown(f"**Likes Received:** {male['likes']}")
                            st.markdown(f"**Phone:** {male['phone']}")
                            st.markdown(f"**Email:** {male['email']}")
                            st.markdown(f"**User ID:** `{male['user_id']}`")
            else:
                st.info("No males received likes in the selected date range.")
        else:
            st.info("No likes found in the selected date range.")


# --- Tab 5: Female Likes ---
with tab_female_likes:
    st.subheader("Females Who Received Likes")
    st.markdown("List of females sorted by number of likes received")

    # Fetch data with filters
    female_likes_data_raw = fetch_overview_stats(
        run_id=run_id_filter,
        origin_phase=phase_filter,
        start_date=start_date,
        end_date=end_date
    )

    if not female_likes_data_raw:
        st.info("No matches found for the selected filters.")
    else:
        df_female_likes = pd.DataFrame(female_likes_data_raw)

        # Get all likes where matched_user is female
        # matched_user_id is the person who RECEIVED the like
        likes_received_f = df_female_likes[df_female_likes['is_liked'] == 'liked'][['matched_user_id']].copy()

        if len(likes_received_f) > 0:
            # Count likes per matched_user
            likes_count_f = likes_received_f.groupby('matched_user_id').size().reset_index(name='likes_received')
            likes_count_f = likes_count_f.sort_values('likes_received', ascending=False)

            # Get all matched_user_ids
            matched_user_ids_f = likes_count_f['matched_user_id'].tolist()

            # Fetch gender for all matched users
            with st.spinner("Loading user data..."):
                matched_genders_f = fetch_user_genders(matched_user_ids_f)

            # Filter to only females
            female_user_ids = [uid for uid in matched_user_ids_f if matched_genders_f.get(uid) == 'female']

            if female_user_ids:
                # Fetch profiles and contact info for females
                female_profiles = fetch_user_profiles_batch(female_user_ids)
                female_emails, female_phones = fetch_user_contact_batch(female_user_ids)

                # Build display data
                female_likes_data = []
                for uid in female_user_ids:
                    like_count = likes_count_f[likes_count_f['matched_user_id'] == uid]['likes_received'].values[0]
                    profile = female_profiles.get(uid, {})
                    female_likes_data.append({
                        'user_id': uid,
                        'name': profile.get('name', 'Unknown'),
                        'likes': like_count,
                        'phone': female_phones.get(uid, 'N/A'),
                        'email': female_emails.get(uid, 'N/A'),
                        'photos': profile.get('profile_images') or profile.get('instagram_images') or []
                    })

                st.metric("Total Females with Likes", len(female_likes_data))
                st.divider()

                # Display each female with likes
                for i, female in enumerate(female_likes_data[:50]):  # Limit to top 50
                    with st.expander(f"#{i+1}: {female['name']} - {female['likes']} likes"):
                        col1, col2 = st.columns([1, 3])
                        with col1:
                            if female['photos']:
                                st.image(female['photos'][0], width=150)
                            else:
                                st.markdown("No photo")
                        with col2:
                            st.markdown(f"**Name:** {female['name']}")
                            st.markdown(f"**Likes Received:** {female['likes']}")
                            st.markdown(f"**Phone:** {female['phone']}")
                            st.markdown(f"**Email:** {female['email']}")
                            st.markdown(f"**User ID:** `{female['user_id']}`")
            else:
                st.info("No females received likes in the selected date range.")
        else:
            st.info("No likes found in the selected date range.")


# --- Tab 6: Trends ---
with tab_trends:
    st.subheader("Match Trends Over Time")

    # Time range selector
    days_options = {"7 days": 7, "14 days": 14, "30 days": 30, "90 days": 90}
    selected_days = st.selectbox("Time Range", options=list(days_options.keys()), index=2)
    days = days_options[selected_days]

    # Fetch time series data
    with st.spinner("Loading trends..."):
        daily_data = fetch_daily_stats(days=days, run_id=run_id_filter, origin_phase=phase_filter)

    if not daily_data:
        st.info("No data available for the selected time range.")
    else:
        df = pd.DataFrame(daily_data)
        df['date'] = pd.to_datetime(df['created_at']).dt.date

        # Daily matches count
        daily_counts = df.groupby('date').size().reset_index(name='matches')
        daily_counts = daily_counts.sort_values('date')

        st.subheader("Matches per Day")
        st.line_chart(daily_counts.set_index('date')['matches'])

        st.divider()

        # Engagement by day
        st.subheader("Engagement by Day")

        daily_engagement = df.groupby('date').agg({
            'is_liked': lambda x: (x == 'liked').sum(),
            'is_viewed': lambda x: x.sum() if x.dtype == bool else (x == True).sum()
        }).reset_index()
        daily_engagement.columns = ['date', 'likes', 'views']
        daily_engagement = daily_engagement.sort_values('date')

        # Merge with daily counts
        daily_engagement = daily_engagement.merge(daily_counts, on='date')
        daily_engagement['like_rate'] = (daily_engagement['likes'] / daily_engagement['matches'] * 100).round(1)
        daily_engagement['view_rate'] = (daily_engagement['views'] / daily_engagement['matches'] * 100).round(1)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Likes per Day**")
            st.bar_chart(daily_engagement.set_index('date')['likes'])
        with col2:
            st.markdown("**Views per Day**")
            st.bar_chart(daily_engagement.set_index('date')['views'])

        st.divider()

        # Summary table
        st.subheader("Daily Summary")
        display_df = daily_engagement[['date', 'matches', 'likes', 'views', 'like_rate', 'view_rate']].copy()
        display_df.columns = ['Date', 'Matches', 'Likes', 'Views', 'Like Rate %', 'View Rate %']
        st.dataframe(
            display_df.sort_values('Date', ascending=False),
            use_container_width=True,
            hide_index=True
        )
