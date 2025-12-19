"""
Match-related data fetching and operations.
"""
import streamlit as st
from typing import Optional
from datetime import datetime, timedelta
from .supabase import supabase, fetch_paginated, batch_fetch
from config import CACHE_TTL_SHORT, CACHE_TTL_MEDIUM, STATUS_PENDING, STATUS_APPROVED


class MatchService:
    """Service for match-related operations."""

    @staticmethod
    @st.cache_data(ttl=CACHE_TTL_SHORT)
    def get_user_matches(user_id: str) -> tuple:
        """
        Fetch all matches for a user.
        Returns (outbound_matches, inbound_matches).
        """
        try:
            # Outbound: user as current_user
            outbound = supabase.table('user_matches').select(
                'match_id, matched_user_id, is_liked, is_viewed, is_mutual, mutual_score, '
                'viewer_scores_candidate, candidate_scores_viewer, rank, origin_phase, '
                'created_at, know_more_count'
            ).eq('current_user_id', user_id).order('created_at', desc=True).execute()

            # Inbound: user as matched_user
            inbound = supabase.table('user_matches').select(
                'match_id, current_user_id, is_liked, is_viewed, is_mutual, mutual_score, '
                'viewer_scores_candidate, candidate_scores_viewer, rank, origin_phase, '
                'created_at, know_more_count'
            ).eq('matched_user_id', user_id).order('created_at', desc=True).execute()

            return outbound.data or [], inbound.data or []
        except Exception:
            return [], []

    @staticmethod
    @st.cache_data(ttl=CACHE_TTL_MEDIUM)
    def get_matches_stats(
        run_id: Optional[str] = None,
        origin_phase: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> list:
        """Fetch matches with optional filters for stats."""
        try:
            query = supabase.table('user_matches').select(
                'match_id, current_user_id, matched_user_id, is_liked, is_viewed, '
                'is_mutual, mutual_score, know_more_count, origin_phase, created_at'
            )

            if run_id:
                query = query.eq('run_id', run_id)
            if origin_phase:
                query = query.eq('origin_phase', origin_phase)
            if start_date:
                query = query.gte('created_at', start_date)
            if end_date:
                query = query.lte('created_at', end_date)

            return fetch_paginated(query)
        except Exception:
            return []

    @staticmethod
    @st.cache_data(ttl=CACHE_TTL_MEDIUM)
    def get_filter_options() -> tuple:
        """Get distinct run_ids and origin_phases for filters."""
        try:
            run_data = fetch_paginated(supabase.table('user_matches').select('run_id'))
            run_ids = list(set(r['run_id'] for r in run_data if r.get('run_id')))

            phase_data = fetch_paginated(supabase.table('user_matches').select('origin_phase'))
            phases = list(set(p['origin_phase'] for p in phase_data if p.get('origin_phase')))

            return sorted(run_ids), sorted(phases)
        except Exception:
            return [], []

    @staticmethod
    @st.cache_data(ttl=CACHE_TTL_MEDIUM)
    def get_daily_stats(days: int = 30, run_id: Optional[str] = None, origin_phase: Optional[str] = None) -> list:
        """Fetch matches for time-series trends."""
        try:
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            query = supabase.table('user_matches').select(
                'created_at, is_liked, is_viewed, is_mutual'
            ).gte('created_at', start_date)

            if run_id:
                query = query.eq('run_id', run_id)
            if origin_phase:
                query = query.eq('origin_phase', origin_phase)

            return fetch_paginated(query)
        except Exception:
            return []

    @staticmethod
    @st.cache_data(ttl=CACHE_TTL_SHORT)
    def get_pending_profiles() -> list:
        """Fetch profiles awaiting human approval."""
        try:
            response = supabase.table('profiles').select('*').eq(
                'profile_status', STATUS_PENDING
            ).order('created_at', desc=True).execute()
            return response.data or []
        except Exception:
            return []

    @staticmethod
    @st.cache_data(ttl=CACHE_TTL_SHORT)
    def get_approved_profiles() -> list:
        """Fetch approved profiles not yet processed by Temporal."""
        try:
            response = supabase.table('profiles').select('*').eq(
                'profile_status', STATUS_APPROVED
            ).order('created_at', desc=True).execute()
            return response.data or []
        except Exception:
            return []

    @staticmethod
    def approve_profile(profiles_id: str) -> bool:
        """Approve a profile (move from pending to approved)."""
        try:
            supabase.table('profiles').update({
                'profile_status': STATUS_APPROVED
            }).eq('profiles_id', profiles_id).execute()
            st.cache_data.clear()
            return True
        except Exception:
            return False

    @staticmethod
    def undo_approval(profiles_id: str) -> bool:
        """Undo approval (move back to pending)."""
        try:
            supabase.table('profiles').update({
                'profile_status': STATUS_PENDING
            }).eq('profiles_id', profiles_id).execute()
            st.cache_data.clear()
            return True
        except Exception:
            return False

    @staticmethod
    @st.cache_data(ttl=CACHE_TTL_SHORT)
    def get_match_counts() -> dict:
        """Get match counts for dashboard overview."""
        try:
            pending = supabase.table('profiles').select('profiles_id', count='exact').eq(
                'profile_status', STATUS_PENDING
            ).execute()

            approved = supabase.table('profiles').select('profiles_id', count='exact').eq(
                'profile_status', STATUS_APPROVED
            ).execute()

            return {
                'pending': pending.count or 0,
                'approved': approved.count or 0,
            }
        except Exception:
            return {'pending': 0, 'approved': 0}
