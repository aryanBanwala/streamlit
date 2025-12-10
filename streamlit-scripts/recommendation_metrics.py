import streamlit as st
import pandas as pd
import json
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime

st.set_page_config(
    page_title="Recommendation Metrics Dashboard",
    page_icon="📊",
    layout="wide"
)

# Load data
@st.cache_data
def load_data():
    json_path = Path(__file__).parent / "utils" / "profiles.json"
    with open(json_path, 'r') as f:
        data = json.load(f)
    return pd.DataFrame(data)

def is_valid_recommendation(row):
    """
    A profile counts as valid recommendation if:
    - female_response is non-null (true/false) OR
    - male_response is non-null (true/false) OR
    - If both responses null, check chat_stages - if either non-null, count it
    - Skip if all are null (testing/unused)
    """
    female_resp = row['female_response']
    male_resp = row['male_response']
    female_stage = row['female_chat_stage']
    male_stage = row['male_chat_stage']

    # If either response is non-null
    if female_resp is not None or male_resp is not None:
        return True

    # Both responses are null, check chat stages
    if female_stage is not None or male_stage is not None:
        return True

    return False

def calculate_metrics(df):
    """Calculate all metrics from the dataframe"""

    # Filter valid recommendations
    df['is_valid'] = df.apply(is_valid_recommendation, axis=1)
    valid_df = df[df['is_valid']].copy()
    skipped_df = df[~df['is_valid']].copy()

    metrics = {}

    # Overview metrics
    metrics['total_valid_recos'] = len(valid_df)
    metrics['total_skipped'] = len(skipped_df)
    metrics['mutual_matches'] = len(valid_df[(valid_df['female_response'] == True) & (valid_df['male_response'] == True)])
    metrics['match_rate'] = (metrics['mutual_matches'] / metrics['total_valid_recos'] * 100) if metrics['total_valid_recos'] > 0 else 0

    # Male metrics
    metrics['unique_males'] = valid_df['male_user_id'].nunique()
    metrics['male_yes_count'] = len(valid_df[valid_df['male_response'] == True])
    metrics['male_no_count'] = len(valid_df[valid_df['male_response'] == False])
    metrics['male_pending_count'] = len(valid_df[valid_df['male_response'].isna()])
    metrics['unique_males_yes'] = valid_df[valid_df['male_response'] == True]['male_user_id'].nunique()
    metrics['unique_males_no'] = valid_df[valid_df['male_response'] == False]['male_user_id'].nunique()
    male_responded = metrics['male_yes_count'] + metrics['male_no_count']
    metrics['male_yes_rate'] = (metrics['male_yes_count'] / male_responded * 100) if male_responded > 0 else 0
    metrics['avg_recos_per_male'] = metrics['total_valid_recos'] / metrics['unique_males'] if metrics['unique_males'] > 0 else 0
    metrics['max_recos_male'] = valid_df['male_user_id'].value_counts().max() if len(valid_df) > 0 else 0

    # Female metrics
    metrics['unique_females'] = valid_df['female_user_id'].nunique()
    metrics['female_yes_count'] = len(valid_df[valid_df['female_response'] == True])
    metrics['female_no_count'] = len(valid_df[valid_df['female_response'] == False])
    metrics['female_pending_count'] = len(valid_df[valid_df['female_response'].isna()])
    metrics['unique_females_yes'] = valid_df[valid_df['female_response'] == True]['female_user_id'].nunique()
    metrics['unique_females_no'] = valid_df[valid_df['female_response'] == False]['female_user_id'].nunique()
    female_responded = metrics['female_yes_count'] + metrics['female_no_count']
    metrics['female_yes_rate'] = (metrics['female_yes_count'] / female_responded * 100) if female_responded > 0 else 0
    metrics['avg_recos_per_female'] = metrics['total_valid_recos'] / metrics['unique_females'] if metrics['unique_females'] > 0 else 0
    metrics['max_recos_female'] = valid_df['female_user_id'].value_counts().max() if len(valid_df) > 0 else 0

    # Conversion funnel
    metrics['at_least_one_responded'] = len(valid_df[
        (valid_df['female_response'].notna()) | (valid_df['male_response'].notna())
    ])
    metrics['at_least_one_yes'] = len(valid_df[
        (valid_df['female_response'] == True) | (valid_df['male_response'] == True)
    ])
    metrics['both_responded'] = len(valid_df[
        (valid_df['female_response'].notna()) & (valid_df['male_response'].notna())
    ])

    # Created by analysis
    metrics['created_by_male'] = len(valid_df[valid_df['created_by'] == 'male'])
    metrics['created_by_female'] = len(valid_df[valid_df['created_by'] == 'female'])

    # Match rate by creator
    male_created = valid_df[valid_df['created_by'] == 'male']
    female_created = valid_df[valid_df['created_by'] == 'female']
    metrics['match_rate_male_created'] = len(male_created[(male_created['female_response'] == True) & (male_created['male_response'] == True)]) / len(male_created) * 100 if len(male_created) > 0 else 0
    metrics['match_rate_female_created'] = len(female_created[(female_created['female_response'] == True) & (female_created['male_response'] == True)]) / len(female_created) * 100 if len(female_created) > 0 else 0

    return metrics, valid_df, skipped_df

def main():
    st.title("📊 Recommendation Metrics Dashboard")
    st.markdown("---")

    # Load and process data
    try:
        df = load_data()
        metrics, valid_df, skipped_df = calculate_metrics(df)
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return

    # Row 1: Overview metrics
    st.header("Overview")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Valid Recommendations", metrics['total_valid_recos'])
    with col2:
        st.metric("Mutual Matches", metrics['mutual_matches'])
    with col3:
        st.metric("Match Rate", f"{metrics['match_rate']:.1f}%")
    with col4:
        st.metric("Skipped (Testing/Unused)", metrics['total_skipped'])

    st.markdown("---")

    # Row 2: Gender-wise breakdown
    st.header("Gender-wise Breakdown")
    col_male, col_female = st.columns(2)

    with col_male:
        st.subheader("👨 Male Metrics")
        st.metric("Unique Males", metrics['unique_males'])

        mcol1, mcol2, mcol3 = st.columns(3)
        with mcol1:
            st.metric("Said Yes", metrics['male_yes_count'], help="Total yes responses")
        with mcol2:
            st.metric("Said No", metrics['male_no_count'], help="Total no responses")
        with mcol3:
            st.metric("Pending", metrics['male_pending_count'], help="No response yet")

        st.metric("Yes Rate", f"{metrics['male_yes_rate']:.1f}%", help="Yes / (Yes + No)")
        st.metric("Unique Males who said Yes", metrics['unique_males_yes'])
        st.metric("Avg Recos per Male", f"{metrics['avg_recos_per_male']:.2f}")
        st.metric("Max Recos (Single Male)", metrics['max_recos_male'])

    with col_female:
        st.subheader("👩 Female Metrics")
        st.metric("Unique Females", metrics['unique_females'])

        fcol1, fcol2, fcol3 = st.columns(3)
        with fcol1:
            st.metric("Said Yes", metrics['female_yes_count'], help="Total yes responses")
        with fcol2:
            st.metric("Said No", metrics['female_no_count'], help="Total no responses")
        with fcol3:
            st.metric("Pending", metrics['female_pending_count'], help="No response yet")

        st.metric("Yes Rate", f"{metrics['female_yes_rate']:.1f}%", help="Yes / (Yes + No)")
        st.metric("Unique Females who said Yes", metrics['unique_females_yes'])
        st.metric("Avg Recos per Female", f"{metrics['avg_recos_per_female']:.2f}")
        st.metric("Max Recos (Single Female)", metrics['max_recos_female'])

    st.markdown("---")

    # Row 3: Conversion Funnel
    st.header("Conversion Funnel")

    funnel_data = {
        'Stage': [
            'Total Valid Recos',
            'At Least One Responded',
            'At Least One Said Yes',
            'Female Said Yes (total)',
            'Male Said Yes (total)',
            'Unique Females who said Yes',
            'Unique Males who said Yes',
            'Unique Females who said No',
            'Unique Males who said No',
            'Both Responded',
            'Mutual Match'
        ],
        'Count': [
            metrics['total_valid_recos'],
            metrics['at_least_one_responded'],
            metrics['at_least_one_yes'],
            metrics['female_yes_count'],
            metrics['male_yes_count'],
            metrics['unique_females_yes'],
            metrics['unique_males_yes'],
            metrics['unique_females_no'],
            metrics['unique_males_no'],
            metrics['both_responded'],
            metrics['mutual_matches']
        ],
        'Description': [
            'Total recommendations created (excluding test/unused data where both responses & chat_stages are null)',
            'At least one person (male OR female) gave a response (yes/no) - matlab kisi ne toh react kiya',
            'At least one person said YES (male ya female mein se kisi ek ne haan bola)',
            'Total YES responses by females (ek female ke multiple yes bhi count)',
            'Total YES responses by males (ek male ke multiple yes bhi count)',
            'Kitni UNIQUE females ne atleast 1 male ko YES bola',
            'Kitne UNIQUE males ne atleast 1 female ko YES bola',
            'Kitni UNIQUE females ne atleast 1 male ko NO bola',
            'Kitne UNIQUE males ne atleast 1 female ko NO bola',
            'Dono ne respond kiya (yes ya no) - both male AND female ne apna decision de diya',
            'MATCH! Dono ne YES bola - female_response=true AND male_response=true'
        ],
        'Formula': [
            'female_response != null OR male_response != null OR chat_stage != null',
            'female_response IN (true,false) OR male_response IN (true,false)',
            'female_response = true OR male_response = true',
            'COUNT(*) WHERE female_response = true',
            'COUNT(*) WHERE male_response = true',
            'COUNT(DISTINCT female_user_id) WHERE female_response = true',
            'COUNT(DISTINCT male_user_id) WHERE male_response = true',
            'COUNT(DISTINCT female_user_id) WHERE female_response = false',
            'COUNT(DISTINCT male_user_id) WHERE male_response = false',
            'female_response != null AND male_response != null',
            'female_response = true AND male_response = true'
        ]
    }

    # Calculate percentages
    funnel_df = pd.DataFrame(funnel_data)
    funnel_df['Percentage'] = (funnel_df['Count'] / metrics['total_valid_recos'] * 100).round(1)
    funnel_df['Label'] = funnel_df.apply(lambda x: f"{x['Stage']}: {x['Count']} ({x['Percentage']}%)", axis=1)

    fig_funnel = go.Figure(go.Funnel(
        y=funnel_df['Stage'],
        x=funnel_df['Count'],
        textinfo="value+percent initial",
        marker={"color": ["#636EFA", "#EF553B", "#00CC96", "#FF6B9D", "#19D3F3", "#FF69B4", "#1E90FF", "#DC143C", "#4169E1", "#AB63FA", "#FFA15A"]}
    ))
    fig_funnel.update_layout(height=450)
    st.plotly_chart(fig_funnel, use_container_width=True)

    # Funnel table with descriptions
    st.subheader("Funnel Breakdown with Explanations")
    st.dataframe(
        funnel_df[['Stage', 'Count', 'Percentage', 'Description', 'Formula']],
        use_container_width=True,
        hide_index=True,
        column_config={
            'Stage': st.column_config.TextColumn('Stage', width='medium'),
            'Count': st.column_config.NumberColumn('Count', width='small'),
            'Percentage': st.column_config.NumberColumn('% of Total', width='small', format='%.1f%%'),
            'Description': st.column_config.TextColumn('Kya Hai?', width='large'),
            'Formula': st.column_config.TextColumn('Logic/Formula', width='large')
        }
    )

    # CSV Download button
    csv_data = funnel_df[['Stage', 'Count', 'Percentage', 'Description', 'Formula']].to_csv(index=False)
    st.download_button(
        label="Download Funnel Data as CSV",
        data=csv_data,
        file_name="funnel_metrics.csv",
        mime="text/csv"
    )

    st.markdown("---")

    # Row 4: Response Distribution Pie Charts
    st.header("Response Distribution")
    pie_col1, pie_col2 = st.columns(2)

    with pie_col1:
        st.subheader("Male Responses")
        male_response_data = {
            'Response': ['Yes', 'No', 'Pending'],
            'Count': [metrics['male_yes_count'], metrics['male_no_count'], metrics['male_pending_count']]
        }
        fig_male_pie = px.pie(
            male_response_data,
            values='Count',
            names='Response',
            color='Response',
            color_discrete_map={'Yes': '#00CC96', 'No': '#EF553B', 'Pending': '#636EFA'}
        )
        st.plotly_chart(fig_male_pie, use_container_width=True)

    with pie_col2:
        st.subheader("Female Responses")
        female_response_data = {
            'Response': ['Yes', 'No', 'Pending'],
            'Count': [metrics['female_yes_count'], metrics['female_no_count'], metrics['female_pending_count']]
        }
        fig_female_pie = px.pie(
            female_response_data,
            values='Count',
            names='Response',
            color='Response',
            color_discrete_map={'Yes': '#00CC96', 'No': '#EF553B', 'Pending': '#636EFA'}
        )
        st.plotly_chart(fig_female_pie, use_container_width=True)

    st.markdown("---")

    # Row 5: Created By Analysis
    st.header("Who Initiated the Recommendation")
    init_col1, init_col2 = st.columns(2)

    with init_col1:
        created_by_data = {
            'Initiator': ['Male', 'Female'],
            'Count': [metrics['created_by_male'], metrics['created_by_female']]
        }
        fig_created = px.bar(
            created_by_data,
            x='Initiator',
            y='Count',
            color='Initiator',
            color_discrete_map={'Male': '#636EFA', 'Female': '#EF553B'}
        )
        fig_created.update_layout(showlegend=False)
        st.plotly_chart(fig_created, use_container_width=True)

    with init_col2:
        st.subheader("Match Rate by Initiator")
        st.metric("Male-initiated Match Rate", f"{metrics['match_rate_male_created']:.1f}%")
        st.metric("Female-initiated Match Rate", f"{metrics['match_rate_female_created']:.1f}%")

    st.markdown("---")

    # Row 6: Time-based Analysis
    st.header("Time-based Analysis")

    try:
        valid_df['created_date'] = pd.to_datetime(valid_df['created_at']).dt.date
        daily_recos = valid_df.groupby('created_date').size().reset_index(name='Recommendations')

        # Daily matches
        matches_df = valid_df[(valid_df['female_response'] == True) & (valid_df['male_response'] == True)]
        if len(matches_df) > 0:
            matches_df['created_date'] = pd.to_datetime(matches_df['created_at']).dt.date
            daily_matches = matches_df.groupby('created_date').size().reset_index(name='Matches')
            daily_recos = daily_recos.merge(daily_matches, on='created_date', how='left').fillna(0)
        else:
            daily_recos['Matches'] = 0

        fig_time = go.Figure()
        fig_time.add_trace(go.Scatter(
            x=daily_recos['created_date'],
            y=daily_recos['Recommendations'],
            mode='lines+markers',
            name='Recommendations',
            line=dict(color='#636EFA')
        ))
        fig_time.add_trace(go.Scatter(
            x=daily_recos['created_date'],
            y=daily_recos['Matches'],
            mode='lines+markers',
            name='Matches',
            line=dict(color='#00CC96')
        ))
        fig_time.update_layout(
            xaxis_title='Date',
            yaxis_title='Count',
            height=400
        )
        st.plotly_chart(fig_time, use_container_width=True)
    except Exception as e:
        st.warning(f"Could not generate time-based chart: {e}")

    st.markdown("---")

    # Row 7: Top Users
    st.header("Top Users")
    top_col1, top_col2 = st.columns(2)

    with top_col1:
        st.subheader("Top 5 Males by Recos Received")
        male_reco_counts = valid_df['male_user_id'].value_counts().head(5).reset_index()
        male_reco_counts.columns = ['Male User ID', 'Recos Received']
        st.dataframe(male_reco_counts, use_container_width=True, hide_index=True)

        st.subheader("Top 5 Males by Yes Given")
        male_yes_df = valid_df[valid_df['male_response'] == True]
        male_yes_counts = male_yes_df['male_user_id'].value_counts().head(5).reset_index()
        male_yes_counts.columns = ['Male User ID', 'Yes Given']
        st.dataframe(male_yes_counts, use_container_width=True, hide_index=True)

    with top_col2:
        st.subheader("Top 5 Females by Recos Received")
        female_reco_counts = valid_df['female_user_id'].value_counts().head(5).reset_index()
        female_reco_counts.columns = ['Female User ID', 'Recos Received']
        st.dataframe(female_reco_counts, use_container_width=True, hide_index=True)

        st.subheader("Top 5 Females by Yes Given")
        female_yes_df = valid_df[valid_df['female_response'] == True]
        female_yes_counts = female_yes_df['female_user_id'].value_counts().head(5).reset_index()
        female_yes_counts.columns = ['Female User ID', 'Yes Given']
        st.dataframe(female_yes_counts, use_container_width=True, hide_index=True)

    st.markdown("---")

    # Row 8: Additional Stats
    st.header("Additional Statistics")

    add_col1, add_col2, add_col3 = st.columns(3)

    with add_col1:
        # One-sided yes (only one said yes)
        one_sided_yes = len(valid_df[
            ((valid_df['female_response'] == True) & (valid_df['male_response'] != True)) |
            ((valid_df['male_response'] == True) & (valid_df['female_response'] != True))
        ])
        st.metric("One-sided Yes (waiting for other)", one_sided_yes)

    with add_col2:
        # Both said no
        both_no = len(valid_df[
            (valid_df['female_response'] == False) & (valid_df['male_response'] == False)
        ])
        st.metric("Both Said No", both_no)

    with add_col3:
        # Cross rejection (one yes, one no)
        cross_rejection = len(valid_df[
            ((valid_df['female_response'] == True) & (valid_df['male_response'] == False)) |
            ((valid_df['male_response'] == True) & (valid_df['female_response'] == False))
        ])
        st.metric("Cross Rejection (One Yes, One No)", cross_rejection)

    st.markdown("---")

    # Expandable section for skipped data
    with st.expander("View Skipped/Testing Data Info"):
        st.write(f"**Total Skipped Entries:** {metrics['total_skipped']}")
        st.write("These are entries where both male_response and female_response are null, AND both chat_stages are null.")
        if len(skipped_df) > 0:
            st.write("Sample skipped entries (first 10):")
            st.dataframe(skipped_df[['profiles_id', 'female_response', 'male_response', 'female_chat_stage', 'male_chat_stage', 'created_at']].head(10), use_container_width=True, hide_index=True)

if __name__ == "__main__":
    main()
