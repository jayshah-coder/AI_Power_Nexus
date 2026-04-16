import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
from datetime import datetime

# --- PAGE SETUP ---
st.set_page_config(page_title="The AI Power Nexus", layout="wide")
st.title("The AI Power Nexus: 2026-2030")
st.markdown("Simulate the physical grid impact and societal cost of human-driven AI demand using live grid data.")

# --- 1. DATA CONNECTIONS (GOOGLE SHEETS & API) ---
SHEET_ID = "1oRgI3uZP8WINBRU6GfybW0K8BUvoz2YHXuQ0Y02QLCY"
EIA_API_KEY = "egUujavB2YGwnp3NE2Wa6qgJzLzHkWPJXVEZ3FDn"

@st.cache_data(ttl=600)
def load_master_log(sheet_id):
    # Fetch the flat CSV from the single sheet
    base_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv"
    raw_df = pd.read_csv(base_url, header=None)
    
    def extract_by_header(col0_name):
        # Scan the first column for the exact header we need
        matches = raw_df[raw_df[0].astype(str).str.strip() == col0_name]
        if matches.empty:
            return pd.DataFrame() # Return empty if not found
        
        start_idx = matches.index[0]
        table_rows = [raw_df.iloc[start_idx].values] # Grab the header row
        
        # Grab all rows below the header until we hit a blank space or a new section
        for i in range(start_idx + 1, len(raw_df)):
            val = str(raw_df.iloc[i, 0]).strip()
            if val == '' or val.lower() == 'nan' or val.startswith('TAB:'):
                break
            table_rows.append(raw_df.iloc[i].values)
        
        # Convert to DataFrame and clean up
        df = pd.DataFrame(table_rows)
        df.columns = df.iloc[0].astype(str).str.strip() # Set headers
        df = df[1:].reset_index(drop=True) # Drop the header row from the data
        return df

    # Dynamically hunt down the specific tables
    df_demo = extract_by_header('State')
    df_tech = extract_by_header('Technology')
    df_benchmarks = extract_by_header('Archetype')
    df_globals = extract_by_header('Variable_Name')
    
    # Clean the demographic percentages safely
    for col in ['Pop_Share_Pct', 'Addressable_Age_Pct', 'AI_Adoption_Pct', 'Casual_Pct', 'Thinker_Pct', 'Creator_Pct', 'Architect_Pct']:
        if col in df_demo.columns:
            df_demo[col] = df_demo[col].astype(str).str.replace('%', '', regex=False).astype(float) / 100.0
            
    # Convert benchmark numbers safely
    for col in ['Tasks_Per_Day', 'Energy_Per_Task_Wh', 'Cooling_Tax_PUE']:
        if col in df_benchmarks.columns:
            df_benchmarks[col] = pd.to_numeric(df_benchmarks[col], errors='coerce')
            
    # Convert tech cost numbers safely
    for col in ['LCOE_USD_per_MWh', 'Est_CAPEX_per_MW', 'Nameplate_Multiplier']:
        if col in df_tech.columns:
            df_tech[col] = pd.to_numeric(df_tech[col], errors='coerce')
            
    return df_demo, df_tech, df_benchmarks, df_globals

try:
    df_demo, df_tech, df_benchmarks, df_globals = load_master_log(SHEET_ID)
except Exception as e:
    st.error(f"Error fetching data. Error: {e}")
    st.stop()

# Safety Check
if df_demo.empty:
    st.error("Could not parse State Demographics from the Master Log. Please check the Google Sheet.")
    st.stop()

# Extract Global Variables safely with fallbacks so the app never crashes
try:
    TOTAL_US_POP = float(df_globals.loc[df_globals['Variable_Name'] == 'Total_US_Internet_Pop', 'Value'].values[0])
except:
    TOTAL_US_POP = 330000000.0

try:
    SOCIAL_CARBON_COST = float(df_globals.loc[df_globals['Variable_Name'] == 'Social_Cost_Carbon', 'Value'].values[0])
except:
    SOCIAL_CARBON_COST = 200.0

# --- 2. SIDEBAR: STATE SELECTION & DEMOGRAPHICS ---
st.sidebar.header("1. Geographic Simulation")
selected_state = st.sidebar.selectbox("Select Target State", df_demo['State'].tolist())

# Get state specific data
state_data = df_demo[df_demo['State'] == selected_state].iloc[0]

# Demographic Waterfall Calculation
state_pop = TOTAL_US_POP * state_data['Pop_Share_Pct']
addressable_pop = state_pop * state_data['Addressable_Age_Pct']

st.sidebar.subheader("AI Adoption Tracker")
# Allow user to override the 2026 baseline adoption
adoption_rate = st.sidebar.slider(
    "Active AI Users (%)", 
    min_value=0.1, max_value=1.0, 
    value=float(state_data['AI_Adoption_Pct']), 
    format="%.2f"
)

active_ai_users = addressable_pop * adoption_rate
st.sidebar.markdown(f"**Total AI Users Simulated:** {active_ai_users:,.0f}")

with st.sidebar.expander("User Archetype Mix (State Default)"):
    casual_pct = st.slider("Casual", 0.0, 1.0, float(state_data['Casual_Pct']))
    thinker_pct = st.slider("Thinker", 0.0, 1.0, float(state_data['Thinker_Pct']))
    creator_pct = st.slider("Creator", 0.0, 1.0, float(state_data['Creator_Pct']))
    architect_pct = st.slider("Architect", 0.0, 1.0, float(state_data['Architect_Pct']))

# --- 3. MATH ENGINE: LOAD CURVE CALCULATION ---
# Map the Energy Benchmarks from the sheet
try:
    energy_costs = {
        str(row['Archetype']).split()[0]: row['Energy_Per_Task_Wh'] * row['Tasks_Per_Day'] 
        for _, row in df_benchmarks.iterrows()
    }
    pue_tax = float(df_benchmarks['Cooling_Tax_PUE'].iloc[0])
except:
    energy_costs = {'Casual': 3.0, 'Thinker': 25.0, 'Creator': 300.0, 'Architect': 75.0}
    pue_tax = 1.15

# Standard 24-hour distribution curve
base_activity_curve = np.array([
    0.05, 0.02, 0.01, 0.01, 0.02, 0.05, 0.15, 0.40, 0.70, 0.90, 
    1.00, 1.00, 0.95, 0.90, 0.95, 0.90, 0.80, 0.75, 0.80, 0.85, 
    0.90, 0.60, 0.30, 0.10
])
base_activity_curve = base_activity_curve / np.sum(base_activity_curve)

archetype_mix = {
    'Casual': casual_pct, 'Thinker': thinker_pct, 
    'Creator': creator_pct, 'Architect': architect_pct
}

daily_mw_load = np.zeros(24)
for arch, pct in archetype_mix.items():
    users = active_ai_users * pct
    daily_wh = users * energy_costs.get(arch, 0)
    daily_mwh_total = (daily_wh / 1_000_000) * pue_tax
    daily_mw_load += (daily_mwh_total * base_activity_curve)

peak_ai_mw = daily_mw_load.max()
total_daily_mwh = daily_mw_load.sum()

# --- 4. LIVE GRID INTEGRATION (EIA API) ---
ba_mapping = {
    'California': 'CISO', 'Texas': 'ERCO', 'Florida': 'FPL',
    'New York': 'NYIS', 'Pennsylvania': 'PJM', 'Illinois': 'MISO',
    'Ohio': 'PJM', 'Georgia': 'SOCO', 'North Carolina': 'DUK',
    'Michigan': 'MISO', 'Massachusetts': 'ISNE', 'New Jersey': 'PJM'
}
region_code = ba_mapping.get(selected_state, 'PJM')

@st.cache_data(ttl=3600)
def fetch_eia_grid_data(api_key, region):
    url = f"https://api.eia.gov/v2/electricity/rto/region-data/data/?api_key={api_key}&frequency=hourly&data[0]=value&facets[respondent][]={region}&sort[0][column]=period&sort[0][direction]=desc&length=24"
    try:
        response = requests.get(url, timeout=10).json()
        values = [float(item['value']) for item in response['response']['data']]
        if len(values) == 24:
            return values[::-1]
    except:
        pass
    return [78000, 76000, 75000, 74500, 75000, 77000, 81000, 85000, 88000, 89000,
            90000, 91000, 91500, 91000, 90500, 90000, 91000, 93000, 95000, 94000,
            91000, 88000, 84000, 80000]

baseline_grid = fetch_eia_grid_data(EIA_API_KEY, region_code)

df_plot = pd.DataFrame({
    'Hour': [f"{i}:00" for i in range(24)],
    'Baseline Grid (MW)': baseline_grid,
    'AI Demand (MW)': daily_mw_load
})
df_plot['Total Load'] = df_plot['Baseline Grid (MW)'] + df_plot['AI Demand (MW)']

# --- 5. TOP METRICS & VISUALIZATION ---
col1, col2, col3 = st.columns(3)
col1.metric(f"State AI Demand Peak", f"{peak_ai_mw:,.0f} MW")
col2.metric("Total Daily Energy", f"{total_daily_mwh:,.0f} MWh")
col3.metric(f"Grid Stress ({region_code})", f"{((df_plot['Total Load'].max() - max(baseline_grid)) / max(baseline_grid) * 100):.2f}%")

st.subheader(f"Live 24-Hour Peak Collision: {selected_state} ({region_code})")
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=df_plot['Hour'], y=df_plot['Baseline Grid (MW)'], mode='lines', name='Actual Grid Load',
    stackgroup='one', line=dict(width=0, color='rgb(131, 192, 238)')
))
fig.add_trace(go.Scatter(
    x=df_plot['Hour'], y=df_plot['AI Demand (MW)'], mode='lines', name='Added AI Load',
    stackgroup='one', line=dict(width=0, color='rgb(255, 99, 71)')
))
fig.update_layout(hovermode='x unified', template='plotly_white', height=400, margin=dict(l=0, r=0, t=30, b=0))
st.plotly_chart(fig, use_container_width=True)

# --- 6. SOCIETAL COST CALCULATOR ---
st.subheader("Societal Cost & Infrastructure Trade-offs")

results = []
annual_mwh = total_daily_mwh * 365

for _, row in df_tech.iterrows():
    try:
        tech_name = row['Technology']
        carbon_rate = 0 if "Nuclear" in tech_name or "Solar" in tech_name else 430
        water_rate = 600 if "Nuclear" in tech_name else (20 if "Solar" in tech_name else 250)
        
        annual_cost = annual_mwh * row['LCOE_USD_per_MWh']
        annual_water = annual_mwh * water_rate
        annual_carbon_tons = (annual_mwh * carbon_rate) / 1000
        social_cost = annual_carbon_tons * SOCIAL_CARBON_COST
        installed_mw_needed = peak_ai_mw * row['Nameplate_Multiplier']
        est_capex = installed_mw_needed * row['Est_CAPEX_per_MW']
        
        results.append({
            "Power Source": tech_name,
            "Req. Capacity (MW)": installed_mw_needed,
            "Est. CAPEX ($B)": est_capex / 1_000_000_000,
            "Direct Energy Cost ($M)": annual_cost / 1_000_000,
            "Social Carbon Cost ($M)": social_cost / 1_000_000,
            "Total Societal Cost ($M)": (annual_cost + social_cost) / 1_000_000,
            "Water Usage (M Gallons)": annual_water / 1_000_000
        })
    except:
        pass # Skip row if data is corrupted

if results:
    st.dataframe(
        pd.DataFrame(results).style.format({
            "Req. Capacity (MW)": "{:,.0f}",
            "Est. CAPEX ($B)": "${:,.2f}",
            "Direct Energy Cost ($M)": "${:,.1f}",
            "Social Carbon Cost ($M)": "${:,.1f}",
            "Total Societal Cost ($M)": "${:,.1f}",
            "Water Usage (M Gallons)": "{:,.1f}"
        }),
        use_container_width=True
    )
