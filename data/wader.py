import streamlit as st
import pandas as pd
import numpy as np
import io
import plotly.figure_factory as ff
import altair as alt  # Keep altair for other potential charts if needed

# --- Configuration and Page Setup ---
st.set_page_config(
    page_title="Georgia Water Quality Dashboard",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --- Data Loading ---
@st.cache_data
def load_real_data():
    """
    Loads the SDWIS CSV files from the local directory into a dictionary of pandas DataFrames.
    This data is cached to improve performance.
    """
    data = {}
    # List of CSV files based on the provided README
    filenames = [
        "SDWA_PUB_WATER_SYSTEMS.csv",
        "SDWA_VIOLATIONS_ENFORCEMENT.csv",
        "SDWA_LCR_SAMPLES.csv",
        "SDWA_SITE_VISITS.csv",
        "SDWA_FACILITIES.csv",
        "SDWA_GEOGRAPHIC_AREAS.csv",
        "SDWA_REF_CODE_VALUES.csv",
        "SDWA_EVENTS_MILESTONES.csv",
        "SDWA_PN_VIOLATION_ASSOC.csv",
        # "SDWA_REF_ANSI_AREAS.csv",
        "SDWA_SERVICE_AREAS.csv"
    ]

    # Create a mapping from filename to a key used in the app
    file_keys = {f: f.replace('.csv', '') for f in filenames}

    for filename in filenames:
        try:
            # The key in the data dictionary should match what the app expects
            key = file_keys[filename]
            # low_memory=False can help with mixed data types in large files
            data[key] = pd.read_csv(filename, low_memory=False)

        except FileNotFoundError:
            st.error(
                f"Error: The file '{filename}' was not found. Please place it in the same directory as the script.")
            # Return an empty dict to prevent further errors
            return {}
        except Exception as e:
            st.error(f"An error occurred while loading '{filename}': {e}")
            return {}

    # Check if essential files were loaded
    if 'SDWA_PUB_WATER_SYSTEMS' not in data or data['SDWA_PUB_WATER_SYSTEMS'].empty:
        st.error(
            "The essential 'SDWA_PUB_WATER_SYSTEMS.csv' file could not be loaded or is empty. The dashboard cannot continue.")
        return {}

    return data


data = load_real_data()

# --- Stop script if data loading failed ---
if not data:
    st.stop()


# --- Helper Functions ---
def get_pws_name(pwsid):
    """Returns the name of a PWS from its ID."""
    if pwsid and pwsid in data['SDWA_PUB_WATER_SYSTEMS']['PWSID'].values:
        return data['SDWA_PUB_WATER_SYSTEMS'].loc[data['SDWA_PUB_WATER_SYSTEMS']['PWSID'] == pwsid, 'PWS_NAME'].iloc[0]
    return "Unknown System"


def get_code_description(value_type, value_code):
    """Looks up a description for a given code from the reference table."""
    # Ensure value_code is not NaN before query
    if pd.isna(value_code):
        return "N/A"
    ref_df = data['SDWA_REF_CODE_VALUES']
    desc = ref_df[(ref_df['VALUE_TYPE'] == value_type) & (ref_df['VALUE_CODE'] == str(value_code))]
    if not desc.empty:
        return desc['VALUE_DESCRIPTION'].iloc[0]
    return str(value_code)


# --- Main App ---
st.title("Georgia Safe Drinking Water Act (SDWA) Dashboard")
st.markdown("Insights from the Q1 2025 SDWIS Data Export for the State of Georgia.")

# --- Sidebar Filters ---
st.sidebar.header("Filter by Water System")
# Create a mapping from PWSID to a more descriptive name for the selectbox
pws_options = data['SDWA_PUB_WATER_SYSTEMS'][['PWSID', 'PWS_NAME', 'CITY_NAME']].copy()
pws_options.dropna(subset=['PWS_NAME', 'CITY_NAME'], inplace=True)
pws_options['display_name'] = pws_options['PWS_NAME'] + " (" + pws_options['CITY_NAME'].astype(str) + ", " + \
                              pws_options['PWSID'] + ")"
pws_display_map = pd.Series(pws_options.PWSID.values, index=pws_options.display_name).to_dict()

selected_pws_display = st.sidebar.selectbox(
    "Select a Public Water System:",
    options=sorted(pws_display_map.keys()),
    index=0
)
selected_pwsid = pws_display_map[selected_pws_display]

# Display high-level info for the selected system in the sidebar
pws_info = data['SDWA_PUB_WATER_SYSTEMS'].loc[data['SDWA_PUB_WATER_SYSTEMS']['PWSID'] == selected_pwsid].iloc[0]
st.sidebar.markdown("---")
st.sidebar.markdown(f"**System Name:** {pws_info['PWS_NAME']}")
st.sidebar.markdown(f"**PWSID:** {pws_info['PWSID']}")
st.sidebar.markdown(f"**Location:** {pws_info['CITY_NAME']}, GA")
st.sidebar.markdown(f"**Population Served:** {int(pws_info['POPULATION_SERVED_COUNT']):,}")
st.sidebar.markdown(f"**System Type:** {get_code_description('PWS_TYPE_CODE', pws_info['PWS_TYPE_CODE'])}")
st.sidebar.markdown("---")

# --- Tabbed Interface ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "💧 Water Quality & Safety",
    "📊 System Performance",
    "🏞️ Your Water Source",
    "🏘️ Community Info",
    "📄 About The Data"
])

# --- Tab 1: Water Quality & Safety ---
with tab1:
    st.header(f"Historical Violation Timeline for: {pws_info['PWS_NAME']}")
    st.markdown(
        "This Gantt chart shows the duration of non-compliance for each violation. Hover over bars for details.")

    # --- Data Preparation for Gantt Chart ---
    pws_violations = data['SDWA_VIOLATIONS_ENFORCEMENT'][
        data['SDWA_VIOLATIONS_ENFORCEMENT']['PWSID'] == selected_pwsid].copy()
    pws_violations['Start'] = pd.to_datetime(pws_violations['NON_COMPL_PER_BEGIN_DATE'], errors='coerce')

    # For ongoing violations, set end date to the most recent start date in the data to keep the timeline relevant
    latest_date = pws_violations['Start'].max()
    if pd.isna(latest_date):
        latest_date = pd.Timestamp.now()  # Fallback if no dates exist

    pws_violations['Finish'] = pd.to_datetime(pws_violations['NON_COMPL_PER_END_DATE'], errors='coerce').fillna(
        latest_date)
    pws_violations.dropna(subset=['Start', 'Finish'], inplace=True)

    gantt_data = []
    if not pws_violations.empty:
        pws_violations['Task'] = pws_violations['CONTAMINANT_CODE'].apply(
            lambda x: get_code_description('CONTAMINANT_CODE', str(int(x))))
        pws_violations['Resource'] = np.where(pws_violations['IS_HEALTH_BASED_IND'] == 'Y', 'Health-Based',
                                              'Non-Health-Based')
        gantt_data = pws_violations[['Task', 'Start', 'Finish', 'Resource']].to_dict('records')

    if not gantt_data:
        st.info("No historical violations found in this dataset for the selected water system.")
    else:
        # --- Gantt Chart ---
        colors = {'Health-Based': 'rgb(217, 83, 79)', 'Non-Health-Based': 'rgb(240, 173, 78)'}

        fig = ff.create_gantt(gantt_data,
                              colors=colors,
                              index_col='Resource',
                              show_colorbar=True,
                              group_tasks=True,
                              title='Violation Timeline by Type')

        fig.update_layout(xaxis_title='Date', yaxis_title='Contaminant / Rule')
        st.plotly_chart(fig, use_container_width=True)

    # --- LCR and Details Table ---
    st.markdown("### Compliance Event Details")
    pws_lcr = data['SDWA_LCR_SAMPLES'][data['SDWA_LCR_SAMPLES']['PWSID'] == selected_pwsid].copy()

    # Prepare violation data for the table
    violations_table = pws_violations.copy()
    violations_table['Date'] = violations_table['Start']
    violations_table['Event Type'] = 'Violation'
    violations_table['Details'] = "Violation: " + violations_table['VIOLATION_CODE'].apply(
        lambda x: get_code_description('VIOLATION_CODE', x)) + " | Status: " + violations_table[
                                      'VIOLATION_STATUS'].astype(str)
    violations_table['Health Based'] = violations_table['Resource']

    # Prepare LCR data for the table
    pws_lcr['Date'] = pd.to_datetime(pws_lcr['SAMPLING_END_DATE'], errors='coerce')
    pws_lcr.dropna(subset=['Date'], inplace=True)
    pws_lcr['Event Type'] = 'LCR Sample'
    pws_lcr['Contaminant'] = pws_lcr['CONTAMINANT_CODE'].apply(lambda x: get_code_description('CONTAMINANT_CODE', x))
    pws_lcr['Details'] = "90th Percentile Result: " + pws_lcr['SAMPLE_MEASURE'].astype(str) + " " + pws_lcr[
        'UNIT_OF_MEASURE'].astype(str)
    pws_lcr['Health Based'] = 'N/A'  # LCR samples are not violations themselves

    # Combine for a unified table
    details_data = pd.concat([
        violations_table[['Date', 'Event Type', 'Task', 'Details', 'Health Based']].rename(
            columns={'Task': 'Contaminant'}),
        pws_lcr[['Date', 'Event Type', 'Contaminant', 'Details', 'Health Based']]
    ], ignore_index=True)

    if details_data.empty:
        st.info("No detailed compliance events to display.")
    else:
        st.dataframe(details_data.sort_values(by='Date', ascending=False), use_container_width=True)

# --- Tab 2: System Performance ---
with tab2:
    st.header(f"Performance Report Card for: {pws_info['PWS_NAME']}")
    st.markdown("A summary of compliance status, enforcement actions, and recent site visits.")

    # Data for selected PWS
    pws_violations = data['SDWA_VIOLATIONS_ENFORCEMENT'][data['SDWA_VIOLATIONS_ENFORCEMENT']['PWSID'] == selected_pwsid]
    pws_visits = data['SDWA_SITE_VISITS'][data['SDWA_SITE_VISITS']['PWSID'] == selected_pwsid]

    # Report Card Metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Violations (in this dataset)", value=len(pws_violations))
    with col2:
        st.metric("Health-Based Violations", value=len(pws_violations[pws_violations['IS_HEALTH_BASED_IND'] == 'Y']))
    with col3:
        st.metric("Site Visits (in this dataset)", value=len(pws_visits))

    st.subheader("Enforcement Actions")
    pws_enforcement = pws_violations[pws_violations['ENFORCEMENT_ID'].notna()]
    if pws_enforcement.empty:
        st.success("No enforcement actions found for this system in this dataset.")
    else:
        display_enforcement = pws_enforcement.copy()
        display_enforcement['Action Type'] = display_enforcement['ENFORCEMENT_ACTION_TYPE_CODE'].apply(
            lambda x: get_code_description('ENFORCEMENT_ACTION_TYPE_CODE', x))
        display_enforcement['Related Violation'] = display_enforcement['VIOLATION_CODE'].apply(
            lambda x: get_code_description('VIOLATION_CODE', x))
        st.dataframe(display_enforcement[['ENFORCEMENT_DATE', 'Action Type', 'Related Violation']],
                     use_container_width=True)

    st.subheader("Site Visits & Inspections")
    if pws_visits.empty:
        st.info("No site visits recorded for this system in this dataset.")
    else:
        display_visits = pws_visits.copy()
        display_visits['Reason'] = display_visits['VISIT_REASON_CODE'].apply(
            lambda x: get_code_description('VISIT_REASON_CODE', x))
        st.dataframe(display_visits[['VISIT_DATE', 'Reason']], use_container_width=True)
        st.write(
            "Inspectors evaluate key areas during a visit. (N=No Deficiencies, R=Recommendations, M=Minor Deficiencies, S=Significant Deficiencies)")
        st.dataframe(display_visits[
                         ['VISIT_DATE', 'MANAGEMENT_OPS_EVAL_CODE', 'SOURCE_WATER_EVAL_CODE', 'TREATMENT_EVAL_CODE',
                          'DISTRIBUTION_EVAL_CODE']], use_container_width=True)

# --- Tab 3: Your Water Source ---
with tab3:
    st.header(f"Water Source Profile for: {pws_info['PWS_NAME']}")

    primary_source_code = pws_info['PRIMARY_SOURCE_CODE']
    primary_source_desc = get_code_description('PRIMARY_SOURCE_CODE', primary_source_code)

    st.info(f"**Primary Water Source:** {primary_source_desc} (`{primary_source_code}`)", icon="💦")

    pws_facilities = data['SDWA_FACILITIES'][data['SDWA_FACILITIES']['PWSID'] == selected_pwsid]
    source_facilities = pws_facilities[pws_facilities['IS_SOURCE_IND'] == 'Y']

    st.subheader("Source Facilities")
    if source_facilities.empty:
        st.warning("No specific source facilities listed for this system.")
    else:
        st.dataframe(source_facilities[['FACILITY_ID', 'FACILITY_NAME', 'FACILITY_TYPE_CODE', 'WATER_TYPE_CODE']],
                     use_container_width=True)

    st.subheader("Source Water Protection")
    swp_code = pws_info['SOURCE_WATER_PROTECTION_CODE']
    if swp_code == 'Y':
        st.success("This system has a source water protection plan in place.", icon="🛡️")
        st.markdown(
            "Source water protection is a proactive approach to preventing contamination of the lakes, rivers, and groundwater that serve as sources of drinking water.")
    else:
        st.warning("This system does not have a source water protection plan reported.", icon="⚠️")
        st.markdown("Without a plan, the water source may be more vulnerable to contamination.")

    if "P" in str(primary_source_code):
        st.info(
            "This system **purchases** some or all of its water from another, larger water system (a wholesaler). The quality of the water delivered to you is dependent on the quality from the wholesale provider.",
            icon="🤝")

# --- Tab 4: Community Info ---
with tab4:
    st.header(f"Community Profile for: {pws_info['PWS_NAME']}")

    pws_geo = data['SDWA_GEOGRAPHIC_AREAS'][data['SDWA_GEOGRAPHIC_AREAS']['PWSID'] == selected_pwsid]

    cities_served = pws_geo[pws_geo['AREA_TYPE_CODE'] == 'CT']['CITY_SERVED'].dropna().unique().tolist()
    counties_served = pws_geo[pws_geo['AREA_TYPE_CODE'] == 'CN']['COUNTY_SERVED'].dropna().unique().tolist()

    st.subheader("Service Area")
    st.markdown(f"This water system primarily serves the following areas:")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**City/Town:**")
        st.write(", ".join(cities_served) if cities_served else "N/A")
    with col2:
        st.markdown("**County:**")
        st.write(", ".join(counties_served) if counties_served else "N/A")

    st.subheader("Schools and Daycares")
    is_school = pws_info['IS_SCHOOL_OR_DAYCARE_IND'] == 'Y'
    if is_school:
        st.success("This system is designated as serving a school or daycare facility.", icon="🏫")
        st.markdown("Special attention is often given to these systems due to the vulnerable populations they serve.")
    else:
        st.info("This system is not primarily designated as serving a school or daycare facility.", icon="🏢")

    st.subheader("Find Systems by County")
    all_counties = sorted(data['SDWA_GEOGRAPHIC_AREAS']['COUNTY_SERVED'].dropna().unique())
    selected_county = st.selectbox("Select a county to see which water systems operate there:", all_counties)

    if selected_county:
        geo_df = data['SDWA_GEOGRAPHIC_AREAS']
        pws_df = data['SDWA_PUB_WATER_SYSTEMS']

        county_pwsids = geo_df[(geo_df['COUNTY_SERVED'] == selected_county) & (geo_df['AREA_TYPE_CODE'] == 'CN')][
            'PWSID']

        if not county_pwsids.empty:
            county_systems = pws_df[pws_df['PWSID'].isin(county_pwsids)][
                ['PWS_NAME', 'PWSID', 'POPULATION_SERVED_COUNT', 'CITY_NAME']]
            st.write(f"Water Systems in {selected_county} County:")
            st.dataframe(county_systems, use_container_width=True)
        else:
            st.write(f"No water systems found for {selected_county} County.")

# --- Tab 5: About The Data ---
with tab5:
    st.header("About The SDWIS Data")
    st.info("This page contains the data dictionary and file structure information provided with the data export.",
            icon="ℹ️")

    readme_content = """
    # Data

    **This dashboard uses the national Safe Drinking Water Information System (SDWIS) data.** This data includes information on public water systems, including monitoring, enforcement, and violation data related to requirements established by the Safe Drinking Water Act (SDWA). 

    The data is a **snapshot** and contains historical records present in the database at the time of export. The date of a violation is found in the timeline, not necessarily the quarter of the export.

    ---

    ## 🗄️ Key Data Files Used
    - **SDWA_PUB_WATER_SYSTEMS.csv**: Core information about each public water system (PWS).
    - **SDWA_VIOLATIONS_ENFORCEMENT.csv**: Details on violations, which form the basis of the timeline.
    - **SDWA_LCR_SAMPLES.csv**: Lead and Copper Rule 90th-percentile sample results.
    - **SDWA_SITE_VISITS.csv**: Records of inspections and sanitary surveys.
    - **SDWA_GEOGRAPHIC_AREAS.csv**: Links water systems to the cities and counties they serve.
    - **SDWA_REF_CODE_VALUES.csv**: A reference table to look up descriptions for various codes (e.g., Contaminant Names).

    ---

    ## 🔗 Extra Reference Links
    - [EPA Drinking Water Data & Tools Guide](https://www.epa.gov/DWdata/drinking-water-data-tools-guide)
    - [EPA National Primary Drinking Water Regulations](https://www.epa.gov/ground-water-and-drinking-water/national-primary-drinking-water-regulations)
    - [SDWIS Search User Guide](https://www.epa.gov/enviro/sdwis-search-user-guide)
    """
    st.markdown(readme_content)
