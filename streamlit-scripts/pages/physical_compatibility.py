"""
Physical Compatibility Scoring - Manually score physical compatibility of match pairs.
"""
import streamlit as st
import os
import sys
from datetime import datetime
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

# --- Constants ---
RUNS_TABLE = 'match_runs'
SCORES_TABLE = 'physical_compatibility_scores'


# --- Data Loading Functions ---
@st.cache_data(ttl=60)
def fetch_all_runs():
    """Fetch all match runs from database."""
    try:
        res = supabase.table(RUNS_TABLE).select(
            'id, run_timestamp, total_matches, matches_ranked'
        ).order('run_timestamp', desc=True).execute()
        return res.data if res.data else []
    except Exception as e:
        st.error(f"Error fetching runs: {e}")
        return []


def fetch_run_data(run_id: str):
    """Fetch full run data including matches JSON."""
    try:
        res = supabase.table(RUNS_TABLE).select('*').eq('id', run_id).maybe_single().execute()
        return res.data if res.data else None
    except Exception as e:
        st.error(f"Error fetching run data: {e}")
        return None


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


def generate_pair_id(user_a_id: str, user_b_id: str) -> str:
    """Generate a consistent pair_id from two user IDs."""
    return f"{user_a_id}_{user_b_id}"


# Physical feature names to display
PHYSICAL_FEATURES = [
    'body_type_male',
    'body_type_female',
    'hair_type',
    'facial_emotions',
    'aesthetic_types',
    'photo_activity_type',
]


@st.cache_data(ttl=60)
def fetch_user_physical_features(user_id: str):
    """Fetch physical features for a user from user_feature_values table."""
    try:
        res = supabase.table('user_feature_values').select(
            'feature_name, feature_value, feature_values, confidence_score'
        ).eq('user_id', user_id).in_('feature_name', PHYSICAL_FEATURES).execute()

        features = []
        if res.data:
            for row in res.data:
                # Use feature_value if available, else feature_values
                value = row.get('feature_value') or row.get('feature_values')
                if isinstance(value, list):
                    value = ', '.join(str(v) for v in value)
                elif isinstance(value, dict):
                    value = str(value)

                features.append({
                    'feature_name': row['feature_name'],
                    'value': value or 'N/A',
                    'confidence': row.get('confidence_score', 0) or 0
                })
        return features
    except Exception as e:
        return []


def fetch_existing_scores(run_timestamp: str):
    """Fetch existing scores for a given run."""
    try:
        res = supabase.table(SCORES_TABLE).select(
            'pair_id, manual_score'
        ).eq('run_timestamp', run_timestamp).execute()

        scores = {}
        if res.data:
            for row in res.data:
                scores[row['pair_id']] = row['manual_score']
        return scores
    except Exception as e:
        return {}


def save_score(match: dict, score: int, run_timestamp: str, run_id: str):
    """Save or update a physical compatibility score."""
    user_a_id = match['user_a_id']
    user_b_id = match['user_b_id']
    pair_id = generate_pair_id(user_a_id, user_b_id)

    try:
        existing = supabase.table(SCORES_TABLE).select('id').eq(
            'pair_id', pair_id
        ).eq('run_timestamp', run_timestamp).maybe_single().execute()

        record = {
            'pair_id': pair_id,
            'user_a_id': user_a_id,
            'user_a_gender': match.get('user_a_gender'),
            'user_b_id': user_b_id,
            'user_b_gender': match.get('user_b_gender'),
            'success_probability': match.get('success_probability'),
            'user_a_rank': match.get('user_a_rank'),
            'user_b_rank': match.get('user_b_rank'),
            'user_a_score': match.get('user_a_score'),
            'user_b_score': match.get('user_b_score'),
            'avg_score': match.get('avg_score'),
            'top_features_a': match.get('top_features_a'),
            'top_features_b': match.get('top_features_b'),
            'manual_score': score,
            'run_timestamp': run_timestamp,
            'scored_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
        }

        is_new_score = False
        if existing and existing.data:
            supabase.table(SCORES_TABLE).update(record).eq(
                'id', existing.data['id']
            ).execute()
        else:
            record['created_at'] = datetime.now().isoformat()
            supabase.table(SCORES_TABLE).insert(record).execute()
            is_new_score = True

        # Update matches_ranked count in match_runs if new score
        if is_new_score and run_id:
            update_matches_ranked(run_id)

        return True
    except Exception as e:
        st.error(f"Failed to save score: {e}")
        return False


def update_matches_ranked(run_id: str):
    """Increment matches_ranked count for a run."""
    try:
        # Get current count
        res = supabase.table(RUNS_TABLE).select('matches_ranked').eq('id', run_id).maybe_single().execute()
        if res.data:
            current = res.data.get('matches_ranked', 0) or 0
            supabase.table(RUNS_TABLE).update({
                'matches_ranked': current + 1
            }).eq('id', run_id).execute()
    except Exception as e:
        pass  # Non-critical, don't block


def display_user_card(meta: dict, label: str, user_id: str = None):
    """Display user photos and physical feature data."""
    name = meta.get('name', 'Unknown') if meta else 'Unknown'
    age = meta.get('age', '') if meta else ''
    city = meta.get('city', '') if meta else ''

    st.markdown(f"**{label}: {name}** {f'({age})' if age else ''} {f'- {city}' if city else ''}")

    if not meta:
        st.caption("No user data")
        st.markdown("""
        <div style="height: 200px; background: #2d2d2d; border-radius: 8px; display: flex; align-items: center; justify-content: center; color: #888;">
            No images available
        </div>
        """, unsafe_allow_html=True)
        return

    # Show photos in horizontal scrollable container
    photos = meta.get('profile_images') or meta.get('instagram_images') or []
    if photos and isinstance(photos, list):
        images_html = ""
        for url in photos:
            images_html += f'<img src="{url}" style="height: 200px; width: auto; object-fit: cover; border-radius: 8px; flex-shrink: 0;">'

        st.markdown(f"""
        <div style="
            display: flex;
            gap: 8px;
            overflow-x: auto;
            padding: 8px 0;
            scrollbar-width: thin;
        ">
            {images_html}
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="height: 200px; background: #2d2d2d; border-radius: 8px; display: flex; align-items: center; justify-content: center; color: #888;">
            No images available
        </div>
        """, unsafe_allow_html=True)

    # Fetch and show physical features from user_feature_values table
    if user_id:
        physical_features = fetch_user_physical_features(user_id)
        if physical_features:
            with st.expander("Physical Features", expanded=False):
                for feature in physical_features:
                    feat_name = feature.get('feature_name', '').replace('_', ' ').title()
                    value = feature.get('value', 'N/A')
                    confidence = feature.get('confidence', 0)

                    # Color code by confidence
                    if confidence >= 0.8:
                        color = "green"
                    elif confidence >= 0.5:
                        color = "orange"
                    else:
                        color = "gray"

                    st.markdown(f":{color}[{feat_name}]: {value} (conf: {confidence:.2f})")


def render_match_card(match: dict, index: int, existing_score: int = None, run_timestamp: str = None, run_id: str = None):
    """Render a single match card with scoring buttons."""
    user_a_id = match['user_a_id']
    user_b_id = match['user_b_id']

    user_a_meta = fetch_user_metadata(user_a_id)
    user_b_meta = fetch_user_metadata(user_b_id)

    user_a_name = user_a_meta.get('name', 'Unknown') if user_a_meta else 'Unknown'
    user_b_name = user_b_meta.get('name', 'Unknown') if user_b_meta else 'Unknown'

    with st.container():
        score_display = f"{existing_score}/5" if existing_score else "Not scored"
        st.markdown(f"### Match {index + 1}: {user_a_name} & {user_b_name}")
        st.caption(f"Prob: {match.get('success_probability', 0):.2f} | Avg Score: {match.get('avg_score', 0):.2f} | Current Score: {score_display}")

        col_a, col_b = st.columns(2)

        with col_a:
            gender_a = match.get('user_a_gender', 'unknown').capitalize()
            display_user_card(user_a_meta, gender_a, user_a_id)

        with col_b:
            gender_b = match.get('user_b_gender', 'unknown').capitalize()
            display_user_card(user_b_meta, gender_b, user_b_id)

        # Score buttons
        st.markdown("**Rate Physical Compatibility:**")
        score_cols = st.columns(5)
        for i in range(5):
            with score_cols[i]:
                score_val = i + 1
                btn_type = "primary" if existing_score == score_val else "secondary"
                if st.button(str(score_val), key=f"score_{user_a_id}_{user_b_id}_{score_val}", type=btn_type, use_container_width=True):
                    if save_score(match, score_val, run_timestamp, run_id):
                        st.rerun()

        st.divider()


# --- Sidebar: Run Selection ---
st.sidebar.header("Select Run")

all_runs = fetch_all_runs()

if not all_runs:
    st.sidebar.warning("No match runs found in database.")
    st.info("No match runs available. Please add runs to the `match_runs` table first.")
    st.stop()

# Create dropdown options
run_options = {}
for run in all_runs:
    ts = run['run_timestamp']
    # Format: "2025-11-13 11:59 (78 matches, 45 ranked)"
    ts_display = ts[:16].replace('T', ' ') if ts else 'Unknown'
    label = f"{ts_display} ({run['total_matches']} matches, {run['matches_ranked']} ranked)"
    run_options[label] = run['id']

# Initialize session state for selected run
if 'selected_run_id' not in st.session_state:
    st.session_state.selected_run_id = all_runs[0]['id'] if all_runs else None

selected_label = st.sidebar.selectbox(
    "Match Run",
    options=list(run_options.keys()),
    index=0
)

selected_run_id = run_options[selected_label]

# Update session state
if selected_run_id != st.session_state.selected_run_id:
    st.session_state.selected_run_id = selected_run_id
    st.rerun()

# Fetch selected run data
run_data = fetch_run_data(selected_run_id)

if not run_data:
    st.error("Failed to load run data.")
    st.stop()

run_timestamp = run_data['run_timestamp']
matches_json = run_data['matches_json']
total_matches = run_data['total_matches']
matches_ranked = run_data['matches_ranked']

# Extract matches from JSON
mutual_matches = matches_json.get('mutual_matches', []) if matches_json else []
stats = matches_json.get('stats', {}) if matches_json else {}

# Fetch existing scores
existing_scores = fetch_existing_scores(run_timestamp)
scored_count = len(existing_scores)

st.sidebar.divider()

# --- Sidebar: Stats ---
st.sidebar.subheader("Algorithm Stats")
st.sidebar.metric("Total Users", stats.get('total_users', 0))
col1, col2 = st.sidebar.columns(2)
with col1:
    st.metric("Males", stats.get('males', 0))
with col2:
    st.metric("Females", stats.get('females', 0))

st.sidebar.metric("Avg Success Prob", f"{stats.get('avg_success_probability', 0):.2f}")

st.sidebar.divider()

# --- Sidebar: Progress ---
st.sidebar.subheader("Scoring Progress")
st.sidebar.metric("Total Matches", total_matches)
col1, col2 = st.sidebar.columns(2)
with col1:
    st.metric("Scored", scored_count)
with col2:
    st.metric("Pending", total_matches - scored_count)

if total_matches > 0:
    progress = scored_count / total_matches
    st.sidebar.progress(progress, text=f"{int(progress * 100)}% complete")


# --- Main Content ---
col_title, col_refresh = st.columns([4, 1])
with col_title:
    st.title("Physical Compatibility Scoring")
with col_refresh:
    if st.button("Refresh", use_container_width=True, type="primary"):
        st.cache_data.clear()
        st.rerun()

ts_display = run_timestamp[:16].replace('T', ' ') if run_timestamp else 'Unknown'
st.info(f"Scoring matches from run: **{ts_display}** | Progress: {scored_count}/{total_matches}")

if not mutual_matches:
    st.warning("No matches found in this run.")
    st.stop()

# Display matches
for idx, match in enumerate(mutual_matches):
    pair_id = generate_pair_id(match['user_a_id'], match['user_b_id'])
    current_score = existing_scores.get(pair_id)
    render_match_card(match, idx, current_score, run_timestamp, selected_run_id)
