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
st.title("Pair Scoring")

# =====================
# CONFIGURATION SECTION
# =====================
CONFIG = {
    "max_users": 10,
    "min_candidates": 9,  # minimum candidates a user should have
    "top_count": 3,
    "avg_count": 3,
    "low_count": 3,
    "score_min": 1,
    "score_max": 10,
    "pairs_per_page": 10,  # pagination
}

# --- Minimal CSS for progress bar and persona section ---
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
.persona-box {
    background: rgba(100, 100, 100, 0.15);
    border-radius: 8px;
    padding: 12px;
    margin: 10px 0;
    max-height: 200px;
    overflow-y: auto;
    font-size: 14px;
    line-height: 1.5;
    border-left: 3px solid #9c27b0;
}
</style>
""", unsafe_allow_html=True)

# --- Session State Initialization ---
if 'rankings_data' not in st.session_state:
    st.session_state.rankings_data = None
if 'selected_users' not in st.session_state:
    st.session_state.selected_users = []
if 'pairs' not in st.session_state:
    st.session_state.pairs = []
if 'ratings' not in st.session_state:
    st.session_state.ratings = {}
if 'expanded_pair' not in st.session_state:
    st.session_state.expanded_pair = None
if 'user_metadata_cache' not in st.session_state:
    st.session_state.user_metadata_cache = {}
if 'user_personas_cache' not in st.session_state:
    st.session_state.user_personas_cache = {}
if 'step' not in st.session_state:
    st.session_state.step = 1
if 'current_page' not in st.session_state:
    st.session_state.current_page = 0


# --- Supabase Data Fetching ---
@st.cache_data(ttl=600)
def fetch_user_metadata_batch(_user_ids_tuple):
    """Fetch metadata for multiple users from Supabase."""
    user_ids = list(_user_ids_tuple)
    if not user_ids:
        return {}
    try:
        supabase = get_supabase_client()
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


@st.cache_data(ttl=600)
def fetch_user_personas_batch(_user_ids_tuple):
    """Fetch user personas for multiple users from Supabase."""
    user_ids = list(_user_ids_tuple)
    if not user_ids:
        return {}
    try:
        supabase = get_supabase_client()
        result = supabase.table('user_personas').select(
            'user_id, user_persona_para'
        ).in_('user_id', user_ids).execute()

        if result.data:
            return {row['user_id']: row.get('user_persona_para', '') for row in result.data}
        return {}
    except Exception as e:
        st.error(f"Failed to fetch user personas: {e}")
        return {}


def safe_get(data, key, default='N/A'):
    """Safely get a value from dict, returning default if None or missing."""
    if not data:
        return default
    val = data.get(key)
    if val is None or val == '':
        return default
    return val


def render_user_card_streamlit(user_id, metadata, ranking_data=None, persona=None):
    """Render a user card using native Streamlit components."""
    gender = metadata.get('gender', 'unknown') if metadata else 'unknown'
    gender_label = gender.upper() if gender != 'unknown' else 'USER'
    gender_color = "#e91e63" if gender == "female" else "#2196f3" if gender == "male" else "#9e9e9e"

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
    work = safe_get(metadata, 'work_exp')
    education = safe_get(metadata, 'education')

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

    # User Persona (scrollable section with paragraphs)
    if persona:
        st.markdown("**About:**")
        # Split into sentences and create 4 equal paragraphs
        sentences = [s.strip() for s in persona.replace('!', '.').replace('?', '.').split('.') if s.strip()]
        if len(sentences) >= 4:
            chunk_size = len(sentences) // 4
            remainder = len(sentences) % 4
            paragraphs = []
            start = 0
            for i in range(4):
                end = start + chunk_size + (1 if i < remainder else 0)
                para_sentences = sentences[start:end]
                paragraphs.append('. '.join(para_sentences) + '.')
                start = end
            formatted_persona = '</p><p style="margin: 8px 0;">'.join(paragraphs)
        else:
            formatted_persona = persona
        st.markdown(f'<div class="persona-box"><p style="margin: 8px 0;">{formatted_persona}</p></div>', unsafe_allow_html=True)


# --- File Upload ---
st.subheader("Step 1: Upload JSON")
uploaded_file = st.file_uploader("Upload user rankings JSON file", type=["json"], key="rankings_upload")


@st.cache_data
def load_rankings_data(file_content: str):
    """Load user rankings JSON data."""
    try:
        return json.loads(file_content)
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON: {e}")
        return None


def get_users_with_min_candidates(rankings_data, min_candidates):
    """Get users with at least min_candidates candidates."""
    return {user_id: candidates for user_id, candidates in rankings_data.items()
            if len(candidates) >= min_candidates}


def select_candidates_for_user(candidates, top_count, avg_count, low_count):
    """Select top, average, and lowest score candidates for a user."""
    # Candidates should already be sorted by rank, but let's sort by score to be safe
    sorted_candidates = sorted(candidates, key=lambda x: x.get('score', 0), reverse=True)

    if len(sorted_candidates) < (top_count + avg_count + low_count):
        return sorted_candidates

    top = sorted_candidates[:top_count]
    low = sorted_candidates[-low_count:]

    middle_start = top_count
    middle_end = len(sorted_candidates) - low_count
    middle_pool = sorted_candidates[middle_start:middle_end]

    if len(middle_pool) >= avg_count:
        step = max(1, len(middle_pool) // avg_count)
        avg = [middle_pool[i * step] for i in range(min(avg_count, len(middle_pool)))]
    else:
        avg = middle_pool

    return top + avg + low


def generate_pairs(selected_users, user_candidates_dict, config):
    """Generate pairs list from selected users."""
    pairs = []
    for user_id in selected_users:
        candidates = user_candidates_dict.get(user_id, [])
        selected = select_candidates_for_user(
            candidates, config['top_count'], config['avg_count'], config['low_count']
        )
        for i, candidate in enumerate(selected):
            if i < config['top_count']:
                category = 'top'
            elif i < config['top_count'] + config['avg_count']:
                category = 'avg'
            else:
                category = 'low'
            pairs.append({
                'user_id': user_id,
                'candidate_id': candidate.get('candidate_id'),
                'ranking_data': candidate,
                'category': category
            })
    random.shuffle(pairs)
    return pairs


def get_pair_key(pair):
    """Generate unique key for a pair."""
    return f"{pair['user_id']}_{pair['candidate_id']}"


# --- Main Logic ---
if uploaded_file is not None:
    file_content = uploaded_file.read().decode('utf-8')
    data = load_rankings_data(file_content)

    if data is None:
        st.stop()

    st.session_state.rankings_data = data
    total_users = len(data)
    total_candidates = sum(len(candidates) for candidates in data.values())

    st.success(f"Loaded {total_users} users with {total_candidates} total candidate rankings")

    user_candidates_dict = get_users_with_min_candidates(data, CONFIG['min_candidates'])
    eligible_count = len(user_candidates_dict)

    st.info(f"Found {eligible_count} users with >= {CONFIG['min_candidates']} candidates")

    if eligible_count == 0:
        st.warning("No users meet the minimum candidates requirement.")
        st.stop()

    # --- Step 2: Select Number of Users ---
    st.divider()
    st.subheader("Step 2: Select Number of Users")

    max_selectable = min(CONFIG['max_users'], eligible_count)
    num_users = st.slider(
        "How many users to review?",
        min_value=1, max_value=max_selectable,
        value=min(5, max_selectable),
        key="num_users_slider"
    )

    pairs_per_user = CONFIG['top_count'] + CONFIG['avg_count'] + CONFIG['low_count']
    total_pairs = num_users * pairs_per_user

    st.caption(f"This will generate **{total_pairs}** pairs ({CONFIG['top_count']} top + {CONFIG['avg_count']} avg + {CONFIG['low_count']} low per user)")

    if st.button("Generate Pairs for Review", type="primary"):
        all_user_ids = list(user_candidates_dict.keys())
        selected = random.sample(all_user_ids, num_users)
        st.session_state.selected_users = selected

        pairs = generate_pairs(selected, user_candidates_dict, config=CONFIG)
        st.session_state.pairs = pairs

        for pair in pairs:
            key = get_pair_key(pair)
            if key not in st.session_state.ratings:
                st.session_state.ratings[key] = {'score': None, 'reason': '', 'submitted': False}

        # Pre-fetch all user metadata
        all_user_ids_set = set()
        for p in pairs:
            all_user_ids_set.add(p['user_id'])
            all_user_ids_set.add(p['candidate_id'])

        with st.spinner("Loading user data from Supabase..."):
            metadata = fetch_user_metadata_batch(tuple(all_user_ids_set))
            st.session_state.user_metadata_cache = metadata
            personas = fetch_user_personas_batch(tuple(all_user_ids_set))
            st.session_state.user_personas_cache = personas

        st.session_state.step = 3
        st.rerun()

    # --- Step 3: Review Pairs ---
    if st.session_state.step >= 3 and st.session_state.pairs:
        st.divider()
        st.subheader("Step 3: Review Pairs")

        pairs = st.session_state.pairs
        ratings = st.session_state.ratings
        metadata_cache = st.session_state.user_metadata_cache

        # Auto-fetch metadata and personas if cache is empty
        personas_cache = st.session_state.user_personas_cache
        if not metadata_cache:
            all_user_ids_set = set()
            for p in pairs:
                all_user_ids_set.add(p['user_id'])
                all_user_ids_set.add(p['candidate_id'])
            with st.spinner("Loading user data from database..."):
                metadata = fetch_user_metadata_batch(tuple(all_user_ids_set))
                st.session_state.user_metadata_cache = metadata
                metadata_cache = metadata
                personas = fetch_user_personas_batch(tuple(all_user_ids_set))
                st.session_state.user_personas_cache = personas
                personas_cache = personas

        submitted_count = sum(1 for p in pairs if ratings.get(get_pair_key(p), {}).get('submitted', False))
        total_count = len(pairs)
        progress_pct = (submitted_count / total_count * 100) if total_count > 0 else 0

        # Header with download, reload and progress
        col_download, col_reload, col_progress = st.columns([1, 1, 2])

        with col_download:
            if submitted_count > 0:
                csv_data = []
                for pair in pairs:
                    key = get_pair_key(pair)
                    rating = ratings.get(key, {})
                    if rating.get('submitted'):
                        # Convert hybrid_score (0-1) to out of 10
                        ranking = pair['ranking_data']
                        hybrid = ranking.get('hybrid_score') if ranking.get('hybrid_score') is not None else ranking.get('score')
                        algo_score_10 = round(float(hybrid) * 10, 1) if hybrid is not None else None
                        csv_data.append({
                            'user_id': pair['user_id'],
                            'candidate_id': pair['candidate_id'],
                            'algo_score': algo_score_10,
                            'category': pair.get('category'),  # top/avg/low
                            'human_score': rating.get('score'),
                            'reason': rating.get('reason', '')
                        })

                df = pd.DataFrame(csv_data)
                csv_buffer = BytesIO()
                df.to_csv(csv_buffer, index=False)
                csv_buffer.seek(0)

                st.download_button(
                    label=f"Download CSV ({submitted_count})",
                    data=csv_buffer,
                    file_name="pair_scoring_ratings.csv",
                    mime="text/csv",
                    type="primary"
                )
            else:
                st.button("Download CSV (0)", disabled=True)

        with col_reload:
            if st.button("Reload from DB", type="secondary", use_container_width=True):
                fetch_user_metadata_batch.clear()
                fetch_user_personas_batch.clear()
                all_user_ids_set = set()
                for p in pairs:
                    all_user_ids_set.add(p['user_id'])
                    all_user_ids_set.add(p['candidate_id'])
                with st.spinner("Reloading user data..."):
                    metadata = fetch_user_metadata_batch(tuple(all_user_ids_set))
                    st.session_state.user_metadata_cache = metadata
                    personas = fetch_user_personas_batch(tuple(all_user_ids_set))
                    st.session_state.user_personas_cache = personas
                st.rerun()

        with col_progress:
            st.markdown(f"**Progress:** {submitted_count} / {total_count}")
            st.markdown(f'''
            <div class="progress-container">
                <div class="progress-bar" style="width: {progress_pct}%"></div>
            </div>
            ''', unsafe_allow_html=True)

        st.divider()

        # --- Pagination ---
        pairs_per_page = CONFIG['pairs_per_page']
        total_pages = (total_count + pairs_per_page - 1) // pairs_per_page  # ceiling division

        # Ensure current page is valid
        if st.session_state.current_page >= total_pages:
            st.session_state.current_page = max(0, total_pages - 1)

        current_page = st.session_state.current_page
        start_idx = current_page * pairs_per_page
        end_idx = min(start_idx + pairs_per_page, total_count)

        # Pagination controls at top
        col_prev, col_page_info, col_next = st.columns([1, 2, 1])

        with col_prev:
            if st.button("← Previous", disabled=(current_page == 0), use_container_width=True):
                st.session_state.current_page -= 1
                st.rerun()

        with col_page_info:
            st.markdown(f"<div style='text-align: center; padding: 8px;'><b>Page {current_page + 1} of {total_pages}</b> (showing {start_idx + 1}-{end_idx} of {total_count})</div>", unsafe_allow_html=True)

        with col_next:
            if st.button("Next →", disabled=(current_page >= total_pages - 1), use_container_width=True):
                st.session_state.current_page += 1
                st.rerun()

        st.divider()

        # Display only current page pairs
        page_pairs = pairs[start_idx:end_idx]

        for idx, pair in enumerate(page_pairs):
            actual_idx = start_idx + idx  # actual index in full list
            key = get_pair_key(pair)
            rating = ratings.get(key, {'score': None, 'reason': '', 'submitted': False})
            is_submitted = rating.get('submitted', False)
            ranking_data = pair['ranking_data']

            user_meta = metadata_cache.get(pair['user_id'], {})
            candidate_meta = metadata_cache.get(pair['candidate_id'], {})
            user_persona = personas_cache.get(pair['user_id'], '')
            candidate_persona = personas_cache.get(pair['candidate_id'], '')

            # Get names with fallback to truncated ID
            user_name = pair['user_id'][:8]
            if user_meta and user_meta.get('name'):
                user_name = user_meta.get('name')

            candidate_name = pair['candidate_id'][:8]
            if candidate_meta and candidate_meta.get('name'):
                candidate_name = candidate_meta.get('name')

            # Use expander for each pair
            with st.expander(f"#{actual_idx+1} {user_name} × {candidate_name}{'  ✓' if is_submitted else ''}", expanded=(st.session_state.expanded_pair == key)):
                # Two column layout for user/candidate
                col_user, col_candidate = st.columns(2)

                with col_user:
                    st.markdown("### User")
                    render_user_card_streamlit(pair['user_id'], user_meta, persona=user_persona)
                    st.code(pair['user_id'], language=None)

                with col_candidate:
                    st.markdown("### Candidate")
                    render_user_card_streamlit(pair['candidate_id'], candidate_meta, ranking_data, persona=candidate_persona)
                    st.code(pair['candidate_id'], language=None)

                # Rating section using fragment for isolated rerun
                st.markdown("---")

                @st.fragment
                def rating_section(pair_key, current_rating):
                    if current_rating.get('submitted', False):
                        col_info, col_edit = st.columns([3, 1])
                        with col_info:
                            st.success(f"Score: {current_rating.get('score')} / 10 | Reason: {current_rating.get('reason', 'N/A')}")
                        with col_edit:
                            if st.button("Edit", key=f"edit_{pair_key}", type="secondary"):
                                st.session_state.ratings[pair_key]['submitted'] = False
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
                                key=f"score_{pair_key}"
                            )

                        with col_reason:
                            reason_val = st.text_input(
                                "Reasoning",
                                value=current_rating.get('reason', ''),
                                placeholder="Why this score?",
                                key=f"reason_{pair_key}"
                            )

                        with col_submit:
                            st.write("")
                            if st.button("Submit", key=f"submit_{pair_key}", type="primary"):
                                st.session_state.ratings[pair_key] = {
                                    'score': score_val,
                                    'reason': reason_val,
                                    'submitted': True
                                }
                                st.rerun()

                rating_section(key, rating)

        # Pagination controls at bottom too
        st.divider()
        col_prev2, col_page_info2, col_next2 = st.columns([1, 2, 1])

        with col_prev2:
            if st.button("← Previous", disabled=(current_page == 0), use_container_width=True, key="prev_bottom"):
                st.session_state.current_page -= 1
                st.rerun()

        with col_page_info2:
            st.markdown(f"<div style='text-align: center; padding: 8px;'><b>Page {current_page + 1} of {total_pages}</b></div>", unsafe_allow_html=True)

        with col_next2:
            if st.button("Next →", disabled=(current_page >= total_pages - 1), use_container_width=True, key="next_bottom"):
                st.session_state.current_page += 1
                st.rerun()

else:
    st.info("Please upload a user rankings JSON file to begin.")
