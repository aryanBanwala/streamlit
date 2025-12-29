"""
Remove Unnecessary Users - Review users and mark them for removal
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
    from dependencies import get_supabase_client, get_pinecone_client, get_pinecone_index_name
except ImportError:
    st.error("Error: 'dependencies.py' not found.")
    st.stop()

# Load environment
dotenv_path = os.path.join(parent_dir, '.env')
load_dotenv(dotenv_path)

try:
    supabase = get_supabase_client()
except Exception as e:
    st.error(f"Supabase connection failed: {e}")
    st.stop()

# Custom CSS
st.markdown("""
<style>
@keyframes slideIn {
    from {
        opacity: 0;
        transform: translateY(-10px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.user-card {
    animation: slideIn 0.3s ease-out;
    padding: 16px;
    margin: 8px 0;
    background-color: #1e1e1e;
    border-radius: 10px;
    border-left: 4px solid #4CAF50;
}

.user-card.removed {
    border-left-color: #ff6b6b;
    opacity: 0.7;
}

.stat-box {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 20px;
    border-radius: 10px;
    text-align: center;
    color: white;
}

.filter-section {
    background-color: #262626;
    padding: 15px;
    border-radius: 8px;
    margin-bottom: 20px;
}
</style>
""", unsafe_allow_html=True)

# Title
st.title("Remove Unnecessary Users")
st.caption("Review users and mark them for removal")

# --- Data Fetching Functions ---

@st.cache_data(ttl=60)
def fetch_users_to_review():
    """Fetch users where hasAppropriatePhotos is true or null (not false)."""
    try:
        # Fetch all users with pagination (500 per page)
        all_users = []
        page_size = 500
        offset = 0

        while True:
            query = supabase.table('user_metadata').select(
                'user_id, name, city, area, work_exp, education, interesting_facts, religion, '
                'profile_images, collage_images, instagram_images, "shouldBeRemoved", "hasAppropriatePhotos", created_at, '
                'gender, professional_tier, attractiveness, age'
            )

            # Add pagination
            res = query.range(offset, offset + page_size - 1).execute()

            if not res.data:
                break

            all_users.extend(res.data)

            # If we got fewer results than page_size, we've reached the end
            if len(res.data) < page_size:
                break

            offset += page_size

        if not all_users:
            return []

        # Filter: hasAppropriatePhotos != false (i.e., true or null)
        filtered = [u for u in all_users if u.get('hasAppropriatePhotos') != False]
        return filtered
    except Exception as e:
        st.error(f"Error fetching users: {e}")
        return []

def update_should_be_removed(user_id: str, value):
    """Update shouldBeRemoved field for a user."""
    try:
        supabase.table('user_metadata').update(
            {'shouldBeRemoved': value}
        ).eq('user_id', user_id).execute()
        return True
    except Exception as e:
        st.error(f"Error updating user: {e}")
        return False

def update_pinecone_should_be_removed(user_id: str, value: bool):
    """Update shouldBeRemoved in Pinecone for all 4 namespaces."""
    namespaces = ["lifestyle", "__default__", "work_edu", "personality"]
    pc = get_pinecone_client()
    if not pc:
        st.warning("Pinecone client not available")
        return False

    index_name = get_pinecone_index_name()
    index = pc.Index(index_name)

    for ns in namespaces:
        try:
            # Fetch existing record to get current metadata
            result = index.fetch(ids=[user_id], namespace=ns)
            if user_id in result.vectors:
                existing = result.vectors[user_id]
                metadata = existing.metadata or {}
                metadata["shouldBeRemoved"] = value
                # Update with existing vector and new metadata
                index.upsert(
                    vectors=[{
                        "id": user_id,
                        "values": existing.values,
                        "metadata": metadata
                    }],
                    namespace=ns
                )
        except Exception as e:
            st.error(f"Error updating Pinecone namespace {ns}: {e}")
            return False
    return True

# --- Session State Initialization ---
if 'remove_current_page' not in st.session_state:
    st.session_state.remove_current_page = 1
if 'remove_users_per_page' not in st.session_state:
    st.session_state.remove_users_per_page = 10

# --- Load Users ---
all_users = fetch_users_to_review()

# --- Sidebar Stats ---
st.sidebar.header("Statistics")
st.sidebar.divider()

total_users = len(all_users)
removed_count = len([u for u in all_users if u.get('shouldBeRemoved') == True])
female_count = len([u for u in all_users if u.get('gender', '').lower() == 'female'])
male_count = len([u for u in all_users if u.get('gender', '').lower() == 'male'])

st.sidebar.metric("Total Users", total_users)
st.sidebar.metric("Removed", removed_count)
st.sidebar.metric("Females", female_count)
st.sidebar.metric("Males", male_count)

st.sidebar.divider()

# --- Filters ---
st.sidebar.header("Filters")

# Date filter
filter_date = st.sidebar.date_input(
    "Created on or after",
    value=None,
    key="filter_date"
)

# Gender filter
gender_options = ["All", "male", "female"]
gender_filter = st.sidebar.selectbox(
    "Gender",
    options=gender_options,
    key="filter_gender"
)

# Tier filter
tier_options = ["All", "1", "2", "3", "Not Set"]
tier_filter = st.sidebar.selectbox(
    "Professional Tier",
    options=tier_options,
    key="filter_tier"
)

# Attractiveness filter
attractiveness_options = ["All", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "Not Rated"]
attractiveness_filter = st.sidebar.selectbox(
    "Attractiveness Score",
    options=attractiveness_options,
    key="filter_attractiveness"
)

# City filter
unique_cities = sorted(set(u.get('city') for u in all_users if u.get('city')))
city_options = ["All"] + unique_cities
city_filter = st.sidebar.selectbox(
    "City",
    options=city_options,
    key="filter_city"
)

# Age filter
col_age1, col_age2 = st.sidebar.columns(2)
with col_age1:
    filter_age_min = st.number_input("Min Age", min_value=18, max_value=100, value=18, key="filter_age_min")
with col_age2:
    filter_age_max = st.number_input("Max Age", min_value=18, max_value=100, value=100, key="filter_age_max")

# Status filter (Removed/Not Removed)
status_options = ["All", "Not Removed", "Removed"]
status_filter = st.sidebar.selectbox(
    "Removal Status",
    options=status_options,
    key="filter_status"
)

st.sidebar.divider()

# --- Search by User ID ---
st.sidebar.header("Search by User ID")
search_user_id = st.sidebar.text_input("Enter User ID", key="search_user_id", placeholder="e.g., 6097cfc5-32f6-...")
search_btn = st.sidebar.button("Search", key="search_btn")

# --- Apply Filters ---
filtered_users = all_users.copy()

# Apply date filter
if filter_date:
    filtered_users = [u for u in filtered_users if u.get('created_at') and u.get('created_at')[:10] >= filter_date.isoformat()]

# Apply gender filter
if gender_filter != "All":
    filtered_users = [u for u in filtered_users if u.get('gender', '').lower() == gender_filter.lower()]

# Apply tier filter
if tier_filter == "Not Set":
    filtered_users = [u for u in filtered_users if u.get('professional_tier') is None]
elif tier_filter != "All":
    filtered_users = [u for u in filtered_users if u.get('professional_tier') == int(tier_filter)]

# Apply attractiveness filter
if attractiveness_filter == "Not Rated":
    filtered_users = [u for u in filtered_users if u.get('attractiveness') is None]
elif attractiveness_filter != "All":
    filtered_users = [u for u in filtered_users if u.get('attractiveness') == int(attractiveness_filter)]

# Apply city filter
if city_filter != "All":
    filtered_users = [u for u in filtered_users if u.get('city') == city_filter]

# Apply age filter
filtered_users = [u for u in filtered_users if u.get('age') is None or (filter_age_min <= (u.get('age') or 0) <= filter_age_max)]

# Apply status filter
if status_filter == "Not Removed":
    filtered_users = [u for u in filtered_users if u.get('shouldBeRemoved') != True]
elif status_filter == "Removed":
    filtered_users = [u for u in filtered_users if u.get('shouldBeRemoved') == True]

# --- Handle User ID Search ---
searched_user = None
if search_user_id:
    search_id = search_user_id.strip()
    # Search in all users (not just filtered)
    for user in all_users:
        if user.get('user_id') == search_id:
            searched_user = user
            break

    if search_btn and not searched_user:
        st.sidebar.error("User not found")

# --- Pagination ---
st.sidebar.divider()
st.sidebar.header("Pagination")
users_per_page = st.sidebar.number_input(
    "Users per page",
    min_value=5,
    max_value=100,
    value=10,
    step=5,
    key="users_per_page_input"
)
st.session_state.remove_users_per_page = users_per_page

total_filtered = len(filtered_users)
total_pages = max(1, (total_filtered + users_per_page - 1) // users_per_page)

# Ensure current page is within bounds
if st.session_state.remove_current_page > total_pages:
    st.session_state.remove_current_page = total_pages

# Page selector
st.sidebar.number_input(
    "Page",
    min_value=1,
    max_value=total_pages,
    value=st.session_state.remove_current_page,
    key='remove_page_input',
    on_change=lambda: setattr(st.session_state, 'remove_current_page', st.session_state.remove_page_input)
)

# --- Clear Cache Button ---
st.sidebar.divider()
if st.sidebar.button("Refresh Data", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

# --- Main Content ---
st.divider()

# If user searched, show only that user
if searched_user:
    st.subheader("Search Result")
    page_users = [searched_user]
else:
    # Results header
    col_results, col_view = st.columns([3, 1])
    with col_results:
        st.subheader(f"Showing {total_filtered} users (Page {st.session_state.remove_current_page}/{total_pages})")

    # Calculate slice for current page
    start_idx = (st.session_state.remove_current_page - 1) * users_per_page
    end_idx = start_idx + users_per_page
    page_users = filtered_users[start_idx:end_idx]

# --- Display Users ---
if not page_users:
    st.warning("No users found with current filters.")
else:
    for idx, user in enumerate(page_users):
        user_id = user.get('user_id')
        is_removed = user.get('shouldBeRemoved') == True

        # Build expander title
        name = user.get('name') or 'Unknown'
        age = user.get('age')
        gender = user.get('gender') or 'N/A'
        city = user.get('city') or 'N/A'

        age_str = f", {age}y" if age else ""
        title = f"{'❌ ' if is_removed else ''}{name}{age_str} - {gender} - {city}"

        # Create expandable card for each user
        with st.expander(title, expanded=False):
            # Action buttons at top
            col_action1, col_action2, col_spacer = st.columns([1, 1, 2])
            with col_action1:
                if is_removed:
                    if st.button("Undo Removal", key=f"undo_{user_id}", type="secondary"):
                        if update_should_be_removed(user_id, None):
                            update_pinecone_should_be_removed(user_id, False)
                            st.success("Restored!")
                            st.cache_data.clear()
                            st.rerun()
                else:
                    if st.button("Remove", key=f"remove_{user_id}", type="primary"):
                        if update_should_be_removed(user_id, True):
                            update_pinecone_should_be_removed(user_id, True)
                            st.warning("Marked for removal!")
                            st.cache_data.clear()
                            st.rerun()

            if is_removed:
                st.error("This user is marked for removal")

            st.divider()

            # Photos section
            photos = []
            if user.get('profile_images'):
                photos.extend(user['profile_images'])
            if user.get('collage_images'):
                photos.extend(user['collage_images'])
            if user.get('instagram_images'):
                photos.extend(user['instagram_images'])

            if photos:
                st.markdown("**Photos**")
                # Display photos in a grid (max 6)
                photo_cols = st.columns(min(len(photos), 3))
                for photo_idx, photo_url in enumerate(photos[:6]):
                    with photo_cols[photo_idx % 3]:
                        try:
                            st.image(photo_url, use_container_width=True)
                        except Exception:
                            st.error("Failed to load image")
                st.divider()

            # User details in columns
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Basic Info**")
                st.markdown(f"- **Name:** {user.get('name') or 'N/A'}")
                st.markdown(f"- **Age:** {user.get('age') or 'N/A'}")
                st.markdown(f"- **Gender:** {user.get('gender') or 'N/A'}")
                st.markdown(f"- **City:** {user.get('city') or 'N/A'}")
                st.markdown(f"- **Area:** {user.get('area') or 'N/A'}")
                st.markdown(f"- **Religion:** {user.get('religion') or 'N/A'}")

            with col2:
                st.markdown("**Professional Info**")
                tier = user.get('professional_tier')
                tier_display = f"Tier {tier}" if tier else "Not Set"
                attractiveness = user.get('attractiveness')
                attr_display = f"{attractiveness}/10" if attractiveness else "Not Rated"
                st.markdown(f"- **Professional Tier:** {tier_display}")
                st.markdown(f"- **Attractiveness:** {attr_display}")
                st.markdown(f"- **Work:** {user.get('work_exp') or 'N/A'}")
                st.markdown(f"- **Education:** {user.get('education') or 'N/A'}")
                st.markdown(f"- **Created:** {user.get('created_at', 'N/A')[:10] if user.get('created_at') else 'N/A'}")

            st.divider()

            # Interesting Facts
            st.markdown("**Interesting Facts**")
            facts = user.get('interesting_facts') or []
            if facts:
                for fact in facts:
                    st.markdown(f"- {fact}")
            else:
                st.markdown("No interesting facts available")

# --- Pagination Controls at Bottom (only show if not searching) ---
if not searched_user:
    st.divider()
    col_prev, col_info, col_next = st.columns([1, 2, 1])

    with col_prev:
        if st.button("< Previous", disabled=(st.session_state.remove_current_page <= 1), use_container_width=True):
            st.session_state.remove_current_page -= 1
            st.rerun()

    with col_info:
        st.markdown(f"<center>Page {st.session_state.remove_current_page} of {total_pages}</center>", unsafe_allow_html=True)

    with col_next:
        if st.button("Next >", disabled=(st.session_state.remove_current_page >= total_pages), use_container_width=True):
            st.session_state.remove_current_page += 1
            st.rerun()
