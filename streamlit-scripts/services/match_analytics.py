"""
Match Analytics Service - Data fetching, processing, and JSON caching.
"""
import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Callable, Optional

# Add parent directory for imports
current_dir = os.path.dirname(__file__)
parent_dir = os.path.abspath(os.path.join(current_dir, '../..'))
sys.path.insert(0, parent_dir)

from dependencies import get_supabase_client

# Constants
BATCH_SIZE = 250      # 250 rows per batch
BATCH_DELAY = 0.2     # 0.2 seconds between batches

# Data folder path
DATA_DIR = Path(__file__).parent.parent / 'data'

# JSON file paths
USER_MATCHES_JSON = DATA_DIR / 'user_matches.json'
USER_METADATA_JSON = DATA_DIR / 'user_metadata.json'
LAST_REFRESH_FILE = DATA_DIR / 'last_refresh.txt'


def data_exists() -> bool:
    """Check if required JSON files exist."""
    return USER_MATCHES_JSON.exists() and USER_METADATA_JSON.exists()


def get_last_refresh_time() -> Optional[str]:
    """Get last refresh timestamp from file."""
    if LAST_REFRESH_FILE.exists():
        return LAST_REFRESH_FILE.read_text().strip()
    return None


def delete_old_jsons() -> None:
    """Delete match analytics JSON files in data folder."""
    if USER_MATCHES_JSON.exists():
        USER_MATCHES_JSON.unlink()
    if USER_METADATA_JSON.exists():
        USER_METADATA_JSON.unlink()
    if LAST_REFRESH_FILE.exists():
        LAST_REFRESH_FILE.unlink()


def fetch_user_matches(progress_callback: Optional[Callable] = None) -> list:
    """
    Fetch all user_matches from Supabase in batches.

    Args:
        progress_callback: Function(batch_num, total_batches, rows_fetched) for progress updates

    Returns:
        List of all user_matches records
    """
    supabase = get_supabase_client()
    all_data = []
    offset = 0
    batch_num = 0

    # First, get total count
    count_response = supabase.table('user_matches').select('match_id', count='exact').execute()
    total_count = count_response.count if count_response.count else 0
    total_batches = (total_count // BATCH_SIZE) + (1 if total_count % BATCH_SIZE else 0)

    if total_batches == 0:
        total_batches = 1

    while True:
        batch_num += 1

        response = supabase.table('user_matches').select(
            'match_id, current_user_id, matched_user_id, rank, is_viewed, viewed_at, '
            'is_liked, liked_at, know_more_count, origin_phase, created_at'
        ).range(offset, offset + BATCH_SIZE - 1).execute()

        if not response.data:
            break

        all_data.extend(response.data)

        if progress_callback:
            progress_callback(batch_num, total_batches, len(all_data))

        if len(response.data) < BATCH_SIZE:
            break

        offset += BATCH_SIZE
        time.sleep(BATCH_DELAY)

    return all_data


def fetch_user_metadata(progress_callback: Optional[Callable] = None) -> list:
    """
    Fetch all user_metadata from Supabase in batches.

    Args:
        progress_callback: Function(batch_num, total_batches, rows_fetched) for progress updates

    Returns:
        List of all user_metadata records
    """
    supabase = get_supabase_client()
    all_data = []
    offset = 0
    batch_num = 0

    # First, get total count
    count_response = supabase.table('user_metadata').select('user_id', count='exact').execute()
    total_count = count_response.count if count_response.count else 0
    total_batches = (total_count // BATCH_SIZE) + (1 if total_count % BATCH_SIZE else 0)

    if total_batches == 0:
        total_batches = 1

    while True:
        batch_num += 1

        response = supabase.table('user_metadata').select(
            'user_id, gender, professional_tier'
        ).range(offset, offset + BATCH_SIZE - 1).execute()

        if not response.data:
            break

        all_data.extend(response.data)

        if progress_callback:
            progress_callback(batch_num, total_batches, len(all_data))

        if len(response.data) < BATCH_SIZE:
            break

        offset += BATCH_SIZE
        time.sleep(BATCH_DELAY)

    return all_data


def save_json_files(matches: list, metadata: list) -> None:
    """Save fetched data to JSON files."""
    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Save user_matches
    with open(USER_MATCHES_JSON, 'w') as f:
        json.dump({
            'metadata': {
                'fetched_at': datetime.now().isoformat(),
                'total_rows': len(matches),
                'table': 'user_matches'
            },
            'data': matches
        }, f)

    # Save user_metadata
    with open(USER_METADATA_JSON, 'w') as f:
        json.dump({
            'metadata': {
                'fetched_at': datetime.now().isoformat(),
                'total_rows': len(metadata),
                'table': 'user_metadata'
            },
            'data': metadata
        }, f)

    # Save last refresh timestamp in IST (UTC+5:30)
    ist = timezone(timedelta(hours=5, minutes=30))
    refresh_time = datetime.now(ist).strftime('%b %d, %Y %I:%M %p IST')
    LAST_REFRESH_FILE.write_text(refresh_time)


def load_json_files() -> tuple:
    """
    Load data from JSON files.

    Returns:
        Tuple of (matches_data, metadata_data) or (None, None) if files don't exist
    """
    if not data_exists():
        return None, None

    with open(USER_MATCHES_JSON, 'r') as f:
        matches_json = json.load(f)

    with open(USER_METADATA_JSON, 'r') as f:
        metadata_json = json.load(f)

    return matches_json.get('data', []), metadata_json.get('data', [])


def get_available_dates(matches: list) -> list:
    """
    Get unique dates from matches data, sorted descending.

    Args:
        matches: List of match records

    Returns:
        List of date strings (YYYY-MM-DD format), sorted newest first
    """
    dates = set()
    for match in matches:
        created_at = match.get('created_at')
        if created_at:
            date_str = created_at[:10]  # Extract YYYY-MM-DD
            dates.add(date_str)

    return sorted(dates, reverse=True)


# ==============================================
# RETENTION ANALYTICS HELPER FUNCTIONS
# ==============================================

def build_likes_set(matches: list) -> set:
    """
    Build a set of (user_a, user_b) pairs where user_a liked user_b.
    Used for mutual match detection without relying on is_mutual field.
    """
    return {
        (m.get('current_user_id'), m.get('matched_user_id'))
        for m in matches
        if m.get('is_liked') == 'liked'
    }


def is_mutual_match(user_a: str, user_b: str, likes_set: set) -> bool:
    """Check if both users liked each other (NOT relying on is_mutual field)."""
    return (user_a, user_b) in likes_set and (user_b, user_a) in likes_set


def get_user_activity_on_date(user_id: str, date: str, matches: list) -> dict:
    """
    Get user's activity summary on a specific date.
    Uses viewed_at timestamp to determine activity date.

    Returns:
        dict with keys: viewed, liked, disliked, passed, matched_users
    """
    activity = {
        'viewed': False,
        'liked': [],      # list of matched_user_ids they liked
        'disliked': [],
        'passed': [],
        'viewed_profiles': []
    }

    for m in matches:
        if m.get('current_user_id') != user_id:
            continue

        # Check viewed_at date
        viewed_at = m.get('viewed_at', '')
        if viewed_at and viewed_at[:10] == date:
            activity['viewed'] = True
            activity['viewed_profiles'].append(m.get('matched_user_id'))

            is_liked = m.get('is_liked')
            if is_liked == 'liked':
                activity['liked'].append(m.get('matched_user_id'))
            elif is_liked == 'disliked':
                activity['disliked'].append(m.get('matched_user_id'))
            elif is_liked == 'passed':
                activity['passed'].append(m.get('matched_user_id'))

    return activity


def user_active_on_date(user_id: str, date: str, matches: list) -> bool:
    """Check if user viewed at least 1 profile on the given date."""
    for m in matches:
        if m.get('current_user_id') != user_id:
            continue
        viewed_at = m.get('viewed_at', '')
        if viewed_at and viewed_at[:10] == date:
            return True
    return False


def classify_user_category_on_date(user_id: str, date: str, matches: list, likes_set: set) -> str:
    """
    Classify user as A/B/C on a specific date.

    Categories:
        A = viewed/passed only (no likes/dislikes on that date)
        B = liked OR disliked someone but no mutual match on that date
        C = got a mutual match on that date
        None = no activity on that date
    """
    activity = get_user_activity_on_date(user_id, date, matches)

    if not activity['viewed']:
        return None  # No activity

    # Check for mutual matches (Category C)
    for liked_user in activity['liked']:
        if is_mutual_match(user_id, liked_user, likes_set):
            return 'C'

    # Check for likes without mutual (Category B)
    if activity['liked']:
        return 'B'

    # Check for dislikes (Category B - they took action, not just viewed)
    if activity['disliked']:
        return 'B'

    # Viewed/passed only (Category A)
    return 'A'


def get_highest_category_ever(user_id: str, matches: list, likes_set: set) -> str:
    """
    Get the highest category a user has ever achieved.
    C > B > A

    Categories:
        A = ONLY viewed/passed (never liked or disliked anyone ever)
        B = liked someone but no mutual match
        C = got at least one mutual match
    """
    has_liked = False
    has_disliked = False
    has_viewed = False

    for m in matches:
        if m.get('current_user_id') != user_id:
            continue

        if m.get('is_viewed'):
            has_viewed = True

        is_liked_val = m.get('is_liked')
        if is_liked_val == 'liked':
            has_liked = True
            matched_user = m.get('matched_user_id')
            if is_mutual_match(user_id, matched_user, likes_set):
                return 'C'  # Got mutual match
        elif is_liked_val == 'disliked':
            has_disliked = True

    if has_liked:
        return 'B'  # Liked but no mutual
    if has_disliked:
        return 'B'  # Disliked someone - NOT a pure viewer
    if has_viewed:
        return 'A'  # Only viewed/passed (never liked or disliked)
    return None


def get_retention_dates(matches: list) -> list:
    """
    Get unique dates from created_at timestamps, sorted descending.
    Same as get_available_dates - uses created_at for consistency.
    """
    dates = set()
    for m in matches:
        created_at = m.get('created_at', '')
        if created_at:
            dates.add(created_at[:10])
    return sorted(dates, reverse=True)


def get_user_match_dates(user_id: str, matches: list, likes_set: set) -> list:
    """
    Get ALL dates when user got mutual matches.
    Match date = when this user first liked the matched_user (liked_at).
    A user can have multiple matches with different people.

    Returns:
        List of dates (sorted ascending) when matches happened
    """
    match_dates = set()
    for m in matches:
        if m.get('current_user_id') != user_id:
            continue
        if m.get('is_liked') == 'liked':
            matched_user = m.get('matched_user_id')
            if is_mutual_match(user_id, matched_user, likes_set):
                # Get the date when this user liked (first like to this matched_user)
                liked_at = m.get('liked_at', '')
                if liked_at:
                    match_dates.add(liked_at[:10])
    return sorted(match_dates) if match_dates else []


def get_user_first_like_date(user_id: str, matches: list) -> str:
    """
    Get the date when user first liked someone.
    """
    first_like_date = None
    for m in matches:
        if m.get('current_user_id') != user_id:
            continue
        if m.get('is_liked') == 'liked':
            liked_at = m.get('liked_at', '')
            if liked_at:
                date = liked_at[:10]
                if first_like_date is None or date < first_like_date:
                    first_like_date = date
    return first_like_date if first_like_date else '-'


def get_user_like_dates(user_id: str, matches: list) -> list:
    """
    Get ALL dates when user liked someone (not mutual).
    Returns list of unique dates sorted ascending.
    """
    like_dates = set()
    for m in matches:
        if m.get('current_user_id') != user_id:
            continue
        if m.get('is_liked') == 'liked':
            liked_at = m.get('liked_at', '')
            if liked_at:
                like_dates.add(liked_at[:10])
    return sorted(like_dates) if like_dates else []


def get_user_view_dates(user_id: str, matches: list) -> list:
    """
    Get ALL unique dates when user viewed profiles (using viewed_at timestamp).
    Returns list of unique dates sorted ascending.
    """
    view_dates = set()
    for m in matches:
        if m.get('current_user_id') != user_id:
            continue
        viewed_at = m.get('viewed_at', '')
        if viewed_at:
            view_dates.add(viewed_at[:10])
    return sorted(view_dates) if view_dates else []


def compare_with_operator(value: int, operator: str, target: int) -> bool:
    """Compare value with target using the specified operator."""
    if operator == '>=':
        return value >= target
    elif operator == '==':
        return value == target
    elif operator == '<=':
        return value <= target
    elif operator == '>':
        return value > target
    elif operator == '<':
        return value < target
    return True  # Default pass if unknown operator


def get_users_by_retention_criteria(
    category: str,
    category_dates: list,
    return_dates: list,
    and_logic: bool,
    use_highest_category: bool,
    matches: list,
    metadata: list,
    likes_set: set,
    gender: str = 'both',
    tier: str = 'all',
    match_count_op: str = None,
    match_count_val: int = None,
    return_count_op: str = None,
    return_count_val: int = None,
    like_count_op: str = None,
    like_count_val: int = None,
    view_count_op: str = None,
    view_count_val: int = None
) -> list:
    """
    Main query function for User List tab.

    Args:
        category: 'A', 'B', or 'C'
        category_dates: dates when user should be this category
        return_dates: dates to check if user came back
        and_logic: True = must be active on ALL return dates, False = ANY
        use_highest_category: True = check highest category ever, False = on specific dates
        matches: full matches list
        metadata: user metadata list
        likes_set: pre-built likes set for mutual detection
        gender: 'both', 'male', 'female'
        tier: 'all', '1', '2', '3'
        match_count_op: Operator for mutual match dates count filter (>=, ==, <=, >, <) - Category C
        match_count_val: Value for mutual match dates count filter - Category C
        return_count_op: Operator for returned dates count filter (>=, ==, <=, >, <)
        return_count_val: Value for returned dates count filter
        like_count_op: Operator for like dates count filter (>=, ==, <=, >, <) - Category B
        like_count_val: Value for like dates count filter - Category B
        view_count_op: Operator for viewed dates count filter (>=, ==, <=, >, <) - Category A
        view_count_val: Value for viewed dates count filter - Category A

    Returns:
        List of dicts with user_id and activity info
    """
    # Build user metadata lookup
    user_lookup = {}
    for user in metadata:
        user_lookup[user.get('user_id')] = {
            'gender': user.get('gender'),
            'tier': user.get('professional_tier')
        }

    # Get all unique user_ids from matches
    all_users = set(m.get('current_user_id') for m in matches)

    matching_users = []

    for user_id in all_users:
        # Apply gender/tier filters
        user_info = user_lookup.get(user_id, {})

        if gender != 'both' and user_info.get('gender') != gender:
            continue
        if tier != 'all':
            user_tier = user_info.get('tier')
            if user_tier is None or str(user_tier) != tier:
                continue

        # Check category
        if use_highest_category:
            user_category = get_highest_category_ever(user_id, matches, likes_set)
        else:
            # Must be this category on at least one of the category_dates
            user_category = None
            for date in category_dates:
                cat = classify_user_category_on_date(user_id, date, matches, likes_set)
                if cat == category:
                    user_category = category
                    break

        if user_category != category:
            continue

        # Check return behavior
        if return_dates:
            return_activity = []
            for date in return_dates:
                if user_active_on_date(user_id, date, matches):
                    return_activity.append(date)

            if and_logic:
                # Must be active on ALL return dates
                if len(return_activity) != len(return_dates):
                    continue
            else:
                # Must be active on at least one return date
                if not return_activity:
                    continue
        else:
            return_activity = []

        # Get additional info based on category
        match_dates_list = None
        like_dates_list = None
        view_dates_list = None

        if category == 'C':
            # For Category C, show ALL dates when they got matches (can be multiple)
            match_dates_list = get_user_match_dates(user_id, matches, likes_set)
            match_dates_str = ', '.join(match_dates_list) if match_dates_list else '-'
            # For filtering returned_on, use the FIRST (earliest) match date
            first_action_date = match_dates_list[0] if match_dates_list else None
        elif category == 'B':
            # For Category B, show ALL dates when they liked (no mutual match)
            like_dates_list = get_user_like_dates(user_id, matches)
            like_dates_str = ', '.join(like_dates_list) if like_dates_list else '-'
            # For filtering returned_on, use the FIRST (earliest) like date
            first_action_date = like_dates_list[0] if like_dates_list else None
        elif category == 'A':
            # For Category A, show ALL dates when they viewed profiles
            view_dates_list = get_user_view_dates(user_id, matches)
            view_dates_str = ', '.join(view_dates_list) if view_dates_list else '-'
            first_action_date = None  # Category A doesn't filter return dates
        else:
            first_action_date = None

        # For Category C: Only consider return dates AFTER the match date
        if category == 'C' and first_action_date:
            valid_return_dates = [d for d in return_dates if d > first_action_date]
            filtered_return = [d for d in return_activity if d > first_action_date]

            # Check if we're allowing 0 return dates
            allow_zero_returns = (return_count_op == '>=' and return_count_val == 0) or \
                                 (return_count_op == '==' and return_count_val == 0) or \
                                 (return_count_op == '<=' and return_count_val is not None) or \
                                 (return_count_op == '<' and return_count_val is not None and return_count_val > 0)

            # Re-apply AND/OR logic on the valid return dates (skip if allowing zero returns)
            if valid_return_dates and not allow_zero_returns:
                if and_logic:
                    if len(filtered_return) != len(valid_return_dates):
                        continue
                else:
                    if not filtered_return:
                        continue
            elif not valid_return_dates and not allow_zero_returns:
                continue

        # For Category B: Only consider return dates AFTER the first like date
        elif category == 'B' and first_action_date:
            valid_return_dates = [d for d in return_dates if d > first_action_date]
            filtered_return = [d for d in return_activity if d > first_action_date]

            # Check if we're allowing 0 return dates
            allow_zero_returns = (return_count_op == '>=' and return_count_val == 0) or \
                                 (return_count_op == '==' and return_count_val == 0) or \
                                 (return_count_op == '<=' and return_count_val is not None) or \
                                 (return_count_op == '<' and return_count_val is not None and return_count_val > 0)

            # Re-apply AND/OR logic on the valid return dates (skip if allowing zero returns)
            if valid_return_dates and not allow_zero_returns:
                if and_logic:
                    if len(filtered_return) != len(valid_return_dates):
                        continue
                else:
                    if not filtered_return:
                        continue
            elif not valid_return_dates and not allow_zero_returns:
                continue
        else:
            # For Category A or others, use original return_activity
            filtered_return = return_activity

        # Sort dates in ascending order (oldest first)
        filtered_return = sorted(filtered_return) if filtered_return else []

        # Apply additional filters for Category C
        if category == 'C':
            # Filter by mutual match dates count
            if match_count_op and match_count_val is not None:
                num_match_dates = len(match_dates_list) if match_dates_list else 0
                if not compare_with_operator(num_match_dates, match_count_op, match_count_val):
                    continue

            # Filter by returned dates count
            if return_count_op and return_count_val is not None:
                num_return_dates = len(filtered_return)
                if not compare_with_operator(num_return_dates, return_count_op, return_count_val):
                    continue

        # Apply additional filters for Category B
        elif category == 'B':
            # Filter by like dates count
            if like_count_op and like_count_val is not None:
                num_like_dates = len(like_dates_list) if like_dates_list else 0
                if not compare_with_operator(num_like_dates, like_count_op, like_count_val):
                    continue

            # Filter by returned dates count
            if return_count_op and return_count_val is not None:
                num_return_dates = len(filtered_return)
                if not compare_with_operator(num_return_dates, return_count_op, return_count_val):
                    continue

        # Apply additional filters for Category A
        elif category == 'A':
            # Filter by viewed dates count
            if view_count_op and view_count_val is not None:
                num_view_dates = len(view_dates_list) if view_dates_list else 0
                if not compare_with_operator(num_view_dates, view_count_op, view_count_val):
                    continue

        # Build the user record
        user_record = {
            'user_id': user_id,
            'category': user_category,
            'gender': user_info.get('gender', '-'),
            'tier': user_info.get('tier', '-'),
        }

        # Add category-specific columns
        if category == 'C':
            user_record['match_dates'] = match_dates_str
            user_record['match_dates_count'] = len(match_dates_list) if match_dates_list else 0
            user_record['return_dates_count'] = len(filtered_return)
            user_record['returned_on'] = ', '.join(filtered_return) if filtered_return else '-'
        elif category == 'B':
            user_record['like_dates'] = like_dates_str
            user_record['like_dates_count'] = len(like_dates_list) if like_dates_list else 0
            user_record['return_dates_count'] = len(filtered_return)
            user_record['returned_on'] = ', '.join(filtered_return) if filtered_return else '-'
        elif category == 'A':
            user_record['view_dates'] = view_dates_str
            user_record['view_dates_count'] = len(view_dates_list) if view_dates_list else 0

        matching_users.append(user_record)

    return matching_users


def calculate_retention_matrix(
    category_dates: list,
    return_dates: list,
    matches: list,
    metadata: list,
    likes_set: set,
    use_highest_category: bool,
    gender: str = 'both',
    tier: str = 'all'
) -> dict:
    """
    Calculate retention matrix for all categories (A, B, C).

    Returns:
        {
            'A': {'users': [user_ids], 'count': N, 'returned': {date: count}},
            'B': {...},
            'C': {...}
        }
    """
    # Build user metadata lookup
    user_lookup = {}
    for user in metadata:
        user_lookup[user.get('user_id')] = {
            'gender': user.get('gender'),
            'tier': user.get('professional_tier')
        }

    # Get all unique user_ids
    all_users = set(m.get('current_user_id') for m in matches)

    # Classify users into categories
    cohorts = {'A': [], 'B': [], 'C': []}

    for user_id in all_users:
        # Apply gender/tier filters
        user_info = user_lookup.get(user_id, {})

        if gender != 'both' and user_info.get('gender') != gender:
            continue
        if tier != 'all':
            user_tier = user_info.get('tier')
            if user_tier is None or str(user_tier) != tier:
                continue

        # Classify user
        if use_highest_category:
            category = get_highest_category_ever(user_id, matches, likes_set)
        else:
            # Get category on the first category_date
            category = None
            for date in category_dates:
                category = classify_user_category_on_date(user_id, date, matches, likes_set)
                if category:
                    break

        if category in cohorts:
            cohorts[category].append(user_id)

    # Calculate retention for each return date
    result = {}
    for cat, users in cohorts.items():
        returned = {}
        for date in return_dates:
            count = sum(1 for u in users if user_active_on_date(u, date, matches))
            returned[date] = count

        result[cat] = {
            'users': users,
            'count': len(users),
            'returned': returned
        }

    return result


def calculate_user_transitions(
    start_dates: list,
    end_dates: list,
    matches: list,
    likes_set: set,
    metadata: list,
    gender: str = 'both',
    tier: str = 'all'
) -> dict:
    """
    Calculate how users transitioned between categories.

    Returns:
        {
            'A->A': count, 'A->B': count, 'A->C': count,
            'B->B': count, 'B->C': count,
            'C->C': count
        }
    """
    # Build user metadata lookup
    user_lookup = {}
    for user in metadata:
        user_lookup[user.get('user_id')] = {
            'gender': user.get('gender'),
            'tier': user.get('professional_tier')
        }

    all_users = set(m.get('current_user_id') for m in matches)

    transitions = {
        'A->A': 0, 'A->B': 0, 'A->C': 0,
        'B->B': 0, 'B->C': 0,
        'C->C': 0,
        'lost': {'A': 0, 'B': 0, 'C': 0}  # Users who didn't return
    }

    for user_id in all_users:
        # Apply filters
        user_info = user_lookup.get(user_id, {})
        if gender != 'both' and user_info.get('gender') != gender:
            continue
        if tier != 'all':
            user_tier = user_info.get('tier')
            if user_tier is None or str(user_tier) != tier:
                continue

        # Get start category (on any of start_dates)
        start_cat = None
        for date in start_dates:
            start_cat = classify_user_category_on_date(user_id, date, matches, likes_set)
            if start_cat:
                break

        if not start_cat:
            continue

        # Get end category (highest across end_dates)
        end_cat = None
        for date in end_dates:
            cat = classify_user_category_on_date(user_id, date, matches, likes_set)
            if cat:
                # Take highest category
                if end_cat is None or (cat == 'C') or (cat == 'B' and end_cat == 'A'):
                    end_cat = cat

        if not end_cat:
            transitions['lost'][start_cat] += 1
            continue

        # Record transition
        key = f"{start_cat}->{end_cat}"
        if key in transitions:
            transitions[key] += 1

    return transitions


def filter_data(matches: list, metadata: list,
                selected_dates: list = None,
                gender: str = 'both',
                tier: str = 'all') -> list:
    """
    Filter matches data based on selected filters.

    Args:
        matches: List of match records
        metadata: List of user metadata records
        selected_dates: List of date strings to include
        gender: 'both', 'male', or 'female'
        tier: 'all', '1', '2', or '3'

    Returns:
        Filtered list of matches
    """
    # Build user metadata lookup
    user_lookup = {}
    for user in metadata:
        user_lookup[user.get('user_id')] = {
            'gender': user.get('gender'),
            'tier': user.get('professional_tier')
        }

    filtered = []
    for match in matches:
        # Date filter
        if selected_dates:
            created_at = match.get('created_at', '')[:10]
            if created_at not in selected_dates:
                continue

        # Get user info for current_user_id
        current_user_id = match.get('current_user_id')
        user_info = user_lookup.get(current_user_id, {})

        # Gender filter (on current_user_id)
        if gender != 'both':
            if user_info.get('gender') != gender:
                continue

        # Tier filter (on current_user_id)
        if tier != 'all':
            user_tier = user_info.get('tier')
            if user_tier is None or str(user_tier) != tier:
                continue

        filtered.append(match)

    return filtered
