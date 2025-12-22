"""
Helper utilities for data processing.
"""
from datetime import datetime
from typing import Any, Optional, List, Dict
from collections import defaultdict


def safe_get(data: dict, *keys, default: Any = None) -> Any:
    """
    Safely get nested dictionary value.

    Args:
        data: Dictionary to search
        *keys: Keys to traverse
        default: Default value if not found

    Returns:
        Value or default
    """
    result = data
    for key in keys:
        if isinstance(result, dict):
            result = result.get(key, default)
        else:
            return default
    return result if result is not None else default


def calculate_stats(data: List[dict], group_by: Optional[str] = None) -> dict:
    """
    Calculate statistics from a list of records.

    Args:
        data: List of data records
        group_by: Optional field to group by

    Returns:
        Statistics dictionary
    """
    if not data:
        return {
            'total': 0,
            'liked': 0,
            'disliked': 0,
            'passed': 0,
            'viewed': 0,
            'mutual': 0,
            'like_rate': 0,
            'view_rate': 0,
            'mutual_rate': 0,
        }

    total = len(data)
    liked = sum(1 for d in data if d.get('is_liked') == 'liked')
    disliked = sum(1 for d in data if d.get('is_liked') == 'disliked')
    passed = sum(1 for d in data if d.get('is_liked') == 'passed')
    viewed = sum(1 for d in data if d.get('is_viewed'))
    mutual = sum(1 for d in data if d.get('is_mutual'))

    return {
        'total': total,
        'liked': liked,
        'disliked': disliked,
        'passed': passed,
        'viewed': viewed,
        'mutual': mutual,
        'like_rate': (liked / total * 100) if total > 0 else 0,
        'dislike_rate': (disliked / total * 100) if total > 0 else 0,
        'pass_rate': (passed / total * 100) if total > 0 else 0,
        'view_rate': (viewed / total * 100) if total > 0 else 0,
        'mutual_rate': (mutual / total * 100) if total > 0 else 0,
    }


def group_by_date(data: List[dict], date_field: str = 'created_at') -> Dict[str, list]:
    """
    Group data by date.

    Args:
        data: List of records
        date_field: Field containing datetime

    Returns:
        Dictionary grouped by date string
    """
    grouped = defaultdict(list)

    for item in data:
        date_value = item.get(date_field)
        if date_value:
            if isinstance(date_value, str):
                date_key = date_value[:10]  # YYYY-MM-DD
            elif isinstance(date_value, datetime):
                date_key = date_value.strftime('%Y-%m-%d')
            else:
                continue
            grouped[date_key].append(item)

    return dict(grouped)


def group_by_field(data: List[dict], field: str) -> Dict[str, list]:
    """
    Group data by a field value.

    Args:
        data: List of records
        field: Field to group by

    Returns:
        Dictionary grouped by field value
    """
    grouped = defaultdict(list)

    for item in data:
        key = item.get(field, 'Unknown')
        grouped[str(key)].append(item)

    return dict(grouped)


def filter_data(
    data: List[dict],
    filters: Dict[str, Any]
) -> List[dict]:
    """
    Filter data based on criteria.

    Args:
        data: List of records
        filters: Dictionary of {field: value} to filter by

    Returns:
        Filtered list
    """
    result = data

    for field, value in filters.items():
        if value is None:
            continue
        if isinstance(value, list):
            result = [d for d in result if d.get(field) in value]
        else:
            result = [d for d in result if d.get(field) == value]

    return result


def paginate(data: List[Any], page: int, page_size: int) -> tuple:
    """
    Paginate a list.

    Args:
        data: List to paginate
        page: Current page (1-indexed)
        page_size: Items per page

    Returns:
        Tuple of (paginated_data, total_pages, start_idx, end_idx)
    """
    total = len(data)
    total_pages = max(1, (total + page_size - 1) // page_size)

    # Ensure page is in valid range
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * page_size
    end_idx = min(start_idx + page_size, total)

    return data[start_idx:end_idx], total_pages, start_idx, end_idx


def merge_dicts(*dicts) -> dict:
    """Merge multiple dictionaries."""
    result = {}
    for d in dicts:
        if d:
            result.update(d)
    return result
