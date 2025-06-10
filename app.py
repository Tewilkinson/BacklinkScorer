import streamlit as st
import pandas as pd
import numpy as np
import io

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
        'Link Type': ['text', 'text'],  # 'text', 'image', or 'nav'
        'Nofollow': ['FALSE', 'FALSE'],  # TRUE or FALSE
        'Sponsored': ['FALSE', 'FALSE'],  # TRUE or FALSE
        'Lost Date': ['', ''],
        'First Seen': ['2023-06-01', '2023-06-02'],
        'Last Seen': ['2023-06-10', '2023-06-11']
    }
    df = pd.DataFrame(data)
    output = io.BytesIO()
    
    # Use openpyxl instead of xlsxwriter for compatibility
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    return output

# Function to clean up columns by stripping leading/trailing spaces and ensuring string type
def clean_data(df):
    # Convert columns to string and strip any extra spaces, handle non-strings gracefully
    df['Nofollow'] = df['Nofollow'].astype(str).str.strip()
    df['Sponsored'] = df['Sponsored'].astype(str).str.strip()
    df['Lost Date'] = df['Lost Date'].fillna('').astype(str).str.strip()  # Handle NaN and empty strings

    return df

# Function to calculate the score for a backlink
def calculate_score(row, anchor_keywords):
    # Debugging: Print the Nofollow, Sponsored, and Lost Date values
    print(f"Processing {row['Referring page title']} - Nofollow: {row['Nofollow']}, Sponsored: {row['Sponsored']}, Lost Date: {row['Lost Date']}")

    # Check if Nofollow or Sponsored is TRUE or if Lost Date exists
    if row['Nofollow'].strip().upper() == 'TRUE' or row['Sponsored'].strip().upper() == 'TRUE' or row['Lost Date'].strip() != '':
        print(f"Skipping {row['Referring page title']} due to Nofollow, Sponsored, or Lost Date")
        return 0

    # Normalize values
    dr_min, dr_max = 0, 100
    ur_min, ur_max = 0, 100
    rd_min, rd_max = 0, 5000
    traffic_min, traffic_max = 0, 1000000
    
    normalized_dr = normalize(row['Domain rating'], dr_min, dr_max)
    normalized_ur = normalize(row['UR'], ur_min, ur_max)
    normalized_rd = normalize(row['Referring domains'], rd_min, rd_max)
    normalized_traffic = normalize(row['Page traffic'], traffic_min, traffic_max)

    # Anchor text bonus
    anchor_text = row['Anchor'] if isinstance(row['Anchor'], str) else ''
    anchor_bonus = 0
    for keyword in anchor_keywords:
        if keyword.lower() in anchor_text.lower():
            anchor_bonus += 1  # Apply bonus for matching keywords

    # Link type adjustment (boost for text, penalty for image/nav)
    link_type_adjustment = 0
    if row['Link Type'] == 'text':
        link_type_adjustment = 2
    elif row['Link Type'] in ['image', 'nav']:
        link_type_adjustment = -2
    
    # Final score calculation
    score = (
        (normalized_dr * 0.30) + 
        (normalized_ur * 0.20) + 
        (normalized_rd * 0.20) + 
        (normalized_traffic * 0.15) + 
        (anchor_bonus * 0.10) + 
        (link_type_adjustment * 0.05)  # Text boost or penalty
    )
    
    # Debugging: Print the final score
    print(f"Final Score for {row['Referring page title']}: {score}")
    
    return score


# Streamlit UI setup
st.title('Backlink Scoring Tool')

# Provide a template file for download
st.sidebar.subheader('Download Template')
st.sidebar.write('Download the Excel template to fill out your backlink data.')
st.sidebar.download_button('Download Template', create_template(), file_name='backlink_template.xlsx')

# Upload Excel file
uploaded_file = st.file_uploader("Upload your backlink data (Excel)", type=['xlsx'])

# Input box for anchor text keyword boost
anchor_input = st.text_input("Enter keywords for anchor text boost (comma-separated):", "")

# Process input anchor keywords
if anchor_input:
    anchor_keywords = [keyword.strip() for keyword in anchor_input.split(',')]
else:
    anchor_keywords = []

if uploaded_file:
    # Load data from uploaded file
    df = pd.read_excel(uploaded_file)
    
    # Clean up the data
    df = clean_data(df)

    # Ensure the necessary columns exist
    required_columns = ['Referring page title', 'Referring page URL', 'Domain rating', 'UR', 'Referring domains', 'Page traffic', 'Anchor', 'Link Type', 'Nofollow', 'Sponsored', 'Lost Date', 'First Seen', 'Last Seen']
    
    if all(col in df.columns for col in required_columns):
        # Apply the scoring function to each row
        df['Score'] = df.apply(calculate_score, axis=1, anchor_keywords=anchor_keywords)
        
        # Display the results
        st.write("Backlink Scores (out of 10):", df[['Referring page title', 'Score']])

        # Visualize the scores as a bar chart
        st.bar_chart(df[['Referring page title', 'Score']].set_index('Referring page title'))
        
        # Generate the Excel file and allow users to download it
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)
        output.seek(0)

        # Allow users to download the scored Excel file
        st.download_button('Download Scored Data', output, file_name="scored_backlinks.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.error("The uploaded file must contain the required columns: Referring page title, Referring page URL, Domain rating, UR, Referring domains, Page traffic, Anchor, Link Type, Nofollow, Sponsored, Lost Date, First Seen, Last Seen.")
