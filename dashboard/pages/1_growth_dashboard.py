"""
Growth Dashboard - Main home page with key metrics, signup trends, and top cities.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# Import services
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.analytics import (
    get_growth_dashboard_data,
    get_filtered_signups,
    get_filtered_onboarded,
    get_top_cities,
)


# --- Helper Functions ---

def format_number(n: int) -> str:
    """Format number with commas."""
    return f"{n:,}"


def get_cache_age(cached_at: str) -> str:
    """Get human-readable cache age."""
    try:
        cached_time = datetime.fromisoformat(cached_at)
        age_seconds = (datetime.now() - cached_time).total_seconds()
        if age_seconds < 60:
            return "just now"
        elif age_seconds < 3600:
            return f"{int(age_seconds / 60)} min ago"
        else:
            return f"{int(age_seconds / 3600)} hr ago"
    except:
        return "unknown"


# --- Page Header ---

col_title, col_refresh = st.columns([4, 1])

with col_title:
    st.title("Growth Dashboard")

with col_refresh:
    if st.button("Refresh", type="primary", use_container_width=True):
        get_growth_dashboard_data.clear()
        st.rerun()


# --- Load Data (cached for 30 min) ---

with st.spinner("Loading dashboard data..."):
    data = get_growth_dashboard_data()

# Check for errors
if data.get('error'):
    st.error(f"Error loading data: {data['error']}")
    st.stop()

# Show cache age
cache_age = get_cache_age(data.get('cached_at', ''))
st.caption(f"Data updated {cache_age}")


# --- Time Filter ---

st.markdown("---")

filter_cols = st.columns([1, 1, 1, 1, 4])

with filter_cols[0]:
    btn_7d = st.button("7d", use_container_width=True,
                       type="primary" if st.session_state.get('period', '7d') == '7d' else "secondary")
with filter_cols[1]:
    btn_14d = st.button("14d", use_container_width=True,
                        type="primary" if st.session_state.get('period') == '14d' else "secondary")
with filter_cols[2]:
    btn_30d = st.button("30d", use_container_width=True,
                        type="primary" if st.session_state.get('period') == '30d' else "secondary")
with filter_cols[3]:
    btn_all = st.button("All", use_container_width=True,
                        type="primary" if st.session_state.get('period') == 'all' else "secondary")

# Handle button clicks
if btn_7d:
    st.session_state['period'] = '7d'
    st.rerun()
elif btn_14d:
    st.session_state['period'] = '14d'
    st.rerun()
elif btn_30d:
    st.session_state['period'] = '30d'
    st.rerun()
elif btn_all:
    st.session_state['period'] = 'all'
    st.rerun()

# Get selected period
selected_period = st.session_state.get('period', '7d')
period_days = {'7d': 7, '14d': 14, '30d': 30, 'all': None}.get(selected_period, 7)


# --- Key Metrics Row ---

st.markdown("### Key Metrics")

metrics_cols = st.columns(6)

# Total Signups (from user_data)
with metrics_cols[0]:
    total_signups = data.get('total_signups', 0)

    st.metric(
        label="Total Signups",
        value=format_number(total_signups),
    )

# Onboarded Users (from user_metadata)
with metrics_cols[1]:
    total_onboarded = data.get('total_onboarded', 0)
    onboarded_gender = data.get('onboarded_by_gender', {})
    onb_males = onboarded_gender.get('male', 0)
    onb_females = onboarded_gender.get('female', 0)

    st.metric(
        label="Onboarded",
        value=format_number(total_onboarded),
        delta=f"M:{onb_males} F:{onb_females}",
        delta_color="off"
    )

# New Signups (for selected period)
with metrics_cols[2]:
    period_key = selected_period if selected_period != 'all' else '30d'
    period_data = data.get('period_signups', {}).get(period_key, {})
    current_signups = period_data.get('current', 0)
    growth_rate = period_data.get('growth', 0)

    st.metric(
        label=f"New Signups ({selected_period})",
        value=format_number(current_signups),
        delta=f"{growth_rate:+.1f}%",
        delta_color="normal" if growth_rate >= 0 else "inverse"
    )

# Total Matches
with metrics_cols[3]:
    st.metric(
        label="Total Matches",
        value=format_number(data.get('total_matches', 0)),
    )

# Mutual Matches
with metrics_cols[4]:
    mutual = data.get('mutual_matches', 0)
    total_matches = data.get('total_matches', 0)
    mutual_rate = (mutual / total_matches * 100) if total_matches > 0 else 0

    st.metric(
        label="Mutual Matches",
        value=format_number(mutual),
        delta=f"{mutual_rate:.1f}% rate",
        delta_color="off"
    )

# Like Rate
with metrics_cols[5]:
    like_rate = data.get('like_rate', 0)
    st.metric(
        label="Like Rate",
        value=f"{like_rate:.1f}%",
    )


# --- Signup Trends Chart (from user_data - total only) ---

st.markdown("---")
st.markdown("### Signup Trends")

# Get filtered signups (in-memory, no DB call)
signup_data = get_filtered_signups(data, period_days)

if signup_data:
    df_signups = pd.DataFrame(signup_data)

    # Create line chart with Plotly - single line for total signups
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df_signups['date'],
        y=df_signups['total'],
        name='Signups',
        line=dict(color='#1976d2', width=2),
        mode='lines+markers'
    ))

    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Signups",
        hovermode="x unified",
        showlegend=False,
        margin=dict(l=0, r=0, t=10, b=0),
        height=300,
        font=dict(family="Arial, sans-serif"),
    )

    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No signup data available for the selected period.")


# --- Onboarded Users Chart (from user_metadata - with gender split) ---

st.markdown("---")
st.markdown("### Onboarded Users Trends")

# Get filtered onboarded users (in-memory, no DB call)
onboarded_data = get_filtered_onboarded(data, period_days)

if onboarded_data:
    df_onboarded = pd.DataFrame(onboarded_data)

    # Create line chart with male/female split
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df_onboarded['date'],
        y=df_onboarded['male'],
        name='Male',
        line=dict(color='#1976d2', width=2),
        mode='lines+markers'
    ))

    fig.add_trace(go.Scatter(
        x=df_onboarded['date'],
        y=df_onboarded['female'],
        name='Female',
        line=dict(color='#e91e63', width=2),
        mode='lines+markers'
    ))

    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Onboarded",
        hovermode="x unified",
        showlegend=False,
        margin=dict(l=0, r=0, t=10, b=0),
        height=300,
        font=dict(family="Arial, sans-serif"),
    )

    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No onboarded user data available for the selected period.")


# --- Top Cities Chart ---

st.markdown("---")
st.markdown("### Top Cities")

# Get top cities (in-memory, no DB call)
cities_data = get_top_cities(data, n=10)

if cities_data:
    df_cities = pd.DataFrame(cities_data)

    # Create horizontal bar chart
    fig = px.bar(
        df_cities,
        x='count',
        y='city',
        orientation='h',
        text='count',
        color_discrete_sequence=['#1976d2']
    )

    fig.update_layout(
        xaxis_title="Users",
        yaxis_title="",
        yaxis=dict(autorange="reversed"),  # Top city at top
        margin=dict(l=0, r=0, t=10, b=0),
        height=400,
        showlegend=False,
    )

    fig.update_traces(textposition='outside')

    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No city data available.")


# --- Footer ---

st.markdown("---")
st.caption("Data refreshes automatically every 30 minutes. Click 'Refresh' to force update.")
