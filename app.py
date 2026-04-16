import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests

# --- PAGE SETUP ---
st.set_page_config(page_title="The AI Power Nexus", layout="wide")
st.title("The AI Power Nexus: 2026-2030")
st.markdown("Simulate the physical grid impact and societal cost of human-driven AI demand.")

# --- 1. DATA CONNECTIONS ---
SHEET_ID = "1oRgI3uZP8WINBRU6GfybW0K8BUvoz2YHXuQ0Y02QLCY"
EIA_API_KEY = "egUujavB2YGwnp3NE2Wa6qgJzLzHkWPJXVEZ3FDn"

@st.cache_data(ttl=600)
def load_master_log(sheet_id):
    base_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv"
    raw_df = pd.read_csv(base_url, header=None)
    
    def extract_table(header_marker):
        # Find row where the first cell matches our header marker
        matches = raw_df[raw_df[0].astype(str).str.strip() == header_marker]
        if matches.empty: return pd.DataFrame()
        
        start = matches.index[0]
        rows = []
        for i in range(start, len(raw_df)):
            val = str(raw_df.iloc[i, 0]).strip().lower()
            if i > start and (val == '' or val == 'nan' or val.startswith('tab:')):
                break
            rows.append(raw_df.iloc[i].values)
            
        df = pd.DataFrame(rows)
        df.columns = df.iloc[0].astype(str).str.strip()
        df = df[1:].dropna(axis=1, how='all').reset_index(drop=True)
        return df

    return extract_table('State'), extract_table('Technology'), extract_table('Archetype'), extract_table('Variable_Name')

# Attempt Load
try:
    df_demo, df_tech, df_benchmarks, df_globals = load_master_log(SHEET_ID)
except:
    st.error("Connection to Master Log failed. Using built-in defaults.")
    df_demo = pd.DataFrame()

# --- 2. FALLBACKS & DATA CLEANING ---
# If the sheet fails, we use these constants to keep the app alive
if df_demo.empty:
    st.warning("Master Log formatting issue detected. Loading default 2026 constants.")
    TOTAL_US_POP = 330000000.0
    SOCIAL_COST = 200.0
    states_list = ["New Jersey", "New York", "California", "Texas", "Massachusetts"]
    # Mocking a basic structure for the fallbacks
    state_data_defaults = {'New Jersey': [0.028, 0.75, 0.50, 0.60, 0.20, 0.10, 0.10]}
else:
    # Safe Extraction of Globals
    try:
        TOTAL_US_POP = float(df_globals.loc[df_globals['Variable_Name'].str.contains('Pop', na=False), 'Value'].values[0].replace(',', ''))
    except: TOTAL_US_POP = 330000000.0
    
    try:
        SOCIAL_COST = float(df_globals.loc[df_globals['Variable_Name'].str.contains('Carbon', na=False), 'Value'].values[0])
    except: SOCIAL_COST = 200.0
    
    states_list = df_demo['State'].tolist()

# --- 3. SIDEBAR ---
st.sidebar.header("1. Geographic Simulation")
selected_state = st.sidebar.selectbox("Select Target State", states_list)

if not df_demo.empty:
    s_row = df_demo[df_demo['State'] == selected_state].iloc[0]
    # Helper to clean percentages
    def p2f(x): return float(str(x).replace('%','')) / 100.0 if '%' in str(x) else float(x)
    
    pop_share = p2f(s_row['Pop_Share_Pct'])
    age_pct = p2f(s_row['Addressable_Age_Pct'])
    adopt_pct = p2f(s_row['AI_Adoption_Pct'])
    c_pct, t_pct, cr_pct, a_pct = p2f(s_row['Casual_Pct']), p2f(s_row['Thinker_Pct']), p2f(s_row['Creator_Pct']), p2f(s_row['Architect_Pct'])
else:
    # Hard fallback numbers
    pop_share, age_pct, adopt_pct = 0.03, 0.75, 0.50
    c_pct, t_pct, cr_pct, a_pct = 0.60, 0.20, 0.10, 0.10

adoption_rate = st.sidebar.slider("AI Adoption Rate", 0.1, 1.0, adopt_pct)
active_users = TOTAL_US_POP * pop_share * age_pct * adoption_rate

st.sidebar.markdown(f"**Target Users:** {active_users:,.0f}")

# --- 4. GRID & CHART ---
# Standard hourly curve
curve = np.array([0.05, 0.02, 0.01, 0.01, 0.02, 0.05, 0.15, 0.40, 0.70, 0.90, 1.00, 1.00, 0.95, 0.90, 0.95, 0.90, 0.80, 0.75, 0.80, 0.85, 0.90, 0.60, 0.30, 0.10])
curve = curve / np.sum(curve)

# Simplified Demand Math for stability
daily_mwh = (active_users * 15 * 1.15) / 1_000_000 # Average 15Wh per user/day
hourly_ai_mw = daily_mwh * curve

# Mock Grid (Pulled from logic in previous steps)
grid_base = np.array([78000, 76000, 75000, 74500, 75000, 77000, 81000, 85000, 88000, 89000, 90000, 91000, 91500, 91000, 90500, 90000, 91000, 93000, 95000, 94000, 91000, 88000, 84000, 80000])

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader(f"24-Hour Grid Impact: {selected_state}")
    fig = go.Figure()
    fig.add_trace(go.Scatter(y=grid_base, name="Base Grid", stackgroup='one', fillcolor='rgba(131, 192, 238, 0.5)', line=dict(width=0)))
    fig.add_trace(go.Scatter(y=hourly_ai_mw, name="AI Load", stackgroup='one', fillcolor='rgba(255, 99, 71, 0.8)', line=dict(width=0)))
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.metric("Peak AI Demand", f"{hourly_ai_mw.max():,.0f} MW")
    st.metric("Daily Energy Consumed", f"{daily_mwh:,.0f} MWh")
    st.metric("Grid Stress Increase", f"{(hourly_ai_mw.max()/grid_base.max()*100):.2f}%")

# --- 5. INFRASTRUCTURE TABLE ---
st.subheader("Infrastructure Deployment Requirements")
infra_data = [
    {"Tech": "SMR (Nuclear)", "Capacity Needed": hourly_ai_mw.max() * 1.05, "Cost ($B)": (hourly_ai_mw.max() * 8.0) / 1000},
    {"Tech": "Natural Gas", "Capacity Needed": hourly_ai_mw.max() * 1.10, "Cost ($B)": (hourly_ai_mw.max() * 1.2) / 1000},
    {"Tech": "Solar + Storage", "Capacity Needed": hourly_ai_mw.max() * 3.50, "Cost ($B)": (hourly_ai_mw.max() * 2.5) / 1000}
]
st.table(pd.DataFrame(infra_data))
