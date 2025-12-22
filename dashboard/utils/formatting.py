"""
Formatting utilities for display.
"""
from datetime import datetime
from typing import Optional, Union


def format_number(value: Union[int, float], decimals: int = 0) -> str:
    """Format number with commas."""
    if value is None:
        return "N/A"
    if decimals > 0:
        return f"{value:,.{decimals}f}"
    return f"{int(value):,}"


def format_percentage(value: float, decimals: int = 1) -> str:
    """Format as percentage."""
    if value is None:
        return "N/A"
    return f"{value:.{decimals}f}%"


def format_date(value: Union[str, datetime], format_str: str = "%b %d, %Y") -> str:
    """Format date for display."""
    if value is None:
        return "N/A"
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return value[:10] if len(value) >= 10 else value
    return value.strftime(format_str)


def format_datetime(value: Union[str, datetime], format_str: str = "%b %d, %Y %H:%M") -> str:
    """Format datetime for display."""
    if value is None:
        return "N/A"
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return value[:16] if len(value) >= 16 else value
    return value.strftime(format_str)


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to max length."""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def get_gender_icon(gender: Optional[str]) -> str:
    """Get gender icon."""
    if gender == 'male':
        return "M"
    elif gender == 'female':
        return "F"
    return "?"


def get_gender_color(gender: Optional[str]) -> str:
    """Get gender color."""
    if gender == 'male':
        return "#1976d2"
    elif gender == 'female':
        return "#e91e63"
    return "#9e9e9e"


def get_status_badge(status: str) -> tuple:
    """
    Get status badge styling.
    Returns (color, label).
    """
    status_map = {
        'liked': ('#4caf50', 'Liked'),
        'disliked': ('#f44336', 'Disliked'),
        'passed': ('#9e9e9e', 'Passed'),
        'viewed': ('#2196f3', 'Viewed'),
        'pending': ('#ff9800', 'Pending'),
        'approved': ('#4caf50', 'Approved'),
        'rejected': ('#f44336', 'Rejected'),
    }
    return status_map.get(status.lower(), ('#9e9e9e', status.capitalize()))


def format_user_id(user_id: str, short: bool = True) -> str:
    """Format user ID for display."""
    if not user_id:
        return "N/A"
    if short and len(user_id) > 8:
        return f"{user_id[:8]}..."
    return user_id


def format_delta(current: float, previous: float) -> tuple:
    """
    Calculate and format delta between two values.
    Returns (delta_value, delta_string, is_positive).
    """
    if previous == 0:
        return 0, "N/A", True

    delta = ((current - previous) / previous) * 100
    delta_str = f"{delta:+.1f}%"
    is_positive = delta >= 0

    return delta, delta_str, is_positive
