"""
Analytics-related data fetching for dashboards.
"""
import streamlit as st
from typing import Optional
from datetime import datetime, timedelta
from collections import defaultdict
from .supabase import supabase, fetch_all, fetch_with_filter, batch_fetch, get_supabase_client
from config import CACHE_TTL_SHORT, CACHE_TTL_MEDIUM

# 30 minute TTL for growth dashboard (1800 seconds)
CACHE_TTL_GROWTH = 1800


# ============================================================================
# GROWTH DASHBOARD - Single cached function for all dashboard data
# ============================================================================

@st.cache_data(ttl=CACHE_TTL_GROWTH)
def get_growth_dashboard_data() -> dict:
    """
    Fetch ALL data needed for growth dashboard in a single cached call.
    This runs ONCE every 30 minutes, shared across ALL users.

    Returns:
        dict with all growth metrics, pre-processed for display
    """
    try:
        # 1. Fetch signups from user_data (this is where users first sign up)
        signups = fetch_all('user_data', 'user_id, gender, created_at')

        # 2. Fetch onboarded users from user_metadata (users who completed onboarding)
        onboarded_users = fetch_all('user_metadata', 'user_id, gender, city, created_at')

        # 3. Fetch all match data with pagination (500 per page)
        matches = fetch_all('user_matches', 'match_id, is_liked, is_mutual, created_at')

        # 4. Process signup data (from user_data) - total only, no gender split
        total_signups = len(signups)
        signups_by_date = defaultdict(int)

        for signup in signups:
            created_at = signup.get('created_at')
            if created_at:
                date_str = created_at[:10]  # YYYY-MM-DD
                signups_by_date[date_str] += 1

        # 5. Process onboarded user data (from user_metadata)
        total_onboarded = len(onboarded_users)
        onboarded_by_gender = defaultdict(int)
        onboarded_by_date = defaultdict(lambda: {'male': 0, 'female': 0, 'total': 0})
        cities = defaultdict(int)

        for user in onboarded_users:
            gender = user.get('gender', 'unknown')
            onboarded_by_gender[gender] += 1

            city = user.get('city')
            if city:
                cities[city] += 1

            # Onboarded by date with gender split
            created_at = user.get('created_at')
            if created_at:
                date_str = created_at[:10]  # YYYY-MM-DD
                onboarded_by_date[date_str]['total'] += 1
                if gender in ['male', 'female']:
                    onboarded_by_date[date_str][gender] += 1

        # 6. Process match data
        total_matches = len(matches)
        mutual_matches = sum(1 for m in matches if m.get('is_mutual'))
        liked_count = sum(1 for m in matches if m.get('is_liked') == 'liked')
        like_rate = (liked_count / total_matches * 100) if total_matches > 0 else 0

        # 7. Calculate period metrics (for delta comparisons) - based on signups from user_data
        today = datetime.now()
        periods = {
            '7d': 7,
            '14d': 14,
            '30d': 30,
        }

        period_signups = {}
        for period_name, days in periods.items():
            start_date = (today - timedelta(days=days)).strftime('%Y-%m-%d')
            prev_start = (today - timedelta(days=days * 2)).strftime('%Y-%m-%d')

            current = sum(
                1 for s in signups
                if s.get('created_at') and s['created_at'][:10] >= start_date
            )
            previous = sum(
                1 for s in signups
                if s.get('created_at') and prev_start <= s['created_at'][:10] < start_date
            )

            growth = ((current - previous) / previous * 100) if previous > 0 else 0

            period_signups[period_name] = {
                'current': current,
                'previous': previous,
                'growth': growth,
            }

        return {
            # Signup metrics (from user_data) - total only
            'total_signups': total_signups,
            'signups_by_date': dict(signups_by_date),

            # Onboarded user metrics (from user_metadata)
            'total_onboarded': total_onboarded,
            'onboarded_by_gender': dict(onboarded_by_gender),
            'onboarded_by_date': dict(onboarded_by_date),
            'cities': dict(cities),

            # Match metrics
            'total_matches': total_matches,
            'mutual_matches': mutual_matches,
            'like_rate': like_rate,

            # Period comparisons (based on signups)
            'period_signups': period_signups,

            # Cache metadata
            'cached_at': datetime.now().isoformat(),
        }

    except Exception as e:
        return {
            'total_signups': 0,
            'signups_by_date': {},
            'total_onboarded': 0,
            'onboarded_by_gender': {},
            'onboarded_by_date': {},
            'cities': {},
            'total_matches': 0,
            'mutual_matches': 0,
            'like_rate': 0,
            'period_signups': {},
            'cached_at': datetime.now().isoformat(),
            'error': str(e),
        }


def get_filtered_signups(data: dict, days: int) -> list:
    """
    Filter signup data by number of days (in-memory, no DB call).
    Signups are from user_data - total count only, no gender split.

    Args:
        data: Growth dashboard data from get_growth_dashboard_data()
        days: Number of days to include (None for all)

    Returns:
        List of dicts with date and total for charting
    """
    signups_by_date = data.get('signups_by_date', {})

    if days:
        cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        filtered = {k: v for k, v in signups_by_date.items() if k >= cutoff}
    else:
        filtered = signups_by_date

    # Convert to sorted list for charting
    result = []
    for date_str in sorted(filtered.keys()):
        result.append({
            'date': date_str,
            'total': filtered[date_str] if isinstance(filtered[date_str], int) else filtered[date_str].get('total', 0),
        })

    return result


def get_filtered_onboarded(data: dict, days: int) -> list:
    """
    Filter onboarded user data by number of days (in-memory, no DB call).
    Onboarded users are from user_metadata - with gender split.

    Args:
        data: Growth dashboard data from get_growth_dashboard_data()
        days: Number of days to include (None for all)

    Returns:
        List of dicts with date, male, female, total for charting
    """
    onboarded_by_date = data.get('onboarded_by_date', {})

    if days:
        cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        filtered = {k: v for k, v in onboarded_by_date.items() if k >= cutoff}
    else:
        filtered = onboarded_by_date

    # Convert to sorted list for charting
    result = []
    for date_str in sorted(filtered.keys()):
        result.append({
            'date': date_str,
            'male': filtered[date_str].get('male', 0),
            'female': filtered[date_str].get('female', 0),
            'total': filtered[date_str].get('total', 0),
        })

    return result


def get_top_cities(data: dict, n: int = 10) -> list:
    """
    Get top N cities by user count (in-memory, no DB call).

    Args:
        data: Growth dashboard data from get_growth_dashboard_data()
        n: Number of top cities to return

    Returns:
        List of dicts with city and count, sorted descending
    """
    cities = data.get('cities', {})
    sorted_cities = sorted(cities.items(), key=lambda x: x[1], reverse=True)[:n]
    return [{'city': city, 'count': count} for city, count in sorted_cities]


# ============================================================================
# DEMOGRAPHICS - Cached function for demographics page
# ============================================================================

@st.cache_data(ttl=CACHE_TTL_MEDIUM)
def get_demographics_data() -> dict:
    """
    Fetch ALL demographics data in a single cached call.
    Filter by gender is done in-memory after fetch.
    """
    try:
        data = fetch_all('user_metadata', 'gender, age, city, religion, professional_tier')

        # Process gender counts
        gender_counts = {}
        for user in data:
            gender = user.get('gender', 'unknown')
            gender_counts[gender] = gender_counts.get(gender, 0) + 1

        # Process age groups
        age_groups = {}
        for user in data:
            age = user.get('age')
            if age:
                if age < 25:
                    group = '18-24'
                elif age < 30:
                    group = '25-29'
                elif age < 35:
                    group = '30-34'
                elif age < 40:
                    group = '35-39'
                else:
                    group = '40+'
                age_groups[group] = age_groups.get(group, 0) + 1

        # Process cities
        city_counts = {}
        for user in data:
            city = user.get('city')
            if city:
                city_counts[city] = city_counts.get(city, 0) + 1

        # Process religions
        religion_counts = {}
        for user in data:
            religion = user.get('religion')
            if religion:
                religion_counts[religion] = religion_counts.get(religion, 0) + 1

        # Process professional tiers
        tier_counts = {}
        for user in data:
            tier = user.get('professional_tier')
            if tier is not None and isinstance(tier, int):
                if tier < 0:
                    tier_str = "Unassigned"
                else:
                    tier_str = f"Tier {tier}"
                tier_counts[tier_str] = tier_counts.get(tier_str, 0) + 1

        return {
            'raw_data': data,  # For filtering
            'total': len(data),
            'gender': gender_counts,
            'age_groups': age_groups,
            'cities': city_counts,
            'religions': religion_counts,
            'professional_tiers': tier_counts,
            'cached_at': datetime.now().isoformat(),
        }

    except Exception as e:
        return {
            'raw_data': [],
            'total': 0,
            'gender': {},
            'age_groups': {},
            'cities': {},
            'religions': {},
            'professional_tiers': {},
            'cached_at': datetime.now().isoformat(),
            'error': str(e),
        }


def filter_demographics_by_gender(data: dict, gender_filter: str) -> dict:
    """
    Filter demographics data by gender (in-memory, no DB call).

    Args:
        data: Demographics data from get_demographics_data()
        gender_filter: 'all', 'male', or 'female'

    Returns:
        Filtered demographics dict
    """
    if gender_filter == 'all':
        return data

    raw_data = data.get('raw_data', [])
    filtered = [u for u in raw_data if u.get('gender') == gender_filter]

    # Reprocess all breakdowns
    age_groups = {}
    city_counts = {}
    religion_counts = {}
    tier_counts = {}

    for user in filtered:
        # Age groups
        age = user.get('age')
        if age:
            if age < 25:
                group = '18-24'
            elif age < 30:
                group = '25-29'
            elif age < 35:
                group = '30-34'
            elif age < 40:
                group = '35-39'
            else:
                group = '40+'
            age_groups[group] = age_groups.get(group, 0) + 1

        # Cities
        city = user.get('city')
        if city:
            city_counts[city] = city_counts.get(city, 0) + 1

        # Religions
        religion = user.get('religion')
        if religion:
            religion_counts[religion] = religion_counts.get(religion, 0) + 1

        # Professional tiers
        tier = user.get('professional_tier')
        if tier is not None and isinstance(tier, int):
            if tier < 0:
                tier_str = "Unassigned"
            else:
                tier_str = f"Tier {tier}"
            tier_counts[tier_str] = tier_counts.get(tier_str, 0) + 1

    return {
        'total': len(filtered),
        'gender': {gender_filter: len(filtered)},
        'age_groups': age_groups,
        'cities': city_counts,
        'religions': religion_counts,
        'professional_tiers': tier_counts,
    }


class AnalyticsService:
    """Service for analytics and metrics."""

    @staticmethod
    @st.cache_data(ttl=CACHE_TTL_SHORT)
    def get_signup_stats(days: int = 30) -> list:
        """Get user signups over time with pagination."""
        try:
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            return fetch_with_filter(
                'user_metadata',
                'created_at, gender',
                'created_at', 'gte', start_date
            )
        except Exception:
            return []

    @staticmethod
    @st.cache_data(ttl=CACHE_TTL_MEDIUM)
    def get_demographics() -> dict:
        """Get user demographic breakdown with pagination."""
        try:
            data = fetch_all('user_metadata', 'gender, age, city, religion, professional_tier')

            # Process demographics
            demographics = {
                'gender': {},
                'age_groups': {},
                'cities': {},
                'religions': {},
                'professional_tiers': {},
            }

            for user in data:
                # Gender
                gender = user.get('gender', 'unknown')
                demographics['gender'][gender] = demographics['gender'].get(gender, 0) + 1

                # Age groups
                age = user.get('age')
                if age:
                    if age < 25:
                        group = '18-24'
                    elif age < 30:
                        group = '25-29'
                    elif age < 35:
                        group = '30-34'
                    elif age < 40:
                        group = '35-39'
                    else:
                        group = '40+'
                    demographics['age_groups'][group] = demographics['age_groups'].get(group, 0) + 1

                # Cities
                city = user.get('city', 'Unknown')
                if city:
                    demographics['cities'][city] = demographics['cities'].get(city, 0) + 1

                # Religion
                religion = user.get('religion', 'Unknown')
                if religion:
                    demographics['religions'][religion] = demographics['religions'].get(religion, 0) + 1

                # Professional tier
                tier = user.get('professional_tier', 'Unknown')
                if tier:
                    demographics['professional_tiers'][str(tier)] = demographics['professional_tiers'].get(str(tier), 0) + 1

            return demographics
        except Exception:
            return {
                'gender': {},
                'age_groups': {},
                'cities': {},
                'religions': {},
                'professional_tiers': {},
            }

    @staticmethod
    @st.cache_data(ttl=CACHE_TTL_SHORT)
    def get_onboarding_stats() -> dict:
        """Get onboarding funnel stats with pagination."""
        try:
            # Get users with completed onboarding (have profile_images)
            data = fetch_all('user_metadata', 'user_id, profile_images, collage_images, gender')

            total = len(data)
            with_photos = sum(1 for u in data if u.get('profile_images'))
            with_collage = sum(1 for u in data if u.get('collage_images'))

            return {
                'total_users': total,
                'with_photos': with_photos,
                'with_collage': with_collage,
                'photo_rate': (with_photos / total * 100) if total > 0 else 0,
                'collage_rate': (with_collage / total * 100) if total > 0 else 0,
            }
        except Exception:
            return {
                'total_users': 0,
                'with_photos': 0,
                'with_collage': 0,
                'photo_rate': 0,
                'collage_rate': 0,
            }

    @staticmethod
    @st.cache_data(ttl=CACHE_TTL_SHORT)
    def get_chat_sessions(user_id: str, chat_type: str) -> tuple:
        """Get chat sessions and messages for a user with pagination."""
        try:
            sessions = fetch_all(
                'chat_sessions', '*',
                filters={'user_id': user_id, 'chat_type': chat_type},
                order_by='created_at', desc=True
            )

            messages = []
            if sessions:
                session_ids = [s['id'] for s in sessions]
                messages = batch_fetch('chat_messages', 'session_id', session_ids, '*')
                # Sort messages by created_at
                messages = sorted(messages, key=lambda m: m.get('created_at', ''))

            return sessions, messages
        except Exception:
            return [], []

    @staticmethod
    @st.cache_data(ttl=CACHE_TTL_MEDIUM)
    def get_users_with_chat_type(chat_type: str, after_date: Optional[str] = None) -> list:
        """Get user IDs that have sessions of the given chat type with pagination."""
        try:
            if after_date:
                # Use fetch_with_filter for date filter, then filter chat_type in memory
                data = fetch_with_filter(
                    'chat_sessions', 'user_id, chat_type',
                    'created_at', 'gte', after_date
                )
                data = [s for s in data if s.get('chat_type') == chat_type]
            else:
                data = fetch_all('chat_sessions', 'user_id', filters={'chat_type': chat_type})

            if data:
                return list(set(s['user_id'] for s in data))
            return []
        except Exception:
            return []

    @staticmethod
    @st.cache_data(ttl=CACHE_TTL_SHORT)
    def get_growth_metrics(days: int = 7) -> dict:
        """Get growth metrics for the dashboard with pagination."""
        try:
            today = datetime.now()
            start_date = (today - timedelta(days=days)).strftime('%Y-%m-%d')
            prev_start = (today - timedelta(days=days * 2)).strftime('%Y-%m-%d')

            # Fetch all users with created_at for counting
            all_users = fetch_all('user_metadata', 'user_id, created_at')

            # Count current period signups
            current_count = sum(
                1 for u in all_users
                if u.get('created_at') and u['created_at'][:10] >= start_date
            )

            # Count previous period signups
            previous_count = sum(
                1 for u in all_users
                if u.get('created_at') and prev_start <= u['created_at'][:10] < start_date
            )

            growth = ((current_count - previous_count) / previous_count * 100) if previous_count > 0 else 0

            return {
                'current_signups': current_count,
                'previous_signups': previous_count,
                'growth_rate': growth,
            }
        except Exception:
            return {
                'current_signups': 0,
                'previous_signups': 0,
                'growth_rate': 0,
            }
