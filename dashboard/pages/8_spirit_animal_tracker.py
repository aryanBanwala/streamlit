"""
Spirit Animal Conversion Tracker
Tracks quiz completions → signups → onboarding across actual-test and prod DBs.
"""
import streamlit as st
import pandas as pd
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.analytics import get_spirit_animal_conversion_data


def format_number(n: int) -> str:
    return f"{n:,}"


def get_cache_age(cached_at: str) -> str:
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
    st.title("Spirit Animal Tracker")

with col_refresh:
    if st.button("Refresh", type="primary", use_container_width=True):
        get_spirit_animal_conversion_data.clear()
        st.rerun()

# --- Load Data ---

with st.spinner("Loading conversion data..."):
    data = get_spirit_animal_conversion_data()

if data.get('error'):
    st.error(f"Error loading data: {data['error']}")
    st.stop()

cache_age = get_cache_age(data.get('cached_at', ''))
st.caption(f"Data updated {cache_age}")

# --- Key Metrics ---

st.markdown("---")
st.markdown("### Conversion Funnel")

duplicate_emails = data.get('duplicate_emails', {})
metric_cols = st.columns(4)

with metric_cols[0]:
    st.metric(
        label="Unique Quiz Completions",
        value=format_number(data['total_quiz_completions']),
        delta=f"{data['total_quiz_rows']} total rows",
        delta_color="off",
    )

with metric_cols[1]:
    st.metric(
        label="Signed Up",
        value=format_number(data['total_signed_up']),
        delta=f"{data['quiz_to_signup_rate']:.1f}% of quiz",
        delta_color="off",
    )

with metric_cols[2]:
    st.metric(
        label="Onboarded",
        value=format_number(data['total_onboarded']),
        delta=f"{data['quiz_to_onboard_rate']:.1f}% of quiz",
        delta_color="off",
    )

with metric_cols[3]:
    st.metric(
        label="Duplicate Entries",
        value=format_number(len(duplicate_emails)),
        delta=f"{sum(duplicate_emails.values()) - len(duplicate_emails)} extra rows",
        delta_color="off",
    )

# --- Conversion Rates ---

st.markdown("---")
st.markdown("### Conversion Rates")

rate_cols = st.columns(3)

with rate_cols[0]:
    st.metric(label="Quiz → Signup", value=f"{data['quiz_to_signup_rate']:.1f}%")

with rate_cols[1]:
    st.metric(label="Signup → Onboard", value=f"{data['signup_to_onboard_rate']:.1f}%")

with rate_cols[2]:
    st.metric(label="Quiz → Onboard", value=f"{data['quiz_to_onboard_rate']:.1f}%")

# --- Email Drill-Down Tables ---

st.markdown("---")
st.markdown("### Email Breakdown")

tab_not_signed, tab_not_onboarded, tab_onboarded, tab_duplicates = st.tabs([
    f"Not Signed Up ({len(data['not_signed_up_emails'])})",
    f"Signed Up, Not Onboarded ({len(data['signed_up_not_onboarded_emails'])})",
    f"Onboarded ({len(data['onboarded_emails'])})",
    f"Duplicates ({len(duplicate_emails)})",
])

with tab_not_signed:
    emails = data['not_signed_up_emails']
    if emails:
        st.dataframe(
            pd.DataFrame({'Email': emails}),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("All quiz completers have signed up.")

with tab_not_onboarded:
    emails = data['signed_up_not_onboarded_emails']
    if emails:
        st.dataframe(
            pd.DataFrame({'Email': emails}),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("All signed-up users have onboarded.")

with tab_onboarded:
    emails = data['onboarded_emails']
    if emails:
        st.dataframe(
            pd.DataFrame({'Email': emails}),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No onboarded users from quiz yet.")

with tab_duplicates:
    if duplicate_emails:
        df_dupes = pd.DataFrame([
            {'Email': email, 'Submissions': count}
            for email, count in duplicate_emails.items()
        ])
        st.dataframe(df_dupes, use_container_width=True, hide_index=True)
    else:
        st.info("No duplicate entries found.")

# --- Footer ---

st.markdown("---")
st.caption("Data refreshes automatically every 30 minutes. Click 'Refresh' to force update.")
