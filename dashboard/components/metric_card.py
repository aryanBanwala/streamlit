"""
Metric card components for displaying KPIs and statistics.
"""
import streamlit as st
from typing import Optional, Union


def metric_card(
    label: str,
    value: Union[int, float, str],
    delta: Optional[Union[int, float, str]] = None,
    delta_color: str = "normal",
    help_text: Optional[str] = None,
    prefix: str = "",
    suffix: str = "",
    format_value: bool = True
) -> None:
    """
    Display a styled metric card.

    Args:
        label: Metric label/title
        value: Main metric value
        delta: Change value (optional)
        delta_color: Color for delta ("normal", "inverse", "off")
        help_text: Tooltip text (optional)
        prefix: Prefix for value (e.g., "$")
        suffix: Suffix for value (e.g., "%")
        format_value: Whether to format numbers with commas
    """
    # Format value
    if format_value and isinstance(value, (int, float)):
        if isinstance(value, float):
            display_value = f"{prefix}{value:,.2f}{suffix}"
        else:
            display_value = f"{prefix}{value:,}{suffix}"
    else:
        display_value = f"{prefix}{value}{suffix}"

    # Format delta
    if delta is not None:
        if isinstance(delta, (int, float)):
            if isinstance(delta, float):
                delta_str = f"{delta:+.1f}%"
            else:
                delta_str = f"{delta:+,}"
        else:
            delta_str = str(delta)
    else:
        delta_str = None

    st.metric(
        label=label,
        value=display_value,
        delta=delta_str,
        delta_color=delta_color,
        help=help_text
    )


def metric_row(
    metrics: list,
    columns: Optional[int] = None
) -> None:
    """
    Display multiple metrics in a row.

    Args:
        metrics: List of dicts with metric_card parameters
        columns: Number of columns (defaults to len(metrics))
    """
    num_cols = columns or len(metrics)
    cols = st.columns(num_cols)

    for idx, metric in enumerate(metrics):
        with cols[idx % num_cols]:
            metric_card(**metric)


def stats_table(
    data: dict,
    title: Optional[str] = None,
    columns: list = None
) -> None:
    """
    Display stats in a table format.

    Args:
        data: Dict with {metric_name: {col1: val1, col2: val2}}
        title: Optional section title
        columns: Column headers
    """
    if title:
        st.markdown(f"### {title}")

    if not columns:
        columns = list(next(iter(data.values())).keys()) if data else []

    # Header row
    header_cols = st.columns([1.5] + [1] * len(columns))
    with header_cols[0]:
        st.markdown("**Metric**")
    for idx, col in enumerate(columns):
        with header_cols[idx + 1]:
            st.markdown(f"**{col}**")

    # Data rows
    for metric_name, values in data.items():
        row_cols = st.columns([1.5] + [1] * len(columns))
        with row_cols[0]:
            st.markdown(metric_name)
        for idx, col in enumerate(columns):
            with row_cols[idx + 1]:
                val = values.get(col, 'N/A')
                if isinstance(val, (int, float)):
                    if isinstance(val, float):
                        st.markdown(f"{val:,.2f}")
                    else:
                        st.markdown(f"{val:,}")
                else:
                    st.markdown(str(val))
