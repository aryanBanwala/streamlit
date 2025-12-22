"""
Dashboard Configuration
Central configuration for the Lambda Admin Dashboard.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from parent directory
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# Environment
ENVIRONMENT = os.getenv('ENVIRONMENT', 'preprod')
IS_PROD = ENVIRONMENT == 'prod'

# Supabase Configuration
SUPABASE_URL = os.getenv('SUPABASE_URL_PROD' if IS_PROD else 'SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY_PROD' if IS_PROD else 'SUPABASE_SERVICE_ROLE_KEY')

# Storage
STORAGE_BUCKET = "chat-images"

# Cache TTL (seconds)
CACHE_TTL_SHORT = 60      # 1 minute - for frequently changing data
CACHE_TTL_MEDIUM = 300    # 5 minutes - for semi-static data
CACHE_TTL_LONG = 3600     # 1 hour - for static data

# Pagination defaults
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# Date formats
DATE_FORMAT = '%Y-%m-%d'
DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'

# Profile status constants
STATUS_PENDING = 'female_null-male_null-msg_human_approval_required'
STATUS_APPROVED = 'female_null-male_null-msg_human_approved'

# Colors for UI
COLORS = {
    'primary': '#1976d2',
    'success': '#4caf50',
    'warning': '#ff9800',
    'error': '#f44336',
    'male': '#1976d2',
    'female': '#e91e63',
    'neutral': '#9e9e9e',
}
