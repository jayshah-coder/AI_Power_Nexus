import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# --- PAGE SETUP ---
st.set_page_config(page_title="The AI Power Nexus", layout="wide")
st.title("The AI Power Nexus: 2026-2030")

# --- 1. DATA CONNECTIONS ---
SHEET_ID = "1oRgI3uZP8WINBRU6GfybW0K8BUvoz2YHXuQ0Y02QLCY"

@st.cache_data(ttl=300)
def load_master_log(sheet_id):
    base_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv"
    raw_df = pd.read_csv(base_url, header=None)
    
    def extract_table(header_marker):
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
        df.columns = df.iloc[0] # Temporary columns
        return df[1:].reset_index(drop=True)

    return extract_table('State'), extract_table('Variable_Name')

# Attempt Load
df_demo, df_globals = load_master_log(SHEET_ID)

# --- 2. THE FAIL-SAFE DEFAULTS ---
# If extraction fails, these are the emergency numbers
TOTAL_US_POP = 330000000.0
ADOPT_BASE = 0.50

# --- 3. SIDEBAR & LOGIC ---
st.sidebar.header("Geographic Simulation")

if not df_demo.empty:
    # Use position rather than name to avoid KeyError
    # Col 0: State, Col 1: Pop Share, Col 2: Age Pct, Col 3: Adoption
    states_list = df_demo.iloc[:, 0].tolist()
    selected_state = st.sidebar.selectbox("Select Target State", states_list)
    
    s_row = df_demo[df_demo.iloc[:, 0] == selected_state].iloc[0]
    
    def clean_val(val):
        try:
            return float(str(val).replace('%','').strip()) / 100.0 if '%' in str(val) else float(val)
        except: return 0.0

    pop_share = clean_val(s_row.iloc[1])
    age_pct   = clean_val(s_row.iloc[2])
    adopt_val = clean_val(s_row.iloc[3])
else:
    st.sidebar.warning("Using built-in demo data.")
    selected_state = "New Jersey (Demo)"
    pop_share, age_pct, adopt_val = 0.028, 0.75, 0.50

adoption_rate = st.sidebar.slider("AI Adoption Rate", 0.1, 1.0, adopt_val)
active_users = TOTAL_US_POP * pop_share * age_pct * adoption_rate

st.sidebar.metric("Target AI Users", f"{active_users:,.0f}")

# --- 4. CALCULATIONS & CHART ---
# Standard hourly curve
curve = np.array([0.05, 0.02, 0.01, 0.01, 0.02, 0.05, 0.15, 0.40, 0.70, 0.90, 1.00, 1.00, 0.95, 0.90, 0.95, 0.90, 0.80, 0.75, 0.80, 0.85, 0.90, 0.60, 0.30, 0.10])
curve = curve / np.sum(curve)

# Average 15Wh per user/day baseline
daily_mwh = (active_users * 15 * 1.15) / 1_000_000 
hourly_ai_mw = daily_mwh * curve
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
    st.metric("Daily Energy", f"{daily_mwh:,.0f} MWh")
    st.metric("Grid Stress Increase", f"{(hourly_ai_mw.max()/grid_base.max()*100):.2f}%")

# --- 5. INFRASTRUCTURE TABLE ---
st.subheader("Infrastructure Requirements")
infra_data = [
    {"Power Source": "SMR (Nuclear)", "Capacity Needed (MW)": f"{hourly_ai_mw.max() * 1.05:,.0f}", "Est. Cost ($B)": f"${(hourly_ai_mw.max() * 8.0) / 1000:,.2f}"},
    {"Power Source": "Natural Gas", "Capacity Needed (MW)": f"{hourly_ai_mw.max() * 1.10:,.0f}", "Est. Cost ($B)": f"${(hourly_ai_mw.max() * 1.2) / 1000:,.2f}"},
    {"Power Source": "Solar + Storage", "Capacity Needed (MW)": f"{hourly_ai_mw.max() * 3.50:,.0f}", "Est. Cost ($B)": f"${(hourly_ai_mw.max() * 2.5) / 1000:,.2f}"}
]
st.table(infra_data)

if st.sidebar.checkbox("Show Raw Data Debugger"):
    st.write("Demographics Table (Extracted):", df_demo)
