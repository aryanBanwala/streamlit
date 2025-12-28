"""
Match Analytics Page - User matches analytics with 8 metric tabs.
"""
import streamlit as st
import time
from datetime import datetime
import os
import sys
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Add parent directory for imports
current_dir = os.path.dirname(__file__)
parent_dir = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.insert(0, parent_dir)

from services.match_analytics import (
    data_exists,
    get_last_refresh_time,
    delete_old_jsons,
    fetch_user_matches,
    fetch_user_metadata,
    save_json_files,
    load_json_files,
    get_available_dates,
    filter_data
)

# --- Page Title ---
st.title("Match Analytics")

# --- Custom CSS for modern UI ---
st.markdown("""
<style>
/* Sticky header container */
.sticky-header {
    position: sticky;
    top: 0;
    z-index: 999;
    background: var(--background-color);
    padding: 1rem 0;
    border-bottom: 1px solid rgba(128, 128, 128, 0.2);
    margin-bottom: 1rem;
}

/* Date chips container */
.date-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 8px 0;
}

/* Individual date chip */
.date-chip {
    display: inline-flex;
    align-items: center;
    padding: 6px 12px;
    border-radius: 20px;
    font-size: 14px;
    cursor: pointer;
    transition: all 0.2s ease;
    border: 1px solid rgba(128, 128, 128, 0.3);
}

.date-chip.selected {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border-color: transparent;
    box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
}

.date-chip:not(.selected) {
    background: rgba(128, 128, 128, 0.1);
}

.date-chip:hover:not(.selected) {
    background: rgba(128, 128, 128, 0.2);
    border-color: rgba(102, 126, 234, 0.5);
}

/* Full screen loading overlay */
.loading-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.85);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    z-index: 9999;
    color: white;
}

.loading-content {
    background: rgba(30, 30, 30, 0.95);
    padding: 40px 60px;
    border-radius: 16px;
    text-align: center;
    max-width: 600px;
    width: 90%;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}

.loading-title {
    font-size: 24px;
    margin-bottom: 24px;
    color: #fff;
}

.progress-container {
    background: rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    height: 12px;
    margin: 20px 0;
    overflow: hidden;
}

.progress-bar {
    height: 100%;
    background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    border-radius: 12px;
    transition: width 0.3s ease;
}

.step-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 0;
    font-size: 14px;
    text-align: left;
}

.step-icon {
    font-size: 18px;
}

.elapsed-time {
    margin-top: 20px;
    font-size: 13px;
    color: rgba(255, 255, 255, 0.6);
}

/* No data screen */
.no-data-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 80px 20px;
    text-align: center;
}

.no-data-icon {
    font-size: 64px;
    margin-bottom: 24px;
    opacity: 0.5;
}

.no-data-title {
    font-size: 24px;
    margin-bottom: 12px;
    color: var(--text-color);
}

.no-data-subtitle {
    font-size: 16px;
    color: rgba(128, 128, 128, 0.8);
    margin-bottom: 32px;
}

/* Filter section styling */
.filter-section {
    background: rgba(128, 128, 128, 0.05);
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 16px;
}

.filter-label {
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: rgba(128, 128, 128, 0.7);
    margin-bottom: 8px;
}

/* Refresh button area */
.refresh-area {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-top: 16px;
    padding-top: 16px;
    border-top: 1px solid rgba(128, 128, 128, 0.2);
}

.last-refreshed {
    font-size: 13px;
    color: rgba(128, 128, 128, 0.7);
}

/* Fix dataframe alignment - left align all content */
[data-testid="stDataFrame"] {
    width: 100% !important;
}

[data-testid="stDataFrame"] > div {
    width: 100% !important;
}

/* Target glide-data-grid cells */
[data-testid="stDataFrame"] [data-testid="glideDataEditor"] {
    width: 100% !important;
}

/* Force left alignment on all cell content */
.dvn-scroller .dvn-cell {
    justify-content: flex-start !important;
    text-align: left !important;
}

/* Target the actual cell spans */
[data-testid="stDataFrameResizable"] span {
    text-align: left !important;
}

/* Fix metric alignment */
[data-testid="stMetric"] {
    text-align: left !important;
}

/* Ensure tab content fills width */
.stTabs [data-baseweb="tab-panel"] {
    width: 100% !important;
}
</style>
""", unsafe_allow_html=True)


# --- Session State Initialization ---
if 'refresh_in_progress' not in st.session_state:
    st.session_state.refresh_in_progress = False
if 'selected_dates' not in st.session_state:
    st.session_state.selected_dates = []
if 'gender_filter' not in st.session_state:
    st.session_state.gender_filter = 'both'
if 'tier_filter' not in st.session_state:
    st.session_state.tier_filter = 'all'



def format_date_display(date_str: str) -> str:
    """Format YYYY-MM-DD to more readable format like 'Dec 28'."""
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        return dt.strftime('%b %d')
    except:
        return date_str


def run_refresh():
    """Execute the full refresh process with progress tracking."""
    st.session_state.refresh_in_progress = True

    # Create placeholder for loading UI
    loading_placeholder = st.empty()

    start_time = time.time()
    steps = [
        {'name': 'Deleting old cached JSON files...', 'status': 'pending'},
        {'name': 'Fetching user_matches', 'status': 'pending', 'progress': ''},
        {'name': 'Fetching user_metadata', 'status': 'pending', 'progress': ''},
        {'name': 'Processing & saving data...', 'status': 'pending'},
    ]

    def update_loading_ui(current_step: int, progress_pct: float, step_detail: str = ''):
        elapsed = int(time.time() - start_time)
        elapsed_str = f"{elapsed}s"

        # Estimate ETA based on progress
        if progress_pct > 0:
            eta = int((elapsed / progress_pct) * (100 - progress_pct))
            eta_str = f"~{eta}s"
        else:
            eta_str = "calculating..."

        # Update step statuses
        for i, step in enumerate(steps):
            if i < current_step:
                step['status'] = 'completed'
            elif i == current_step:
                step['status'] = 'in_progress'
                if step_detail:
                    step['progress'] = step_detail
            else:
                step['status'] = 'pending'

        # Build step HTML
        steps_html = ""
        for step in steps:
            if step['status'] == 'completed':
                icon = "✅"
            elif step['status'] == 'in_progress':
                icon = "🔄"
            else:
                icon = "⏳"

            progress_text = f" ({step.get('progress', '')})" if step.get('progress') else ""
            steps_html += f'<div class="step-item"><span class="step-icon">{icon}</span> {step["name"]}{progress_text}</div>'

        loading_placeholder.markdown(f"""
        <div class="loading-overlay">
            <div class="loading-content">
                <div class="loading-title">🔄 REFRESHING DATA...</div>
                <div class="progress-container">
                    <div class="progress-bar" style="width: {progress_pct}%"></div>
                </div>
                <div style="text-align: center; margin-bottom: 20px; font-size: 16px;">{int(progress_pct)}%</div>
                {steps_html}
                <div class="elapsed-time">Elapsed: {elapsed_str} | ETA: {eta_str}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    try:
        # Step 1: Delete old JSONs (5%)
        update_loading_ui(0, 2, '')
        delete_old_jsons()
        update_loading_ui(0, 5, '')
        time.sleep(0.3)

        # Step 2: Fetch user_matches (5% - 50%)
        matches_data = []
        def matches_progress(batch, total, rows):
            pct = 5 + (batch / total) * 45
            update_loading_ui(1, pct, f'Batch {batch}/{total} - {rows} rows')

        matches_data = fetch_user_matches(matches_progress)
        update_loading_ui(1, 50, f'Done - {len(matches_data)} rows')
        time.sleep(0.2)

        # Step 3: Fetch user_metadata (50% - 90%)
        metadata_data = []
        def metadata_progress(batch, total, rows):
            pct = 50 + (batch / total) * 40
            update_loading_ui(2, pct, f'Batch {batch}/{total} - {rows} rows')

        metadata_data = fetch_user_metadata(metadata_progress)
        update_loading_ui(2, 90, f'Done - {len(metadata_data)} rows')
        time.sleep(0.2)

        # Step 4: Process & Save (90% - 100%)
        update_loading_ui(3, 95, '')
        save_json_files(matches_data, metadata_data)
        update_loading_ui(3, 100, '')
        time.sleep(0.5)

    except Exception as e:
        loading_placeholder.empty()
        st.error(f"Error during refresh: {str(e)}")
        st.session_state.refresh_in_progress = False
        return

    loading_placeholder.empty()
    st.session_state.refresh_in_progress = False
    st.session_state.selected_dates = []  # Reset selection
    st.rerun()


# --- Check if data exists ---
if not data_exists():
    # Show No Data Screen
    st.markdown("""
    <div class="no-data-container">
        <div class="no-data-icon">📊</div>
        <div class="no-data-title">No Data Available</div>
        <div class="no-data-subtitle">Click the button below to fetch data from Supabase</div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("🔄 REFRESH DATA", type="primary", use_container_width=True):
            run_refresh()

    st.stop()


# --- Load Data ---
matches, metadata = load_json_files()
available_dates = get_available_dates(matches)
last_refresh = get_last_refresh_time()

# Initialize selected dates if empty (select latest 2 dates by default)
if not st.session_state.selected_dates and available_dates:
    st.session_state.selected_dates = available_dates[:2]


# --- STICKY HEADER WITH FILTERS ---
st.markdown("---")

# Date Filter Section
st.markdown("##### 📅 Select Dates")

# Create date selection using multiselect with custom styling
date_options = {date: format_date_display(date) for date in available_dates}

# Show dates as chips using columns
num_dates = len(available_dates)
if num_dates > 0:
    # Use multiselect for date selection
    selected = st.multiselect(
        "Select dates to analyze",
        options=available_dates,
        default=st.session_state.selected_dates,
        format_func=lambda x: format_date_display(x),
        label_visibility="collapsed"
    )
    st.session_state.selected_dates = selected

    # Quick selection buttons
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("Select All", use_container_width=True):
            st.session_state.selected_dates = available_dates.copy()
            st.rerun()
    with col2:
        if st.button("Clear All", use_container_width=True):
            st.session_state.selected_dates = []
            st.rerun()
    with col3:
        if st.button("Last 3 Days", use_container_width=True):
            st.session_state.selected_dates = available_dates[:3]
            st.rerun()
    with col4:
        if st.button("Last 7 Days", use_container_width=True):
            st.session_state.selected_dates = available_dates[:7]
            st.rerun()

st.markdown("")

# Gender and Tier Filters in columns
filter_col1, filter_col2, filter_col3 = st.columns([1, 1, 2])

with filter_col1:
    st.markdown("##### 👤 Gender")
    gender = st.radio(
        "Gender filter",
        options=['both', 'male', 'female'],
        format_func=lambda x: {'both': 'Both', 'male': 'Male Only', 'female': 'Female Only'}[x],
        horizontal=True,
        label_visibility="collapsed"
    )
    st.session_state.gender_filter = gender

with filter_col2:
    st.markdown("##### 🏷️ Tier")
    tier = st.radio(
        "Tier filter",
        options=['all', '1', '2', '3'],
        format_func=lambda x: {'all': 'All', '1': 'Tier 1', '2': 'Tier 2', '3': 'Tier 3'}[x],
        horizontal=True,
        label_visibility="collapsed"
    )
    st.session_state.tier_filter = tier

with filter_col3:
    st.markdown("##### 🔄 Data Refresh")
    refresh_col1, refresh_col2 = st.columns([1, 2])
    with refresh_col1:
        if st.button("🔄 REFRESH DATA", type="primary", use_container_width=True):
            run_refresh()
    with refresh_col2:
        if last_refresh:
            st.markdown(f"<div style='padding-top: 8px; color: rgba(128,128,128,0.7); font-size: 13px;'>Last Refreshed: {last_refresh}</div>", unsafe_allow_html=True)

st.markdown("---")

# --- Apply Filters ---
filtered_matches = filter_data(
    matches,
    metadata,
    selected_dates=st.session_state.selected_dates,
    gender=st.session_state.gender_filter,
    tier=st.session_state.tier_filter
)

# --- Summary Stats ---
total_matches = len(filtered_matches)
unique_users = len(set(m.get('current_user_id') for m in filtered_matches))

stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
with stat_col1:
    st.metric("Total Matches", f"{total_matches:,}")
with stat_col2:
    st.metric("Unique Users", f"{unique_users:,}")
with stat_col3:
    st.metric("Dates Selected", len(st.session_state.selected_dates))
with stat_col4:
    viewed_count = sum(1 for m in filtered_matches if m.get('is_viewed'))
    view_rate = (viewed_count / total_matches * 100) if total_matches > 0 else 0
    st.metric("View Rate", f"{view_rate:.1f}%")

st.markdown("---")

# --- Build user metadata lookup for tier analysis ---
user_lookup = {}
for user in metadata:
    user_lookup[user.get('user_id')] = {
        'gender': user.get('gender'),
        'tier': user.get('professional_tier')
    }

# --- METRIC TABS ---
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "1. Funnel", "2. Hours", "3. Time", "4. Rank",
    "5. Tier", "6. Dates", "7. KM", "8. Ghost"
])


# ============================================
# TAB 1: FUNNEL - Core User-Level Funnel
# ============================================
with tab1:
    st.markdown("### Core User Funnel")
    st.markdown("*All counts are unique `current_user_id` counts, NOT row counts.*")

    if not filtered_matches:
        st.warning("No data available for selected filters.")
    else:
        # Calculate funnel metrics
        # Group matches by user
        user_matches_map = {}
        for m in filtered_matches:
            uid = m.get('current_user_id')
            if uid not in user_matches_map:
                user_matches_map[uid] = []
            user_matches_map[uid].append(m)

        # Funnel counts
        users_with_matches = len(user_matches_map)

        users_viewed = set()
        users_engaged = set()  # know_more_count > 0
        users_decided = set()  # is_liked is not null
        users_liked = set()
        users_disliked = set()
        users_passed = set()

        for uid, user_match_list in user_matches_map.items():
            has_viewed = False
            has_engaged = False
            has_decided = False
            has_liked = False
            has_disliked = False
            has_passed = False

            for m in user_match_list:
                if m.get('is_viewed'):
                    has_viewed = True
                if m.get('know_more_count', 0) > 0:
                    has_engaged = True

                is_liked = m.get('is_liked')
                if is_liked is not None:
                    has_decided = True
                    if is_liked == 'liked':
                        has_liked = True
                    elif is_liked == 'disliked':
                        has_disliked = True
                    elif is_liked == 'passed':
                        has_passed = True

            if has_viewed:
                users_viewed.add(uid)
            if has_engaged:
                users_engaged.add(uid)
            if has_decided:
                users_decided.add(uid)
            if has_liked:
                users_liked.add(uid)
            if has_disliked:
                users_disliked.add(uid)
            if has_passed:
                users_passed.add(uid)

        users_no_action = users_with_matches - len(users_viewed)

        # Calculate "Users who Got Match" (mutual likes)
        # Step 1: Build a set of all (b, a) pairs where b liked a from FULL matches table
        all_likes_reverse = set()  # (matched_user_id, current_user_id) where is_liked = 'liked'
        for m in matches:  # Use full matches, not filtered
            if m.get('is_liked') == 'liked':
                all_likes_reverse.add((m.get('current_user_id'), m.get('matched_user_id')))

        # Step 2: For each a->b like in filtered data, check if b->a exists in full table
        users_got_match = set()
        for m in filtered_matches:
            if m.get('is_liked') == 'liked':
                a = m.get('current_user_id')
                b = m.get('matched_user_id')
                # Check if b liked a (reverse) exists in full table
                if (b, a) in all_likes_reverse:
                    users_got_match.add(a)
                    # If b->a is also in filtered data, b gets counted too
                    # But we only count users from filtered data (a is already from filtered)

        # Calculate percentages
        def calc_pct(val, base):
            return (val / base * 100) if base > 0 else 0

        # Build funnel data with tooltips
        funnel_data = [
            {
                'Stage': 'Users with Matches',
                'Count': users_with_matches,
                'Absolute %': 100.0,
                'Relative %': '-',
                'tooltip': 'Total unique users who received matches in selected date range'
            },
            {
                'Stage': 'Users who Viewed',
                'Count': len(users_viewed),
                'Absolute %': calc_pct(len(users_viewed), users_with_matches),
                'Relative %': calc_pct(len(users_viewed), users_with_matches),
                'tooltip': 'Users who opened and viewed at least 1 match (is_viewed = true)'
            },
            {
                'Stage': 'Users who Engaged (KM > 0)',
                'Count': len(users_engaged),
                'Absolute %': calc_pct(len(users_engaged), users_with_matches),
                'Relative %': calc_pct(len(users_engaged), len(users_viewed)) if len(users_viewed) > 0 else 0,
                'tooltip': 'Users who clicked "Know More" at least once on any match (know_more_count > 0)'
            },
            {
                'Stage': 'Users who Decided',
                'Count': len(users_decided),
                'Absolute %': calc_pct(len(users_decided), users_with_matches),
                'Relative %': calc_pct(len(users_decided), len(users_engaged)) if len(users_engaged) > 0 else 0,
                'tooltip': 'Users who took any action - liked, disliked, or passed on at least 1 match (is_liked is not null)'
            },
        ]

        # Sub-categories
        sub_data = [
            {
                'Stage': '  - Liked at least 1',
                'Count': len(users_liked),
                'Absolute %': calc_pct(len(users_liked), users_with_matches),
                'Relative %': calc_pct(len(users_liked), len(users_decided)) if len(users_decided) > 0 else 0,
                'tooltip': 'Users who liked at least 1 match (is_liked = "liked")'
            },
            {
                'Stage': '  - Disliked at least 1',
                'Count': len(users_disliked),
                'Absolute %': calc_pct(len(users_disliked), users_with_matches),
                'Relative %': calc_pct(len(users_disliked), len(users_decided)) if len(users_decided) > 0 else 0,
                'tooltip': 'Users who disliked at least 1 match (is_liked = "disliked")'
            },
            {
                'Stage': '  - Passed at least 1',
                'Count': len(users_passed),
                'Absolute %': calc_pct(len(users_passed), users_with_matches),
                'Relative %': calc_pct(len(users_passed), len(users_decided)) if len(users_decided) > 0 else 0,
                'tooltip': 'Users who passed on at least 1 match (is_liked = "passed")'
            },
            {
                'Stage': '  - Got Match (mutual like)',
                'Count': len(users_got_match),
                'Absolute %': calc_pct(len(users_got_match), users_with_matches),
                'Relative %': calc_pct(len(users_got_match), len(users_liked)) if len(users_liked) > 0 else 0,
                'tooltip': 'Users who liked someone AND that person also liked them back (a->b liked AND b->a liked). Checks reverse like from full table, not just selected dates.'
            },
        ]

        no_action_data = [
            {
                'Stage': 'Users No Action Yet',
                'Count': users_no_action,
                'Absolute %': calc_pct(users_no_action, users_with_matches),
                'Relative %': '-',
                'tooltip': 'Users who got matches but never opened/viewed any of them'
            },
        ]

        # Display table
        st.markdown("#### Detailed Breakdown")

        all_data = funnel_data + sub_data + no_action_data

        # Create DataFrame for display
        df_funnel = pd.DataFrame([
            {
                'Stage': row['Stage'],
                'Count': row['Count'],
                'Absolute %': f"{row['Absolute %']:.1f}%" if isinstance(row['Absolute %'], (int, float)) else row['Absolute %'],
                'Relative %': f"{row['Relative %']:.1f}%" if isinstance(row['Relative %'], (int, float)) else row['Relative %'],
            }
            for row in all_data
        ])

        st.dataframe(df_funnel, use_container_width=True, hide_index=True)

        # Show tooltips/explanations in an expander
        with st.expander("What do these metrics mean?"):
            for row in all_data:
                st.markdown(f"**{row['Stage'].strip()}**: {row['tooltip']}")

        # Key insights
        st.markdown("#### Key Insights")
        col1, col2, col3 = st.columns(3)
        with col1:
            view_rate = calc_pct(len(users_viewed), users_with_matches)
            st.metric("View Rate", f"{view_rate:.1f}%", help="% of users who viewed at least 1 match")
        with col2:
            engage_rate = calc_pct(len(users_engaged), len(users_viewed)) if len(users_viewed) > 0 else 0
            st.metric("Engagement Rate", f"{engage_rate:.1f}%", help="% of viewers who clicked Know More")
        with col3:
            like_rate = calc_pct(len(users_liked), len(users_decided)) if len(users_decided) > 0 else 0
            st.metric("Like Rate", f"{like_rate:.1f}%", help="% of deciders who liked someone")


# ============================================
# TAB 2: HOURS - Activity Hour Distribution
# ============================================
with tab2:
    st.markdown("### Activity Hour Distribution")
    st.markdown("*Unique user counts per hour (sorted by count, highest first)*")

    if not filtered_matches:
        st.warning("No data available for selected filters.")
    else:
        def extract_hour(timestamp_str):
            """Extract hour from ISO timestamp string."""
            if not timestamp_str:
                return None
            try:
                # Handle various timestamp formats
                if 'T' in timestamp_str:
                    dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                else:
                    dt = datetime.strptime(timestamp_str[:19], '%Y-%m-%d %H:%M:%S')
                return dt.hour
            except:
                return None

        def format_hour(hour):
            """Format hour as readable string like '9 PM'."""
            if hour == 0:
                return "12 AM"
            elif hour < 12:
                return f"{hour} AM"
            elif hour == 12:
                return "12 PM"
            else:
                return f"{hour - 12} PM"

        # 2a. View Hour Distribution
        view_hours = {}
        for m in filtered_matches:
            if m.get('is_viewed') and m.get('viewed_at'):
                hour = extract_hour(m.get('viewed_at'))
                if hour is not None:
                    uid = m.get('current_user_id')
                    if hour not in view_hours:
                        view_hours[hour] = set()
                    view_hours[hour].add(uid)

        # 2b. Like Hour Distribution
        like_hours = {}
        for m in filtered_matches:
            if m.get('is_liked') == 'liked' and m.get('liked_at'):
                hour = extract_hour(m.get('liked_at'))
                if hour is not None:
                    uid = m.get('current_user_id')
                    if hour not in like_hours:
                        like_hours[hour] = set()
                    like_hours[hour].add(uid)

        # 2c. Dislike/Pass Hour Distribution
        reject_hours = {}
        for m in filtered_matches:
            if m.get('is_liked') in ['disliked', 'passed'] and m.get('liked_at'):
                hour = extract_hour(m.get('liked_at'))
                if hour is not None:
                    uid = m.get('current_user_id')
                    if hour not in reject_hours:
                        reject_hours[hour] = set()
                    reject_hours[hour].add(uid)

        def create_hour_chart(hour_data, title, color):
            """Create horizontal bar chart for hour distribution."""
            if not hour_data:
                return None

            # Convert to counts and sort by count descending
            hour_counts = [(h, len(users)) for h, users in hour_data.items()]
            hour_counts.sort(key=lambda x: x[1], reverse=True)

            total_users = sum(c for _, c in hour_counts)

            df = pd.DataFrame([
                {
                    'Hour': f"Hour {h} ({format_hour(h)})",
                    'Users': count,
                    'Percentage': count / total_users * 100 if total_users > 0 else 0
                }
                for h, count in hour_counts
            ])

            fig = px.bar(
                df,
                y='Hour',
                x='Users',
                orientation='h',
                text=df.apply(lambda row: f"{row['Users']} ({row['Percentage']:.1f}%)", axis=1),
                color_discrete_sequence=[color]
            )
            fig.update_layout(
                title=title,
                height=500,
                margin=dict(l=20, r=20, t=60, b=20),
                yaxis={'categoryorder': 'total ascending'}
            )
            fig.update_traces(textposition='outside')

            # Calculate summary stats
            peak_hour = hour_counts[0][0] if hour_counts else 0
            top3_pct = sum(c for _, c in hour_counts[:3]) / total_users * 100 if total_users > 0 else 0
            dead_hours = [h for h, c in hour_counts if c / total_users * 100 < 1] if total_users > 0 else []

            return fig, {
                'peak': peak_hour,
                'top3_pct': top3_pct,
                'dead_hours': dead_hours,
                'total': total_users
            }

        # Display charts in columns
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### View Hours")
            result = create_hour_chart(view_hours, "When Users View Matches", "#667eea")
            if result:
                fig, stats = result
                st.plotly_chart(fig, use_container_width=True)
                st.caption(f"Peak: {format_hour(stats['peak'])} | Top 3 hrs: {stats['top3_pct']:.1f}% | Total: {stats['total']} users")

        with col2:
            st.markdown("#### Like Hours")
            result = create_hour_chart(like_hours, "When Users Like Matches", "#21C354")
            if result:
                fig, stats = result
                st.plotly_chart(fig, use_container_width=True)
                st.caption(f"Peak: {format_hour(stats['peak'])} | Top 3 hrs: {stats['top3_pct']:.1f}% | Total: {stats['total']} users")

        st.markdown("---")

        st.markdown("#### Dislike/Pass Hours")
        result = create_hour_chart(reject_hours, "When Users Reject Matches", "#f5576c")
        if result:
            fig, stats = result
            st.plotly_chart(fig, use_container_width=True)
            st.caption(f"Peak: {format_hour(stats['peak'])} | Top 3 hrs: {stats['top3_pct']:.1f}% | Total: {stats['total']} users")


# ============================================
# TAB 3: TIME - Time to Decision
# ============================================
with tab3:
    st.markdown("### Time to Decision")
    st.markdown("*How long after viewing did users make a decision? (liked_at - viewed_at)*")

    if not filtered_matches:
        st.warning("No data available for selected filters.")
    else:
        def parse_timestamp(ts_str):
            """Parse ISO timestamp string to datetime."""
            if not ts_str:
                return None
            try:
                if 'T' in ts_str:
                    return datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                else:
                    return datetime.strptime(ts_str[:19], '%Y-%m-%d %H:%M:%S')
            except:
                return None

        def format_time(minutes):
            """Format minutes to readable string."""
            if minutes < 1:
                return f"{minutes * 60:.0f} sec"
            elif minutes < 60:
                return f"{minutes:.1f} min"
            elif minutes < 1440:
                return f"{minutes / 60:.1f} hr"
            else:
                return f"{minutes / 1440:.1f} days"

        def get_time_bucket(minutes):
            """Categorize time difference into fixed buckets."""
            if minutes < 1:
                return "< 1 min"
            elif minutes < 2:
                return "1-2 min"
            elif minutes < 3:
                return "2-3 min"
            elif minutes < 4:
                return "3-4 min"
            elif minutes < 5:
                return "4-5 min"
            elif minutes < 10:
                return "5-10 min"
            elif minutes < 15:
                return "10-15 min"
            elif minutes < 20:
                return "15-20 min"
            elif minutes < 25:
                return "20-25 min"
            elif minutes < 30:
                return "25-30 min"
            elif minutes < 40:
                return "30-40 min"
            elif minutes < 50:
                return "40-50 min"
            elif minutes < 60:
                return "50-60 min"
            elif minutes < 120:  # 2 hours
                return "1-2 hr"
            elif minutes < 240:  # 4 hours
                return "2-4 hr"
            elif minutes < 360:  # 6 hours
                return "4-6 hr"
            elif minutes < 480:  # 8 hours
                return "6-8 hr"
            elif minutes < 960:  # 16 hours
                return "8-16 hr"
            elif minutes < 1440:  # 24 hours
                return "16-24 hr"
            else:
                return "24+ hr"

        # Define bucket order for sorting
        bucket_order = [
            "< 1 min",
            "1-2 min",
            "2-3 min",
            "3-4 min",
            "4-5 min",
            "5-10 min",
            "10-15 min",
            "15-20 min",
            "20-25 min",
            "25-30 min",
            "30-40 min",
            "40-50 min",
            "50-60 min",
            "1-2 hr",
            "2-4 hr",
            "4-6 hr",
            "6-8 hr",
            "8-16 hr",
            "16-24 hr",
            "24+ hr"
        ]

        # Collect time differences for LIKES vs DISLIKES/PASSES
        like_times = []  # (user_id, minutes)
        reject_times = []  # (user_id, minutes)

        for m in filtered_matches:
            viewed_at = parse_timestamp(m.get('viewed_at'))
            liked_at = parse_timestamp(m.get('liked_at'))
            is_liked = m.get('is_liked')

            if viewed_at and liked_at and is_liked:
                diff = (liked_at - viewed_at).total_seconds() / 60  # Convert to minutes
                if diff >= 0:  # Only positive differences (liked_at after viewed_at)
                    uid = m.get('current_user_id')
                    if is_liked == 'liked':
                        like_times.append((uid, diff))
                    elif is_liked in ['disliked', 'passed']:
                        reject_times.append((uid, diff))

        def create_time_bucket_chart(time_data, title, color):
            """Create horizontal bar chart for time bucket distribution."""
            if not time_data:
                return None, None

            # Count unique users per bucket
            bucket_users = {b: set() for b in bucket_order}
            all_minutes = []

            for uid, minutes in time_data:
                bucket = get_time_bucket(minutes)
                bucket_users[bucket].add(uid)
                all_minutes.append(minutes)

            # Convert to counts
            bucket_counts = [(b, len(bucket_users[b])) for b in bucket_order]
            total_users = sum(c for _, c in bucket_counts)

            if total_users == 0:
                return None, None

            df = pd.DataFrame([
                {
                    'Bucket': b,
                    'Users': count,
                    'Percentage': count / total_users * 100 if total_users > 0 else 0
                }
                for b, count in bucket_counts
            ])

            fig = px.bar(
                df,
                y='Bucket',
                x='Users',
                orientation='h',
                text=df.apply(lambda row: f"{row['Users']} ({row['Percentage']:.1f}%)", axis=1),
                color_discrete_sequence=[color]
            )
            fig.update_layout(
                title=title,
                height=max(500, len(bucket_order) * 28),
                margin=dict(l=20, r=20, t=60, b=20),
                yaxis={'categoryorder': 'array', 'categoryarray': bucket_order[::-1]}
            )
            fig.update_traces(textposition='outside')

            # Calculate stats
            avg_time = sum(all_minutes) / len(all_minutes) if all_minutes else 0
            sorted_minutes = sorted(all_minutes)
            median_time = sorted_minutes[len(sorted_minutes) // 2] if sorted_minutes else 0

            stats = {
                'avg': avg_time,
                'median': median_time,
                'total': total_users
            }

            return fig, stats

        # Display charts side by side
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### LIKES")
            result = create_time_bucket_chart(like_times, "Time to Like", "#21C354")
            if result[0]:
                fig, stats = result
                st.plotly_chart(fig, use_container_width=True)
                st.caption(f"Avg: {format_time(stats['avg'])} | Median: {format_time(stats['median'])} | {stats['total']} decisions")
            else:
                st.info("No like decisions with valid timestamps found.")

        with col2:
            st.markdown("#### DISLIKES/PASSES")
            result = create_time_bucket_chart(reject_times, "Time to Reject", "#f5576c")
            if result[0]:
                fig, stats = result
                st.plotly_chart(fig, use_container_width=True)
                st.caption(f"Avg: {format_time(stats['avg'])} | Median: {format_time(stats['median'])} | {stats['total']} decisions")
            else:
                st.info("No dislike/pass decisions with valid timestamps found.")

        st.markdown("---")

        # Comparison insight
        st.markdown("#### Comparison Insight")

        if like_times and reject_times:
            like_avg = sum(t for _, t in like_times) / len(like_times)
            reject_avg = sum(t for _, t in reject_times) / len(reject_times)

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Avg Time to Like", format_time(like_avg))
            with col2:
                st.metric("Avg Time to Reject", format_time(reject_avg))
            with col3:
                diff = like_avg - reject_avg
                if diff > 0:
                    st.metric("Difference", f"+{format_time(abs(diff))}", help="Likes take longer (users think before liking)")
                else:
                    st.metric("Difference", f"-{format_time(abs(diff))}", help="Rejects take longer")

            # Insight text
            if like_avg > reject_avg:
                st.success("**Good sign:** Users take more time before liking someone, indicating thoughtful decisions rather than impulse swipes.")
            else:
                st.warning("**Note:** Users take longer to reject than to like. This might indicate hesitation or users coming back to profiles before rejecting.")

            # Quick stats table
            st.markdown("#### Summary Table")

            # Calculate instant decision rates (< 1 min)
            like_instant = sum(1 for _, t in like_times if t < 1) / len(like_times) * 100 if like_times else 0
            reject_instant = sum(1 for _, t in reject_times if t < 1) / len(reject_times) * 100 if reject_times else 0

            summary_df = pd.DataFrame([
                {'Metric': 'Total Decisions', 'Likes': len(like_times), 'Dislikes/Passes': len(reject_times)},
                {'Metric': 'Average Time', 'Likes': format_time(like_avg), 'Dislikes/Passes': format_time(reject_avg)},
                {'Metric': 'Instant (< 1 min) %', 'Likes': f"{like_instant:.1f}%", 'Dislikes/Passes': f"{reject_instant:.1f}%"},
            ])
            st.dataframe(summary_df, use_container_width=True, hide_index=True)
        else:
            st.info("Need both likes and dislikes/passes data to show comparison.")


# ============================================
# TAB 4: RANK - Rank Performance
# ============================================
with tab4:
    st.markdown("### Rank Performance")
    st.markdown("*How do matches at different ranks (1-9) perform? All counts are unique users per rank.*")

    if not filtered_matches:
        st.warning("No data available for selected filters.")
    else:
        # Group matches by rank
        rank_data = {}  # rank -> list of matches

        for m in filtered_matches:
            rank = m.get('rank')
            if rank is not None:
                if rank not in rank_data:
                    rank_data[rank] = []
                rank_data[rank].append(m)

        # Calculate metrics for each rank
        rank_metrics = []

        for rank in sorted(rank_data.keys()):
            rank_matches = rank_data[rank]

            # Unique users at this rank
            all_users = set(m.get('current_user_id') for m in rank_matches)
            total_users = len(all_users)

            # Users who viewed at this rank
            viewed_users = set(m.get('current_user_id') for m in rank_matches if m.get('is_viewed'))
            viewed_count = len(viewed_users)

            # Average know_more_count at this rank (only for viewed matches)
            km_values = [m.get('know_more_count') or 0 for m in rank_matches if m.get('is_viewed')]
            km_avg = sum(km_values) / len(km_values) if km_values else 0

            # Users who liked at this rank
            liked_users = set(m.get('current_user_id') for m in rank_matches if m.get('is_liked') == 'liked')
            liked_count = len(liked_users)

            # Users who disliked at this rank
            disliked_users = set(m.get('current_user_id') for m in rank_matches if m.get('is_liked') == 'disliked')
            disliked_count = len(disliked_users)

            # Users who passed at this rank
            passed_users = set(m.get('current_user_id') for m in rank_matches if m.get('is_liked') == 'passed')
            passed_count = len(passed_users)

            # Calculate percentages
            view_pct = (viewed_count / total_users * 100) if total_users > 0 else 0
            like_pct = (liked_count / viewed_count * 100) if viewed_count > 0 else 0
            dislike_pct = (disliked_count / viewed_count * 100) if viewed_count > 0 else 0
            pass_pct = (passed_count / viewed_count * 100) if viewed_count > 0 else 0

            rank_metrics.append({
                'Rank': rank,
                'Total': total_users,
                'Viewed': viewed_count,
                'View%': f"{view_pct:.1f}%",
                'KM Avg': f"{km_avg:.3f}",
                'Liked': liked_count,
                'Like%': f"{like_pct:.1f}%",
                'Disliked': disliked_count,
                'Dis%': f"{dislike_pct:.1f}%",
                'Passed': passed_count,
                'Pass%': f"{pass_pct:.1f}%"
            })

        if rank_metrics:
            # Display table
            df_rank = pd.DataFrame(rank_metrics)
            st.dataframe(df_rank, use_container_width=True, hide_index=True)

            st.markdown("---")

            # Visual charts
            st.markdown("#### 📊 Visual Breakdown")

            col1, col2 = st.columns(2)

            with col1:
                # View rate by rank
                view_data = pd.DataFrame([
                    {'Rank': f"Rank {r['Rank']}", 'View Rate': float(r['View%'].replace('%', ''))}
                    for r in rank_metrics
                ])
                fig_view = px.bar(
                    view_data,
                    x='Rank',
                    y='View Rate',
                    title='View Rate by Rank',
                    color_discrete_sequence=['#667eea']
                )
                fig_view.update_layout(height=300, yaxis_title='View Rate (%)')
                st.plotly_chart(fig_view, use_container_width=True)

            with col2:
                # Like rate by rank
                like_data = pd.DataFrame([
                    {'Rank': f"Rank {r['Rank']}", 'Like Rate': float(r['Like%'].replace('%', ''))}
                    for r in rank_metrics
                ])
                fig_like = px.bar(
                    like_data,
                    x='Rank',
                    y='Like Rate',
                    title='Like Rate by Rank (of viewers)',
                    color_discrete_sequence=['#21C354']
                )
                fig_like.update_layout(height=300, yaxis_title='Like Rate (%)')
                st.plotly_chart(fig_like, use_container_width=True)

            # Insights
            st.markdown("#### 💡 Key Insights")

            if len(rank_metrics) >= 2:
                first_rank = rank_metrics[0]
                last_rank = rank_metrics[-1]

                col1, col2, col3 = st.columns(3)
                with col1:
                    view_drop = float(first_rank['View%'].replace('%', '')) - float(last_rank['View%'].replace('%', ''))
                    st.metric(
                        f"View Rate Drop (Rank 1→{last_rank['Rank']})",
                        f"{view_drop:.1f}%",
                        help=f"Rank 1: {first_rank['View%']} → Rank {last_rank['Rank']}: {last_rank['View%']}"
                    )
                with col2:
                    like_drop = float(first_rank['Like%'].replace('%', '')) - float(last_rank['Like%'].replace('%', ''))
                    st.metric(
                        f"Like Rate Drop (Rank 1→{last_rank['Rank']})",
                        f"{like_drop:.1f}%",
                        help=f"Rank 1: {first_rank['Like%']} → Rank {last_rank['Rank']}: {last_rank['Like%']}"
                    )
                with col3:
                    km_first = float(first_rank['KM Avg'])
                    km_last = float(last_rank['KM Avg'])
                    km_diff = km_first - km_last
                    diff_label = "Drop" if km_diff > 0 else "Increase"
                    st.metric(
                        f"KM Avg {diff_label} (Rank 1→{last_rank['Rank']})",
                        f"{abs(km_diff):.2f}",
                        help=f"Rank 1: {first_rank['KM Avg']} → Rank {last_rank['Rank']}: {last_rank['KM Avg']}"
                    )

            # Explanation
            with st.expander("What do these metrics mean?"):
                st.markdown("""
                - **Rank**: Position of the match (1 = first shown, 9 = last shown)
                - **Total**: Unique users who had a match at this rank
                - **Viewed / View%**: Users who opened/viewed the match at this rank
                - **KM Avg**: Average "Know More" clicks at this rank
                - **Liked / Like%**: Users who liked (% of viewers)
                - **Disliked / Dis%**: Users who disliked (% of viewers)
                - **Passed / Pass%**: Users who passed (% of viewers)

                **Insight**: Lower ranks typically have lower view rates as users may stop swiping before reaching them.
                """)
        else:
            st.info("No rank data available for the selected filters.")


# ============================================
# TAB 5: TIER - Tier Analysis
# ============================================
with tab5:
    st.markdown("### Tier Analysis")
    st.markdown("*How do different tiers interact? Viewer tier vs Candidate (matched_user) tier.*")

    if not filtered_matches:
        st.warning("No data available for selected filters.")
    else:
        # Build matched_user lookup for tier info
        matched_user_lookup = {}
        for user in metadata:
            matched_user_lookup[user.get('user_id')] = {
                'gender': user.get('gender'),
                'tier': user.get('professional_tier')
            }

        # ===== VIEWER TIER ANALYSIS =====
        st.markdown("#### Viewer Tier Breakdown")
        st.markdown("*How do viewers of different tiers behave?*")

        # Group by viewer tier (current_user_id's tier)
        viewer_tier_data = {1: [], 2: [], 3: []}

        for m in filtered_matches:
            viewer_id = m.get('current_user_id')
            viewer_info = user_lookup.get(viewer_id, {})
            viewer_tier = viewer_info.get('tier')

            if viewer_tier in [1, 2, 3]:
                viewer_tier_data[viewer_tier].append(m)

        # Calculate metrics per viewer tier
        viewer_metrics = []
        for tier in [1, 2, 3]:
            tier_matches = viewer_tier_data[tier]
            if not tier_matches:
                continue

            total = len(tier_matches)
            viewed = sum(1 for m in tier_matches if m.get('is_viewed'))
            liked = sum(1 for m in tier_matches if m.get('is_liked') == 'liked')
            disliked = sum(1 for m in tier_matches if m.get('is_liked') == 'disliked')
            passed = sum(1 for m in tier_matches if m.get('is_liked') == 'passed')
            km_values = [m.get('know_more_count') or 0 for m in tier_matches if m.get('is_viewed')]
            km_avg = sum(km_values) / len(km_values) if km_values else 0

            view_rate = (viewed / total * 100) if total > 0 else 0
            like_rate = (liked / viewed * 100) if viewed > 0 else 0
            dislike_rate = (disliked / viewed * 100) if viewed > 0 else 0
            pass_rate = (passed / viewed * 100) if viewed > 0 else 0

            viewer_metrics.append({
                'Viewer Tier': f"Tier {tier}",
                'Matches': total,
                'Viewed': viewed,
                'View%': f"{view_rate:.1f}%",
                'KM Avg': f"{km_avg:.3f}",
                'Liked': liked,
                'Like%': f"{like_rate:.1f}%",
                'Disliked': disliked,
                'Dis%': f"{dislike_rate:.1f}%",
                'Passed': passed,
                'Pass%': f"{pass_rate:.1f}%"
            })

        if viewer_metrics:
            df_viewer = pd.DataFrame(viewer_metrics)
            st.dataframe(df_viewer, use_container_width=True, hide_index=True)

        st.markdown("---")

        # ===== CANDIDATE TIER ANALYSIS =====
        st.markdown("#### Candidate Tier Breakdown")
        st.markdown("*How are candidates of different tiers received?*")

        # Group by candidate tier (matched_user_id's tier)
        candidate_tier_data = {1: [], 2: [], 3: []}

        for m in filtered_matches:
            matched_id = m.get('matched_user_id')
            matched_info = matched_user_lookup.get(matched_id, {})
            matched_tier = matched_info.get('tier')

            if matched_tier in [1, 2, 3]:
                candidate_tier_data[matched_tier].append(m)

        # Calculate metrics per candidate tier
        candidate_metrics = []
        for tier in [1, 2, 3]:
            tier_matches = candidate_tier_data[tier]
            if not tier_matches:
                continue

            total = len(tier_matches)
            viewed = sum(1 for m in tier_matches if m.get('is_viewed'))
            liked = sum(1 for m in tier_matches if m.get('is_liked') == 'liked')
            disliked = sum(1 for m in tier_matches if m.get('is_liked') == 'disliked')
            passed = sum(1 for m in tier_matches if m.get('is_liked') == 'passed')
            km_values = [m.get('know_more_count') or 0 for m in tier_matches if m.get('is_viewed')]
            km_avg = sum(km_values) / len(km_values) if km_values else 0

            view_rate = (viewed / total * 100) if total > 0 else 0
            like_rate = (liked / viewed * 100) if viewed > 0 else 0
            dislike_rate = (disliked / viewed * 100) if viewed > 0 else 0
            pass_rate = (passed / viewed * 100) if viewed > 0 else 0

            candidate_metrics.append({
                'Candidate Tier': f"Tier {tier}",
                'Shown': total,
                'Viewed': viewed,
                'View%': f"{view_rate:.1f}%",
                'KM Avg': f"{km_avg:.3f}",
                'Liked': liked,
                'Like%': f"{like_rate:.1f}%",
                'Disliked': disliked,
                'Dis%': f"{dislike_rate:.1f}%",
                'Passed': passed,
                'Pass%': f"{pass_rate:.1f}%"
            })

        if candidate_metrics:
            df_candidate = pd.DataFrame(candidate_metrics)
            st.dataframe(df_candidate, use_container_width=True, hide_index=True)

        st.markdown("---")

        # ===== 3x3 TIER MATRIX =====
        st.markdown("#### 3x3 Tier Interaction Matrix")
        st.markdown("*Viewer Tier (rows) vs Candidate Tier (columns)*")

        # Select metric for matrix
        matrix_metric = st.radio(
            "Select metric for matrix:",
            options=['like_rate', 'view_rate', 'count', 'km_avg'],
            format_func=lambda x: {
                'like_rate': 'Like Rate %',
                'view_rate': 'View Rate %',
                'count': 'Match Count',
                'km_avg': 'KM Average'
            }[x],
            horizontal=True
        )

        # Build 3x3 matrix data
        matrix_data = {}  # (viewer_tier, candidate_tier) -> {matches, viewed, liked, km_values}

        for vt in [1, 2, 3]:
            for ct in [1, 2, 3]:
                matrix_data[(vt, ct)] = {'matches': 0, 'viewed': 0, 'liked': 0, 'km_values': []}

        for m in filtered_matches:
            viewer_id = m.get('current_user_id')
            matched_id = m.get('matched_user_id')

            viewer_info = user_lookup.get(viewer_id, {})
            matched_info = matched_user_lookup.get(matched_id, {})

            viewer_tier = viewer_info.get('tier')
            matched_tier = matched_info.get('tier')

            if viewer_tier in [1, 2, 3] and matched_tier in [1, 2, 3]:
                key = (viewer_tier, matched_tier)
                matrix_data[key]['matches'] += 1

                if m.get('is_viewed'):
                    matrix_data[key]['viewed'] += 1
                    matrix_data[key]['km_values'].append(m.get('know_more_count') or 0)

                if m.get('is_liked') == 'liked':
                    matrix_data[key]['liked'] += 1

        # Build matrix for display
        matrix_values = []
        for vt in [1, 2, 3]:
            row = []
            for ct in [1, 2, 3]:
                data = matrix_data[(vt, ct)]
                if matrix_metric == 'count':
                    row.append(data['matches'])
                elif matrix_metric == 'view_rate':
                    rate = (data['viewed'] / data['matches'] * 100) if data['matches'] > 0 else 0
                    row.append(round(rate, 1))
                elif matrix_metric == 'like_rate':
                    rate = (data['liked'] / data['viewed'] * 100) if data['viewed'] > 0 else 0
                    row.append(round(rate, 1))
                elif matrix_metric == 'km_avg':
                    avg = sum(data['km_values']) / len(data['km_values']) if data['km_values'] else 0
                    row.append(round(avg, 3))
            matrix_values.append(row)

        # Create heatmap
        matrix_df = pd.DataFrame(
            matrix_values,
            index=['Viewer T1', 'Viewer T2', 'Viewer T3'],
            columns=['Candidate T1', 'Candidate T2', 'Candidate T3']
        )

        fig_matrix = px.imshow(
            matrix_values,
            x=['Candidate T1', 'Candidate T2', 'Candidate T3'],
            y=['Viewer T1', 'Viewer T2', 'Viewer T3'],
            text_auto=True,
            color_continuous_scale='RdYlGn' if matrix_metric in ['like_rate', 'view_rate'] else 'Blues',
            aspect='equal'
        )

        metric_label = {
            'like_rate': 'Like Rate %',
            'view_rate': 'View Rate %',
            'count': 'Match Count',
            'km_avg': 'KM Average'
        }[matrix_metric]

        fig_matrix.update_layout(
            title=f"Tier Interaction: {metric_label}",
            height=400,
            xaxis_title="Candidate Tier",
            yaxis_title="Viewer Tier"
        )

        st.plotly_chart(fig_matrix, use_container_width=True)

        # Show raw data table
        st.markdown("**Raw Matrix Values:**")
        st.dataframe(matrix_df, use_container_width=True)

        # Insights
        st.markdown("---")
        st.markdown("#### Insights")

        col1, col2 = st.columns(2)

        with col1:
            # Same-tier preference
            same_tier_likes = sum(matrix_data[(t, t)]['liked'] for t in [1, 2, 3])
            same_tier_viewed = sum(matrix_data[(t, t)]['viewed'] for t in [1, 2, 3])
            same_tier_rate = (same_tier_likes / same_tier_viewed * 100) if same_tier_viewed > 0 else 0

            diff_tier_likes = sum(matrix_data[(vt, ct)]['liked'] for vt in [1, 2, 3] for ct in [1, 2, 3] if vt != ct)
            diff_tier_viewed = sum(matrix_data[(vt, ct)]['viewed'] for vt in [1, 2, 3] for ct in [1, 2, 3] if vt != ct)
            diff_tier_rate = (diff_tier_likes / diff_tier_viewed * 100) if diff_tier_viewed > 0 else 0

            st.metric("Same-Tier Like Rate", f"{same_tier_rate:.1f}%", help="When viewer and candidate are same tier")
            st.metric("Cross-Tier Like Rate", f"{diff_tier_rate:.1f}%", help="When viewer and candidate are different tiers")

        with col2:
            # Up vs Down preference
            up_likes = sum(matrix_data[(vt, ct)]['liked'] for vt in [1, 2, 3] for ct in [1, 2, 3] if ct < vt)  # Lower tier = higher number
            up_viewed = sum(matrix_data[(vt, ct)]['viewed'] for vt in [1, 2, 3] for ct in [1, 2, 3] if ct < vt)
            up_rate = (up_likes / up_viewed * 100) if up_viewed > 0 else 0

            down_likes = sum(matrix_data[(vt, ct)]['liked'] for vt in [1, 2, 3] for ct in [1, 2, 3] if ct > vt)
            down_viewed = sum(matrix_data[(vt, ct)]['viewed'] for vt in [1, 2, 3] for ct in [1, 2, 3] if ct > vt)
            down_rate = (down_likes / down_viewed * 100) if down_viewed > 0 else 0

            st.metric("Dating Up Rate", f"{up_rate:.1f}%", help="Lower tier viewer liking higher tier candidate")
            st.metric("Dating Down Rate", f"{down_rate:.1f}%", help="Higher tier viewer liking lower tier candidate")

        # Explanation
        with st.expander("What do these metrics mean?"):
            st.markdown("""
            - **Viewer Tier**: The tier of the user who received the match (current_user_id)
            - **Candidate Tier**: The tier of the matched profile (matched_user_id)
            - **Same-Tier**: When viewer and candidate have the same professional tier
            - **Dating Up**: When a lower tier person likes a higher tier person (e.g., Tier 3 liking Tier 1)
            - **Dating Down**: When a higher tier person likes a lower tier person (e.g., Tier 1 liking Tier 3)

            **Tier Numbers**: Tier 1 is highest quality, Tier 3 is lower quality (based on professional_tier field)
            """)


# ============================================
# TAB 6: DATES - Date-wise Engagement
# ============================================
with tab6:
    st.markdown("### Date-wise Engagement")
    st.markdown("*Track engagement metrics over time.*")

    if not filtered_matches:
        st.warning("No data available for selected filters.")
    else:
        # Group matches by date
        date_data = {}  # date_str -> list of matches

        for m in filtered_matches:
            created_at = m.get('created_at', '')
            if created_at:
                date_str = created_at[:10]  # YYYY-MM-DD
                if date_str not in date_data:
                    date_data[date_str] = []
                date_data[date_str].append(m)

        # Calculate metrics per date
        date_metrics = []
        sorted_dates = sorted(date_data.keys())

        for date_str in sorted_dates:
            day_matches = date_data[date_str]

            total = len(day_matches)
            unique_users = len(set(m.get('current_user_id') for m in day_matches))
            viewed = sum(1 for m in day_matches if m.get('is_viewed'))
            viewed_users = len(set(m.get('current_user_id') for m in day_matches if m.get('is_viewed')))
            liked = sum(1 for m in day_matches if m.get('is_liked') == 'liked')
            disliked = sum(1 for m in day_matches if m.get('is_liked') == 'disliked')
            passed = sum(1 for m in day_matches if m.get('is_liked') == 'passed')

            view_rate = (viewed / total * 100) if total > 0 else 0
            like_rate = (liked / viewed * 100) if viewed > 0 else 0
            dislike_rate = (disliked / viewed * 100) if viewed > 0 else 0
            pass_rate = (passed / viewed * 100) if viewed > 0 else 0

            # Format date for display
            try:
                dt = datetime.strptime(date_str, '%Y-%m-%d')
                display_date = dt.strftime('%b %d (%a)')
            except:
                display_date = date_str

            date_metrics.append({
                'Date': display_date,
                'date_raw': date_str,
                'Matches': total,
                'Users': unique_users,
                'Viewed': viewed,
                'View%': view_rate,
                'Liked': liked,
                'Like%': like_rate,
                'Disliked': disliked,
                'Dis%': dislike_rate,
                'Passed': passed,
                'Pass%': pass_rate
            })

        if date_metrics:
            # Trend Charts
            st.markdown("#### Engagement Trends")

            # Create line chart for key metrics
            df_trends = pd.DataFrame(date_metrics)

            col1, col2 = st.columns(2)

            with col1:
                fig_volume = go.Figure()
                fig_volume.add_trace(go.Scatter(
                    x=df_trends['Date'],
                    y=df_trends['Matches'],
                    mode='lines+markers',
                    name='Total Matches',
                    line=dict(color='#667eea', width=2)
                ))
                fig_volume.add_trace(go.Scatter(
                    x=df_trends['Date'],
                    y=df_trends['Users'],
                    mode='lines+markers',
                    name='Unique Users',
                    line=dict(color='#21C354', width=2)
                ))
                fig_volume.update_layout(
                    title='Volume Over Time',
                    height=350,
                    xaxis_title='Date',
                    yaxis_title='Count'
                )
                st.plotly_chart(fig_volume, use_container_width=True)

            with col2:
                fig_rates = go.Figure()
                fig_rates.add_trace(go.Scatter(
                    x=df_trends['Date'],
                    y=df_trends['View%'],
                    mode='lines+markers',
                    name='View Rate',
                    line=dict(color='#667eea', width=2)
                ))
                fig_rates.add_trace(go.Scatter(
                    x=df_trends['Date'],
                    y=df_trends['Like%'],
                    mode='lines+markers',
                    name='Like Rate',
                    line=dict(color='#21C354', width=2)
                ))
                fig_rates.add_trace(go.Scatter(
                    x=df_trends['Date'],
                    y=df_trends['Dis%'],
                    mode='lines+markers',
                    name='Dislike Rate',
                    line=dict(color='#f5576c', width=2)
                ))
                fig_rates.update_layout(
                    title='Rates Over Time',
                    height=350,
                    xaxis_title='Date',
                    yaxis_title='Rate (%)'
                )
                st.plotly_chart(fig_rates, use_container_width=True)

            st.markdown("---")

            # Daily breakdown table
            st.markdown("#### Daily Breakdown")

            # Format for display
            df_display = pd.DataFrame([
                {
                    'Date': row['Date'],
                    'Matches': row['Matches'],
                    'Users': row['Users'],
                    'Viewed': row['Viewed'],
                    'View%': f"{row['View%']:.1f}%",
                    'Liked': row['Liked'],
                    'Like%': f"{row['Like%']:.1f}%",
                    'Disliked': row['Disliked'],
                    'Dis%': f"{row['Dis%']:.1f}%",
                    'Passed': row['Passed'],
                    'Pass%': f"{row['Pass%']:.1f}%"
                }
                for row in date_metrics
            ])

            st.dataframe(df_display, use_container_width=True, hide_index=True)

            st.markdown("---")

            # Day-over-day comparison
            st.markdown("#### Day-over-Day Changes")

            if len(date_metrics) >= 2:
                dod_changes = []
                for i in range(1, len(date_metrics)):
                    prev = date_metrics[i-1]
                    curr = date_metrics[i]

                    matches_change = ((curr['Matches'] - prev['Matches']) / prev['Matches'] * 100) if prev['Matches'] > 0 else 0
                    users_change = ((curr['Users'] - prev['Users']) / prev['Users'] * 100) if prev['Users'] > 0 else 0
                    view_change = curr['View%'] - prev['View%']
                    like_change = curr['Like%'] - prev['Like%']

                    dod_changes.append({
                        'Date': curr['Date'],
                        'Matches Change': f"{matches_change:+.1f}%",
                        'Users Change': f"{users_change:+.1f}%",
                        'View Rate Change': f"{view_change:+.1f}pp",
                        'Like Rate Change': f"{like_change:+.1f}pp"
                    })

                df_dod = pd.DataFrame(dod_changes)
                st.dataframe(df_dod, use_container_width=True, hide_index=True)

            # Summary statistics
            st.markdown("---")
            st.markdown("#### Period Summary")

            col1, col2, col3, col4 = st.columns(4)

            total_matches = sum(d['Matches'] for d in date_metrics)
            total_users = len(set(m.get('current_user_id') for m in filtered_matches))
            avg_daily_matches = total_matches / len(date_metrics) if date_metrics else 0
            avg_daily_users = sum(d['Users'] for d in date_metrics) / len(date_metrics) if date_metrics else 0

            with col1:
                st.metric("Total Matches", f"{total_matches:,}")
            with col2:
                st.metric("Total Unique Users", f"{total_users:,}")
            with col3:
                st.metric("Avg Daily Matches", f"{avg_daily_matches:.0f}")
            with col4:
                st.metric("Avg Daily Users", f"{avg_daily_users:.0f}")

            # Peak day analysis
            if date_metrics:
                peak_matches_day = max(date_metrics, key=lambda x: x['Matches'])
                peak_users_day = max(date_metrics, key=lambda x: x['Users'])
                peak_like_rate_day = max(date_metrics, key=lambda x: x['Like%'])

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Peak Matches Day", peak_matches_day['Date'], f"{peak_matches_day['Matches']} matches")
                with col2:
                    st.metric("Peak Users Day", peak_users_day['Date'], f"{peak_users_day['Users']} users")
                with col3:
                    st.metric("Best Like Rate Day", peak_like_rate_day['Date'], f"{peak_like_rate_day['Like%']:.1f}%")

        else:
            st.info("No date data available for the selected filters.")


# ============================================
# TAB 7: KM - Know More Distribution
# ============================================
with tab7:
    st.markdown("### Know More Distribution")
    st.markdown("*How many times do users click 'Know More' on profiles?*")

    if not filtered_matches:
        st.warning("No data available for selected filters.")
    else:
        # Only consider viewed matches for KM analysis
        viewed_matches = [m for m in filtered_matches if m.get('is_viewed')]

        if not viewed_matches:
            st.warning("No viewed matches found for selected filters.")
        else:
            # Get KM counts
            km_counts = {}  # km_value -> count of matches
            km_by_decision = {'liked': [], 'disliked': [], 'passed': [], 'km_no_decision': []}

            for m in viewed_matches:
                km = m.get('know_more_count') or 0
                km_counts[km] = km_counts.get(km, 0) + 1

                decision = m.get('is_liked')
                if decision == 'liked':
                    km_by_decision['liked'].append(km)
                elif decision == 'disliked':
                    km_by_decision['disliked'].append(km)
                elif decision == 'passed':
                    km_by_decision['passed'].append(km)
                elif km > 0:
                    # Clicked KM but no final decision (is_liked is null/empty/other)
                    km_by_decision['km_no_decision'].append(km)

            # Summary stats
            all_km = [m.get('know_more_count') or 0 for m in viewed_matches]
            avg_km = sum(all_km) / len(all_km) if all_km else 0
            max_km = max(all_km) if all_km else 0
            zero_km = sum(1 for km in all_km if km == 0)
            zero_pct = (zero_km / len(all_km) * 100) if all_km else 0

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Avg KM Count", f"{avg_km:.2f}")
            with col2:
                st.metric("Max KM Count", max_km)
            with col3:
                st.metric("Zero KM %", f"{zero_pct:.1f}%")
            with col4:
                st.metric("Total Viewed", len(viewed_matches))

            st.markdown("---")

            # Distribution chart
            st.markdown("#### KM Count Distribution")

            # Prepare data for chart (0, 1, 2, 3, 4, 5+)
            km_buckets = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, '5+': 0}
            for km, count in km_counts.items():
                if km >= 5:
                    km_buckets['5+'] += count
                else:
                    km_buckets[km] = km_buckets.get(km, 0) + count

            total = sum(km_buckets.values())
            df_km = pd.DataFrame([
                {
                    'KM Count': str(k),
                    'Matches': v,
                    'Percentage': (v / total * 100) if total > 0 else 0
                }
                for k, v in km_buckets.items()
            ])

            fig_km = px.bar(
                df_km,
                x='KM Count',
                y='Matches',
                text=df_km.apply(lambda row: f"{row['Matches']} ({row['Percentage']:.1f}%)", axis=1),
                color_discrete_sequence=['#667eea']
            )
            fig_km.update_layout(
                title='Know More Click Distribution',
                height=350,
                xaxis_title='Know More Count',
                yaxis_title='Number of Matches'
            )
            fig_km.update_traces(textposition='outside')
            st.plotly_chart(fig_km, use_container_width=True)

            st.markdown("---")

            # KM by decision type
            st.markdown("#### KM Count by Decision")

            decision_stats = []
            # Categories to display in the table (always show all 4, even if 0)
            display_decisions = ['liked', 'disliked', 'passed', 'km_no_decision']
            for decision in display_decisions:
                km_list = km_by_decision.get(decision, [])
                display_name = 'Clicked KM, No Decision' if decision == 'km_no_decision' else decision.replace('_', ' ').title()
                if km_list:
                    avg = sum(km_list) / len(km_list)
                    zero_pct = sum(1 for km in km_list if km == 0) / len(km_list) * 100
                    decision_stats.append({
                        'Decision': display_name,
                        'Count': len(km_list),
                        'Avg KM': f"{avg:.2f}",
                        'Zero KM %': f"{zero_pct:.1f}%",
                        'Max KM': max(km_list)
                    })
                else:
                    # Show 0 if no data for this category
                    decision_stats.append({
                        'Decision': display_name,
                        'Count': 0,
                        'Avg KM': "0.00",
                        'Zero KM %': "-",
                        'Max KM': 0
                    })

            if decision_stats:
                df_decision = pd.DataFrame(decision_stats)
                st.dataframe(df_decision, use_container_width=True, hide_index=True)

            # Comparison chart
            col1, col2 = st.columns(2)

            with col1:
                # Average KM by decision
                avg_data = []
                for decision in display_decisions:
                    km_list = km_by_decision.get(decision, [])
                    if km_list:
                        display_name = 'KM, No Decision' if decision == 'km_no_decision' else decision.replace('_', ' ').title()
                        avg_data.append({
                            'Decision': display_name,
                            'Avg KM': sum(km_list) / len(km_list)
                        })

                if avg_data:
                    df_avg = pd.DataFrame(avg_data)
                    fig_avg = px.bar(
                        df_avg,
                        x='Decision',
                        y='Avg KM',
                        text=df_avg['Avg KM'].apply(lambda x: f"{x:.2f}"),
                        color='Decision',
                        color_discrete_map={
                            'Liked': '#21C354',
                            'Disliked': '#f5576c',
                            'Passed': '#ffa500',
                            'KM, No Decision': '#888888'
                        }
                    )
                    fig_avg.update_layout(
                        title='Avg KM by Decision',
                        height=300,
                        showlegend=False
                    )
                    fig_avg.update_traces(textposition='outside')
                    st.plotly_chart(fig_avg, use_container_width=True)

            with col2:
                # Zero KM percentage by decision
                zero_data = []
                for decision in display_decisions:
                    km_list = km_by_decision.get(decision, [])
                    if km_list:
                        zero_pct = sum(1 for km in km_list if km == 0) / len(km_list) * 100
                        display_name = 'KM, No Decision' if decision == 'km_no_decision' else decision.replace('_', ' ').title()
                        zero_data.append({
                            'Decision': display_name,
                            'Zero KM %': zero_pct
                        })

                if zero_data:
                    df_zero = pd.DataFrame(zero_data)
                    fig_zero = px.bar(
                        df_zero,
                        x='Decision',
                        y='Zero KM %',
                        text=df_zero['Zero KM %'].apply(lambda x: f"{x:.1f}%"),
                        color='Decision',
                        color_discrete_map={
                            'Liked': '#21C354',
                            'Disliked': '#f5576c',
                            'Passed': '#ffa500',
                            'KM, No Decision': '#888888'
                        }
                    )
                    fig_zero.update_layout(
                        title='Zero KM % by Decision',
                        height=300,
                        showlegend=False
                    )
                    fig_zero.update_traces(textposition='outside')
                    st.plotly_chart(fig_zero, use_container_width=True)

            st.markdown("---")

            # Insights
            st.markdown("#### Insights")

            # Calculate insights
            liked_avg = sum(km_by_decision['liked']) / len(km_by_decision['liked']) if km_by_decision['liked'] else 0
            disliked_avg = sum(km_by_decision['disliked']) / len(km_by_decision['disliked']) if km_by_decision['disliked'] else 0

            col1, col2 = st.columns(2)
            with col1:
                km_diff = liked_avg - disliked_avg
                if km_diff > 0:
                    st.success(f"**Likes have +{km_diff:.2f} higher avg KM** than dislikes. Users engage more before liking.")
                elif km_diff < 0:
                    st.warning(f"**Dislikes have +{abs(km_diff):.2f} higher avg KM** than likes. Users may be researching before rejecting.")
                else:
                    st.info("Likes and dislikes have similar KM engagement.")

            with col2:
                if zero_pct > 50:
                    st.warning(f"**{zero_pct:.1f}% of views have zero KM clicks.** Many users decide without exploring profiles.")
                else:
                    st.success(f"**{100 - zero_pct:.1f}% of views have at least 1 KM click.** Good engagement!")

            # Detailed breakdown table
            with st.expander("Detailed KM Breakdown"):
                detailed_data = []
                for km_val in sorted(km_counts.keys()):
                    count = km_counts[km_val]
                    pct = (count / len(viewed_matches) * 100) if viewed_matches else 0
                    detailed_data.append({
                        'KM Count': km_val,
                        'Matches': count,
                        'Percentage': f"{pct:.2f}%"
                    })
                df_detailed = pd.DataFrame(detailed_data)
                st.dataframe(df_detailed, use_container_width=True, hide_index=True)


# ============================================
# TAB 8: GHOST - Ghost & Pass-Only Users
# ============================================
with tab8:
    st.markdown("### Ghost & Pass-Only Users")

    # Clear definitions at the top
    st.markdown("""
    | Category | Definition |
    |----------|------------|
    | **Active** | Users who have **liked or disliked** at least one match |
    | **Ghost** | Users who **viewed** matches but **never liked, disliked, or passed** anyone |
    | **Pass-Only** | Users who **only passed** on matches, never liked or disliked |
    | **No Views** | Users who have matches assigned but **never opened/viewed** any |
    """)

    st.markdown("---")

    if not filtered_matches:
        st.warning("No data available for selected filters.")
    else:
        # Group matches by current_user_id to analyze user behavior
        user_behavior = {}  # user_id -> {'viewed': 0, 'liked': 0, 'disliked': 0, 'passed': 0, 'no_decision': 0}

        for m in filtered_matches:
            user_id = m.get('current_user_id')
            if user_id not in user_behavior:
                user_behavior[user_id] = {
                    'viewed': 0,
                    'liked': 0,
                    'disliked': 0,
                    'passed': 0,
                    'no_decision': 0,
                    'total_matches': 0
                }

            user_behavior[user_id]['total_matches'] += 1

            if m.get('is_viewed'):
                user_behavior[user_id]['viewed'] += 1

                decision = m.get('is_liked')
                if decision == 'liked':
                    user_behavior[user_id]['liked'] += 1
                elif decision == 'disliked':
                    user_behavior[user_id]['disliked'] += 1
                elif decision == 'passed':
                    user_behavior[user_id]['passed'] += 1
                else:
                    user_behavior[user_id]['no_decision'] += 1

        # Categorize users
        ghost_users = []  # Viewed but no likes/dislikes (only passes or no decision)
        pass_only_users = []  # Only passed, never liked or disliked
        no_view_users = []  # Never viewed any match
        active_users = []  # At least one like or dislike
        super_active = []  # High engagement

        for user_id, stats in user_behavior.items():
            total_decisions = stats['liked'] + stats['disliked'] + stats['passed']

            if stats['viewed'] == 0:
                no_view_users.append({'user_id': user_id, **stats})
            elif stats['liked'] == 0 and stats['disliked'] == 0:
                if stats['passed'] > 0:
                    pass_only_users.append({'user_id': user_id, **stats})
                else:
                    ghost_users.append({'user_id': user_id, **stats})
            else:
                active_users.append({'user_id': user_id, **stats})
                if stats['liked'] + stats['disliked'] >= 5:
                    super_active.append({'user_id': user_id, **stats})

        total_users = len(user_behavior)

        # Summary metrics
        st.markdown("#### User Behavior Summary")

        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Total Users", total_users)
        with col2:
            ghost_pct = (len(ghost_users) / total_users * 100) if total_users > 0 else 0
            st.metric("Ghost Users", f"{len(ghost_users)} ({ghost_pct:.1f}%)")
        with col3:
            pass_pct = (len(pass_only_users) / total_users * 100) if total_users > 0 else 0
            st.metric("Pass-Only", f"{len(pass_only_users)} ({pass_pct:.1f}%)")
        with col4:
            noview_pct = (len(no_view_users) / total_users * 100) if total_users > 0 else 0
            st.metric("No Views", f"{len(no_view_users)} ({noview_pct:.1f}%)")
        with col5:
            active_pct = (len(active_users) / total_users * 100) if total_users > 0 else 0
            st.metric("Active Users", f"{len(active_users)} ({active_pct:.1f}%)")


        st.markdown("---")

        # Distribution pie chart
        st.markdown("#### User Distribution")

        col1, col2 = st.columns(2)

        with col1:
            pie_data = pd.DataFrame([
                {'Category': 'Active', 'Count': len(active_users)},
                {'Category': 'Ghost', 'Count': len(ghost_users)},
                {'Category': 'Pass-Only', 'Count': len(pass_only_users)},
                {'Category': 'No Views', 'Count': len(no_view_users)}
            ])

            fig_pie = px.pie(
                pie_data,
                values='Count',
                names='Category',
                color='Category',
                color_discrete_map={
                    'Active': '#21C354',
                    'Ghost': '#888888',
                    'Pass-Only': '#ffa500',
                    'No Views': '#f5576c'
                },
                hole=0.4
            )
            fig_pie.update_layout(
                title='User Category Distribution',
                height=350
            )
            fig_pie.update_traces(textposition='outside', textinfo='label+percent')
            st.plotly_chart(fig_pie, use_container_width=True)

        with col2:
            # Engagement funnel
            funnel_data = [
                {'Stage': 'Total Users', 'Count': total_users},
                {'Stage': 'Viewed At Least 1', 'Count': total_users - len(no_view_users)},
                {'Stage': 'Made Any Decision', 'Count': len(active_users) + len(pass_only_users)},
                {'Stage': 'Liked/Disliked', 'Count': len(active_users)}
            ]
            df_funnel = pd.DataFrame(funnel_data)

            fig_funnel = px.funnel(
                df_funnel,
                x='Count',
                y='Stage',
                color_discrete_sequence=['#667eea']
            )
            fig_funnel.update_layout(
                title='Engagement Funnel',
                height=350
            )
            st.plotly_chart(fig_funnel, use_container_width=True)

        st.markdown("---")

        # Ghost Users Analysis
        st.markdown("#### Ghost Users Details")

        if ghost_users:
            # Sort by viewed count descending
            ghost_users_sorted = sorted(ghost_users, key=lambda x: x['viewed'], reverse=True)

            col1, col2 = st.columns(2)
            with col1:
                avg_viewed_ghost = sum(g['viewed'] for g in ghost_users) / len(ghost_users)
                st.metric("Avg Views per Ghost", f"{avg_viewed_ghost:.1f}")
            with col2:
                max_viewed_ghost = max(g['viewed'] for g in ghost_users)
                st.metric("Max Views (Ghost)", max_viewed_ghost)

            # View distribution for ghosts
            ghost_view_buckets = {'1': 0, '2-3': 0, '4-5': 0, '6-10': 0, '10+': 0}
            for g in ghost_users:
                v = g['viewed']
                if v == 1:
                    ghost_view_buckets['1'] += 1
                elif v <= 3:
                    ghost_view_buckets['2-3'] += 1
                elif v <= 5:
                    ghost_view_buckets['4-5'] += 1
                elif v <= 10:
                    ghost_view_buckets['6-10'] += 1
                else:
                    ghost_view_buckets['10+'] += 1

            df_ghost_dist = pd.DataFrame([
                {'Views': k, 'Users': v}
                for k, v in ghost_view_buckets.items()
            ])

            fig_ghost = px.bar(
                df_ghost_dist,
                x='Views',
                y='Users',
                text='Users',
                color_discrete_sequence=['#888888']
            )
            fig_ghost.update_layout(
                title='Ghost Users by View Count',
                height=300,
                xaxis_title='Number of Views',
                yaxis_title='Users'
            )
            fig_ghost.update_traces(textposition='outside')
            st.plotly_chart(fig_ghost, use_container_width=True)

            with st.expander("Ghost Users List (Top 20)"):
                df_ghost = pd.DataFrame(ghost_users_sorted[:20])
                df_ghost = df_ghost[['user_id', 'viewed', 'total_matches']]
                df_ghost.columns = ['User ID', 'Viewed', 'Total Matches']
                st.dataframe(df_ghost, use_container_width=True, hide_index=True)
        else:
            st.success("No ghost users found! All viewers are making decisions.")

        st.markdown("---")

        # Pass-Only Users Analysis
        st.markdown("#### Pass-Only Users Details")

        if pass_only_users:
            pass_users_sorted = sorted(pass_only_users, key=lambda x: x['passed'], reverse=True)

            col1, col2 = st.columns(2)
            with col1:
                avg_passed = sum(p['passed'] for p in pass_only_users) / len(pass_only_users)
                st.metric("Avg Passes per User", f"{avg_passed:.1f}")
            with col2:
                max_passed = max(p['passed'] for p in pass_only_users)
                st.metric("Max Passes", max_passed)

            # Pass distribution
            pass_buckets = {'1': 0, '2-3': 0, '4-5': 0, '6-10': 0, '10+': 0}
            for p in pass_only_users:
                v = p['passed']
                if v == 1:
                    pass_buckets['1'] += 1
                elif v <= 3:
                    pass_buckets['2-3'] += 1
                elif v <= 5:
                    pass_buckets['4-5'] += 1
                elif v <= 10:
                    pass_buckets['6-10'] += 1
                else:
                    pass_buckets['10+'] += 1

            df_pass_dist = pd.DataFrame([
                {'Passes': k, 'Users': v}
                for k, v in pass_buckets.items()
            ])

            fig_pass = px.bar(
                df_pass_dist,
                x='Passes',
                y='Users',
                text='Users',
                color_discrete_sequence=['#ffa500']
            )
            fig_pass.update_layout(
                title='Pass-Only Users by Pass Count',
                height=300,
                xaxis_title='Number of Passes',
                yaxis_title='Users'
            )
            fig_pass.update_traces(textposition='outside')
            st.plotly_chart(fig_pass, use_container_width=True)

            with st.expander("Pass-Only Users List (Top 20)"):
                df_pass = pd.DataFrame(pass_users_sorted[:20])
                df_pass = df_pass[['user_id', 'viewed', 'passed', 'total_matches']]
                df_pass.columns = ['User ID', 'Viewed', 'Passed', 'Total Matches']
                st.dataframe(df_pass, use_container_width=True, hide_index=True)
        else:
            st.success("No pass-only users found!")

        st.markdown("---")

        # No Views Users Analysis
        st.markdown("#### No Views Users Details")

        if no_view_users:
            no_view_sorted = sorted(no_view_users, key=lambda x: x['total_matches'], reverse=True)

            col1, col2 = st.columns(2)
            with col1:
                avg_matches = sum(u['total_matches'] for u in no_view_users) / len(no_view_users)
                st.metric("Avg Matches per User", f"{avg_matches:.1f}")
            with col2:
                max_matches = max(u['total_matches'] for u in no_view_users)
                st.metric("Max Matches Assigned", max_matches)

            # Matches distribution for no-view users
            noview_buckets = {'1': 0, '2-3': 0, '4-5': 0, '6-10': 0, '10+': 0}
            for u in no_view_users:
                m = u['total_matches']
                if m == 1:
                    noview_buckets['1'] += 1
                elif m <= 3:
                    noview_buckets['2-3'] += 1
                elif m <= 5:
                    noview_buckets['4-5'] += 1
                elif m <= 10:
                    noview_buckets['6-10'] += 1
                else:
                    noview_buckets['10+'] += 1

            df_noview_dist = pd.DataFrame([
                {'Matches': k, 'Users': v}
                for k, v in noview_buckets.items()
            ])

            fig_noview = px.bar(
                df_noview_dist,
                x='Matches',
                y='Users',
                text='Users',
                color_discrete_sequence=['#f5576c']
            )
            fig_noview.update_layout(
                title='No-View Users by Matches Assigned',
                height=300,
                xaxis_title='Matches Assigned',
                yaxis_title='Users'
            )
            fig_noview.update_traces(textposition='outside')
            st.plotly_chart(fig_noview, use_container_width=True)

            with st.expander("No Views Users List (Top 20)"):
                df_noview = pd.DataFrame(no_view_sorted[:20])
                df_noview = df_noview[['user_id', 'total_matches']]
                df_noview.columns = ['User ID', 'Total Matches']
                st.dataframe(df_noview, use_container_width=True, hide_index=True)
        else:
            st.success("No users with zero views! Everyone has opened at least one match.")

        st.markdown("---")

        # Insights
        st.markdown("#### Insights")

        col1, col2 = st.columns(2)

        with col1:
            inactive_pct = ghost_pct + pass_pct + noview_pct
            if inactive_pct > 50:
                st.error(f"**{inactive_pct:.1f}% of users are inactive** (ghost, pass-only, or no views). Consider engagement strategies.")
            elif inactive_pct > 30:
                st.warning(f"**{inactive_pct:.1f}% of users are inactive.** Room for improvement in engagement.")
            else:
                st.success(f"**Only {inactive_pct:.1f}% inactive users.** Good engagement levels!")

        with col2:
            if ghost_pct > 10:
                st.warning(f"**{ghost_pct:.1f}% are ghost users** - viewing but not acting. May need UX improvements or push notifications.")
            else:
                st.success(f"**Low ghost rate ({ghost_pct:.1f}%).** Users are making decisions after viewing.")
