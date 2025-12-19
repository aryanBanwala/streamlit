"""
Analytics-related data fetching for dashboards.
"""
import streamlit as st
from typing import Optional
from datetime import datetime, timedelta
from .supabase import supabase, fetch_paginated
from config import CACHE_TTL_SHORT, CACHE_TTL_MEDIUM


class AnalyticsService:
    """Service for analytics and metrics."""

    @staticmethod
    @st.cache_data(ttl=CACHE_TTL_SHORT)
    def get_signup_stats(days: int = 30) -> list:
        """Get user signups over time."""
        try:
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            response = supabase.table('user_metadata').select(
                'created_at, gender'
            ).gte('created_at', start_date).execute()
            return response.data or []
        except Exception:
            return []

    @staticmethod
    @st.cache_data(ttl=CACHE_TTL_MEDIUM)
    def get_demographics() -> dict:
        """Get user demographic breakdown."""
        try:
            response = supabase.table('user_metadata').select(
                'gender, age, city, religion, professional_tier'
            ).execute()
            data = response.data or []

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
        """Get onboarding funnel stats."""
        try:
            # Get users with completed onboarding (have profile_images)
            response = supabase.table('user_metadata').select(
                'user_id, profile_images, collage_images, gender'
            ).execute()
            data = response.data or []

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
        """Get chat sessions and messages for a user."""
        try:
            sessions = supabase.table('chat_sessions').select('*').eq(
                'user_id', user_id
            ).eq('chat_type', chat_type).order('created_at', desc=True).execute()

            messages = []
            if sessions.data:
                session_ids = [s['id'] for s in sessions.data]
                messages_response = supabase.table('chat_messages').select('*').in_(
                    'session_id', session_ids
                ).order('created_at', desc=False).execute()
                messages = messages_response.data or []

            return sessions.data or [], messages
        except Exception:
            return [], []

    @staticmethod
    @st.cache_data(ttl=CACHE_TTL_MEDIUM)
    def get_users_with_chat_type(chat_type: str, after_date: Optional[str] = None) -> list:
        """Get user IDs that have sessions of the given chat type."""
        try:
            query = supabase.table('chat_sessions').select('user_id').eq('chat_type', chat_type)
            if after_date:
                query = query.gte('created_at', after_date)
            response = query.execute()
            if response.data:
                return list(set(s['user_id'] for s in response.data))
            return []
        except Exception:
            return []

    @staticmethod
    @st.cache_data(ttl=CACHE_TTL_SHORT)
    def get_growth_metrics(days: int = 7) -> dict:
        """Get growth metrics for the dashboard."""
        try:
            today = datetime.now()
            start_date = (today - timedelta(days=days)).strftime('%Y-%m-%d')
            prev_start = (today - timedelta(days=days * 2)).strftime('%Y-%m-%d')

            # Current period signups
            current = supabase.table('user_metadata').select(
                'user_id', count='exact'
            ).gte('created_at', start_date).execute()

            # Previous period signups (for comparison)
            previous = supabase.table('user_metadata').select(
                'user_id', count='exact'
            ).gte('created_at', prev_start).lt('created_at', start_date).execute()

            current_count = current.count or 0
            previous_count = previous.count or 0

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
