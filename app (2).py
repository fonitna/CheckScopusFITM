
import streamlit as st
import pandas as pd
import re
import numpy as np
from scholarly import scholarly

st.set_page_config(layout='wide') # Optional: Use wide layout for better display

st.title('Scopus Publication Checker')

st.write("### Flexible Data Input and Scopus Indexing Check")
st.write("You can either enter a Google Scholar ID to fetch your publications directly or upload your `jittimon_research.csv` file.")
st.write("Then, upload the Scopus Sources List Excel file (`ext_list_Feb_2026.xlsx`) to check indexing status.")

# Helper function to clean strings for matching
def clean_string_for_exact_match(text):
    if pd.isna(text):
        return np.nan
    text = str(text).lower().strip()
    text = re.sub(r'[^a-z0-9]', '', text) # Keep only alphanumeric characters
    text = re.sub(r'\s+', ' ', text) # Replace multiple spaces with a single space
    return text.strip()

@st.cache_data(show_spinner="Fetching Google Scholar data...")
def fetch_google_scholar_data(author_id):
    try:
        author = scholarly.search_author_id(author_id)
        st.write(f"Found author: {author['name']}")
        author = scholarly.fill(author, sections=['basics', 'publications'])

        pub_list = []
        for pub in author['publications']:
            p = scholarly.fill(pub)
            bib = p['bib']
            pub_list.append({
                'Title': bib.get('title', 'N/A'),
                'Year': bib.get('pub_year', 'N/A'),
                'Citations': p.get('num_citations', 0),
                'Venue': bib.get('journal', bib.get('conference', 'N/A')),
                'Author': bib.get('author', 'N/A')
            })
        df = pd.DataFrame(pub_list)
        df['Year_numeric'] = pd.to_numeric(df['Year'], errors='coerce')
        df = df.sort_values(by='Year_numeric', ascending=False)
        df['Year'] = df['Year_numeric'].astype(pd.Int64Dtype()).astype(str).replace('<NA>', 'N/A')
        return df
    except Exception as e:
        st.error(f"Error fetching Google Scholar data: {e}")
        return None

@st.cache_data(show_spinner="Loading Scopus data...")
def load_scopus_file(uploaded_file):
    try:
        scopus_sources_df = pd.read_excel(uploaded_file)
        # Preprocessing scopus_sources_df (Scopus data)
        scopus_sources_df['Source_Title_cleaned_for_exact'] = scopus_sources_df['Source Title'].apply(clean_string_for_exact_match)

        # Handle 'Source Type' column if not present from direct column access
        if 'Source Type' not in scopus_sources_df.columns:
            subject_area_columns = [col for col in scopus_sources_df.columns if re.match(r'^\d{4}\\n', str(col)) or 'Top level' in str(col)]
            def get_source_types_dynamic(row):
                source_types = []
                for col in subject_area_columns:
                    if pd.notna(row[col]) and row[col] == 1: # Assuming 1 indicates presence
                        source_types.append(col.split('\n')[-1].strip())
                    elif pd.notna(row[col]) and 'Top level' in col:
                         source_types.append(col.split('\n')[-1].strip())
                return ', '.join(source_types) if source_types else 'Journal' # Default to Journal or N/A
            st.warning(" 'Source Type' column not found directly. Attempting to infer from other columns. This might not be fully accurate.")
            scopus_sources_df['Source Type'] = scopus_sources_df.apply(get_source_types_dynamic, axis=1)

        scopus_sources_df['Source Type'] = scopus_sources_df['Source Type'].fillna('Journal')

        return scopus_sources_df
    except Exception as e:
        st.error(f"Error loading Scopus Excel file: {e}")
        return None

# --- Research Data Input --- #
df_research = None

input_method = st.radio("Choose your research data input method:", ("Google Scholar ID", "Upload CSV"))

if input_method == "Google Scholar ID":
    scholar_id = st.text_input("Enter Google Scholar Author ID (e.g., Chhuh88AAAAJ)")
    if scholar_id:
        df_research = fetch_google_scholar_data(scholar_id)
        if df_research is not None:
            st.success("Google Scholar data fetched successfully!")
            st.subheader("Preview of fetched Google Scholar data:")
            st.dataframe(df_research.head())
            csv_gs_output = df_research.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button(
                label="Download Fetched Google Scholar Data as CSV",
                data=csv_gs_output,
                file_name=f"google_scholar_{scholar_id}_publications.csv",
                mime="text/csv",
            )
else: # input_method == "Upload CSV"
    uploaded_research_file = st.file_uploader("Upload your Google Scholar research CSV (e.g., jittimon_research.csv)", type=['csv'])
    if uploaded_research_file is not None:
        try:
            df_research = pd.read_csv(uploaded_research_file)
            st.success("Research CSV uploaded successfully!")
            # Ensure Year_numeric and Year columns are processed for uploaded CSV as well
            df_research['Year_numeric'] = pd.to_numeric(df_research['Year'], errors='coerce')
            df_research = df_research.sort_values(by='Year_numeric', ascending=False)
            df_research['Year'] = df_research['Year_numeric'].astype(pd.Int64Dtype()).astype(str).replace('<NA>', 'N/A')
            st.subheader("Preview of uploaded research data:")
            st.dataframe(df_research.head())
        except Exception as e:
            st.error(f"Error reading uploaded research CSV: {e}")


# --- Scopus Data Input --- #
st.markdown("--- ")
st.write("### Upload Scopus Sources List")

if 'scopus_sources_df' not in st.session_state:
    st.session_state.scopus_sources_df = None

uploaded_scopus_file = st.file_uploader("Upload Scopus Sources List Excel (ext_list_Feb_2026.xlsx)", type=['xlsx'])

if uploaded_scopus_file is not None and st.session_state.scopus_sources_df is None:
    st.session_state.scopus_sources_df = load_scopus_file(uploaded_scopus_file)
    if st.session_state.scopus_sources_df is not None:
        st.success("Scopus Sources List loaded successfully!")

elif uploaded_scopus_file is None and st.session_state.scopus_sources_df is not None:
    st.info("Scopus Sources List already loaded from a previous upload.")
elif uploaded_scopus_file is not None and st.session_state.scopus_sources_df is not None:
    # If a new file is uploaded while one is already in session_state, update it.
    st.session_state.scopus_sources_df = load_scopus_file(uploaded_scopus_file)
    if st.session_state.scopus_sources_df is not None:
        st.success("Scopus Sources List updated successfully with new upload!")

scopus_sources_df = st.session_state.scopus_sources_df

# --- Data Processing and Comparison Logic --- #
if df_research is not None and scopus_sources_df is not None:
    st.markdown("--- ")
    st.subheader("Analyzing Publications...")

    try:
        # Clean Venue column in df_research
        df_research['Venue_cleaned_for_exact'] = df_research['Venue'].apply(clean_string_for_exact_match)

        # Create a mapping from cleaned Scopus source title to Source Type
        scopus_source_type_map = scopus_sources_df.set_index('Source_Title_cleaned_for_exact')['Source Type'].to_dict()

        # Comparison Logic
        df_research['Is_Scopus_Indexed'] = df_research['Venue_cleaned_for_exact'].isin(scopus_sources_df['Source_Title_cleaned_for_exact']).fillna(False)
        df_research['Source_Type'] = df_research['Venue_cleaned_for_exact'].map(scopus_source_type_map).fillna('N/A')

        # --- Display Results ---
        st.subheader("Your Research Publications with Scopus Status")

        scopus_indexed_publications = df_research[df_research['Is_Scopus_Indexed']].sort_values(by='Year_numeric', ascending=False)
        non_scopus_indexed_publications = df_research[~df_research['Is_Scopus_Indexed']].sort_values(by='Year_numeric', ascending=False)
        na_venues = df_research[df_research['Venue'].isna() | (df_research['Venue'] == 'N/A')]

        # Display counts using columns
        total_pubs = len(df_research)
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(label="Total Publications", value=total_pubs)
        with col2:
            st.metric(label="Scopus Indexed", value=len(scopus_indexed_publications))
        with col3:
            st.metric(label="Non-Scopus Indexed (with Venue)", value=len(non_scopus_indexed_publications) - len(na_venues)) # Exclude N/A venues
        with col4:
            st.metric(label="Missing Venue Info", value=len(na_venues))


        if not scopus_indexed_publications.empty:
            st.markdown("### ✅ Publications Found in Scopus")
            st.dataframe(scopus_indexed_publications[['Year', 'Title', 'Venue', 'Citations', 'Source_Type']])
        else:
            st.info("No publications found to be indexed in Scopus based on exact venue title matching.")

        if not non_scopus_indexed_publications.empty:
            st.markdown("### ❌ Publications NOT Found in Scopus (or no exact match)")
            st.dataframe(non_scopus_indexed_publications[['Year', 'Title', 'Venue', 'Citations']])
        else:
            st.success("All your publications were found in Scopus!")

        if not na_venues.empty:
            st.markdown("### ⚠️ Publications with Missing Venue Information (Cannot check Scopus indexing)")
            st.dataframe(na_venues[['Year', 'Title', 'Citations']])

        # --- Download Results ---
        st.subheader("Download Full Results")
        csv_output = df_research[['Year', 'Title', 'Venue', 'Citations', 'Is_Scopus_Indexed', 'Source_Type']].to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button(
            label="Download results as CSV",
            data=csv_output,
            file_name="research_with_scopus_status.csv",
            mime="text/csv",
        )

    except Exception as e:
        st.error(f"An error occurred during data processing: {e}")
else:
    if df_research is None:
        st.info("Please provide your research data (Google Scholar ID or CSV upload) to proceed.")
    if scopus_sources_df is None:
        st.info("Please upload the Scopus Sources List Excel file to proceed.")

