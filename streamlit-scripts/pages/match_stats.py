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


@st.cache_data(ttl=300)
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


@st.cache_data(ttl=300)
def fetch_user_genders(user_ids: tuple):
    """Fetch gender for a list of user_ids from user_metadata."""
    if not user_ids:
        return {}
    try:
        # Batch fetch in chunks of 500 to avoid query limits
        gender_map = {}
        user_ids_list = list(user_ids)
        for i in range(0, len(user_ids_list), 500):
            chunk = user_ids_list[i:i+500]
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


@st.cache_data(ttl=300)
def fetch_user_contact_batch(user_ids: tuple):
    """Batch fetch user emails and phones from user_data table."""
    if not user_ids:
        return {}, {}
    try:
        email_map = {}
        phone_map = {}
        user_ids_list = list(user_ids)
        for i in range(0, len(user_ids_list), 500):
            chunk = user_ids_list[i:i+500]
            res = supabase.table('user_data').select('user_id, user_email, user_phone').in_('user_id', chunk).execute()
            if res.data:
                for u in res.data:
                    email_map[u['user_id']] = u.get('user_email')
                    phone_map[u['user_id']] = u.get('user_phone')
        return email_map, phone_map
    except Exception as e:
        return {}, {}


@st.cache_data(ttl=300)
def fetch_user_profiles_batch(user_ids: tuple):
    """Batch fetch user profiles from user_metadata."""
    if not user_ids:
        return {}
    try:
        user_ids_list = list(user_ids)
        res = supabase.table('user_metadata').select(
            'user_id, name, age, gender, city, phone_num, profile_images, instagram_images'
        ).in_('user_id', user_ids_list).execute()
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


# --- Sidebar ---
# Refresh button - only clears main data cache, not user profiles/genders
if st.sidebar.button("Refresh Data", use_container_width=True, type="primary"):
    # Clear only the main data fetching caches
    fetch_overview_stats.clear()
    fetch_daily_stats.clear()
    st.rerun()

# Set filters to None (no filtering)
run_id_filter = None
phase_filter = None
start_date = None
end_date = None


# --- Main Content ---
st.title("Match Stats")

# Tabs
tab_overview, tab_funnel, tab_user, tab_mutual, tab_per_user, tab_male_likes, tab_female_likes, tab_trends = st.tabs(["Overview", "Funnel", "User Search", "Mutual Likes", "Per User Matches", "Male Likes", "Female Likes", "Trends"])


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

        # Parse dates and add date column
        df['created_at'] = pd.to_datetime(df['created_at'])
        df['action_date'] = df['created_at'].dt.date

        # Get unique dates for dropdown
        unique_overview_dates = sorted(df['action_date'].unique())
        overview_date_options = ["All Dates"] + [str(d) for d in unique_overview_dates]
        selected_overview_date = st.selectbox("Filter by Date", options=overview_date_options, index=0, key="overview_date_filter")

        # Filter by selected date
        if selected_overview_date != "All Dates":
            selected_overview_date_obj = datetime.strptime(selected_overview_date, '%Y-%m-%d').date()
            df = df[df['action_date'] == selected_overview_date_obj]

        if len(df) == 0:
            st.info("No data for the selected date.")
        else:
            total_count = len(df)

            # Fetch gender data for all current_user_ids
            all_user_ids = tuple(sorted(set(df['current_user_id'].tolist())))
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


# --- Tab 2: Funnel ---
with tab_funnel:
    st.subheader("User Journey Funnel")
    st.markdown("Breakdown of user actions from recommendations to final decisions")

    # Fetch data with filters
    funnel_data = fetch_overview_stats(
        run_id=run_id_filter,
        origin_phase=phase_filter,
        start_date=start_date,
        end_date=end_date
    )

    if not funnel_data:
        st.info("No matches found for the selected filters.")
    else:
        df_funnel = pd.DataFrame(funnel_data)

        # Parse dates and add date column
        df_funnel['created_at'] = pd.to_datetime(df_funnel['created_at'])
        df_funnel['action_date'] = df_funnel['created_at'].dt.date

        # Get unique dates for dropdown
        unique_funnel_dates = sorted(df_funnel['action_date'].unique())
        funnel_date_options = ["All Dates"] + [str(d) for d in unique_funnel_dates]
        selected_funnel_date = st.selectbox("Filter by Date", options=funnel_date_options, index=0, key="funnel_date_filter")

        # Filter by selected date
        if selected_funnel_date != "All Dates":
            selected_funnel_date_obj = datetime.strptime(selected_funnel_date, '%Y-%m-%d').date()
            df_funnel = df_funnel[df_funnel['action_date'] == selected_funnel_date_obj]

        if len(df_funnel) == 0:
            st.info("No data for the selected date.")
        else:
            # Fetch gender data for all current_user_ids (the person who received the recommendation)
            all_funnel_user_ids = tuple(sorted(set(df_funnel['current_user_id'].tolist())))
            with st.spinner("Loading gender data..."):
                funnel_gender_map = fetch_user_genders(all_funnel_user_ids)

            # Add gender column
            df_funnel['user_gender'] = df_funnel['current_user_id'].map(funnel_gender_map)

            # Split by gender
            df_funnel_male = df_funnel[df_funnel['user_gender'] == 'male']
            df_funnel_female = df_funnel[df_funnel['user_gender'] == 'female']

            def calc_funnel_stats(data, gender_label, full_data):
                """Calculate funnel statistics for a given dataset.

                Args:
                    data: Gender-filtered data for calculating gender-specific stats
                    gender_label: "Male" or "Female"
                    full_data: Full dataset with both genders for matching algorithm
                """
                total = len(data)
                if total == 0:
                    return None

                # Unique users (current_user_id = person who received recommendation)
                unique_users = data['current_user_id'].nunique()

                # Viewed = is_viewed is True
                viewed = int(data['is_viewed'].sum()) if 'is_viewed' in data.columns else 0
                not_viewed = total - viewed

                # Unique users who viewed at least one recommendation
                users_who_viewed = data[data['is_viewed'] == True]['current_user_id'].nunique() if 'is_viewed' in data.columns else 0

                # Actions
                liked = len(data[data['is_liked'] == 'liked'])
                disliked = len(data[data['is_liked'] == 'disliked'])
                passed = len(data[data['is_liked'] == 'passed'])

                # Unique users who took each action
                users_who_liked = data[data['is_liked'] == 'liked']['current_user_id'].nunique()
                users_who_disliked = data[data['is_liked'] == 'disliked']['current_user_id'].nunique()
                users_who_passed = data[data['is_liked'] == 'passed']['current_user_id'].nunique()

                # No action = not liked, disliked, or passed (is_liked is null or empty)
                actioned = liked + disliked + passed
                no_action = total - actioned

                # Unique users who took any action
                users_with_action = data[data['is_liked'].isin(['liked', 'disliked', 'passed'])]['current_user_id'].nunique()
                users_no_action = unique_users - users_with_action

                # Know more (clicked to see more details)
                know_more_clicked = len(data[data['know_more_count'] > 0]) if 'know_more_count' in data.columns else 0
                users_know_more = data[data['know_more_count'] > 0]['current_user_id'].nunique() if 'know_more_count' in data.columns else 0

                # Mutual matches - use the same algorithm as Mutual Likes tab
                # Use full_data (both genders) for the matching algorithm
                likes_history = {}
                likes_df = full_data[full_data['is_liked'] == 'liked']
                for _, row in likes_df.iterrows():
                    key = (row['current_user_id'], row['matched_user_id'])
                    like_date = row['action_date']
                    if key not in likes_history or like_date < likes_history[key]:
                        likes_history[key] = like_date

                # Find matches using the algorithm with full data
                matched_users = set()
                matched_pairs = set()
                unique_action_dates = sorted(full_data['action_date'].unique())

                for target_date in unique_action_dates:
                    day_data = full_data[full_data['action_date'] == target_date]
                    day_action_lookup = {}
                    for _, row in day_data.iterrows():
                        key = (row['current_user_id'], row['matched_user_id'])
                        day_action_lookup[key] = row['is_liked']

                    for (user1, user2), action1 in day_action_lookup.items():
                        pair_key = tuple(sorted([user1, user2]))
                        if pair_key in matched_pairs:
                            continue

                        action2 = day_action_lookup.get((user2, user1))
                        is_match = False

                        if action2 is not None:
                            if action1 == 'liked' and action2 == 'liked':
                                is_match = True
                            elif action1 == 'liked' and action2 == 'passed':
                                prev_like_date = likes_history.get((user2, user1))
                                if prev_like_date and prev_like_date < target_date:
                                    is_match = True
                            elif action1 == 'passed' and action2 == 'liked':
                                prev_like_date = likes_history.get((user1, user2))
                                if prev_like_date and prev_like_date < target_date:
                                    is_match = True
                        else:
                            if action1 == 'liked':
                                prev_like_date = likes_history.get((user2, user1))
                                if prev_like_date and prev_like_date < target_date:
                                    is_match = True

                        if is_match:
                            matched_pairs.add(pair_key)
                            matched_users.add(user1)
                            matched_users.add(user2)

                mutual = len(matched_pairs)
                # Filter to only users from this gender's dataset
                gender_user_ids = set(data['current_user_id'].unique())
                users_with_mutual = len(matched_users & gender_user_ids)

                # Profile view distribution (how many profiles each user viewed per day)
                # For each user, get their max daily view count to categorize engagement level
                if 'is_viewed' in data.columns and 'action_date' in data.columns:
                    # Group by user AND date to get daily view counts
                    views_per_user_per_day = data[data['is_viewed'] == True].groupby(['current_user_id', 'action_date']).size()
                    # For each user, get their maximum daily views (best engagement day)
                    if len(views_per_user_per_day) > 0:
                        max_views_per_user = views_per_user_per_day.groupby('current_user_id').max()
                        users_viewed_1_3 = len(max_views_per_user[(max_views_per_user >= 1) & (max_views_per_user <= 3)])
                        users_viewed_4_6 = len(max_views_per_user[(max_views_per_user >= 4) & (max_views_per_user <= 6)])
                        users_viewed_7_9 = len(max_views_per_user[max_views_per_user >= 7])
                    else:
                        users_viewed_1_3 = 0
                        users_viewed_4_6 = 0
                        users_viewed_7_9 = 0
                else:
                    users_viewed_1_3 = 0
                    users_viewed_4_6 = 0
                    users_viewed_7_9 = 0

                # Recommendations distribution (how many matches/recommendations each user received)
                recs_per_user = data.groupby('current_user_id').size()
                min_recs = int(recs_per_user.min()) if len(recs_per_user) > 0 else 0
                max_recs = int(recs_per_user.max()) if len(recs_per_user) > 0 else 0
                median_recs = float(recs_per_user.median()) if len(recs_per_user) > 0 else 0
                users_with_lt_9 = len(recs_per_user[recs_per_user < 9])
                users_with_9 = len(recs_per_user[recs_per_user == 9])
                users_with_gt_9 = len(recs_per_user[recs_per_user > 9])

                return {
                    'gender': gender_label,
                    'total_recommendations': total,
                    'unique_users': unique_users,
                    'avg_recs_per_user': (total / unique_users) if unique_users > 0 else 0,
                    'viewed': viewed,
                    'viewed_rate': (viewed / total * 100) if total > 0 else 0,
                    'users_who_viewed': users_who_viewed,
                    'users_viewed_rate': (users_who_viewed / unique_users * 100) if unique_users > 0 else 0,
                    'not_viewed': not_viewed,
                    'not_viewed_rate': (not_viewed / total * 100) if total > 0 else 0,
                    'any_action': actioned,
                    'any_action_rate': (actioned / total * 100) if total > 0 else 0,
                    'users_with_action': users_with_action,
                    'users_action_rate': (users_with_action / unique_users * 100) if unique_users > 0 else 0,
                    'no_action': no_action,
                    'no_action_rate': (no_action / total * 100) if total > 0 else 0,
                    'users_no_action': users_no_action,
                    'liked': liked,
                    'liked_rate': (liked / total * 100) if total > 0 else 0,
                    'users_who_liked': users_who_liked,
                    'users_liked_rate': (users_who_liked / unique_users * 100) if unique_users > 0 else 0,
                    'liked_of_actioned': (liked / actioned * 100) if actioned > 0 else 0,
                    'disliked': disliked,
                    'disliked_rate': (disliked / total * 100) if total > 0 else 0,
                    'users_who_disliked': users_who_disliked,
                    'passed': passed,
                    'passed_rate': (passed / total * 100) if total > 0 else 0,
                    'users_who_passed': users_who_passed,
                    'know_more': know_more_clicked,
                    'know_more_rate': (know_more_clicked / total * 100) if total > 0 else 0,
                    'users_know_more': users_know_more,
                    'mutual': mutual,
                    'mutual_rate': (mutual / total * 100) if total > 0 else 0,
                    'users_with_mutual': users_with_mutual,
                    'users_with_mutual_rate': (users_with_mutual / unique_users * 100) if unique_users > 0 else 0,
                    'conversion_rate': (liked / total * 100) if total > 0 else 0,
                    'users_viewed_1_3': users_viewed_1_3,
                    'users_viewed_4_6': users_viewed_4_6,
                    'users_viewed_7_9': users_viewed_7_9,
                    'min_recs': min_recs,
                    'max_recs': max_recs,
                    'median_recs': median_recs,
                    'users_with_lt_9': users_with_lt_9,
                    'users_with_9': users_with_9,
                    'users_with_gt_9': users_with_gt_9,
                }

            # Calculate stats for both genders (pass full df_funnel for matching algorithm)
            male_funnel = calc_funnel_stats(df_funnel_male, "Male", df_funnel)
            female_funnel = calc_funnel_stats(df_funnel_female, "Female", df_funnel)

            # Display funnel as flow chart
            def display_funnel_chart(stats, gender_label, color):
                """Display funnel as a visual flow chart."""
                if stats is None:
                    st.info(f"No data for {gender_label} users")
                    return

                # CSS for funnel boxes
                st.markdown(f"""
                <style>
                .funnel-box {{
                    background: linear-gradient(135deg, {color}22, {color}11);
                    border-left: 4px solid {color};
                    border-radius: 8px;
                    padding: 15px;
                    margin: 8px 0;
                    text-align: center;
                }}
                .funnel-box h3 {{
                    margin: 0 0 5px 0;
                    font-size: 24px;
                    color: {color};
                }}
                .funnel-box p {{
                    margin: 0;
                    font-size: 14px;
                    color: #888;
                }}
                .funnel-arrow {{
                    text-align: center;
                    font-size: 24px;
                    color: #555;
                    margin: 5px 0;
                }}
                .funnel-split {{
                    display: flex;
                    justify-content: space-around;
                    gap: 10px;
                }}
                .funnel-split-box {{
                    flex: 1;
                    background: #1a1a2e;
                    border-radius: 8px;
                    padding: 12px;
                    text-align: center;
                }}
                .funnel-split-box.green {{ border-left: 3px solid #4CAF50; }}
                .funnel-split-box.red {{ border-left: 3px solid #f44336; }}
                .funnel-split-box.yellow {{ border-left: 3px solid #ff9800; }}
                .funnel-split-box.blue {{ border-left: 3px solid #2196F3; }}
                </style>
                """, unsafe_allow_html=True)

                # Title
                st.markdown(f"### {gender_label} Funnel")

                # Stage 1: Users
                st.markdown(f"""
                <div class="funnel-box" title="Total number of unique users who received match recommendations in this period">
                    <h3>{stats['unique_users']:,}</h3>
                    <p>Unique Users</p>
                    <p style="font-size:12px; color:#666;">({stats['total_recommendations']:,} recommendations, ~{stats['avg_recs_per_user']:.1f}/user)</p>
                </div>
                <div class="funnel-arrow">↓</div>
                """, unsafe_allow_html=True)

                # Stage 2: Viewed
                viewed_pct = stats['users_viewed_rate']
                st.markdown(f"""
                <div class="funnel-box" title="Users who opened/viewed at least one recommended profile. Percentage is of total unique users.">
                    <h3>{stats['users_who_viewed']:,}</h3>
                    <p>Users Viewed ({viewed_pct:.1f}%)</p>
                    <p style="font-size:12px; color:#666;">({stats['viewed']:,} views)</p>
                </div>
                <div class="funnel-arrow">↓</div>
                """, unsafe_allow_html=True)

                # Stage 2.5: Viewing Depth Breakdown (how many profiles users viewed)
                total_viewers = stats['users_viewed_1_3'] + stats['users_viewed_4_6'] + stats['users_viewed_7_9']
                if total_viewers > 0:
                    pct_1_3 = (stats['users_viewed_1_3'] / stats['users_who_viewed'] * 100) if stats['users_who_viewed'] > 0 else 0
                    pct_4_6 = (stats['users_viewed_4_6'] / stats['users_who_viewed'] * 100) if stats['users_who_viewed'] > 0 else 0
                    pct_7_9 = (stats['users_viewed_7_9'] / stats['users_who_viewed'] * 100) if stats['users_who_viewed'] > 0 else 0
                    st.markdown(f"""
                    <div style="background: linear-gradient(135deg, #9c27b022, #9c27b011); border-left: 4px solid #9c27b0; border-radius: 8px; padding: 15px; margin: 8px 0; text-align: center;" title="Breakdown of how many profiles each user viewed before taking action or dropping off">
                        <p style="margin: 0 0 10px 0; font-size: 14px; color: #888;">Profiles Viewed per User</p>
                        <div class="funnel-split">
                            <div class="funnel-split-box" style="border-left: 3px solid #f44336;" title="Users who viewed only 1-3 profiles - early drop-off, low engagement">
                                <h4 style="color:#f44336; margin:0;">{stats['users_viewed_1_3']:,}</h4>
                                <p style="margin:0; font-size:13px;">1-3 profiles</p>
                                <p style="margin:0; font-size:11px; color:#666;">({pct_1_3:.1f}%)</p>
                            </div>
                            <div class="funnel-split-box" style="border-left: 3px solid #ff9800;" title="Users who viewed 4-6 profiles - moderate engagement">
                                <h4 style="color:#ff9800; margin:0;">{stats['users_viewed_4_6']:,}</h4>
                                <p style="margin:0; font-size:13px;">4-6 profiles</p>
                                <p style="margin:0; font-size:11px; color:#666;">({pct_4_6:.1f}%)</p>
                            </div>
                            <div class="funnel-split-box" style="border-left: 3px solid #4CAF50;" title="Users who viewed 7-9 profiles - high engagement, viewed most recommendations">
                                <h4 style="color:#4CAF50; margin:0;">{stats['users_viewed_7_9']:,}</h4>
                                <p style="margin:0; font-size:13px;">7-9 profiles</p>
                                <p style="margin:0; font-size:11px; color:#666;">({pct_7_9:.1f}%)</p>
                            </div>
                        </div>
                    </div>
                    <div class="funnel-arrow">↓</div>
                    """, unsafe_allow_html=True)

                # Stage 3: Took Action
                action_pct = stats['users_action_rate']
                st.markdown(f"""
                <div class="funnel-box" title="Users who took at least one action (liked, disliked, or passed) on any recommendation. Percentage is of total unique users.">
                    <h3>{stats['users_with_action']:,}</h3>
                    <p>Users Took Action ({action_pct:.1f}%)</p>
                    <p style="font-size:12px; color:#666;">({stats['any_action']:,} actions)</p>
                </div>
                <div class="funnel-arrow">↓</div>
                """, unsafe_allow_html=True)

                # Stage 4: Action breakdown (side by side)
                st.markdown(f"""
                <div class="funnel-split">
                    <div class="funnel-split-box green" title="Users who liked at least one profile. Shows interest in potential matches.">
                        <h4 style="color:#4CAF50; margin:0;">{stats['users_who_liked']:,}</h4>
                        <p style="margin:0; font-size:13px;">Liked</p>
                        <p style="margin:0; font-size:11px; color:#666;">{stats['liked']:,} likes ({stats['liked_rate']:.1f}%)</p>
                    </div>
                    <div class="funnel-split-box red" title="Users who disliked at least one profile. Explicit rejection of a recommendation.">
                        <h4 style="color:#f44336; margin:0;">{stats['users_who_disliked']:,}</h4>
                        <p style="margin:0; font-size:13px;">Disliked</p>
                        <p style="margin:0; font-size:11px; color:#666;">{stats['disliked']:,} dislikes ({stats['disliked_rate']:.1f}%)</p>
                    </div>
                    <div class="funnel-split-box yellow" title="Users who passed on at least one profile. Skipped without explicit like/dislike.">
                        <h4 style="color:#ff9800; margin:0;">{stats['users_who_passed']:,}</h4>
                        <p style="margin:0; font-size:13px;">Passed</p>
                        <p style="margin:0; font-size:11px; color:#666;">{stats['passed']:,} passes ({stats['passed_rate']:.1f}%)</p>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Summary metrics
                st.markdown("---")
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.metric("Conversion Rate", f"{stats['conversion_rate']:.1f}%")
                with c2:
                    st.metric("Users No Action", f"{stats['users_no_action']:,}")
                with c3:
                    st.metric("Know More", f"{stats['users_know_more']:,}")
                with c4:
                    st.metric("Users with Mutual Likes", f"{stats['users_with_mutual']:,} / {stats['unique_users']:,}", f"{stats['users_with_mutual_rate']:.1f}%")

            # Display both funnels side by side
            col_male, col_female = st.columns(2)

            with col_male:
                display_funnel_chart(male_funnel, "Male", "#2196F3")

            with col_female:
                display_funnel_chart(female_funnel, "Female", "#E91E63")

            st.divider()

            # Comparison Table
            st.subheader("Side-by-Side Comparison")

            if male_funnel and female_funnel:
                comparison_data = {
                    'Metric': [
                        'Total Recommendations',
                        'Unique Users',
                        'Avg Recs/User',
                        'Viewed (recs)',
                        'Users Viewed',
                        'Viewed Rate',
                        'Took Action (recs)',
                        'Users Took Action',
                        'Action Rate',
                        'No Action (recs)',
                        'Liked (recs)',
                        'Users Liked',
                        'Like Rate',
                        'Disliked (recs)',
                        'Passed (recs)',
                        'Know More (recs)',
                        'Mutual Matches',
                        'Conversion Rate',
                        'Viewed 1-3 Profiles',
                        'Viewed 4-6 Profiles',
                        'Viewed 7-9 Profiles',
                        'Min Recs/User',
                        'Max Recs/User',
                        'Median Recs/User',
                        'Users < 9 Recs',
                        'Users = 9 Recs',
                        'Users > 9 Recs'
                    ],
                    'Male': [
                        f"{male_funnel['total_recommendations']:,}",
                        f"{male_funnel['unique_users']:,}",
                        f"{male_funnel['avg_recs_per_user']:.1f}",
                        f"{male_funnel['viewed']:,}",
                        f"{male_funnel['users_who_viewed']:,}",
                        f"{male_funnel['viewed_rate']:.1f}%",
                        f"{male_funnel['any_action']:,}",
                        f"{male_funnel['users_with_action']:,}",
                        f"{male_funnel['any_action_rate']:.1f}%",
                        f"{male_funnel['no_action']:,}",
                        f"{male_funnel['liked']:,}",
                        f"{male_funnel['users_who_liked']:,}",
                        f"{male_funnel['liked_rate']:.1f}%",
                        f"{male_funnel['disliked']:,}",
                        f"{male_funnel['passed']:,}",
                        f"{male_funnel['know_more']:,}",
                        f"{male_funnel['mutual']:,}",
                        f"{male_funnel['conversion_rate']:.1f}%",
                        f"{male_funnel['users_viewed_1_3']:,}",
                        f"{male_funnel['users_viewed_4_6']:,}",
                        f"{male_funnel['users_viewed_7_9']:,}",
                        f"{male_funnel['min_recs']}",
                        f"{male_funnel['max_recs']}",
                        f"{male_funnel['median_recs']:.0f}",
                        f"{male_funnel['users_with_lt_9']:,}",
                        f"{male_funnel['users_with_9']:,}",
                        f"{male_funnel['users_with_gt_9']:,}"
                    ],
                    'Female': [
                        f"{female_funnel['total_recommendations']:,}",
                        f"{female_funnel['unique_users']:,}",
                        f"{female_funnel['avg_recs_per_user']:.1f}",
                        f"{female_funnel['viewed']:,}",
                        f"{female_funnel['users_who_viewed']:,}",
                        f"{female_funnel['viewed_rate']:.1f}%",
                        f"{female_funnel['any_action']:,}",
                        f"{female_funnel['users_with_action']:,}",
                        f"{female_funnel['any_action_rate']:.1f}%",
                        f"{female_funnel['no_action']:,}",
                        f"{female_funnel['liked']:,}",
                        f"{female_funnel['users_who_liked']:,}",
                        f"{female_funnel['liked_rate']:.1f}%",
                        f"{female_funnel['disliked']:,}",
                        f"{female_funnel['passed']:,}",
                        f"{female_funnel['know_more']:,}",
                        f"{female_funnel['mutual']:,}",
                        f"{female_funnel['conversion_rate']:.1f}%",
                        f"{female_funnel['users_viewed_1_3']:,}",
                        f"{female_funnel['users_viewed_4_6']:,}",
                        f"{female_funnel['users_viewed_7_9']:,}",
                        f"{female_funnel['min_recs']}",
                        f"{female_funnel['max_recs']}",
                        f"{female_funnel['median_recs']:.0f}",
                        f"{female_funnel['users_with_lt_9']:,}",
                        f"{female_funnel['users_with_9']:,}",
                        f"{female_funnel['users_with_gt_9']:,}"
                    ]
                }

                comparison_df = pd.DataFrame(comparison_data)
                st.dataframe(comparison_df, use_container_width=True, hide_index=True)


# --- Tab 3: User Search ---
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
                    matched_ids = tuple(sorted(set(m['matched_user_id'] for m in outbound)))
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
                    current_ids = tuple(sorted(set(m['current_user_id'] for m in inbound)))
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
    st.markdown("""
    **Match Rules (evaluated per day):**
    - Like + Like = Match
    - Like + Passed = Match (if the 'passed' user liked on a previous day)
    - Passed + Like = Match (if the 'passed' user liked on a previous day)
    - Like + No action = Match (if the other user liked on a previous day)
    - Passed + Passed / Like + Dislike / Dislike + Like = No match
    """)

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

        # Parse dates and add date column
        df_mutual['created_at'] = pd.to_datetime(df_mutual['created_at'])
        df_mutual['action_date'] = df_mutual['created_at'].dt.date

        # Treat NULL/None as 'passed'
        df_mutual['is_liked'] = df_mutual['is_liked'].fillna('passed')

        # Filter to only actions (liked, disliked, passed)
        actions_df = df_mutual[df_mutual['is_liked'].isin(['liked', 'disliked', 'passed'])][
            ['current_user_id', 'matched_user_id', 'is_liked', 'action_date', 'mutual_score', 'origin_phase', 'created_at']
        ].copy()

        if actions_df.empty:
            st.info("No actions (likes/dislikes/passes) found in the selected date range.")
        else:
            # Get unique dates sorted
            unique_dates = sorted(actions_df['action_date'].unique())

            # Build historical likes lookup: {(user_a, user_b): earliest_like_date}
            # This tracks when user_a first liked user_b
            likes_history = {}
            likes_df = actions_df[actions_df['is_liked'] == 'liked']
            for _, row in likes_df.iterrows():
                key = (row['current_user_id'], row['matched_user_id'])
                like_date = row['action_date']
                if key not in likes_history or like_date < likes_history[key]:
                    likes_history[key] = like_date

            def find_matches_for_date(target_date, actions_df, likes_history, already_matched_pairs):
                """Find all matches for a specific date using the new algorithm.
                Returns (matches, missed_matches) tuple.

                Rules:
                1. Like + Like (same day) = Match
                2. Like + Passed (same day) = Match if 'passed' user liked on a previous day
                3. Passed + Like (same day) = Match if 'passed' user liked on a previous day
                4. Like (today) + No action (today) = Match if other user liked on a previous day
                5. Passed + Passed / Like + Dislike / Dislike + Like = No match
                """
                matches = []
                missed_matches = []
                seen_pairs = set()

                # Get actions for this specific date
                day_actions = actions_df[actions_df['action_date'] == target_date]

                # Build lookup for this day: {(user_a, user_b): action}
                day_action_lookup = {}
                day_details_lookup = {}
                for _, row in day_actions.iterrows():
                    key = (row['current_user_id'], row['matched_user_id'])
                    day_action_lookup[key] = row['is_liked']
                    day_details_lookup[key] = {
                        'mutual_score': row['mutual_score'],
                        'origin_phase': row['origin_phase'],
                        'created_at': row['created_at']
                    }

                # For each action on this day, check if there's a matching action
                for (user1, user2), action1 in day_action_lookup.items():
                    pair_key = tuple(sorted([user1, user2]))
                    if pair_key in seen_pairs or pair_key in already_matched_pairs:
                        continue

                    # Get user2's action towards user1 on this day
                    action2 = day_action_lookup.get((user2, user1))

                    is_match = False
                    is_missed = False
                    match_type = ""
                    missed_reason = ""

                    if action2 is not None:
                        # Both users took action on the same day
                        if action1 == 'liked' and action2 == 'liked':
                            is_match = True
                            match_type = "Like + Like"
                        elif action1 == 'liked' and action2 == 'passed':
                            # Check if user2 liked user1 on a previous day
                            prev_like_date = likes_history.get((user2, user1))
                            if prev_like_date and prev_like_date < target_date:
                                is_match = True
                                match_type = "Like + Passed (prev like)"
                            else:
                                is_missed = True
                                missed_reason = "Like + Passed (no prev like)"
                        elif action1 == 'passed' and action2 == 'liked':
                            # Check if user1 liked user2 on a previous day
                            prev_like_date = likes_history.get((user1, user2))
                            if prev_like_date and prev_like_date < target_date:
                                is_match = True
                                match_type = "Passed + Like (prev like)"
                            else:
                                is_missed = True
                                missed_reason = "Passed + Like (no prev like)"
                        elif action1 == 'passed' and action2 == 'passed':
                            is_missed = True
                            missed_reason = "Passed + Passed"
                        elif action1 == 'liked' and action2 == 'disliked':
                            is_missed = True
                            missed_reason = "Like + Dislike"
                        elif action1 == 'disliked' and action2 == 'liked':
                            is_missed = True
                            missed_reason = "Dislike + Like"
                        elif action1 == 'disliked' and action2 == 'disliked':
                            is_missed = True
                            missed_reason = "Dislike + Dislike"
                        elif action1 == 'disliked' and action2 == 'passed':
                            is_missed = True
                            missed_reason = "Dislike + Passed"
                        elif action1 == 'passed' and action2 == 'disliked':
                            is_missed = True
                            missed_reason = "Passed + Dislike"
                    else:
                        # User2 did NOT take action on this day
                        # Check if user1 liked today AND user2 liked on a previous day
                        if action1 == 'liked':
                            prev_like_date = likes_history.get((user2, user1))
                            if prev_like_date and prev_like_date < target_date:
                                is_match = True
                                match_type = "Like + Previous Like"

                    details = day_details_lookup.get((user1, user2), day_details_lookup.get((user2, user1), {}))

                    if is_match:
                        seen_pairs.add(pair_key)
                        matches.append({
                            'user_1': user1,
                            'user_2': user2,
                            'match_date': target_date,
                            'match_type': match_type,
                            'mutual_score': details.get('mutual_score'),
                            'origin_phase': details.get('origin_phase'),
                            'created_at': details.get('created_at')
                        })
                    elif is_missed:
                        seen_pairs.add(pair_key)
                        missed_matches.append({
                            'user_1': user1,
                            'user_2': user2,
                            'match_date': target_date,
                            'missed_reason': missed_reason,
                            'action_1': action1,
                            'action_2': action2,
                            'mutual_score': details.get('mutual_score'),
                            'origin_phase': details.get('origin_phase'),
                            'created_at': details.get('created_at')
                        })

                return matches, missed_matches

            # Find matches for all dates
            all_matches_by_date = {}
            all_matches_combined = []
            all_missed_by_date = {}
            all_missed_combined = []
            already_matched_pairs = set()  # Track pairs already matched to avoid duplicates

            for d in unique_dates:
                day_matches, day_missed = find_matches_for_date(d, actions_df, likes_history, already_matched_pairs)
                if day_matches:
                    all_matches_by_date[d] = day_matches
                    all_matches_combined.extend(day_matches)
                    # Add matched pairs to the set
                    for m in day_matches:
                        already_matched_pairs.add(tuple(sorted([m['user_1'], m['user_2']])))
                if day_missed:
                    all_missed_by_date[d] = day_missed
                    all_missed_combined.extend(day_missed)

            # Date filter dropdown - include dates with matches OR missed matches
            dates_with_data = set(all_matches_by_date.keys()) | set(all_missed_by_date.keys())
            date_options = ["All Dates"] + [str(d) for d in sorted(dates_with_data)]
            selected_date_filter = st.selectbox("Filter by Date", options=date_options, index=0)

            # Determine which matches and missed matches to show
            if selected_date_filter == "All Dates":
                # Deduplicate combined matches (same pair might appear on multiple days)
                seen_combined = set()
                display_matches = []
                for m in all_matches_combined:
                    pair_key = tuple(sorted([m['user_1'], m['user_2']]))
                    if pair_key not in seen_combined:
                        seen_combined.add(pair_key)
                        display_matches.append(m)
                # Deduplicate missed matches
                seen_missed = set()
                display_missed = []
                for m in all_missed_combined:
                    pair_key = tuple(sorted([m['user_1'], m['user_2']]))
                    if pair_key not in seen_missed:
                        seen_missed.add(pair_key)
                        display_missed.append(m)
            else:
                selected_date_obj = datetime.strptime(selected_date_filter, '%Y-%m-%d').date()
                display_matches = all_matches_by_date.get(selected_date_obj, [])
                display_missed = all_missed_by_date.get(selected_date_obj, [])

            # Show metrics
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            with col_m1:
                st.metric("Matches", len(display_matches))
            with col_m2:
                st.metric("Missed Matches", len(display_missed))
            with col_m3:
                st.metric("Total Unique Matches", len(set(
                    tuple(sorted([m['user_1'], m['user_2']])) for m in all_matches_combined
                )))
            with col_m4:
                st.metric("Total Missed", len(set(
                    tuple(sorted([m['user_1'], m['user_2']])) for m in all_missed_combined
                )))

            st.divider()

            # --- Unique Males/Females with Matches Section ---
            if display_matches:
                # Collect all user IDs from matches
                match_user_ids = list(set(
                    [m['user_1'] for m in display_matches] +
                    [m['user_2'] for m in display_matches]
                ))
                match_user_ids_tuple = tuple(sorted(match_user_ids))

                # Fetch genders for all matched users
                with st.spinner("Loading gender data for matched users..."):
                    matched_user_genders = fetch_user_genders(match_user_ids_tuple)
                    matched_user_profiles = fetch_user_profiles_batch(match_user_ids_tuple)

                # Count matches per user
                user_match_counts = {}
                for m in display_matches:
                    user_match_counts[m['user_1']] = user_match_counts.get(m['user_1'], 0) + 1
                    user_match_counts[m['user_2']] = user_match_counts.get(m['user_2'], 0) + 1

                # Fetch contact info for phone numbers
                with st.spinner("Loading contact data..."):
                    _, matched_user_phones = fetch_user_contact_batch(match_user_ids_tuple)

                # Build a lookup for each user's matched partners
                user_matched_partners = {}
                for m in display_matches:
                    u1, u2 = m['user_1'], m['user_2']
                    if u1 not in user_matched_partners:
                        user_matched_partners[u1] = []
                    if u2 not in user_matched_partners:
                        user_matched_partners[u2] = []
                    user_matched_partners[u1].append(u2)
                    user_matched_partners[u2].append(u1)

                # Split by gender
                males_with_matches = []
                females_with_matches = []
                for uid in match_user_ids:
                    gender = matched_user_genders.get(uid)
                    profile = matched_user_profiles.get(uid, {})
                    phone = matched_user_phones.get(uid) or profile.get('phone_num') or 'N/A'
                    user_data = {
                        'user_id': uid,
                        'name': profile.get('name', 'Unknown'),
                        'age': profile.get('age', 'N/A'),
                        'city': profile.get('city', 'N/A'),
                        'phone': phone,
                        'match_count': user_match_counts.get(uid, 0),
                        'matched_partner_ids': user_matched_partners.get(uid, [])
                    }
                    if gender == 'male':
                        males_with_matches.append(user_data)
                    elif gender == 'female':
                        females_with_matches.append(user_data)

                # Sort by match count descending
                males_with_matches = sorted(males_with_matches, key=lambda x: -x['match_count'])
                females_with_matches = sorted(females_with_matches, key=lambda x: -x['match_count'])

                st.markdown("### Users with Matches by Gender")

                col_males_matches, col_females_matches = st.columns(2)

                with col_males_matches:
                    st.markdown(f"#### Males with Matches ({len(males_with_matches)})")
                    if males_with_matches:
                        # Create dataframe
                        males_df = pd.DataFrame(males_with_matches)
                        males_display_df = males_df[['user_id', 'name', 'age', 'city', 'phone', 'match_count']].copy()
                        males_display_df.columns = ['User ID', 'Name', 'Age', 'City', 'Phone', 'Matches']

                        # Display dataframe with row selection
                        male_selection = st.dataframe(
                            males_display_df,
                            use_container_width=True,
                            hide_index=True,
                            height=400,
                            selection_mode="single-row",
                            on_select="rerun",
                            key="males_table"
                        )

                        # Show matched users for selected male
                        if male_selection and male_selection.selection and male_selection.selection.rows:
                            selected_idx = male_selection.selection.rows[0]
                            selected_male_user = males_with_matches[selected_idx]
                            st.divider()
                            partner_ids = selected_male_user.get('matched_partner_ids', [])
                            if partner_ids:
                                st.markdown(f"**{selected_male_user['name']}'s Matches ({len(partner_ids)}):**")
                                for pid in partner_ids:
                                    p_profile = matched_user_profiles.get(pid, {})
                                    p_phone = matched_user_phones.get(pid) or p_profile.get('phone_num') or 'N/A'
                                    p_gender = matched_user_genders.get(pid, 'N/A')
                                    with st.expander(f"{p_profile.get('name', 'Unknown')} ({p_gender})"):
                                        st.markdown(f"**User ID:** `{pid}`")
                                        st.markdown(f"**Name:** {p_profile.get('name', 'Unknown')}")
                                        st.markdown(f"**Age:** {p_profile.get('age', 'N/A')}")
                                        st.markdown(f"**City:** {p_profile.get('city', 'N/A')}")
                                        st.markdown(f"**Phone:** {p_phone}")
                            else:
                                st.info("No matched partners found")
                    else:
                        st.info("No males found in matches")

                with col_females_matches:
                    st.markdown(f"#### Females with Matches ({len(females_with_matches)})")
                    if females_with_matches:
                        # Create dataframe
                        females_df = pd.DataFrame(females_with_matches)
                        females_display_df = females_df[['user_id', 'name', 'age', 'city', 'phone', 'match_count']].copy()
                        females_display_df.columns = ['User ID', 'Name', 'Age', 'City', 'Phone', 'Matches']

                        # Display dataframe with row selection
                        female_selection = st.dataframe(
                            females_display_df,
                            use_container_width=True,
                            hide_index=True,
                            height=400,
                            selection_mode="single-row",
                            on_select="rerun",
                            key="females_table"
                        )

                        # Show matched users for selected female
                        if female_selection and female_selection.selection and female_selection.selection.rows:
                            selected_idx = female_selection.selection.rows[0]
                            selected_female_user = females_with_matches[selected_idx]
                            st.divider()
                            partner_ids = selected_female_user.get('matched_partner_ids', [])
                            if partner_ids:
                                st.markdown(f"**{selected_female_user['name']}'s Matches ({len(partner_ids)}):**")
                                for pid in partner_ids:
                                    p_profile = matched_user_profiles.get(pid, {})
                                    p_phone = matched_user_phones.get(pid) or p_profile.get('phone_num') or 'N/A'
                                    p_gender = matched_user_genders.get(pid, 'N/A')
                                    with st.expander(f"{p_profile.get('name', 'Unknown')} ({p_gender})"):
                                        st.markdown(f"**User ID:** `{pid}`")
                                        st.markdown(f"**Name:** {p_profile.get('name', 'Unknown')}")
                                        st.markdown(f"**Age:** {p_profile.get('age', 'N/A')}")
                                        st.markdown(f"**City:** {p_profile.get('city', 'N/A')}")
                                        st.markdown(f"**Phone:** {p_phone}")
                            else:
                                st.info("No matched partners found")
                    else:
                        st.info("No females found in matches")

                st.divider()

            # Build action history lookup for display: {(user_a, user_b): [(date, action), ...]}
            action_history = {}
            for _, row in actions_df.iterrows():
                key = (row['current_user_id'], row['matched_user_id'])
                if key not in action_history:
                    action_history[key] = []
                action_history[key].append({
                    'date': row['action_date'],
                    'action': row['is_liked']
                })
            # Sort each user's actions by date
            for key in action_history:
                action_history[key] = sorted(action_history[key], key=lambda x: x['date'])

            def format_action_history(user_from, user_to):
                """Format action history for display."""
                history = action_history.get((user_from, user_to), [])
                if not history:
                    return "No actions"
                lines = []
                for h in history:
                    action_emoji = {"liked": "❤️", "passed": "⏭️", "disliked": "👎"}.get(h['action'], "❓")
                    lines.append(f"{action_emoji} {h['action'].capitalize()} on {h['date']}")
                return "\n".join(lines)

            # Display matches
            if not display_matches:
                st.info("No matches found for the selected date.")
            else:
                # Group matches by type for summary
                match_type_counts = {}
                for m in display_matches:
                    mtype = m['match_type']
                    match_type_counts[mtype] = match_type_counts.get(mtype, 0) + 1

                st.markdown("#### Match Type Breakdown")
                match_type_cols = st.columns(len(match_type_counts) if match_type_counts else 1)
                for idx, (mtype, count) in enumerate(sorted(match_type_counts.items(), key=lambda x: -x[1])):
                    with match_type_cols[idx % len(match_type_cols)]:
                        st.metric(mtype, count)

                st.divider()

                # Get all user IDs for profile fetching
                all_mutual_user_ids = list(set(
                    [p['user_1'] for p in display_matches] +
                    [p['user_2'] for p in display_matches]
                ))
                all_mutual_user_ids_tuple = tuple(sorted(all_mutual_user_ids))

                with st.spinner("Loading user profiles..."):
                    mutual_profiles = fetch_user_profiles_batch(all_mutual_user_ids_tuple)
                    mutual_genders = fetch_user_genders(all_mutual_user_ids_tuple)
                    mutual_emails, mutual_phones = fetch_user_contact_batch(all_mutual_user_ids_tuple)

                # Display each mutual pair
                for i, pair in enumerate(display_matches):
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

                    match_type_badge = f"[{pair['match_type']}]" if pair.get('match_type') else ""
                    with st.expander(f"#{i+1}: {user1_name} ({user1_gender}) + {user2_name} ({user2_gender}) {match_type_badge}"):
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
                            # Show action history: user1's actions towards user2
                            st.markdown("---")
                            st.markdown(f"**Actions towards {user2_name}:**")
                            st.markdown(format_action_history(user1_id, user2_id))

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
                            # Show action history: user2's actions towards user1
                            st.markdown("---")
                            st.markdown(f"**Actions towards {user1_name}:**")
                            st.markdown(format_action_history(user2_id, user1_id))

                        st.divider()
                        st.markdown(f"**Match Type:** {pair.get('match_type', 'N/A')} | **Match Date:** {pair['match_date']} | **Mutual Score:** {pair['mutual_score']} | **Phase:** {pair['origin_phase']}")


# --- Tab: Per User Matches ---
with tab_per_user:
    st.subheader("Per User Matches")
    st.markdown("View each user with all their match details listed below them")

    # Fetch data with filters
    per_user_matches_data = fetch_overview_stats(
        run_id=run_id_filter,
        origin_phase=phase_filter,
        start_date=start_date,
        end_date=end_date
    )

    if not per_user_matches_data:
        st.info("No matches found for the selected filters.")
    else:
        df_per_user = pd.DataFrame(per_user_matches_data)

        # Parse dates and add date column
        df_per_user['created_at'] = pd.to_datetime(df_per_user['created_at'])
        df_per_user['action_date'] = df_per_user['created_at'].dt.date

        # Treat NULL/None as 'passed'
        df_per_user['is_liked'] = df_per_user['is_liked'].fillna('passed')

        # Filter to only actions (liked, disliked, passed)
        actions_per_user_df = df_per_user[df_per_user['is_liked'].isin(['liked', 'disliked', 'passed'])][
            ['current_user_id', 'matched_user_id', 'is_liked', 'action_date', 'mutual_score', 'origin_phase', 'created_at']
        ].copy()

        if actions_per_user_df.empty:
            st.info("No actions (likes/dislikes/passes) found in the selected date range.")
        else:
            # Get unique dates sorted
            unique_dates_pu = sorted(actions_per_user_df['action_date'].unique())

            # Build historical likes lookup
            likes_history_pu = {}
            likes_df_pu = actions_per_user_df[actions_per_user_df['is_liked'] == 'liked']
            for _, row in likes_df_pu.iterrows():
                key = (row['current_user_id'], row['matched_user_id'])
                like_date = row['action_date']
                if key not in likes_history_pu or like_date < likes_history_pu[key]:
                    likes_history_pu[key] = like_date

            def find_matches_for_date_pu(target_date, actions_df, likes_history, already_matched_pairs):
                """Find all matches for a specific date."""
                matches = []
                seen_pairs = set()

                day_actions = actions_df[actions_df['action_date'] == target_date]
                day_action_lookup = {}
                day_details_lookup = {}
                for _, row in day_actions.iterrows():
                    key = (row['current_user_id'], row['matched_user_id'])
                    day_action_lookup[key] = row['is_liked']
                    day_details_lookup[key] = {
                        'mutual_score': row['mutual_score'],
                        'origin_phase': row['origin_phase'],
                        'created_at': row['created_at']
                    }

                for (user1, user2), action1 in day_action_lookup.items():
                    pair_key = tuple(sorted([user1, user2]))
                    if pair_key in seen_pairs or pair_key in already_matched_pairs:
                        continue

                    action2 = day_action_lookup.get((user2, user1))
                    is_match = False
                    match_type = ""

                    if action2 is not None:
                        if action1 == 'liked' and action2 == 'liked':
                            is_match = True
                            match_type = "Like + Like"
                        elif action1 == 'liked' and action2 == 'passed':
                            prev_like_date = likes_history.get((user2, user1))
                            if prev_like_date and prev_like_date < target_date:
                                is_match = True
                                match_type = "Like + Passed (prev like)"
                        elif action1 == 'passed' and action2 == 'liked':
                            prev_like_date = likes_history.get((user1, user2))
                            if prev_like_date and prev_like_date < target_date:
                                is_match = True
                                match_type = "Passed + Like (prev like)"
                    else:
                        if action1 == 'liked':
                            prev_like_date = likes_history.get((user2, user1))
                            if prev_like_date and prev_like_date < target_date:
                                is_match = True
                                match_type = "Like + Previous Like"

                    if is_match:
                        seen_pairs.add(pair_key)
                        details = day_details_lookup.get((user1, user2), day_details_lookup.get((user2, user1), {}))
                        matches.append({
                            'user_1': user1,
                            'user_2': user2,
                            'match_date': target_date,
                            'match_type': match_type,
                            'mutual_score': details.get('mutual_score'),
                            'origin_phase': details.get('origin_phase'),
                            'created_at': details.get('created_at')
                        })

                return matches

            # Find all matches
            all_matches_pu = []
            already_matched_pairs_pu = set()

            for d in unique_dates_pu:
                day_matches = find_matches_for_date_pu(d, actions_per_user_df, likes_history_pu, already_matched_pairs_pu)
                if day_matches:
                    all_matches_pu.extend(day_matches)
                    for m in day_matches:
                        already_matched_pairs_pu.add(tuple(sorted([m['user_1'], m['user_2']])))

            if not all_matches_pu:
                st.info("No mutual matches found.")
            else:
                # Date filter
                dates_with_matches_pu = sorted(set(m['match_date'] for m in all_matches_pu))
                date_options_pu = ["All Dates"] + [str(d) for d in dates_with_matches_pu]
                selected_date_pu = st.selectbox("Filter by Date", options=date_options_pu, index=0, key="per_user_date_filter")

                if selected_date_pu == "All Dates":
                    display_matches_pu = all_matches_pu
                else:
                    selected_date_obj_pu = datetime.strptime(selected_date_pu, '%Y-%m-%d').date()
                    display_matches_pu = [m for m in all_matches_pu if m['match_date'] == selected_date_obj_pu]

                # Collect all user IDs
                all_user_ids_pu = list(set(
                    [m['user_1'] for m in display_matches_pu] +
                    [m['user_2'] for m in display_matches_pu]
                ))

                # Fetch profiles, genders, and contact info
                with st.spinner("Loading user data..."):
                    all_user_ids_tuple_pu = tuple(sorted(all_user_ids_pu))
                    profiles_pu = fetch_user_profiles_batch(all_user_ids_tuple_pu)
                    genders_pu = fetch_user_genders(all_user_ids_tuple_pu)
                    emails_pu, phones_pu = fetch_user_contact_batch(all_user_ids_tuple_pu)

                # Build user -> matches mapping
                user_matches_map = {}
                for m in display_matches_pu:
                    u1, u2 = m['user_1'], m['user_2']
                    if u1 not in user_matches_map:
                        user_matches_map[u1] = []
                    if u2 not in user_matches_map:
                        user_matches_map[u2] = []
                    user_matches_map[u1].append({'partner_id': u2, 'match_date': m['match_date'], 'match_type': m['match_type'], 'mutual_score': m['mutual_score']})
                    user_matches_map[u2].append({'partner_id': u1, 'match_date': m['match_date'], 'match_type': m['match_type'], 'mutual_score': m['mutual_score']})

                # Build user data list
                users_data_pu = []
                for uid in all_user_ids_pu:
                    profile = profiles_pu.get(uid, {})
                    users_data_pu.append({
                        'user_id': uid,
                        'name': profile.get('name', 'Unknown'),
                        'age': profile.get('age', 'N/A'),
                        'gender': genders_pu.get(uid, 'N/A'),
                        'city': profile.get('city', 'N/A'),
                        'phone': phones_pu.get(uid) or profile.get('phone_num') or 'N/A',
                        'email': emails_pu.get(uid, 'N/A'),
                        'match_count': len(user_matches_map.get(uid, [])),
                        'matches': user_matches_map.get(uid, [])
                    })

                # Sort by match count descending
                users_data_pu = sorted(users_data_pu, key=lambda x: -x['match_count'])

                # Gender filter
                gender_filter_pu = st.radio("Filter by Gender", options=["All", "Male", "Female"], horizontal=True, key="per_user_gender_filter")

                if gender_filter_pu == "Male":
                    users_data_pu = [u for u in users_data_pu if u['gender'] == 'male']
                elif gender_filter_pu == "Female":
                    users_data_pu = [u for u in users_data_pu if u['gender'] == 'female']

                st.metric("Total Users with Matches", len(users_data_pu))
                st.divider()

                # Display each user with their matches
                for user in users_data_pu:
                    with st.expander(f"{user['name']} ({user['gender']}) - {user['match_count']} matches"):
                        # User details
                        st.markdown(f"**User ID:** `{user['user_id']}`")
                        col_u1, col_u2, col_u3 = st.columns(3)
                        with col_u1:
                            st.markdown(f"**Name:** {user['name']}")
                            st.markdown(f"**Gender:** {user['gender']}")
                        with col_u2:
                            st.markdown(f"**Age:** {user['age']}")
                            st.markdown(f"**City:** {user['city']}")
                        with col_u3:
                            st.markdown(f"**Phone:** {user['phone']}")
                            st.markdown(f"**Email:** {user['email']}")

                        st.divider()
                        st.markdown(f"**Matches ({user['match_count']}):**")

                        # Display each match as a row
                        for idx, match in enumerate(user['matches']):
                            partner_id = match['partner_id']
                            partner_profile = profiles_pu.get(partner_id, {})
                            partner_gender = genders_pu.get(partner_id, 'N/A')
                            partner_phone = phones_pu.get(partner_id) or partner_profile.get('phone_num') or 'N/A'
                            partner_email = emails_pu.get(partner_id, 'N/A')
                            partner_photos = partner_profile.get('profile_images') or partner_profile.get('instagram_images') or []

                            st.markdown(f"---")
                            col_m1, col_m2, col_m3, col_m4 = st.columns([1, 2, 2, 2])
                            with col_m1:
                                if partner_photos:
                                    st.image(partner_photos[0], width=80)
                                else:
                                    st.markdown("No photo")
                            with col_m2:
                                st.markdown(f"**{partner_profile.get('name', 'Unknown')}**")
                                st.markdown(f"ID: `{partner_id}`")
                                st.markdown(f"Gender: {partner_gender}")
                                st.markdown(f"Age: {partner_profile.get('age', 'N/A')}")
                            with col_m3:
                                st.markdown(f"City: {partner_profile.get('city', 'N/A')}")
                                st.markdown(f"Phone: {partner_phone}")
                                st.markdown(f"Email: {partner_email}")
                            with col_m4:
                                st.markdown(f"Match Date: {match['match_date']}")
                                st.markdown(f"Type: {match['match_type']}")
                                st.markdown(f"Score: {match['mutual_score']}")


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
                matched_genders = fetch_user_genders(tuple(sorted(matched_user_ids)))

            # Filter to only males
            male_user_ids = [uid for uid in matched_user_ids if matched_genders.get(uid) == 'male']

            if male_user_ids:
                # Fetch profiles and contact info for males
                male_user_ids_tuple = tuple(sorted(male_user_ids))
                male_profiles = fetch_user_profiles_batch(male_user_ids_tuple)
                male_emails, male_phones = fetch_user_contact_batch(male_user_ids_tuple)

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
                matched_genders_f = fetch_user_genders(tuple(sorted(matched_user_ids_f)))

            # Filter to only females
            female_user_ids = [uid for uid in matched_user_ids_f if matched_genders_f.get(uid) == 'female']

            if female_user_ids:
                # Fetch profiles and contact info for females
                female_user_ids_tuple = tuple(sorted(female_user_ids))
                female_profiles = fetch_user_profiles_batch(female_user_ids_tuple)
                female_emails, female_phones = fetch_user_contact_batch(female_user_ids_tuple)

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
            st.line_chart(daily_engagement.set_index('date')['likes'])
        with col2:
            st.markdown("**Views per Day**")
            st.line_chart(daily_engagement.set_index('date')['views'])

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
