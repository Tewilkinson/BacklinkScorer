import streamlit as st
import pandas as pd
import numpy as np
import io
from urllib.parse import urlparse
import plotly.graph_objects as go

# Function to normalize values to a 0-10 scale
def normalize(value, min_value, max_value):
    return 10 * (value - min_value) / (max_value - min_value)

# Function to generate a template Excel file for user download
def create_template():
    data = {
        'Referring page title': ['Page 1', 'Page 2'],
        'Referring page URL': ['https://example.com/page1', 'https://example.com/page2'],
        'Domain rating': [50, 50],
        'UR': [50, 50],
        'Referring domains': [100, 100],
        'Page traffic': [1000, 1000],
        'Anchor': ['AI Image Generator', 'AI Image Generator'],
        'Link Type': ['text', 'text'],
        'Nofollow': ['FALSE', 'FALSE'],
        'Sponsored': ['FALSE', 'FALSE'],
        'Lost Date': ['', ''],
        'First Seen': ['2023-06-01', '2023-06-02'],
        'Last Seen': ['2023-06-10', '2023-06-11']
    }
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    return output

# Function to clean up columns
def clean_data(df):
    df['Nofollow'] = df['Nofollow'].astype(str).str.strip()
    df['Sponsored'] = df['Sponsored'].astype(str).str.strip()
    df['Lost Date'] = df['Lost Date'].fillna('').astype(str).str.strip()
    return df

# Function to score title relevance
def title_relevance_score(title, keyword):
    if not isinstance(title, str):
        return 0
    title_lower = title.lower()
    keyword_lower = keyword.lower()
    if keyword_lower in title_lower:
        return 1.0  # Exact match
    elif any(part in title_lower for part in keyword_lower.split()):
        return 0.5  # Partial match
    else:
        return -1.0  # Not relevant

# Function to calculate score for a backlink
def calculate_score(row, anchor_keywords, weights):
    if row['Nofollow'].upper() == 'TRUE' or row['Sponsored'].upper() == 'TRUE' or row['Lost Date'] != '':
        return 0

    normalized_dr = normalize(row['Domain rating'], 0, 100)
    normalized_ur = normalize(row['UR'], 0, 100)
    normalized_rd = normalize(row['Referring domains'], 0, 5000)
    normalized_traffic = normalize(row['Page traffic'], 0, 1000000)

    anchor_bonus = sum(1 for keyword in anchor_keywords if keyword.lower() in str(row['Anchor']).lower())

    link_type_adjustment = 2 if row['Link Type'] == 'text' else -2 if row['Link Type'] in ['image', 'nav'] else 0

    title_bonus = 0
    if anchor_keywords:
        title_bonus = title_relevance_score(row['Referring page title'], anchor_keywords[0])

    score = ((normalized_dr * weights['DR']) +
             (normalized_ur * weights['UR']) +
             (normalized_rd * weights['RD']) +
             (normalized_traffic * weights['Traffic']) +
             (anchor_bonus * 0.10) +
             (link_type_adjustment * 0.05) +
             title_bonus)

    return round(score, 1)

# App title
st.title('Backlink Scoring Dashboard')

# Sidebar: Download template
st.sidebar.subheader('📥 Download Template')
st.sidebar.download_button('Download Template', create_template(), file_name='backlink_template.xlsx')

# Tabs: Controls | Dashboard
tab1, tab2 = st.tabs(["📊 Dashboard", "⚙️ Controls"])

with tab2:
    st.subheader("Scoring Weights")

    dr_weight = st.slider("Domain Rating Weight", 0.0, 1.0, 0.10, 0.01)
    ur_weight = st.slider("UR Weight", 0.0, 1.0, 0.30, 0.01)
    rd_weight = st.slider("Referring Domains Weight", 0.0, 1.0, 0.15, 0.01)
    traffic_weight = st.slider("Page Traffic Weight", 0.0, 1.0, 0.30, 0.01)

    total = dr_weight + ur_weight + rd_weight + traffic_weight
    if total == 0:
        st.warning("At least one weight must be greater than 0.")
        weights = {'DR': 0.25, 'UR': 0.25, 'RD': 0.25, 'Traffic': 0.25}
    else:
        weights = {
            'DR': dr_weight / total,
            'UR': ur_weight / total,
            'RD': rd_weight / total,
            'Traffic': traffic_weight / total
        }

    st.markdown(f"""
    **Normalized Weights:**
    - Domain Rating: {weights['DR']:.2f}
    - UR: {weights['UR']:.2f}
    - Referring Domains: {weights['RD']:.2f}
    - Page Traffic: {weights['Traffic']:.2f}
    """)

with tab1:
    anchor_input = st.text_input("Anchor text keywords (comma-separated):", "")
    anchor_keywords = [keyword.strip() for keyword in anchor_input.split(',')] if anchor_input else []

    uploaded_file = st.file_uploader("Upload backlink data (Excel)", type=['xlsx'])

    if uploaded_file:
        df = pd.read_excel(uploaded_file)
        df = clean_data(df)

        required_columns = ['Referring page title', 'Referring page URL', 'Domain rating', 'UR', 'Referring domains',
                            'Page traffic', 'Anchor', 'Link Type', 'Nofollow', 'Sponsored', 'Lost Date', 'First Seen', 'Last Seen']

        if all(col in df.columns for col in required_columns):
            df['Score'] = df.apply(calculate_score, axis=1, anchor_keywords=anchor_keywords, weights=weights)

            # Penalize duplicate domains
            df['Domain'] = df['Referring page URL'].apply(lambda x: urlparse(x).netloc)
            df = df.sort_values(by='Score', ascending=False)
            df['Rank'] = df.groupby('Domain').cumcount()
            df['Score'] = df.apply(lambda row: row['Score'] if row['Rank'] == 0 else round(row['Score'] * 0.5, 1), axis=1)
            df.drop(columns=['Rank'], inplace=True)

            overall_score = df['Score'].sum().round(1)
            total_links_submitted = len(df)

            col1, col2 = st.columns(2)
            col1.metric("📈 Overall Score", f"{overall_score:.1f}")
            col2.metric("🔗 Total Links Submitted", total_links_submitted)

            st.subheader("🏆 Top 10 Links")
            top_links = df[df['Score'] > 0].sort_values(by='Score', ascending=False).head(10)
            top_links = top_links.reset_index(drop=True)
            top_links['Position'] = range(1, len(top_links) + 1)
            st.dataframe(top_links[['Position', 'Referring page title', 'Referring page URL', 'Score']], use_container_width=True, hide_index=True)

            domain_summary = df.groupby('Domain').agg(
                domain_score=('Score', 'sum'),
                link_count=('Referring page URL', 'count')
            ).reset_index().sort_values(by='domain_score', ascending=False).head(10)

            fig = go.Figure()
            fig.add_trace(go.Bar(x=domain_summary['Domain'], y=domain_summary['domain_score'], name='Domain Score', marker_color='red'))
            fig.add_trace(go.Scatter(x=domain_summary['Domain'], y=domain_summary['link_count'], mode='lines+markers', name='Link Count', yaxis='y2', marker_color='black'))

            fig.update_layout(title='Domain Score & Link Count',
                              yaxis=dict(title='Domain Score'),
                              yaxis2=dict(title='Link Count', overlaying='y', side='right'))

            st.plotly_chart(fig, use_container_width=True)

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df.to_excel(writer, index=False)
            output.seek(0)
            st.download_button('Download Scored Data', output, file_name="scored_backlinks.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.error("Missing required columns in uploaded file.")
