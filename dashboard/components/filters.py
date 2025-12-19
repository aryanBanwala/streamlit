"""
Filter components for the dashboard.
"""
import streamlit as st
from datetime import datetime, timedelta
from typing import Optional, Tuple


def date_filter(
    label: str = "Date Range",
    default_days: int = 7,
    key_prefix: str = "",
    show_quick_selects: bool = True
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Date range filter with quick select options.

    Args:
        label: Filter label
        default_days: Default number of days to look back
        key_prefix: Unique key prefix
        show_quick_selects: Show quick select buttons

    Returns:
        Tuple of (start_date, end_date)
    """
    st.markdown(f"**{label}**")

    if show_quick_selects:
        quick_cols = st.columns(4)
        with quick_cols[0]:
            if st.button("7d", key=f"{key_prefix}_7d", use_container_width=True):
                st.session_state[f"{key_prefix}_days"] = 7
        with quick_cols[1]:
            if st.button("14d", key=f"{key_prefix}_14d", use_container_width=True):
                st.session_state[f"{key_prefix}_days"] = 14
        with quick_cols[2]:
            if st.button("30d", key=f"{key_prefix}_30d", use_container_width=True):
                st.session_state[f"{key_prefix}_days"] = 30
        with quick_cols[3]:
            if st.button("All", key=f"{key_prefix}_all", use_container_width=True):
                st.session_state[f"{key_prefix}_days"] = None

    days = st.session_state.get(f"{key_prefix}_days", default_days)

    if days:
        start_date = datetime.now() - timedelta(days=days)
        end_date = datetime.now()
    else:
        start_date = None
        end_date = None

    # Custom date inputs
    date_cols = st.columns(2)
    with date_cols[0]:
        custom_start = st.date_input(
            "Start",
            value=start_date.date() if start_date else None,
            key=f"{key_prefix}_start"
        )
    with date_cols[1]:
        custom_end = st.date_input(
            "End",
            value=end_date.date() if end_date else datetime.now().date(),
            key=f"{key_prefix}_end"
        )

    if custom_start:
        start_date = datetime.combine(custom_start, datetime.min.time())
    if custom_end:
        end_date = datetime.combine(custom_end, datetime.max.time())

    return start_date, end_date


def gender_filter(
    key: str = "gender_filter",
    include_all: bool = True,
    horizontal: bool = True
) -> Optional[str]:
    """
    Gender filter dropdown or radio.

    Args:
        key: Unique key for the widget
        include_all: Whether to include "All" option
        horizontal: Use horizontal radio buttons

    Returns:
        Selected gender or None for "All"
    """
    options = ["All", "Male", "Female"] if include_all else ["Male", "Female"]

    if horizontal:
        selected = st.radio(
            "Gender",
            options=options,
            key=key,
            horizontal=True,
            label_visibility="collapsed"
        )
    else:
        selected = st.selectbox(
            "Gender",
            options=options,
            key=key
        )

    if selected == "All":
        return None
    return selected.lower()


def pagination_controls(
    total_items: int,
    page_size: int = 20,
    key_prefix: str = "pagination"
) -> Tuple[int, int, int]:
    """
    Pagination controls.

    Args:
        total_items: Total number of items
        page_size: Items per page
        key_prefix: Unique key prefix

    Returns:
        Tuple of (current_page, start_index, end_index)
    """
    total_pages = max(1, (total_items + page_size - 1) // page_size)

    # Initialize session state
    if f"{key_prefix}_page" not in st.session_state:
        st.session_state[f"{key_prefix}_page"] = 1

    current_page = st.session_state[f"{key_prefix}_page"]

    # Ensure page is in valid range
    if current_page > total_pages:
        current_page = total_pages
        st.session_state[f"{key_prefix}_page"] = current_page

    # Controls
    col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 1, 1])

    with col1:
        if st.button("<<", key=f"{key_prefix}_first", disabled=current_page == 1):
            st.session_state[f"{key_prefix}_page"] = 1
            st.rerun()

    with col2:
        if st.button("<", key=f"{key_prefix}_prev", disabled=current_page == 1):
            st.session_state[f"{key_prefix}_page"] = current_page - 1
            st.rerun()

    with col3:
        st.markdown(f"<center>Page {current_page} of {total_pages}</center>", unsafe_allow_html=True)

    with col4:
        if st.button(">", key=f"{key_prefix}_next", disabled=current_page == total_pages):
            st.session_state[f"{key_prefix}_page"] = current_page + 1
            st.rerun()

    with col5:
        if st.button(">>", key=f"{key_prefix}_last", disabled=current_page == total_pages):
            st.session_state[f"{key_prefix}_page"] = total_pages
            st.rerun()

    # Calculate indices
    start_idx = (current_page - 1) * page_size
    end_idx = min(start_idx + page_size, total_items)

    st.caption(f"Showing {start_idx + 1} - {end_idx} of {total_items}")

    return current_page, start_idx, end_idx


def search_box(
    placeholder: str = "Search...",
    key: str = "search",
    on_search: callable = None
) -> str:
    """
    Search input box.

    Args:
        placeholder: Placeholder text
        key: Unique key
        on_search: Callback function when search is submitted

    Returns:
        Search query string
    """
    col1, col2 = st.columns([4, 1])

    with col1:
        query = st.text_input(
            "Search",
            key=key,
            placeholder=placeholder,
            label_visibility="collapsed"
        )

    with col2:
        if st.button("Search", key=f"{key}_btn", type="primary", use_container_width=True):
            if on_search and query:
                on_search(query)

    return query
