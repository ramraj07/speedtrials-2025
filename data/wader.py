import streamlit as st
import pandas as pd
import numpy as np
import io

# --- Configuration and Page Setup ---
st.set_page_config(
    page_title="Georgia Water Quality Dashboard",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --- Data Simulation ---
# In a real-world scenario, you would load the 10 CSV files.
# For this self-contained example, we'll simulate those files with mock dataframes.
# This ensures the dashboard is fully functional without needing external files.

@st.cache_data
def load_mock_data():
    """
    Creates a dictionary of pandas DataFrames to simulate the SDWIS CSV files.
    This data is cached to improve performance.
    """
    data = {}
    qtr = '2025Q1'
    georgia_pws_ids = [f'GA000000{i}' for i in range(1, 21)]
    cities = ['Atlanta', 'Augusta', 'Columbus', 'Savannah', 'Athens', 'Macon', 'Roswell', 'Albany', 'Marietta',
              'Warner Robins']
    counties = ['Fulton', 'Richmond', 'Muscogee', 'Chatham', 'Clarke', 'Bibb', 'Cobb', 'Dougherty', 'Gwinnett',
                'Houston']

    # --- SDWA_PUB_WATER_SYSTEMS.csv ---
    pws_data = []
    for i, pwsid in enumerate(georgia_pws_ids):
        pws_data.append({
            'SUBMISSIONYEARQUARTER': qtr,
            'PWSID': pwsid,
            'PWS_NAME': f'{cities[i % len(cities)]} Water Works',
            'PWS_TYPE_CODE': np.random.choice(['CWS', 'TNCWS', 'NTNCWS'], p=[0.7, 0.15, 0.15]),
            'POPULATION_SERVED_COUNT': np.random.randint(500, 500000),
            'SERVICE_CONNECTIONS_COUNT': np.random.randint(150, 150000),
            'PRIMARY_SOURCE_CODE': np.random.choice(['GW', 'SW', 'GWP', 'SWP', 'GU'], p=[0.5, 0.2, 0.1, 0.1, 0.1]),
            'IS_SCHOOL_OR_DAYCARE_IND': np.random.choice(['Y', 'N'], p=[0.1, 0.9]),
            'SOURCE_WATER_PROTECTION_CODE': np.random.choice(['Y', 'N'], p=[0.6, 0.4]),
            'ORG_NAME': f'{cities[i % len(cities)]} Dept. of Water',
            'CITY_NAME': cities[i % len(cities)],
            'STATE_CODE': 'GA',
            'ZIP_CODE': f'303{i:02d}'
        })
    data['SDWA_PUB_WATER_SYSTEMS'] = pd.DataFrame(pws_data)

    # --- SDWA_VIOLATIONS_ENFORCEMENT.csv ---
    violations_data = []
    for pwsid in np.random.choice(georgia_pws_ids, size=15, replace=False):
        for _ in range(np.random.randint(1, 4)):
            is_health_based = np.random.choice(['Y', 'N'], p=[0.4, 0.6])
            violations_data.append({
                'SUBMISSIONYEARQUARTER': qtr,
                'PWSID': pwsid,
                'VIOLATION_ID': f'V-{np.random.randint(10000, 99999)}',
                'VIOLATION_CODE': f'V{np.random.randint(1, 5)}',
                'IS_HEALTH_BASED_IND': is_health_based,
                'CONTAMINANT_CODE': np.random.choice(
                    ['1022', '1030', '2950', '4000']) if is_health_based == 'Y' else 'MR1',
                'NON_COMPL_PER_BEGIN_DATE': '01/15/2025',
                'NON_COMPL_PER_END_DATE': np.random.choice([None, '03/10/2025'], p=[0.5, 0.5]),
                'VIOLATION_STATUS': 'Unaddressed' if pd.isnull(
                    violations_data[-1]['NON_COMPL_PER_END_DATE'] if violations_data else None) else 'Resolved',
                'ENFORCEMENT_ID': f'E-{np.random.randint(1000, 9999)}' if np.random.rand() > 0.5 else None,
                'ENFORCEMENT_ACTION_TYPE_CODE': 'FA01' if violations_data[-1]['ENFORCEMENT_ID'] else None,
                'ENFORCEMENT_DATE': '02/20/2025' if violations_data[-1]['ENFORCEMENT_ID'] else None
            })
    data['SDWA_VIOLATIONS_ENFORCEMENT'] = pd.DataFrame(violations_data)

    # --- SDWA_LCR_SAMPLES.csv ---
    lcr_data = []
    for pwsid in np.random.choice(georgia_pws_ids, size=10, replace=False):
        for contaminant, code, unit in [('Lead', '1030', 'mg/L'), ('Copper', '1022', 'mg/L')]:
            lcr_data.append({
                'SUBMISSIONYEARQUARTER': qtr,
                'PWSID': pwsid,
                'SAMPLE_ID': f'LCR-{np.random.randint(1000, 9999)}',
                'SAMPLING_END_DATE': '03/01/2025',
                'CONTAMINANT_CODE': code,
                'SAMPLE_MEASURE': round(
                    np.random.uniform(0.001, 0.025) if contaminant == 'Lead' else np.random.uniform(0.1, 1.5), 4),
                'UNIT_OF_MEASURE': unit,
            })
    data['SDWA_LCR_SAMPLES'] = pd.DataFrame(lcr_data)

    # --- SDWA_SITE_VISITS.csv ---
    visits_data = []
    for pwsid in np.random.choice(georgia_pws_ids, size=18, replace=False):
        visits_data.append({
            'SUBMISSIONYEARQUARTER': qtr,
            'PWSID': pwsid,
            'VISIT_ID': f'SV-{np.random.randint(1000, 9999)}',
            'VISIT_DATE': f'02/{np.random.randint(1, 28):02d}/2025',
            'VISIT_REASON_CODE': 'SS',
            'MANAGEMENT_OPS_EVAL_CODE': np.random.choice(['N', 'R', 'M', 'S'], p=[0.5, 0.3, 0.15, 0.05])
        })
    data['SDWA_SITE_VISITS'] = pd.DataFrame(visits_data)

    # --- SDWA_FACILITIES.csv ---
    facilities_data = []
    for pwsid in georgia_pws_ids:
        # Each system has a distribution system and a source
        facilities_data.append({
            'SUBMISSIONYEARQUARTER': qtr, 'PWSID': pwsid, 'FACILITY_ID': f'{pwsid}-DS',
            'FACILITY_NAME': 'Main Distribution System', 'FACILITY_TYPE_CODE': 'DS', 'IS_SOURCE_IND': 'N',
            'WATER_TYPE_CODE': None, 'SOURCE_WATER_PROTECTION_CODE': None
        })
        source_type = data['SDWA_PUB_WATER_SYSTEMS'].loc[
            data['SDWA_PUB_WATER_SYSTEMS']['PWSID'] == pwsid, 'PRIMARY_SOURCE_CODE'].iloc[0]
        fac_type = 'WL' if 'G' in source_type else 'IN'  # Well or Intake
        water_type = 'GW' if 'G' in source_type else 'SW'
        facilities_data.append({
            'SUBMISSIONYEARQUARTER': qtr, 'PWSID': pwsid, 'FACILITY_ID': f'{pwsid}-SRC1',
            'FACILITY_NAME': f'Primary Source - {fac_type}', 'FACILITY_TYPE_CODE': fac_type, 'IS_SOURCE_IND': 'Y',
            'WATER_TYPE_CODE': water_type, 'SOURCE_WATER_PROTECTION_CODE': np.random.choice(['Y', 'N'])
        })
    data['SDWA_FACILITIES'] = pd.DataFrame(facilities_data)

    # --- SDWA_GEOGRAPHIC_AREAS.csv ---
    geo_data = []
    for i, pwsid in enumerate(georgia_pws_ids):
        geo_data.append({
            'SUBMISSIONYEARQUARTER': qtr, 'PWSID': pwsid, 'GEO_ID': f'G-{pwsid}-CITY',
            'AREA_TYPE_CODE': 'CT', 'CITY_SERVED': cities[i % len(cities)]
        })
        geo_data.append({
            'SUBMISSIONYEARQUARTER': qtr, 'PWSID': pwsid, 'GEO_ID': f'G-{pwsid}-COUNTY',
            'AREA_TYPE_CODE': 'CN', 'COUNTY_SERVED': counties[i % len(counties)]
        })
    data['SDWA_GEOGRAPHIC_AREAS'] = pd.DataFrame(geo_data)

    # --- SDWA_REF_CODE_VALUES.csv ---
    ref_codes = [
        {'VALUE_TYPE': 'CONTAMINANT_CODE', 'VALUE_CODE': '1022', 'VALUE_DESCRIPTION': 'Copper'},
        {'VALUE_TYPE': 'CONTAMINANT_CODE', 'VALUE_CODE': '1030', 'VALUE_DESCRIPTION': 'Lead'},
        {'VALUE_TYPE': 'CONTAMINANT_CODE', 'VALUE_CODE': '2950', 'VALUE_DESCRIPTION': 'Total Trihalomethanes (TTHM)'},
        {'VALUE_TYPE': 'CONTAMINANT_CODE', 'VALUE_CODE': '4000', 'VALUE_DESCRIPTION': 'Arsenic'},
        {'VALUE_TYPE': 'CONTAMINANT_CODE', 'VALUE_CODE': 'MR1', 'VALUE_DESCRIPTION': 'Monitoring/Reporting Failure'},
        {'VALUE_TYPE': 'VIOLATION_CODE', 'VALUE_CODE': 'V1', 'VALUE_DESCRIPTION': 'MCL, Single Sample'},
        {'VALUE_TYPE': 'VIOLATION_CODE', 'VALUE_CODE': 'V2', 'VALUE_DESCRIPTION': 'MCL, Average'},
        {'VALUE_TYPE': 'VIOLATION_CODE', 'VALUE_CODE': 'V3', 'VALUE_DESCRIPTION': 'Treatment Technique'},
        {'VALUE_TYPE': 'VIOLATION_CODE', 'VALUE_CODE': 'V4', 'VALUE_DESCRIPTION': 'Monitoring & Reporting'},
        {'VALUE_TYPE': 'VISIT_REASON_CODE', 'VALUE_CODE': 'SS', 'VALUE_DESCRIPTION': 'Sanitary Survey'},
        {'VALUE_TYPE': 'ENFORCEMENT_ACTION_TYPE_CODE', 'VALUE_CODE': 'FA01',
         'VALUE_DESCRIPTION': 'Formal Administrative Order'},
        {'VALUE_TYPE': 'PRIMARY_SOURCE_CODE', 'VALUE_CODE': 'GW', 'VALUE_DESCRIPTION': 'Groundwater'},
        {'VALUE_TYPE': 'PRIMARY_SOURCE_CODE', 'VALUE_CODE': 'SW', 'VALUE_DESCRIPTION': 'Surface Water'},
        {'VALUE_TYPE': 'PRIMARY_SOURCE_CODE', 'VALUE_CODE': 'GWP', 'VALUE_DESCRIPTION': 'Purchased Groundwater'},
        {'VALUE_TYPE': 'PRIMARY_SOURCE_CODE', 'VALUE_CODE': 'SWP', 'VALUE_DESCRIPTION': 'Purchased Surface Water'},
        {'VALUE_TYPE': 'PRIMARY_SOURCE_CODE', 'VALUE_CODE': 'GU',
         'VALUE_DESCRIPTION': 'Groundwater under direct influence of surface water'},
    ]
    data['SDWA_REF_CODE_VALUES'] = pd.DataFrame(ref_codes)

    return data


data = load_mock_data()


# --- Helper Functions ---
def get_pws_name(pwsid):
    """Returns the name of a PWS from its ID."""
    if pwsid and pwsid in data['SDWA_PUB_WATER_SYSTEMS']['PWSID'].values:
        return data['SDWA_PUB_WATER_SYSTEMS'].loc[data['SDWA_PUB_WATER_SYSTEMS']['PWSID'] == pwsid, 'PWS_NAME'].iloc[0]
    return "Unknown System"


def get_code_description(value_type, value_code):
    """Looks up a description for a given code from the reference table."""
    ref_df = data['SDWA_REF_CODE_VALUES']
    desc = ref_df[(ref_df['VALUE_TYPE'] == value_type) & (ref_df['VALUE_CODE'] == value_code)]
    if not desc.empty:
        return desc['VALUE_DESCRIPTION'].iloc[0]
    return value_code


# --- Main App ---
st.title("Georgia Safe Drinking Water Act (SDWA) Dashboard")
st.markdown("Insights from the Q1 2025 SDWIS Data Export for the State of Georgia.")

# --- Sidebar Filters ---
st.sidebar.header("Filter by Water System")
# Create a mapping from PWSID to a more descriptive name for the selectbox
pws_options = data['SDWA_PUB_WATER_SYSTEMS'][['PWSID', 'PWS_NAME', 'CITY_NAME']].copy()
pws_options['display_name'] = pws_options['PWS_NAME'] + " (" + pws_options['CITY_NAME'] + ", " + pws_options[
    'PWSID'] + ")"
pws_display_map = pd.Series(pws_options.PWSID.values, index=pws_options.display_name).to_dict()

selected_pws_display = st.sidebar.selectbox(
    "Select a Public Water System:",
    options=pws_display_map.keys(),
    index=0
)
selected_pwsid = pws_display_map[selected_pws_display]

# Display high-level info for the selected system in the sidebar
pws_info = data['SDWA_PUB_WATER_SYSTEMS'].loc[data['SDWA_PUB_WATER_SYSTEMS']['PWSID'] == selected_pwsid].iloc[0]
st.sidebar.markdown("---")
st.sidebar.markdown(f"**System Name:** {pws_info['PWS_NAME']}")
st.sidebar.markdown(f"**PWSID:** {pws_info['PWSID']}")
st.sidebar.markdown(f"**Location:** {pws_info['CITY_NAME']}, GA")
st.sidebar.markdown(f"**Population Served:** {pws_info['POPULATION_SERVED_COUNT']:,}")
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
    st.header(f"Water Quality & Safety for: {pws_info['PWS_NAME']}")
    st.markdown("Review recent contaminant violations and lead/copper sample results.")

    # Filter data for selected PWS
    violations_df = data['SDWA_VIOLATIONS_ENFORCEMENT']
    pws_violations = violations_df[violations_df['PWSID'] == selected_pwsid]

    st.subheader("Recent Violations")
    if pws_violations.empty:
        st.success("No recent violations found for this water system in the Q1 2025 data.")
    else:
        # Create a more readable violations dataframe
        display_violations = pws_violations.copy()
        display_violations['Contaminant'] = display_violations['CONTAMINANT_CODE'].apply(
            lambda x: get_code_description('CONTAMINANT_CODE', x))
        display_violations['Violation Type'] = display_violations['VIOLATION_CODE'].apply(
            lambda x: get_code_description('VIOLATION_CODE', x))

        st.info(f"Found {len(display_violations)} violation(s) for this system.")

        for _, row in display_violations.iterrows():
            is_health_based = row['IS_HEALTH_BASED_IND'] == 'Y'
            violation_status = row['VIOLATION_STATUS']

            if is_health_based:
                st.error(f"**Health-Based Violation:** {row['Violation Type']} for **{row['Contaminant']}**", icon="⚠️")
            else:
                st.warning(f"**Non-Health-Based Violation:** {row['Violation Type']} for **{row['Contaminant']}**",
                           icon="📋")

            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown(f"**Status:** `{violation_status}`")
            with col2:
                st.markdown(f"**Period Start:** {row['NON_COMPL_PER_BEGIN_DATE']}")
            with col3:
                st.markdown(
                    f"**Period End:** {row['NON_COMPL_PER_END_DATE'] if row['NON_COMPL_PER_END_DATE'] else 'Ongoing'}")
            st.markdown("---")

    st.subheader("Lead and Copper Rule (LCR) Sample Results")
    lcr_df = data['SDWA_LCR_SAMPLES']
    pws_lcr = lcr_df[lcr_df['PWSID'] == selected_pwsid]

    if pws_lcr.empty:
        st.info("No Lead and Copper Rule sample data found for this system in Q1 2025.")
    else:
        lead_result = pws_lcr[pws_lcr['CONTAMINANT_CODE'] == '1030']
        copper_result = pws_lcr[pws_lcr['CONTAMINANT_CODE'] == '1022']

        col1, col2 = st.columns(2)
        with col1:
            st.metric(
                label="Lead 90th Percentile Sample",
                value=f"{lead_result['SAMPLE_MEASURE'].iloc[0]} {lead_result['UNIT_OF_MEASURE'].iloc[0]}" if not lead_result.empty else "N/A",
                help="EPA Action Level for Lead is 0.015 mg/L. This value is not the result from your tap, but a system-wide measure."
            )
        with col2:
            st.metric(
                label="Copper 90th Percentile Sample",
                value=f"{copper_result['SAMPLE_MEASURE'].iloc[0]} {copper_result['UNIT_OF_MEASURE'].iloc[0]}" if not copper_result.empty else "N/A",
                help="EPA Action Level for Copper is 1.3 mg/L. This value is not the result from your tap, but a system-wide measure."
            )
        st.caption(f"Samples taken during monitoring period ending {pws_lcr['SAMPLING_END_DATE'].iloc[0]}")

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
        st.metric("Total Violations (Q1 2025)", value=len(pws_violations))
    with col2:
        st.metric("Health-Based Violations", value=len(pws_violations[pws_violations['IS_HEALTH_BASED_IND'] == 'Y']))
    with col3:
        st.metric("Site Visits (Q1 2025)", value=len(pws_visits))

    st.subheader("Enforcement Actions")
    pws_enforcement = pws_violations[pws_violations['ENFORCEMENT_ID'].notna()]
    if pws_enforcement.empty:
        st.success("No enforcement actions found for this system in Q1 2025.")
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
        st.info("No site visits recorded for this system in Q1 2025.")
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

    st.info(f"**Primary Water Source:** {primary_source_desc} (`{primary_source_code}`)", icon="🚰")

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

    if "P" in primary_source_code:
        st.info(
            "This system **purchases** some or all of its water from another, larger water system (a wholesaler). The quality of the water delivered to you is dependent on the quality from the wholesale provider.",
            icon="🤝")

# --- Tab 4: Community Info ---
with tab4:
    st.header(f"Community Profile for: {pws_info['PWS_NAME']}")

    pws_geo = data['SDWA_GEOGRAPHIC_AREAS'][data['SDWA_GEOGRAPHIC_AREAS']['PWSID'] == selected_pwsid]

    cities_served = pws_geo[pws_geo['AREA_TYPE_CODE'] == 'CT']['CITY_SERVED'].tolist()
    counties_served = pws_geo[pws_geo['AREA_TYPE_CODE'] == 'CN']['COUNTY_SERVED'].tolist()

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
        st.success("This water system is designated as serving a school or daycare facility.", icon="🏫")
        st.markdown("Special attention is often given to these systems due to the vulnerable populations they serve.")
    else:
        st.info("This water system is not primarily designated as serving a school or daycare facility.", icon="🏢")

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

    **Across 10 CSV files, this directory includes a full Q1 2025 export of the SDWIS for the state of Georgia.** This README includes information on the File Structure, a Data Dictionary, as well as some (potentially) helpful external links at the bottom. 

    ---

    ## 💾 About the SDWIS
    The Safe Drinking Water Information System (SDWIS) contains information on public water systems, including monitoring, enforcement, and violation data related to requirements established by the Safe Drinking Water Act (SDWA). 

    ---

    ## 🗄️ File Structure
    Key fields for each table are listed in bold below. Key fields uniquely identify the records within each file, and may be used to join and relate data between files.

    *This section has been abridged for the dashboard. The full data dictionary provides detailed column descriptions.*

    - **SDWA_PUB_WATER_SYSTEMS.csv**: Core information about each public water system (PWS).
    - **SDWA_VIOLATIONS_ENFORCEMENT.csv**: Details on violations and associated enforcement actions.
    - **SDWA_LCR_SAMPLES.csv**: Lead and Copper Rule 90th-percentile sample results.
    - **SDWA_SITE_VISITS.csv**: Records of inspections and sanitary surveys.
    - **SDWA_FACILITIES.csv**: Information on physical facilities like treatment plants and wells.
    - **SDWA_GEOGRAPHIC_AREAS.csv**: Links water systems to the cities and counties they serve.
    - **SDWA_REF_CODE_VALUES.csv**: A reference table to look up descriptions for various codes.
    - ... and other supplementary files.

    ---

    ## 📘 Data Element Dictionary
    The following is a list of the data elements and SDWIS-derived elements that appear in the ECHO SDWA download. The data elements are listed alphabetically by data element name.

    *Abridged for brevity. The original document contains over 100 field definitions.*

    **PWSID** - A unique identifying code for a public water system in SDWIS. The PWSID consists of a two-letter state or region code, followed by seven digits.

    **PWS_NAME** - Name of the public water system.

    **VIOLATION_CODE** - A code value that represents a contaminant for which a public water system has incurred a violation of a primary drinking water regulation.

    **CONTAMINANT_CODE** - A code value that represents a contaminant for which a public water system has incurred a violation of a primary drinking water regulation.

    **IS_HEALTH_BASED_IND** - Indicates if this is a health based violation. Valid values are Y (yes) or N (no).

    **ENFORCEMENT_ACTION_TYPE_CODE** - A designated attribute which indicates the coded type of enforcement follow up action was taken by a federal or state agency.

    ---

    ## 🔗 Extra Reference Links
    - [EPA Drinking Water Data & Tools Guide](https://www.epa.gov/DWdata/drinking-water-data-tools-guide)
    - [EPA National Primary Drinking Water Regulations](https://www.epa.gov/ground-water-and-drinking-water/national-primary-drinking-water-regulations)
    - [SDWIS Search User Guide](https://www.epa.gov/enviro/sdwis-search-user-guide)
    """
    st.markdown(readme_content)

