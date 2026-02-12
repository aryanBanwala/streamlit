"""
Spirit Animal Conversion Tracker
Tracks quiz completions → signups → onboarding across actual-test and prod DBs.
"""
import streamlit as st
import pandas as pd
import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client

# Setup paths
current_dir = os.path.dirname(__file__)
scripts_dir = os.path.abspath(os.path.join(current_dir, '..'))
parent_dir = os.path.abspath(os.path.join(scripts_dir, '..'))
sys.path.insert(0, parent_dir)
sys.path.insert(0, scripts_dir)

try:
    from dependencies import get_supabase_client
except ImportError:
    st.error("Error: 'dependencies.py' not found.")
    st.stop()

# Load environment
dotenv_path = os.path.join(parent_dir, '.env')
load_dotenv(dotenv_path)

# --- Supabase Connections ---
try:
    supabase_prod = get_supabase_client()
except Exception as e:
    st.error(f"Failed to connect to prod DB: {e}")
    st.stop()

PAGE_SIZE = 500


@st.cache_resource
def get_actual_test_client():
    url = os.getenv('SUPABASE_URL_ACTUAL_TEST')
    key = os.getenv('SUPABASE_KEY_ACTUAL_TEST')
    if not url or not key:
        raise ValueError("Set SUPABASE_URL_ACTUAL_TEST and SUPABASE_KEY_ACTUAL_TEST in .env")
    return create_client(url, key)


def fetch_all_paginated(client, table, select='*', order_by='created_at'):
    all_data = []
    offset = 0
    while True:
        query = client.table(table).select(select).order(order_by, desc=True)
        response = query.range(offset, offset + PAGE_SIZE - 1).execute()
        if not response.data:
            break
        all_data.extend(response.data)
        if len(response.data) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return all_data


@st.cache_data(ttl=1800)
def get_spirit_animal_conversion_data() -> dict:
    try:
        actual_test = get_actual_test_client()

        # 1. Fetch quiz emails from actual-test DB
        quiz_results = fetch_all_paginated(actual_test, 'spirit_animal_results', 'email, created_at')
        quiz_emails = set()
        email_counts = {}
        for r in quiz_results:
            email = r.get('email')
            if email:
                normalized = email.strip().lower()
                quiz_emails.add(normalized)
                email_counts[normalized] = email_counts.get(normalized, 0) + 1

        duplicate_emails = {e: c for e, c in email_counts.items() if c > 1}

        # 2. Fetch all signed-up users from prod DB (user_data)
        signups = fetch_all_paginated(supabase_prod, 'user_data', 'user_id, user_email')
        email_to_user_id = {}
        for s in signups:
            email = s.get('user_email')
            if email:
                email_to_user_id[email.strip().lower()] = s.get('user_id')

        signup_emails = set(email_to_user_id.keys())

        # 3. Fetch all onboarded user_ids from prod DB (user_metadata)
        onboarded = fetch_all_paginated(supabase_prod, 'user_metadata', 'user_id')
        onboarded_user_ids = set(u.get('user_id') for u in onboarded if u.get('user_id'))

        # 4. Cross-reference
        signed_up_emails = quiz_emails & signup_emails
        not_signed_up_emails = quiz_emails - signup_emails

        signed_up_user_ids = {email_to_user_id[e] for e in signed_up_emails if e in email_to_user_id}
        onboarded_from_quiz = signed_up_user_ids & onboarded_user_ids

        user_id_to_email = {v: k for k, v in email_to_user_id.items()}
        onboarded_emails = {user_id_to_email[uid] for uid in onboarded_from_quiz if uid in user_id_to_email}
        signed_up_not_onboarded = signed_up_emails - onboarded_emails

        total_quiz = len(quiz_emails)
        total_signed_up = len(signed_up_emails)
        total_onboarded = len(onboarded_from_quiz)

        return {
            'total_quiz_completions': total_quiz,
            'total_quiz_rows': len(quiz_results),
            'total_signed_up': total_signed_up,
            'total_onboarded': total_onboarded,
            'quiz_to_signup_rate': (total_signed_up / total_quiz * 100) if total_quiz > 0 else 0,
            'signup_to_onboard_rate': (total_onboarded / total_signed_up * 100) if total_signed_up > 0 else 0,
            'quiz_to_onboard_rate': (total_onboarded / total_quiz * 100) if total_quiz > 0 else 0,
            'not_signed_up_emails': sorted(not_signed_up_emails),
            'signed_up_not_onboarded_emails': sorted(signed_up_not_onboarded),
            'onboarded_emails': sorted(onboarded_emails),
            'duplicate_emails': dict(sorted(duplicate_emails.items(), key=lambda x: x[1], reverse=True)),
            'cached_at': datetime.now().isoformat(),
        }

    except Exception as e:
        return {
            'total_quiz_completions': 0,
            'total_quiz_rows': 0,
            'total_signed_up': 0,
            'total_onboarded': 0,
            'quiz_to_signup_rate': 0,
            'signup_to_onboard_rate': 0,
            'quiz_to_onboard_rate': 0,
            'not_signed_up_emails': [],
            'signed_up_not_onboarded_emails': [],
            'onboarded_emails': [],
            'duplicate_emails': {},
            'cached_at': datetime.now().isoformat(),
            'error': str(e),
        }


# --- Helpers ---

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
        st.dataframe(pd.DataFrame({'Email': emails}), use_container_width=True, hide_index=True)
    else:
        st.info("All quiz completers have signed up.")

with tab_not_onboarded:
    emails = data['signed_up_not_onboarded_emails']
    if emails:
        st.dataframe(pd.DataFrame({'Email': emails}), use_container_width=True, hide_index=True)
    else:
        st.info("All signed-up users have onboarded.")

with tab_onboarded:
    emails = data['onboarded_emails']
    if emails:
        st.dataframe(pd.DataFrame({'Email': emails}), use_container_width=True, hide_index=True)
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
