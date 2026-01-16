import streamlit as st
import json
import os
import sys

# --- Add parent directory to path for imports ---
current_dir = os.path.dirname(__file__)
parent_dir = os.path.abspath(os.path.join(current_dir, '../..'))
sys.path.insert(0, parent_dir)

from dependencies import get_supabase_client

# --- Page Setup ---
# Note: st.set_page_config is handled by main app.py
st.title("Slotting Results Viewer")

# --- File Upload ---
uploaded_file = st.file_uploader("Upload slotting_output.json", type=["json"], key="json_upload")

# --- Data Loading ---
@st.cache_data
def load_slotting_data_from_content(file_content: str):
    """Load the slotting output from uploaded JSON content."""
    try:
        return json.loads(file_content)
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON: {e}")
        return None

def transform_allocations_to_by_user(allocations):
    """Transform flat allocations array into dict grouped by user_id."""
    by_user = {}
    for alloc in allocations:
        uid = alloc['user_id']
        if uid not in by_user:
            by_user[uid] = {'gender': alloc.get('user_gender'), 'matches': []}
        by_user[uid]['matches'].append(alloc)
    return by_user

# --- Data Loading from Uploaded File ---
allocations = []
data = None

if uploaded_file is None:
    st.info("Please upload a slotting_output.json file to view results.")
    st.stop()

# Read and parse the uploaded file
file_content = uploaded_file.read().decode('utf-8')
data = load_slotting_data_from_content(file_content)

if data is None:
    st.stop()

allocations = data.get('allocations', [])
recommendations_by_user = transform_allocations_to_by_user(allocations)
all_user_ids = list(recommendations_by_user.keys())
total_users = len(all_user_ids)

st.success(f"Loaded {len(allocations)} allocations for {total_users} users")

# --- Supabase Image Fetching ---
@st.cache_data(ttl=300)
def fetch_user_images_single(user_id):
    """Fetch profile_images for a single user from Supabase."""
    if not user_id:
        return []
    try:
        supabase = get_supabase_client()
        result = supabase.table('user_metadata').select('profile_images').eq('user_id', user_id).execute()
        if result.data:
            return result.data[0].get('profile_images') or []
        return []
    except Exception as e:
        return []

@st.cache_data(ttl=300)
def fetch_user_images_batch(_user_ids_tuple):
    """Fetch profile_images and city for multiple users from Supabase."""
    user_ids = list(_user_ids_tuple)
    if not user_ids:
        return {}
    try:
        supabase = get_supabase_client()
        result = supabase.table('user_metadata').select('user_id, profile_images, city').in_('user_id', user_ids).execute()
        return {row['user_id']: {
            'images': row.get('profile_images') or [],
            'city': row.get('city') or ''
        } for row in result.data}
    except Exception as e:
        st.warning(f"Failed to fetch images: {e}")
        return {}

def fetch_user_images_for_user_and_matches(user_id, match_ids):
    """Fetch images and city for a specific user and their matches (bypasses cache for reload)."""
    all_ids = [user_id] + list(match_ids)
    if not all_ids:
        return {}
    try:
        supabase = get_supabase_client()
        result = supabase.table('user_metadata').select('user_id, profile_images, city').in_('user_id', all_ids).execute()
        return {row['user_id']: {
            'images': row.get('profile_images') or [],
            'city': row.get('city') or ''
        } for row in result.data}
    except Exception as e:
        st.warning(f"Failed to fetch images for user {user_id}: {e}")
        return {}

@st.cache_data(ttl=300)
def fetch_user_metadata_batch(_user_ids_tuple):
    """Fetch profile_images and professional_tier for multiple users from Supabase."""
    user_ids = list(_user_ids_tuple)
    if not user_ids:
        return {}
    try:
        supabase = get_supabase_client()
        result = supabase.table('user_metadata').select('user_id, profile_images, professional_tier').in_('user_id', user_ids).execute()
        return {row['user_id']: {
            'profile_images': row.get('profile_images') or [],
            'professional_tier': row.get('professional_tier', 'N/A')
        } for row in result.data}
    except Exception as e:
        st.warning(f"Failed to fetch user metadata: {e}")
        return {}

# --- Configuration Dropdown ---
with st.expander("Configuration & Run Info", expanded=False):
    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("Run Info")
        st.write(f"**Run ID:** `{data.get('run_id', 'N/A')}`")
        st.write(f"**Mode:** {data.get('mode', 'N/A')}")
        st.write(f"**Output File:** {data.get('output_file', 'N/A')}")

    with col2:
        st.subheader("Stats")
        stats = data.get('stats', {})
        st.metric("Fill Rate", f"{stats.get('fill_rate', 0) * 100:.2f}%")
        st.write(f"**Duration:** {stats.get('duration_seconds', 'N/A'):.2f}s")
        st.write(f"**Total Users:** {stats.get('total_users', 0)}")
        st.write(f"**Females:** {stats.get('total_females', 0)} ({stats.get('females_complete', 0)} complete)")
        st.write(f"**Males:** {stats.get('total_males', 0)} ({stats.get('males_complete', 0)} complete)")
        st.write(f"**Slots:** {stats.get('slots_filled', 0)} / {stats.get('slots_needed', 0)}")

    with col3:
        st.subheader("Config")
        config = data.get('config', {})
        st.write(f"**Recs per user:** {config.get('recs_per_user', 'N/A')}")
        st.write(f"**Det slots:** {config.get('det_slots_per_user', 'N/A')}")
        st.write(f"**Rand slots:** {config.get('rand_slots_per_user', 'N/A')}")
        st.write(f"**Lowest bucket slots:** {config.get('lowest_bucket_slots_per_user', 'N/A')}")
        st.write(f"**Det fraction:** {config.get('deterministic_fraction', 'N/A')}")
        st.write(f"**Rand fraction:** {config.get('random_fraction', 'N/A')}")

    st.divider()

    col4, col5 = st.columns(2)

    with col4:
        st.subheader("Allocations by Reason")
        alloc_reasons = data.get('allocations_by_reason', {})
        for reason, count in alloc_reasons.items():
            st.write(f"**{reason}:** {count}")

    with col5:
        st.subheader("Exposure Delta")
        stats = data.get('stats', {})
        st.write(f"**Female:** {stats.get('exposure_delta_female', 'N/A')}")
        st.write(f"**Male:** {stats.get('exposure_delta_male', 'N/A')}")
        st.write(f"**Inbound Likes:** {stats.get('inbound_likes_count', 0)}")
        st.write(f"**Users with Inbound Likes:** {stats.get('users_with_inbound_likes', 0)}")

# --- Stats Dropdown ---
def calculate_onesided_stats(recs_by_user):
    """Calculate how many male users have exactly 1-9 ONE_SIDED_BACKFILL matches."""
    counts = {i: 0 for i in range(1, 10)}  # 1 through 9

    for _, user_data in recs_by_user.items():
        # Only count male users
        if user_data.get('gender') != 'male':
            continue

        # Count ONE_SIDED_BACKFILL matches for this user
        onesided_count = sum(
            1 for match in user_data.get('matches', [])
            if 'ONE_SIDED' in match.get('allocation_reason', '')
        )

        # Check if 1-9
        if onesided_count in counts:
            counts[onesided_count] += 1

    return counts

# --- Stats Dropdown ---
with st.expander("Stats", expanded=False):
    onesided_stats = calculate_onesided_stats(recommendations_by_user)

    st.subheader("Male Users by ONE_SIDED_BACKFILL Count")

    # Row 1: 1, 2, 3, 4, 5
    col_s1, col_s2, col_s3, col_s4, col_s5 = st.columns(5)
    with col_s1:
        st.metric("Exactly 1", onesided_stats[1])
    with col_s2:
        st.metric("Exactly 2", onesided_stats[2])
    with col_s3:
        st.metric("Exactly 3", onesided_stats[3])
    with col_s4:
        st.metric("Exactly 4", onesided_stats[4])
    with col_s5:
        st.metric("Exactly 5", onesided_stats[5])

    # Row 2: 6, 7, 8, 9
    col_s6, col_s7, col_s8, col_s9, _ = st.columns(5)
    with col_s6:
        st.metric("Exactly 6", onesided_stats[6])
    with col_s7:
        st.metric("Exactly 7", onesided_stats[7])
    with col_s8:
        st.metric("Exactly 8", onesided_stats[8])
    with col_s9:
        st.metric("Exactly 9", onesided_stats[9])

# --- Card Styling CSS ---
st.markdown("""
<style>
.match-card {
    padding: 8px;
    border-radius: 8px;
    margin-bottom: 8px;
    font-size: 12px;
}
.card-deterministic {
    background-color: #e3f2fd;
    border: 1px solid #1976d2;
}
.card-random {
    background-color: #e8f5e9;
    border: 1px solid #388e3c;
}
.card-lowest {
    background-color: #fff3e0;
    border: 1px solid #f57c00;
}
.card-onesided {
    background-color: #f3e5f5;
    border: 1px solid #7b1fa2;
}
.card-inbound {
    background-color: #fce4ec;
    border: 1px solid #c2185b;
}
.card-title {
    font-weight: bold;
    font-size: 11px;
    color: #333;
    margin-bottom: 4px;
    word-break: break-all;
}
.card-metric {
    margin: 2px 0;
}
.card-badge {
    display: inline-block;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 9px;
    font-weight: bold;
    margin-top: 4px;
}
.badge-det {
    background-color: #1976d2;
    color: white;
}
.badge-rand {
    background-color: #388e3c;
    color: white;
}
.badge-low {
    background-color: #f57c00;
    color: white;
}
.badge-onesided {
    background-color: #7b1fa2;
    color: white;
}
.badge-inbound {
    background-color: #c2185b;
    color: white;
}
.badge-viewed {
    background-color: #607d8b;
    color: white;
}
.badge-liked {
    background-color: #4caf50;
    color: white;
}
.badge-disliked {
    background-color: #f44336;
    color: white;
}
.badge-passed {
    background-color: #9e9e9e;
    color: white;
}
.mutual-yes {
    color: #388e3c;
    font-weight: bold;
}
.mutual-no {
    color: #d32f2f;
    font-weight: bold;
}
.gender-male {
    color: #1976d2;
}
.gender-female {
    color: #c2185b;
}
.copy-btn {
    cursor: pointer;
    padding: 2px 4px;
    font-size: 10px;
    border: none;
    background: #eee;
    border-radius: 3px;
    margin-left: 4px;
}
.copy-btn:hover {
    background: #ddd;
}
</style>
""", unsafe_allow_html=True)

# --- Helper Function for Card Rendering ---
def get_card_class(allocation_reason):
    if "DETERMINISTIC" in allocation_reason:
        return "card-deterministic", "badge-det", "DET"
    elif "RANDOM" in allocation_reason:
        return "card-random", "badge-rand", "RAND"
    elif "LOWEST" in allocation_reason:
        return "card-lowest", "badge-low", "LOW"
    elif "ONE_SIDED" in allocation_reason:
        return "card-onesided", "badge-onesided", "1-SIDE"
    elif "INBOUND" in allocation_reason:
        return "card-inbound", "badge-inbound", "INBOUND"
    else:
        return "card-deterministic", "badge-det", "?"

def render_match_card(match):
    """Render a single match card as HTML and return the rec_id for copy button."""
    card_class, badge_class, badge_text = get_card_class(match.get('allocation_reason', ''))

    rec_id = match.get('recommended_user_id', 'N/A')
    short_id = rec_id[:8] if len(rec_id) > 8 else rec_id

    is_mutual = match.get('is_mutual', False)
    mutual_icon = '<span class="mutual-yes">Y</span>' if is_mutual else '<span class="mutual-no">N</span>'

    rec_gender = match.get('recommended_user_gender', '')
    gender_class = 'gender-male' if rec_gender == 'male' else 'gender-female' if rec_gender == 'female' else ''
    gender_icon = 'M' if rec_gender == 'male' else 'F' if rec_gender == 'female' else '?'

    # Build is_viewed badge
    viewed_badge = ""
    if match.get('is_viewed'):
        viewed_badge = '<span class="card-badge badge-viewed">VIEWED</span>'

    # Build is_liked badge
    liked_badge = ""
    is_liked = match.get('is_liked')
    if is_liked == 'liked':
        liked_badge = '<span class="card-badge badge-liked">LIKED</span>'
    elif is_liked == 'disliked':
        liked_badge = '<span class="card-badge badge-disliked">DISLIKED</span>'
    elif is_liked == 'passed':
        liked_badge = '<span class="card-badge badge-passed">PASSED</span>'

    html = f"""
    <div class="match-card {card_class}">
        <div class="card-title">{short_id}...</div>
        <div class="card-metric"><b>Rank:</b> {match.get('rank', 'N/A')}</div>
        <div class="card-metric"><b>Score:</b> {match.get('mutual_score', 0):.4f}</div>
        <div class="card-metric"><b>Gender:</b> <span class="{gender_class}">{gender_icon}</span></div>
        <div class="card-metric"><b>Mutual:</b> {mutual_icon}</div>
        <span class="card-badge {badge_class}">{badge_text}</span>
        {viewed_badge}
        {liked_badge}
    </div>
    """
    return html, rec_id

# --- Main Content: User Recommendations ---
st.divider()
st.header("User Recommendations")

# --- Search Section ---
st.subheader("Search")

# Reset callback - must be defined before the button
def reset_search():
    st.session_state.viewer_search = ""
    st.session_state.recommended_search = ""

search_col1, search_col2, search_col3, search_col4 = st.columns([2, 2, 1, 1])

with search_col1:
    st.write("**Search by Viewer User ID**")
    st.caption("Find a user and see their matches")
    viewer_search = st.text_input("Enter viewer user_id:", key="viewer_search", placeholder="e.g. 92b3cd43-0bb1-4eea-a56f-c66945eeee01")

with search_col2:
    st.write("**Search by Recommended User ID (Reverse Lookup)**")
    st.caption("Find all users who received this user as a match")
    recommended_search = st.text_input("Enter recommended user_id:", key="recommended_search", placeholder="e.g. 26572d75-4e00-4f42-9568-5b05813b1ddd")

with search_col3:
    st.write("**Reset**")
    st.caption("Clear searches")
    st.button("Reset Search", use_container_width=True, on_click=reset_search)

with search_col4:
    st.write("**Show Images**")
    st.caption("Load from DB")
    show_images = st.toggle("Enable", key="show_images")

# --- Show Unique Males Toggle ---
st.divider()
show_males_col1, show_males_col2 = st.columns([1, 4])
with show_males_col1:
    show_unique_males = st.toggle("Show Unique Males", key="show_unique_males")
with show_males_col2:
    if show_unique_males:
        st.caption("Displaying all unique male users with their metadata")

st.divider()

# --- Helper function for reverse lookup ---
@st.cache_data
def build_reverse_index(allocs):
    """Build a reverse index: recommended_user_id -> list of (viewer_id, match_data)"""
    reverse_idx = {}
    for alloc in allocs:
        rec_id = alloc.get('recommended_user_id')
        viewer_id = alloc.get('user_id')
        if rec_id:
            if rec_id not in reverse_idx:
                reverse_idx[rec_id] = []
            reverse_idx[rec_id].append((viewer_id, alloc))
    return reverse_idx

reverse_index = build_reverse_index(allocations)

# --- Helper to collect all user IDs for a page ---
def get_all_user_ids_for_page(user_ids_to_show):
    """Get all user IDs (viewers and recommended) for image fetching."""
    all_ids = set(user_ids_to_show)
    for uid in user_ids_to_show:
        user_data = recommendations_by_user.get(uid, {})
        for match in user_data.get('matches', [])[:9]:
            rec_id = match.get('recommended_user_id')
            if rec_id:
                all_ids.add(rec_id)
    return list(all_ids)

# --- Display logic based on search ---
def display_user_matches(user_id, user_data, images_map=None, show_reload_btn=True):
    """Display a single user's matches."""
    gender = user_data.get('gender', '?')
    gender_class = 'gender-male' if gender == 'male' else 'gender-female' if gender == 'female' else ''
    gender_icon = 'M' if gender == 'male' else 'F' if gender == 'female' else '?'

    # Get match IDs for this user (needed for reload)
    matches = user_data.get('matches', [])
    match_ids = [m.get('recommended_user_id') for m in matches[:9] if m.get('recommended_user_id')]

    # Handle reload button - fetches fresh images for THIS user and their matches only
    reload_key = f"reload_images_{user_id}"
    fresh_images_key = f"fresh_images_{user_id}"

    # Build effective metadata map for THIS user:
    # - Start with original images_map (batch-loaded for page)
    # - Override with fresh data if user clicked reload
    effective_data = {}
    if images_map:
        effective_data = dict(images_map)
    if fresh_images_key in st.session_state:
        effective_data.update(st.session_state[fresh_images_key])

    # Get user's city
    user_city = effective_data.get(user_id, {}).get('city', '') if effective_data else ''
    city_label = f" · <span style='color:#666;font-size:14px;'>{user_city}</span>" if user_city else ""

    # Header row with user ID, city, and reload button
    header_col1, header_col2 = st.columns([6, 1])
    with header_col1:
        st.markdown(f"### User: `{user_id}` <span class='{gender_class}'>({gender_icon})</span>{city_label}", unsafe_allow_html=True)

    with header_col2:
        if show_reload_btn:
            if st.button("🔄", key=reload_key, help="Reload images for this user and their matches"):
                with st.spinner("Reloading..."):
                    fresh_images = fetch_user_images_for_user_and_matches(user_id, match_ids)
                st.session_state[fresh_images_key] = fresh_images

    # Show user's own images using HTML img tags (more reliable than st.image)
    if effective_data:
        user_imgs = effective_data.get(user_id, {}).get('images', [])[:5]
        if user_imgs:
            img_html = "".join([f'<img src="{url}" width="100" style="margin-right:8px;border-radius:6px;" loading="lazy">' for url in user_imgs])
            st.markdown(f'<div style="margin-bottom:12px;">{img_html} <small>User</small></div>', unsafe_allow_html=True)

    num_matches = len(matches)
    cols = st.columns(min(num_matches, 9))

    for idx, match in enumerate(matches):
        if idx < 9:
            with cols[idx]:
                card_html, rec_id = render_match_card(match)
                st.markdown(card_html, unsafe_allow_html=True)
                # Show match's city
                if effective_data:
                    match_city = effective_data.get(rec_id, {}).get('city', '')
                    if match_city:
                        st.markdown(f"<small style='color:#666;'>📍 {match_city}</small>", unsafe_allow_html=True)
                st.code(rec_id, language=None)
                # Show recommended user's images using HTML img tags
                if effective_data:
                    rec_imgs = effective_data.get(rec_id, {}).get('images', [])[:5]
                    if rec_imgs:
                        imgs_html = "".join([f'<img src="{url}" width="80" style="margin-right:4px;margin-bottom:4px;border-radius:4px;" loading="lazy">' for url in rec_imgs])
                        st.markdown(f'<div style="display:flex;flex-wrap:wrap;">{imgs_html}</div>', unsafe_allow_html=True)
    st.divider()

# --- Show Unique Males View ---
if show_unique_males:
    # Get all unique male user IDs from allocations
    unique_male_ids = set()
    for alloc in allocations:
        if alloc.get('user_gender') == 'male':
            unique_male_ids.add(alloc.get('user_id'))
        if alloc.get('recommended_user_gender') == 'male':
            unique_male_ids.add(alloc.get('recommended_user_id'))

    unique_male_ids = list(unique_male_ids)
    st.info(f"Total unique males: {len(unique_male_ids)}")

    # Pagination for males
    males_per_page = st.slider("Males per page", min_value=10, max_value=100, value=30, step=10, key="males_per_page")
    total_male_pages = (len(unique_male_ids) + males_per_page - 1) // males_per_page

    if 'males_page' not in st.session_state:
        st.session_state.males_page = 1

    males_page = st.number_input("Page", min_value=1, max_value=max(1, total_male_pages), value=st.session_state.males_page, step=1, key="males_page_input")
    if males_page != st.session_state.males_page:
        st.session_state.males_page = males_page
        st.rerun()

    start_idx = (st.session_state.males_page - 1) * males_per_page
    end_idx = min(start_idx + males_per_page, len(unique_male_ids))
    males_on_page = unique_male_ids[start_idx:end_idx]

    st.write(f"Showing males {start_idx + 1} to {end_idx} of {len(unique_male_ids)}")

    # Fetch metadata for males on this page
    with st.spinner("Loading male user metadata..."):
        males_metadata = fetch_user_metadata_batch(tuple(males_on_page))

    # Display males in a grid (5 per row)
    cols_per_row = 5
    for row_start in range(0, len(males_on_page), cols_per_row):
        cols = st.columns(cols_per_row)
        for col_idx, male_id in enumerate(males_on_page[row_start:row_start + cols_per_row]):
            with cols[col_idx]:
                metadata = males_metadata.get(male_id, {})
                images = metadata.get('profile_images', [])[:1]
                pro_tier = metadata.get('professional_tier', 'N/A')

                # Display image using HTML
                if images:
                    st.markdown(f'<img src="{images[0]}" width="100" style="border-radius:8px;" loading="lazy">', unsafe_allow_html=True)
                else:
                    st.markdown('<div style="width:100px;height:100px;background:#eee;border-radius:8px;display:flex;align-items:center;justify-content:center;"><small>No image</small></div>', unsafe_allow_html=True)

                # Professional tier
                st.markdown(f"**Tier:** {pro_tier}")

                # Copyable user ID
                st.code(male_id, language=None)

    st.divider()

# Check if any search is active
elif viewer_search.strip():
    # Search Mode 1: Search by Viewer User ID
    search_term = viewer_search.strip()
    matching_viewers = [uid for uid in all_user_ids if search_term.lower() in uid.lower()]

    if not matching_viewers:
        st.warning(f"No viewer user_id found matching: `{search_term}`")
    else:
        st.success(f"Found {len(matching_viewers)} matching viewer(s)")

        # Pre-fetch all images for matching viewers at once
        images_map = {}
        if show_images:
            all_ids = get_all_user_ids_for_page(matching_viewers)
            with st.spinner("Loading images..."):
                images_map = fetch_user_images_batch(tuple(all_ids))

        for user_id in matching_viewers:
            display_user_matches(user_id, recommendations_by_user[user_id], images_map if show_images else None)

elif recommended_search.strip():
    # Search Mode 2: Reverse Lookup - find who received this user as a match
    search_term = recommended_search.strip()

    # Find all recommended_user_ids that match the search
    matching_rec_ids = [rid for rid in reverse_index.keys() if search_term.lower() in rid.lower()]

    if not matching_rec_ids:
        st.warning(f"No recommended user_id found matching: `{search_term}`")
    else:
        for rec_id in matching_rec_ids:
            viewers_list = reverse_index[rec_id]
            st.success(f"User `{rec_id}` was shown to **{len(viewers_list)}** users")

            # Show each viewer who received this recommendation
            for viewer_id, match_data in viewers_list:
                with st.expander(f"Viewer: `{viewer_id}`"):
                    st.write(f"**Rank in their list:** {match_data.get('rank', 'N/A')}")
                    st.write(f"**Mutual Score:** {match_data.get('mutual_score', 0):.4f}")
                    st.write(f"**Allocation Reason:** {match_data.get('allocation_reason', 'N/A')}")
                    st.write(f"**Is Mutual:** {'Yes' if match_data.get('is_mutual') else 'No'}")
            st.divider()

else:
    # Gender filter
    filter_col1, filter_col2 = st.columns([1, 4])
    with filter_col1:
        gender_filter = st.selectbox("Filter by Gender", ["All", "Male", "Female"], key="gender_filter")

    # Filter users by gender
    if gender_filter == "Male":
        filtered_user_ids = [uid for uid in all_user_ids if recommendations_by_user.get(uid, {}).get('gender') == 'male']
    elif gender_filter == "Female":
        filtered_user_ids = [uid for uid in all_user_ids if recommendations_by_user.get(uid, {}).get('gender') == 'female']
    else:
        filtered_user_ids = all_user_ids

    filtered_total = len(filtered_user_ids)
    st.info(f"Total users: {filtered_total}" + (f" ({gender_filter.lower()})" if gender_filter != "All" else ""))

    # Pagination - store in session state for syncing top/bottom controls
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 1

    users_per_page = st.slider("Users per page", min_value=5, max_value=50, value=20, step=5)
    total_pages = (filtered_total + users_per_page - 1) // users_per_page

    # Reset page if out of bounds
    if st.session_state.current_page > max(1, total_pages):
        st.session_state.current_page = 1

    # Top pagination
    page_top = st.number_input("Page", min_value=1, max_value=max(1, total_pages), value=st.session_state.current_page, step=1, key="page_top")
    if page_top != st.session_state.current_page:
        st.session_state.current_page = page_top
        st.rerun()

    start_idx = (st.session_state.current_page - 1) * users_per_page
    end_idx = min(start_idx + users_per_page, filtered_total)

    st.write(f"Showing users {start_idx + 1} to {end_idx} of {filtered_total}")

    # Display users
    users_on_page = filtered_user_ids[start_idx:end_idx]

    # Pre-fetch all images for the page at once (much faster than per-user fetching)
    images_map = {}
    if show_images:
        all_ids = get_all_user_ids_for_page(users_on_page)
        with st.spinner("Loading images..."):
            images_map = fetch_user_images_batch(tuple(all_ids))

    for user_id in users_on_page:
        display_user_matches(user_id, recommendations_by_user[user_id], images_map if show_images else None)

    # Bottom pagination
    st.write(f"Showing users {start_idx + 1} to {end_idx} of {filtered_total}")
    page_bottom = st.number_input("Page", min_value=1, max_value=max(1, total_pages), value=st.session_state.current_page, step=1, key="page_bottom")
    if page_bottom != st.session_state.current_page:
        st.session_state.current_page = page_bottom
        st.rerun()
