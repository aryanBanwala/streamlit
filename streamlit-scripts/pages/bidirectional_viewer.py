import streamlit as st
import json
import random
import pandas as pd
from io import BytesIO
import os
import sys

# --- Add parent directory to path for imports ---
current_dir = os.path.dirname(__file__)
parent_dir = os.path.abspath(os.path.join(current_dir, '../..'))
sys.path.insert(0, parent_dir)

from dependencies import get_supabase_client

# --- Page Setup ---
st.title("Bidirectional Match Reviewer")

# =====================
# CONFIGURATION SECTION
# =====================
CONFIG = {
    "max_females": 10,
    "min_mutual_matches": 9,
    "top_count": 3,
    "avg_count": 3,
    "low_count": 3,
    "score_min": 1,
    "score_max": 10,
}

# --- Minimal CSS for progress bar ---
st.markdown("""
<style>
.progress-container {
    background: rgba(128,128,128,0.2);
    border-radius: 10px;
    padding: 4px;
    margin: 8px 0;
}
.progress-bar {
    height: 8px;
    border-radius: 6px;
    background: linear-gradient(90deg, #4caf50, #8bc34a);
    transition: width 0.3s ease;
}
</style>
""", unsafe_allow_html=True)

# --- Session State Initialization ---
if 'bidirectional_data' not in st.session_state:
    st.session_state.bidirectional_data = None
if 'selected_females' not in st.session_state:
    st.session_state.selected_females = []
if 'couples' not in st.session_state:
    st.session_state.couples = []
if 'ratings' not in st.session_state:
    st.session_state.ratings = {}
if 'expanded_couple' not in st.session_state:
    st.session_state.expanded_couple = None
if 'user_metadata_cache' not in st.session_state:
    st.session_state.user_metadata_cache = {}
if 'step' not in st.session_state:
    st.session_state.step = 1

# --- Supabase Data Fetching ---
@st.cache_data(ttl=600)
def fetch_user_metadata_batch(_user_ids_tuple):
    """Fetch metadata for multiple users from Supabase."""
    user_ids = list(_user_ids_tuple)
    if not user_ids:
        return {}
    try:
        supabase = get_supabase_client()
        # Fetch all relevant fields from user_metadata
        result = supabase.table('user_metadata').select(
            'user_id, name, age, gender, profile_images, professional_tier, linkedin_profile, '
            'work_exp, education, city, religion, phone_num, instagram_id, attractiveness, '
            'height, area, work_tag, interesting_facts, dob'
        ).in_('user_id', user_ids).execute()

        if result.data:
            return {row['user_id']: row for row in result.data}
        return {}
    except Exception as e:
        st.error(f"Failed to fetch user metadata: {e}")
        return {}


def safe_get(data, key, default='N/A'):
    """Safely get a value from dict, returning default if None or missing."""
    if not data:
        return default
    val = data.get(key)
    if val is None or val == '':
        return default
    return val


def render_user_card_streamlit(user_id, metadata, gender, match_data):
    """Render a user card using native Streamlit components."""
    gender_label = "FEMALE" if gender == "female" else "MALE"
    gender_color = "#e91e63" if gender == "female" else "#2196f3"

    # Fallback suffix for match_data fields
    suffix = "b" if gender == "female" else "a"

    # Get values with proper fallbacks
    name = safe_get(metadata, 'name')
    age = safe_get(metadata, 'age')
    tier = metadata.get('professional_tier') if metadata else None
    linkedin = safe_get(metadata, 'linkedin_profile', '')
    city = safe_get(metadata, 'city')
    area = safe_get(metadata, 'area')
    height = safe_get(metadata, 'height')
    religion = safe_get(metadata, 'religion')
    attractiveness = safe_get(metadata, 'attractiveness')
    work_tag = safe_get(metadata, 'work_tag')

    # Work and education - fallback to match_data if not in metadata
    work = safe_get(metadata, 'work_exp')
    if work == 'N/A':
        work = match_data.get(f'work_exp_{suffix}', 'N/A') or 'N/A'

    education = safe_get(metadata, 'education')
    if education == 'N/A':
        education = match_data.get(f'education_{suffix}', 'N/A') or 'N/A'

    # Photos
    photos = []
    if metadata and metadata.get('profile_images'):
        photos = metadata.get('profile_images', [])[:4]

    # Location display
    location = city if city != 'N/A' else ''
    if area != 'N/A':
        location = f"{area}, {city}" if location else area

    # Tier display
    tier_colors = {-1: "#9e9e9e", 0: "#ffeb3b", 1: "#4caf50", 2: "#2196f3", 3: "#9c27b0"}
    tier_names = {-1: "Unrated", 0: "Tier 0", 1: "Tier 1", 2: "Tier 2", 3: "Tier 3"}
    tier_color = tier_colors.get(tier, "#9e9e9e")
    tier_name = tier_names.get(tier, "N/A") if tier is not None else "N/A"

    # Render using Streamlit native components
    st.markdown(f"<h4 style='color: {gender_color}; margin: 0 0 10px 0; border-bottom: 2px solid {gender_color}; padding-bottom: 5px;'>{gender_label}</h4>", unsafe_allow_html=True)

    # Use columns for a cleaner layout
    st.markdown(f"**Name:** {name}")
    st.markdown(f"**Age:** {age}")

    # Tier with colored badge
    st.markdown(f"**Tier:** <span style='background: {tier_color}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px;'>{tier_name}</span>", unsafe_allow_html=True)

    if attractiveness != 'N/A':
        st.markdown(f"**Attractiveness:** {attractiveness}/10")

    if height != 'N/A':
        st.markdown(f"**Height:** {height} cm")

    st.markdown(f"**Location:** {location if location else 'N/A'}")

    if religion != 'N/A':
        st.markdown(f"**Religion:** {religion}")

    # Truncate long text
    edu_display = str(education)[:80] + "..." if education and len(str(education)) > 80 else education
    work_display = str(work)[:80] + "..." if work and len(str(work)) > 80 else work

    st.markdown(f"**Education:** {edu_display}")
    st.markdown(f"**Work:** {work_display}")

    if work_tag != 'N/A':
        st.markdown(f"**Work Tag:** <span style='background: #4caf50; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px;'>{work_tag}</span>", unsafe_allow_html=True)

    if linkedin:
        st.markdown(f"**LinkedIn:** [{linkedin[:40]}...]({linkedin})")

    # Photos
    if photos:
        st.markdown("**Photos:**")
        photo_cols = st.columns(min(len(photos), 4))
        for i, photo in enumerate(photos[:4]):
            if photo:
                with photo_cols[i]:
                    st.image(photo, width=150)


# --- File Upload ---
st.subheader("Step 1: Upload JSON")
uploaded_file = st.file_uploader("Upload bidirectional JSON file", type=["json"], key="bidirectional_upload")


@st.cache_data
def load_bidirectional_data(file_content: str):
    """Load bidirectional JSON data."""
    try:
        return json.loads(file_content)
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON: {e}")
        return None


def get_females_with_min_matches(mutual_matches, min_matches):
    """Get females with at least min_matches mutual matches."""
    female_matches = {}
    for match in mutual_matches:
        female_id = match.get('user_b_id')
        if female_id:
            if female_id not in female_matches:
                female_matches[female_id] = []
            female_matches[female_id].append(match)
    return {fid: matches for fid, matches in female_matches.items() if len(matches) >= min_matches}


def select_matches_for_female(matches, top_count, avg_count, low_count):
    """Select top, average, and lowest score matches for a female."""
    sorted_matches = sorted(matches, key=lambda x: x.get('avg_score', 0), reverse=True)

    if len(sorted_matches) < (top_count + avg_count + low_count):
        return sorted_matches

    top = sorted_matches[:top_count]
    low = sorted_matches[-low_count:]

    middle_start = top_count
    middle_end = len(sorted_matches) - low_count
    middle_pool = sorted_matches[middle_start:middle_end]

    if len(middle_pool) >= avg_count:
        step = max(1, len(middle_pool) // avg_count)
        avg = [middle_pool[i * step] for i in range(min(avg_count, len(middle_pool)))]
    else:
        avg = middle_pool

    return top + avg + low


def generate_couples(selected_females, female_matches_dict, config):
    """Generate couples list from selected females."""
    couples = []
    for female_id in selected_females:
        matches = female_matches_dict.get(female_id, [])
        selected = select_matches_for_female(
            matches, config['top_count'], config['avg_count'], config['low_count']
        )
        for i, match in enumerate(selected):
            if i < config['top_count']:
                category = 'top'
            elif i < config['top_count'] + config['avg_count']:
                category = 'avg'
            else:
                category = 'low'
            couples.append({
                'female_id': female_id,
                'male_id': match.get('user_a_id'),
                'match_data': match,
                'category': category
            })
    random.shuffle(couples)
    return couples


def get_couple_key(couple):
    """Generate unique key for a couple."""
    return f"{couple['female_id']}_{couple['male_id']}"


# --- Main Logic ---
if uploaded_file is not None:
    file_content = uploaded_file.read().decode('utf-8')
    data = load_bidirectional_data(file_content)

    if data is None:
        st.stop()

    st.session_state.bidirectional_data = data
    mutual_matches = data.get('mutual_matches', [])
    stats = data.get('stats', {})

    st.success(f"Loaded {len(mutual_matches)} mutual matches | {stats.get('females', 0)} females | {stats.get('males', 0)} males")

    female_matches_dict = get_females_with_min_matches(mutual_matches, CONFIG['min_mutual_matches'])
    eligible_count = len(female_matches_dict)

    st.info(f"Found {eligible_count} females with >= {CONFIG['min_mutual_matches']} mutual matches")

    if eligible_count == 0:
        st.warning("No females meet the minimum mutual matches requirement.")
        st.stop()

    # --- Step 2: Select Number of Females ---
    st.divider()
    st.subheader("Step 2: Select Number of Females")

    max_selectable = min(CONFIG['max_females'], eligible_count)
    num_females = st.slider(
        "How many females to review?",
        min_value=1, max_value=max_selectable,
        value=min(5, max_selectable),
        key="num_females_slider"
    )

    matches_per_female = CONFIG['top_count'] + CONFIG['avg_count'] + CONFIG['low_count']
    total_couples = num_females * matches_per_female

    st.caption(f"This will generate **{total_couples}** couples ({CONFIG['top_count']} top + {CONFIG['avg_count']} avg + {CONFIG['low_count']} low per female)")

    if st.button("Generate Couples for Review", type="primary"):
        all_female_ids = list(female_matches_dict.keys())
        selected = random.sample(all_female_ids, num_females)
        st.session_state.selected_females = selected

        couples = generate_couples(selected, female_matches_dict, CONFIG)
        st.session_state.couples = couples

        for couple in couples:
            key = get_couple_key(couple)
            if key not in st.session_state.ratings:
                st.session_state.ratings[key] = {'score': None, 'reason': '', 'submitted': False}

        # Pre-fetch all user metadata
        all_user_ids = set()
        for c in couples:
            all_user_ids.add(c['female_id'])
            all_user_ids.add(c['male_id'])

        with st.spinner("Loading user data from Supabase..."):
            # Use cached data - don't clear cache on every generate
            metadata = fetch_user_metadata_batch(tuple(all_user_ids))
            st.session_state.user_metadata_cache = metadata

        st.session_state.step = 3
        st.rerun()

    # --- Step 3: Review Couples ---
    # Show loading if step 3 but metadata not yet loaded
    if st.session_state.step >= 3 and st.session_state.couples and not st.session_state.user_metadata_cache:
        st.divider()
        st.info("Loading user metadata... Please wait.")
        st.stop()

    # Only show Step 3 when metadata is fully loaded
    if st.session_state.step >= 3 and st.session_state.couples and st.session_state.user_metadata_cache:
        st.divider()
        st.subheader("Step 3: Review Couples")

        couples = st.session_state.couples
        ratings = st.session_state.ratings
        metadata_cache = st.session_state.user_metadata_cache


        submitted_count = sum(1 for c in couples if ratings.get(get_couple_key(c), {}).get('submitted', False))
        total_count = len(couples)
        progress_pct = (submitted_count / total_count * 100) if total_count > 0 else 0

        # Header with download and progress
        col_download, col_progress = st.columns([1, 2])

        with col_download:
            if submitted_count > 0:
                csv_data = []
                for couple in couples:
                    key = get_couple_key(couple)
                    rating = ratings.get(key, {})
                    if rating.get('submitted'):
                        csv_data.append({
                            'user_id_female': couple['female_id'],
                            'user_id_male': couple['male_id'],
                            'score': rating.get('score'),
                            'reason': rating.get('reason', '')
                        })

                df = pd.DataFrame(csv_data)
                csv_buffer = BytesIO()
                df.to_csv(csv_buffer, index=False)
                csv_buffer.seek(0)

                st.download_button(
                    label=f"Download CSV ({submitted_count})",
                    data=csv_buffer,
                    file_name="bidirectional_ratings.csv",
                    mime="text/csv",
                    type="primary"
                )
            else:
                st.button("Download CSV (0)", disabled=True)

        with col_progress:
            st.markdown(f"**Progress:** {submitted_count} / {total_count}")
            st.markdown(f'''
            <div class="progress-container">
                <div class="progress-bar" style="width: {progress_pct}%"></div>
            </div>
            ''', unsafe_allow_html=True)

        st.divider()

        # Display couples as expandable cards
        for idx, couple in enumerate(couples):
            key = get_couple_key(couple)
            rating = ratings.get(key, {'score': None, 'reason': '', 'submitted': False})
            is_submitted = rating.get('submitted', False)
            category = couple['category']
            match_data = couple['match_data']

            female_meta = metadata_cache.get(couple['female_id'], {})
            male_meta = metadata_cache.get(couple['male_id'], {})

            # Get names with fallback to truncated ID
            female_name = couple['female_id'][:8]
            if female_meta and female_meta.get('name'):
                female_name = female_meta.get('name')

            male_name = couple['male_id'][:8]
            if male_meta and male_meta.get('name'):
                male_name = male_meta.get('name')

            # Use expander for each couple
            with st.expander(f"#{idx+1} {female_name} × {male_name}{'  ✓' if is_submitted else ''}", expanded=(st.session_state.expanded_couple == key)):
                # Two column layout for female/male
                col_female, col_male = st.columns(2)

                with col_female:
                    render_user_card_streamlit(couple['female_id'], female_meta, 'female', match_data)
                    st.code(couple['female_id'], language=None)

                with col_male:
                    render_user_card_streamlit(couple['male_id'], male_meta, 'male', match_data)
                    st.code(couple['male_id'], language=None)

                # Rating section using fragment for isolated rerun
                st.markdown("---")

                @st.fragment
                def rating_section(couple_key, current_rating):
                    if current_rating.get('submitted', False):
                        col_info, col_edit = st.columns([3, 1])
                        with col_info:
                            st.success(f"Score: {current_rating.get('score')} / 10 | Reason: {current_rating.get('reason', 'N/A')}")
                        with col_edit:
                            if st.button("Edit", key=f"edit_{couple_key}", type="secondary"):
                                st.session_state.ratings[couple_key]['submitted'] = False
                                st.rerun()
                    else:
                        col_score, col_reason, col_submit = st.columns([1, 2, 1])

                        with col_score:
                            score_val = st.number_input(
                                "Score (1-10)",
                                min_value=CONFIG['score_min'],
                                max_value=CONFIG['score_max'],
                                value=current_rating.get('score') or 5,
                                step=1,
                                key=f"score_{couple_key}"
                            )

                        with col_reason:
                            reason_val = st.text_input(
                                "Reasoning",
                                value=current_rating.get('reason', ''),
                                placeholder="Why this score?",
                                key=f"reason_{couple_key}"
                            )

                        with col_submit:
                            st.write("")
                            if st.button("Submit", key=f"submit_{couple_key}", type="primary"):
                                st.session_state.ratings[couple_key] = {
                                    'score': score_val,
                                    'reason': reason_val,
                                    'submitted': True
                                }
                                st.rerun()

                rating_section(key, rating)

else:
    st.info("Please upload a bidirectional JSON file to begin.")
