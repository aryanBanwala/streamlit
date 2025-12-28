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
BATCH_SIZE = 100      # 100 rows per batch
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
