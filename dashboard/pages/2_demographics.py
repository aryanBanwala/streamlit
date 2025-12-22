"""
Demographics Dashboard - User demographics breakdown with gender filter.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# Import services
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.analytics import get_demographics_data, filter_demographics_by_gender


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
    st.title("Demographics")

with col_refresh:
    if st.button("Refresh", type="primary", use_container_width=True):
        get_demographics_data.clear()
        st.rerun()


# --- Load Data ---

with st.spinner("Loading demographics data..."):
    data = get_demographics_data()

# Check for errors
if data.get('error'):
    st.error(f"Error loading data: {data['error']}")
    st.stop()

# Show cache age
cache_age = get_cache_age(data.get('cached_at', ''))
st.caption(f"Data updated {cache_age}")


# --- Gender Filter ---

st.markdown("---")

filter_cols = st.columns([1, 1, 1, 5])

with filter_cols[0]:
    btn_all = st.button("All", use_container_width=True,
                        type="primary" if st.session_state.get('gender_filter', 'all') == 'all' else "secondary")
with filter_cols[1]:
    btn_male = st.button("Male", use_container_width=True,
                         type="primary" if st.session_state.get('gender_filter') == 'male' else "secondary")
with filter_cols[2]:
    btn_female = st.button("Female", use_container_width=True,
                           type="primary" if st.session_state.get('gender_filter') == 'female' else "secondary")

# Handle button clicks
if btn_all:
    st.session_state['gender_filter'] = 'all'
    st.rerun()
elif btn_male:
    st.session_state['gender_filter'] = 'male'
    st.rerun()
elif btn_female:
    st.session_state['gender_filter'] = 'female'
    st.rerun()

# Get selected filter and apply
selected_filter = st.session_state.get('gender_filter', 'all')
filtered_data = filter_demographics_by_gender(data, selected_filter)


# --- Summary Metrics ---

total_users = data.get('total', 0)
gender_counts = data.get('gender', {})
males = gender_counts.get('male', 0)
females = gender_counts.get('female', 0)

if selected_filter == 'all':
    metric_cols = st.columns(3)
    with metric_cols[0]:
        st.metric("Total Users", format_number(total_users))
    with metric_cols[1]:
        st.metric("Male", format_number(males))
    with metric_cols[2]:
        st.metric("Female", format_number(females))
else:
    filtered_total = filtered_data.get('total', 0)
    st.metric(f"{selected_filter.capitalize()} Users", format_number(filtered_total))


# --- Pie Charts Row ---

st.markdown("---")

pie_cols = st.columns(2)

# Gender Distribution Pie (only show when filter is 'all')
with pie_cols[0]:
    st.markdown("#### Gender Distribution")

    if selected_filter == 'all':
        gender_data = filtered_data.get('gender', {})
        if gender_data:
            df_gender = pd.DataFrame([
                {'gender': k.capitalize(), 'count': v}
                for k, v in gender_data.items()
                if k in ['male', 'female']
            ])

            if not df_gender.empty:
                fig = px.pie(
                    df_gender,
                    values='count',
                    names='gender',
                    color='gender',
                    color_discrete_map={'Male': '#1976d2', 'Female': '#e91e63'},
                    hole=0.4
                )
                fig.update_layout(
                    margin=dict(l=0, r=0, t=10, b=0),
                    height=350,
                    showlegend=True,
                    legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5),
                    font=dict(family="Arial, sans-serif"),
                )
                fig.update_traces(textinfo='percent', textposition='inside')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No gender data available.")
        else:
            st.info("No gender data available.")
    else:
        st.info(f"Showing {selected_filter} users only")

# Religion Distribution Pie
with pie_cols[1]:
    st.markdown("#### Religion Distribution")

    religion_data = filtered_data.get('religions', {})
    if religion_data:
        # Sort by count descending
        sorted_religions = sorted(religion_data.items(), key=lambda x: x[1], reverse=True)
        df_religion = pd.DataFrame([
            {'religion': k, 'count': v}
            for k, v in sorted_religions
        ])

        if not df_religion.empty:
            fig = px.pie(
                df_religion,
                values='count',
                names='religion',
                hole=0.4
            )
            fig.update_layout(
                margin=dict(l=0, r=0, t=10, b=0),
                height=350,
                showlegend=True,
                legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5),
                font=dict(family="Arial, sans-serif"),
            )
            fig.update_traces(textinfo='percent', textposition='inside')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No religion data available.")
    else:
        st.info("No religion data available.")


# --- Age Distribution Bar Chart ---

st.markdown("---")
st.markdown("#### Age Distribution")

age_data = filtered_data.get('age_groups', {})
if age_data:
    # Define order for age groups
    age_order = ['18-24', '25-29', '30-34', '35-39', '40+']
    df_age = pd.DataFrame([
        {'age_group': group, 'count': age_data.get(group, 0)}
        for group in age_order
        if age_data.get(group, 0) > 0
    ])

    if not df_age.empty:
        fig = px.bar(
            df_age,
            x='count',
            y='age_group',
            orientation='h',
            text='count',
            color_discrete_sequence=['#1976d2']
        )
        fig.update_layout(
            xaxis_title="Users",
            yaxis_title="",
            yaxis=dict(categoryorder='array', categoryarray=age_order[::-1]),
            margin=dict(l=0, r=0, t=10, b=0),
            height=300,
            showlegend=False,
            font=dict(family="Arial, sans-serif"),
        )
        fig.update_traces(textposition='outside')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No age data available.")
else:
    st.info("No age data available.")


# --- Bottom Row: Cities and Professional Tier ---

st.markdown("---")

bottom_cols = st.columns(2)

# Top Cities
with bottom_cols[0]:
    st.markdown("#### Top 10 Cities")

    city_data = filtered_data.get('cities', {})
    if city_data:
        sorted_cities = sorted(city_data.items(), key=lambda x: x[1], reverse=True)[:10]
        df_cities = pd.DataFrame([
            {'city': city, 'count': count}
            for city, count in sorted_cities
        ])

        if not df_cities.empty:
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
                yaxis=dict(autorange="reversed"),
                margin=dict(l=0, r=0, t=10, b=0),
                height=400,
                showlegend=False,
                font=dict(family="Arial, sans-serif"),
            )
            fig.update_traces(textposition='outside')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No city data available.")
    else:
        st.info("No city data available.")

# Professional Tier
with bottom_cols[1]:
    st.markdown("#### Professional Tier")

    tier_data = filtered_data.get('professional_tiers', {})
    if tier_data:
        # Sort tiers naturally
        sorted_tiers = sorted(tier_data.items(), key=lambda x: x[0])
        df_tiers = pd.DataFrame([
            {'tier': tier, 'count': count}
            for tier, count in sorted_tiers
        ])

        if not df_tiers.empty:
            fig = px.bar(
                df_tiers,
                x='count',
                y='tier',
                orientation='h',
                text='count',
                color_discrete_sequence=['#4caf50']
            )
            fig.update_layout(
                xaxis_title="Users",
                yaxis_title="",
                yaxis=dict(autorange="reversed"),
                margin=dict(l=0, r=0, t=10, b=0),
                height=400,
                showlegend=False,
                font=dict(family="Arial, sans-serif"),
            )
            fig.update_traces(textposition='outside')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No professional tier data available.")
    else:
        st.info("No professional tier data available.")


# --- Footer ---

st.markdown("---")
st.caption("Data refreshes automatically every 5 minutes. Click 'Refresh' to force update.")
