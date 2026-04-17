import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# --- PAGE SETUP ---
st.set_page_config(page_title="The AI Power Nexus: 2030", layout="wide")
st.title("The AI Power Nexus: 2030 Peak Simulation")

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
        df.columns = df.iloc[0] 
        return df[1:].reset_index(drop=True)

    return extract_table('State'), extract_table('Variable_Name')

# Attempt Load
df_demo, df_globals = load_master_log(SHEET_ID)

# --- 2. FAIL-SAFE DEFAULTS ---
TOTAL_US_POP = 340000000.0 # Adjusted for 2030 US Population estimate
ADOPT_BASE = 0.75 # 2030 default higher adoption

# --- 3. SIDEBAR & LOGIC ---
st.sidebar.header("1. Geographic Simulation")

if not df_demo.empty:
    states_list = df_demo.iloc[:, 0].tolist()
    selected_state = st.sidebar.selectbox("Select Target State", states_list)
    s_row = df_demo[df_demo.iloc[:, 0] == selected_state].iloc[0]
    
    def clean_val(val):
        try:
            return float(str(val).replace('%','').strip()) / 100.0 if '%' in str(val) else float(val)
        except: return 0.0

    pop_share = clean_val(s_row.iloc[1])
    age_pct   = clean_val(s_row.iloc[2])
else:
    st.sidebar.warning("Using built-in demo data.")
    selected_state = "California (Demo)"
    pop_share, age_pct = 0.117, 0.75

adoption_rate = st.sidebar.slider("AI Adoption Rate", 0.1, 1.0, ADOPT_BASE)
active_users = TOTAL_US_POP * pop_share * age_pct * adoption_rate

st.sidebar.metric("Target 2030 AI Users", f"{active_users:,.0f}")

st.sidebar.header("2. 2030 AI Usage Assumptions")
with st.sidebar.expander("Adjust Compute & Hardware Variables", expanded=True):
    daily_queries = st.slider("Avg Daily Queries per User", 10, 500, 100, help="Includes background agentic tasks.")
    wh_per_query = st.slider("Energy per Query (Wh)", 0.5, 100.0, 15.0, help="Text is ~0.3Wh. Image is ~3Wh. Video generation is ~50Wh.")
    pue = st.slider("Data Center PUE (Cooling)", 1.01, 1.50, 1.15)
    
    st.markdown("---")
    st.markdown("**Model Training**")
    training_baseload = st.slider("Dedicated Training Baseload (MW)", 0, 10000, 1500, help="Training runs 24/7. This represents the constant state-level draw for frontier model training clusters.")

# --- 4. CALCULATIONS & CHART ---
# Standard hourly curve for INFERENCE (Human activity peaks during the day/evening)
curve = np.array([0.05, 0.02, 0.01, 0.01, 0.02, 0.05, 0.15, 0.40, 0.70, 0.90, 1.00, 1.00, 0.95, 0.90, 0.95, 0.90, 0.80, 0.75, 0.80, 0.85, 0.90, 0.60, 0.30, 0.10])
curve = curve / np.sum(curve)

# Math: Calculate daily MWh for inference, then distribute across hours, then add constant training baseload
inference_daily_mwh = (active_users * daily_queries * wh_per_query * pue) / 1_000_000 
hourly_inference_mw = inference_daily_mwh * curve
hourly_ai_mw = hourly_inference_mw + training_baseload

total_daily_mwh = inference_daily_mwh + (training_baseload * 24)

# Simulated Summer Peak Grid (Higher afternoon/evening load to represent A/C usage)
grid_base = np.array([72000, 70000, 68000, 67500, 69000, 73000, 78000, 84000, 89000, 93000, 97000, 101000, 105000, 108000, 110500, 112000, 113000, 111000, 106000, 99000, 93000, 86000, 80000, 75000])

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader(f"Simulated Summer Peak Day: {selected_state}")
    fig = go.Figure()
    fig.add_trace(go.Scatter(y=grid_base, name="Base Grid (Summer Peak)", stackgroup='one', fillcolor='rgba(131, 192, 238, 0.5)', line=dict(width=0)))
    fig.add_trace(go.Scatter(y=hourly_ai_mw, name="AI Inference + Training Load", stackgroup='one', fillcolor='rgba(255, 99, 71, 0.8)', line=dict(width=0)))
    
    # Force y-axis to start at 0 and add a little headroom
    fig.update_layout(yaxis=dict(range=[0, max(grid_base + hourly_ai_mw) * 1.1]))
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.metric("Peak AI Demand (MW)", f"{hourly_ai_mw.max():,.0f}")
    st.metric("Total Daily Energy (MWh)", f"{total_daily_mwh:,.0f}")
    st.metric("Grid Stress Increase", f"{(hourly_ai_mw.max()/grid_base.max()*100):.2f}%")

# --- 5. INFRASTRUCTURE TABLE ---
st.subheader("2030 Infrastructure Requirements")
infra_data = [
    {"Power Source": "SMR (Nuclear)", "Capacity Needed (MW)": f"{hourly_ai_mw.max() * 1.05:,.0f}", "Est. CAPEX ($B)": f"${(hourly_ai_mw.max() * 8.0) / 1000:,.2f}"},
    {"Power Source": "Natural Gas", "Capacity Needed (MW)": f"{hourly_ai_mw.max() * 1.10:,.0f}", "Est. CAPEX ($B)": f"${(hourly_ai_mw.max() * 1.2) / 1000:,.2f}"},
    {"Power Source": "Solar + Storage", "Capacity Needed (MW)": f"{hourly_ai_mw.max() * 3.50:,.0f}", "Est. CAPEX ($B)": f"${(hourly_ai_mw.max() * 2.5) / 1000:,.2f}"}
]
st.table(infra_data)

if st.sidebar.checkbox("Show Raw Data Debugger"):
    st.write("Demographics Table (Extracted):", df_demo)
