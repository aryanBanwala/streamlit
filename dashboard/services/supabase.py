"""
Supabase client initialization and connection management.
"""
import os
from pathlib import Path
from dotenv import load_dotenv
import streamlit as st
from supabase import create_client, Client

# Load environment variables directly here to ensure they're available
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)

# Get credentials (prod - default)
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

# Actual-test DB credentials
SUPABASE_URL_ACTUAL_TEST = os.getenv('SUPABASE_URL_ACTUAL_TEST')
SUPABASE_KEY_ACTUAL_TEST = os.getenv('SUPABASE_KEY_ACTUAL_TEST')

# Pagination constants
READ_PAGE_SIZE = 500
WRITE_BATCH_SIZE = 20


@st.cache_resource
def get_supabase_client() -> Client:
    """Get cached Supabase client instance."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError(f"Supabase credentials not configured. URL={bool(SUPABASE_URL)}, KEY={bool(SUPABASE_KEY)}. Check .env at {env_path}")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


class _LazyClient:
    """Lazy-loaded Supabase client wrapper."""
    _client = None

    def __getattr__(self, name):
        if _LazyClient._client is None:
            _LazyClient._client = get_supabase_client()
        return getattr(_LazyClient._client, name)


supabase = _LazyClient()


def fetch_all(table: str, select: str = '*', filters: dict = None, order_by: str = None, desc: bool = False) -> list:
    """
    Fetch all records from a table with pagination (500 per page).

    Args:
        table: Table name
        select: Columns to select
        filters: Dict of {column: value} for eq filters
        order_by: Column to order by
        desc: Order descending if True

    Returns:
        List of all records
    """
    client = get_supabase_client()
    all_data = []
    offset = 0

    while True:
        query = client.table(table).select(select)

        # Apply filters
        if filters:
            for col, val in filters.items():
                query = query.eq(col, val)

        # Apply ordering
        if order_by:
            query = query.order(order_by, desc=desc)

        # Apply pagination
        query = query.range(offset, offset + READ_PAGE_SIZE - 1)

        response = query.execute()
        if not response.data:
            break

        all_data.extend(response.data)

        if len(response.data) < READ_PAGE_SIZE:
            break

        offset += READ_PAGE_SIZE

    return all_data


def fetch_with_filter(table: str, select: str, filter_col: str, filter_op: str, filter_val, order_by: str = None, desc: bool = False) -> list:
    """
    Fetch records with a comparison filter (gte, lte, gt, lt, eq, neq).

    Args:
        table: Table name
        select: Columns to select
        filter_col: Column to filter on
        filter_op: Operator (gte, lte, gt, lt, eq, neq)
        filter_val: Value to compare
        order_by: Column to order by
        desc: Order descending if True

    Returns:
        List of matching records
    """
    client = get_supabase_client()
    all_data = []
    offset = 0

    while True:
        query = client.table(table).select(select)

        # Apply filter
        if filter_op == 'gte':
            query = query.gte(filter_col, filter_val)
        elif filter_op == 'lte':
            query = query.lte(filter_col, filter_val)
        elif filter_op == 'gt':
            query = query.gt(filter_col, filter_val)
        elif filter_op == 'lt':
            query = query.lt(filter_col, filter_val)
        elif filter_op == 'eq':
            query = query.eq(filter_col, filter_val)
        elif filter_op == 'neq':
            query = query.neq(filter_col, filter_val)

        # Apply ordering
        if order_by:
            query = query.order(order_by, desc=desc)

        # Apply pagination
        query = query.range(offset, offset + READ_PAGE_SIZE - 1)

        response = query.execute()
        if not response.data:
            break

        all_data.extend(response.data)

        if len(response.data) < READ_PAGE_SIZE:
            break

        offset += READ_PAGE_SIZE

    return all_data


def fetch_paginated(query_builder, page_size: int = READ_PAGE_SIZE) -> list:
    """
    Fetch all records using pagination to bypass row limits.
    Use this when you have a custom query builder.
    """
    all_data = []
    offset = 0

    while True:
        response = query_builder.range(offset, offset + page_size - 1).execute()
        if not response.data:
            break
        all_data.extend(response.data)
        if len(response.data) < page_size:
            break
        offset += page_size

    return all_data


def batch_fetch(table: str, column: str, values: list, select: str = '*') -> list:
    """
    Batch fetch records by IN clause with pagination.
    """
    if not values:
        return []

    client = get_supabase_client()
    all_data = []

    # Process in batches of READ_PAGE_SIZE
    for i in range(0, len(values), READ_PAGE_SIZE):
        chunk = values[i:i + READ_PAGE_SIZE]
        response = client.table(table).select(select).in_(column, chunk).execute()
        if response.data:
            all_data.extend(response.data)

    return all_data


def batch_insert(table: str, records: list) -> bool:
    """
    Insert records in batches of WRITE_BATCH_SIZE (20).
    """
    if not records:
        return True

    client = get_supabase_client()

    for i in range(0, len(records), WRITE_BATCH_SIZE):
        chunk = records[i:i + WRITE_BATCH_SIZE]
        client.table(table).insert(chunk).execute()

    return True


@st.cache_resource
def get_actual_test_client() -> Client:
    """Get cached Supabase client for actual-test DB."""
    if not SUPABASE_URL_ACTUAL_TEST or not SUPABASE_KEY_ACTUAL_TEST:
        raise ValueError(
            f"Actual-test Supabase credentials not configured. "
            f"URL={bool(SUPABASE_URL_ACTUAL_TEST)}, KEY={bool(SUPABASE_KEY_ACTUAL_TEST)}. "
            f"Set SUPABASE_URL_ACTUAL_TEST and SUPABASE_KEY_ACTUAL_TEST in .env"
        )
    return create_client(SUPABASE_URL_ACTUAL_TEST, SUPABASE_KEY_ACTUAL_TEST)


def fetch_all_actual_test(table: str, select: str = '*', filters: dict = None, order_by: str = None, desc: bool = False) -> list:
    """
    Fetch all records from a table in the actual-test DB with pagination.
    Same interface as fetch_all but uses the actual-test client.
    """
    client = get_actual_test_client()
    all_data = []
    offset = 0

    while True:
        query = client.table(table).select(select)

        if filters:
            for col, val in filters.items():
                query = query.eq(col, val)

        if order_by:
            query = query.order(order_by, desc=desc)

        query = query.range(offset, offset + READ_PAGE_SIZE - 1)

        response = query.execute()
        if not response.data:
            break

        all_data.extend(response.data)

        if len(response.data) < READ_PAGE_SIZE:
            break

        offset += READ_PAGE_SIZE

    return all_data


def batch_update(table: str, records: list, id_column: str = 'id') -> bool:
    """
    Update records in batches of WRITE_BATCH_SIZE (20).
    Each record must have the id_column field.
    """
    if not records:
        return True

    client = get_supabase_client()

    for i in range(0, len(records), WRITE_BATCH_SIZE):
        chunk = records[i:i + WRITE_BATCH_SIZE]
        for record in chunk:
            record_id = record.pop(id_column)
            client.table(table).update(record).eq(id_column, record_id).execute()

    return True
