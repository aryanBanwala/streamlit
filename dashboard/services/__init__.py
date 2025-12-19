"""
Services layer for data fetching and business logic.
"""
from .supabase import get_supabase_client, supabase
from .users import UserService
from .matches import MatchService
from .analytics import AnalyticsService

__all__ = [
    'get_supabase_client',
    'supabase',
    'UserService',
    'MatchService',
    'AnalyticsService',
]
