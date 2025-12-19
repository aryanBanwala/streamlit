"""
Utility functions for the dashboard.
"""
from .formatting import (
    format_number,
    format_percentage,
    format_date,
    format_datetime,
    truncate_text,
    get_gender_icon,
    get_status_badge,
)
from .helpers import (
    safe_get,
    calculate_stats,
    group_by_date,
)

__all__ = [
    'format_number',
    'format_percentage',
    'format_date',
    'format_datetime',
    'truncate_text',
    'get_gender_icon',
    'get_status_badge',
    'safe_get',
    'calculate_stats',
    'group_by_date',
]
