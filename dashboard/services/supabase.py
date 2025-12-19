"""
Supabase client initialization and connection management.
"""
import streamlit as st
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY


@st.cache_resource
def get_supabase_client() -> Client:
    """Get cached Supabase client instance."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Supabase credentials not configured. Check your .env file.")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


# Global client instance
supabase = get_supabase_client()


def fetch_paginated(query_builder, page_size: int = 1000) -> list:
    """
    Fetch all records using pagination to bypass row limits.

    Args:
        query_builder: Supabase query builder instance
        page_size: Number of records per page (default 1000)

    Returns:
        List of all records
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


def batch_fetch(table: str, column: str, values: list, select: str = '*', batch_size: int = 500) -> list:
    """
    Batch fetch records to avoid query limits.

    Args:
        table: Table name
        column: Column to filter on
        values: List of values to match
        select: Columns to select
        batch_size: Number of values per batch

    Returns:
        List of all matching records
    """
    if not values:
        return []

    all_data = []
    for i in range(0, len(values), batch_size):
        chunk = values[i:i + batch_size]
        response = supabase.table(table).select(select).in_(column, chunk).execute()
        if response.data:
            all_data.extend(response.data)

    return all_data
