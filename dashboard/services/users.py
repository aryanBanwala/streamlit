"""
User-related data fetching and operations.
"""
import streamlit as st
from typing import Optional
from .supabase import supabase, batch_fetch
from config import CACHE_TTL_MEDIUM, CACHE_TTL_SHORT, STORAGE_BUCKET


class UserService:
    """Service for user-related operations."""

    @staticmethod
    @st.cache_data(ttl=CACHE_TTL_MEDIUM)
    def get_user_by_id(user_id: str) -> Optional[dict]:
        """Fetch complete user profile by ID."""
        try:
            response = supabase.table('user_metadata').select(
                'user_id, name, age, gender, city, area, height, religion, '
                'education, work_exp, phone_num, profile_images, collage_images, '
                'instagram_images, attractiveness, professional_tier, dating_preferences, '
                'shouldBeRemoved, hasAppropriatePhotos, created_at'
            ).eq('user_id', user_id).maybe_single().execute()
            return response.data
        except Exception as e:
            return None

    @staticmethod
    @st.cache_data(ttl=CACHE_TTL_MEDIUM)
    def get_user_contact(user_id: str) -> dict:
        """Fetch user contact info (email, phone) from user_data table."""
        try:
            response = supabase.table('user_data').select(
                'user_email, user_phone'
            ).eq('user_id', user_id).maybe_single().execute()
            return response.data or {}
        except Exception:
            return {}

    @staticmethod
    @st.cache_data(ttl=CACHE_TTL_MEDIUM)
    def get_users_batch(user_ids: tuple) -> dict:
        """Fetch multiple user profiles as a dict keyed by user_id."""
        if not user_ids:
            return {}

        data = batch_fetch(
            table='user_metadata',
            column='user_id',
            values=list(user_ids),
            select='user_id, name, age, gender, city, profile_images, instagram_images, '
                   'attractiveness, professional_tier'
        )
        return {u['user_id']: u for u in data}

    @staticmethod
    @st.cache_data(ttl=CACHE_TTL_MEDIUM)
    def get_user_genders(user_ids: tuple) -> dict:
        """Fetch gender for multiple users as a dict."""
        if not user_ids:
            return {}

        data = batch_fetch(
            table='user_metadata',
            column='user_id',
            values=list(user_ids),
            select='user_id, gender'
        )
        return {u['user_id']: u.get('gender') for u in data}

    @staticmethod
    @st.cache_data(ttl=CACHE_TTL_MEDIUM)
    def get_user_contacts_batch(user_ids: tuple) -> tuple:
        """Fetch emails and phones for multiple users. Returns (email_map, phone_map)."""
        if not user_ids:
            return {}, {}

        data = batch_fetch(
            table='user_data',
            column='user_id',
            values=list(user_ids),
            select='user_id, user_email, user_phone'
        )

        email_map = {u['user_id']: u.get('user_email') for u in data}
        phone_map = {u['user_id']: u.get('user_phone') for u in data}
        return email_map, phone_map

    @staticmethod
    @st.cache_data(ttl=CACHE_TTL_SHORT)
    def get_total_users() -> dict:
        """Get total user counts by gender."""
        try:
            response = supabase.table('user_metadata').select('gender').execute()
            data = response.data or []

            total = len(data)
            males = sum(1 for u in data if u.get('gender') == 'male')
            females = sum(1 for u in data if u.get('gender') == 'female')

            return {'total': total, 'males': males, 'females': females}
        except Exception:
            return {'total': 0, 'males': 0, 'females': 0}

    @staticmethod
    @st.cache_data(ttl=CACHE_TTL_SHORT)
    def search_users(query: str, gender: Optional[str] = None, limit: int = 50) -> list:
        """Search users by name or email."""
        try:
            # Search in user_metadata by name
            metadata_query = supabase.table('user_metadata').select(
                'user_id, name, gender, age, city'
            ).ilike('name', f'%{query}%').limit(limit)

            if gender and gender != 'all':
                metadata_query = metadata_query.eq('gender', gender)

            response = metadata_query.execute()
            return response.data or []
        except Exception:
            return []

    @staticmethod
    def update_user_images(user_id: str, profile_images: list = None, collage_images: list = None) -> bool:
        """Update user profile or collage images."""
        try:
            update_data = {}
            if profile_images is not None:
                update_data['profile_images'] = profile_images
            if collage_images is not None:
                update_data['collage_images'] = collage_images
                update_data['collage_creation_status'] = None
                update_data['collage_creation_message'] = None

            if update_data:
                supabase.table('user_metadata').update(update_data).eq('user_id', user_id).execute()
            return True
        except Exception:
            return False

    @staticmethod
    def upload_image(file_bytes: bytes, file_path: str, content_type: str = "image/jpeg") -> Optional[str]:
        """Upload image to storage and return public URL."""
        try:
            supabase.storage.from_(STORAGE_BUCKET).upload(
                path=file_path,
                file=file_bytes,
                file_options={"content-type": content_type}
            )
            return supabase.storage.from_(STORAGE_BUCKET).get_public_url(file_path)
        except Exception:
            return None

    @staticmethod
    def delete_image(url: str) -> bool:
        """Delete image from storage."""
        try:
            parts = url.split('/chat-images/')
            if len(parts) > 1:
                path = parts[1]
                supabase.storage.from_(STORAGE_BUCKET).remove([path])
                return True
            return False
        except Exception:
            return False
