import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# --- PAGE SETUP ---
st.set_page_config(page_title="2030 AI Power Nexus", layout="wide")
st.title("AI Power Nexus: 2030 Summer Peak Simulation")
st.markdown("### Modeling the Shift from 'Search' to 'Inference-Heavy' Agentic Workloads")

# --- 1. DATA CONNECTIONS (Using V4 Log) ---
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

df_demo, df_globals = load_master_log(SHEET_ID)

# --- 2. SIDEBAR: GEOGRAPHY & ADOPTION ---
st.sidebar.header("1. 2030 Population & Adoption")
if not df_demo.empty:
    selected_state = st.sidebar.selectbox("Select Target State", df_demo.iloc[:, 0].tolist())
    s_row = df_demo[df_demo.iloc[:, 0] == selected_state].iloc[0]
    pop_share = float(str(s_row.iloc[1]).replace('%','')) / 100.0 if '%' in str(s_row.iloc[1]) else float(s_row.iloc[1])
    age_pct   = float(str(s_row.iloc[2]).replace('%','')) / 100.0 if '%' in str(s_row.iloc[2]) else float(s_row.iloc[2])
else:
    selected_state, pop_share, age_pct = "New Jersey", 0.028, 0.75

total_us_pop = 340_000_000 # 2030 Projection
adoption_rate = st.sidebar.slider("AI Adoption Rate (2030)", 0.1, 1.0, 0.85)
state_users = total_us_pop * pop_share * age_pct * adoption_rate

# --- 3. SIDEBAR: ARCHETYPE MIX ---
st.sidebar.header("2. Archetype Mix (%)")
st.sidebar.caption("Define the user base. 'Searcher' is the remainder.")

thinker_pct = st.sidebar.slider("The Thinker (Reasoning)", 0, 100, 25)
creator_pct = st.sidebar.slider("The Creator (Video/Agent)", 0, (100 - thinker_pct), 15)
searcher_pct = 100 - (thinker_pct + creator_pct)

st.sidebar.info(f"The Searcher (Baseline): {searcher_pct}%")

# --- 4. SIDEBAR: USAGE INTENSITY ---
st.sidebar.header("3. Query Volume (Queries/Day)")
q_searcher = st.sidebar.slider("Searcher Daily Queries", 1, 300, 80)
q_thinker = st.sidebar.slider("Thinker Daily Queries", 1, 200, 40)
q_creator = st.sidebar.slider("Creator Daily Queries", 1, 100, 15)

# Fixed 2030 Efficiency Constants
WH_SEARCHER = 0.3
WH_THINKER = 15.0
WH_CREATOR = 100.0
PUE_2030 = 1.12 # Optimized data center cooling

# Training Cluster Baseload (MW) - Constant 24/7 load
training_baseload = st.sidebar.number_input("State Training Baseload (MW)", 0, 10000, 1200)

# --- 5. CALCULATIONS ---
# Segment users
u_searcher = state_users * (searcher_pct / 100.0)
u_thinker  = state_users * (thinker_pct / 100.0)
u_creator  = state_users * (creator_pct / 100.0)

# Daily MWh per category
mwh_searcher = (u_searcher * q_searcher * WH_SEARCHER * PUE_2030) / 1_000_000
mwh_thinker  = (u_thinker * q_thinker * WH_THINKER * PUE_2030) / 1_000_000
mwh_creator  = (u_creator * q_creator * WH_CREATOR * PUE_2030) / 1_000_000

# Hourly distribution (Peak during evening hours 6PM-10PM)
inference_curve = np.array([0.05, 0.02, 0.01, 0.01, 0.02, 0.05, 0.15, 0.40, 0.70, 0.90, 1.00, 1.05, 1.10, 1.05, 1.10, 1.15, 1.20, 1.30, 1.40, 1.35, 1.20, 0.90, 0.50, 0.20])
inference_curve = inference_curve / np.sum(inference_curve)

hourly_ai_mw = (mwh_searcher + mwh_thinker + mwh_creator) * inference_curve + training_baseload

# 2030 Summer Peak Grid Load (Simulated for high A/C usage)
grid_base = np.array([72000, 70000, 68000, 67500, 69000, 73000, 78000, 84000, 89000, 93000, 97000, 101000, 105000, 108000, 110500, 112000, 113000, 111000, 106000, 99000, 93000, 86000, 80000, 75000])

# --- 6. VISUALIZATION ---
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader(f"2030 Summer Peak Simulation: {selected_state}")
    fig = go.Figure()
    fig.add_trace(go.Scatter(y=grid_base, name="Base Grid (Summer Heat)", stackgroup='one', fillcolor='rgba(131, 192, 238, 0.4)', line=dict(width=0)))
    fig.add_trace(go.Scatter(y=hourly_ai_mw, name="AI Load (Training + Inference)", stackgroup='one', fillcolor='rgba(255, 99, 71, 0.8)', line=dict(width=0)))
    fig.update_layout(yaxis_title="Megawatts (MW)", xaxis_title="Hour of Day", hovermode="x unified", template="plotly_white")
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.markdown("### Grid Impact Metrics")
    st.metric("Peak AI Demand", f"{hourly_ai_mw.max():,.0f} MW")
    st.metric("Daily Energy Usage", f"{(total_daily_energy := hourly_ai_mw.sum()):,.0f} MWh")
    st.metric("Grid Stress Increase", f"{(hourly_ai_mw.max() / grid_base.max() * 100):.2f}%")
    
    with st.expander("Energy Share by Archetype"):
        st.write(f"**Searchers:** {mwh_searcher:,.0f} MWh")
        st.write(f"**Thinkers:** {mwh_thinker:,.0f} MWh")
        st.write(f"**Creators:** {mwh_creator:,.0f} MWh")
        st.write(f"**Training:** {training_baseload * 24:,.0f} MWh")

# --- 7. INFRASTRUCTURE TABLE ---
st.subheader("2030 Asset Deployment Requirements")
st.markdown("Required capacity to firm this load without triggering brownouts.")
infra_df = pd.DataFrame([
    {"Power Source": "Small Modular Reactors (SMR)", "Capacity (MW)": f"{hourly_ai_mw.max() * 1.05:,.0f}", "Est. Cost ($B)": f"${(hourly_ai_mw.max() * 8.5) / 1000:,.2f}"},
    {"Power Source": "Combined Cycle Gas (CCGT)", "Capacity (MW)": f"{hourly_ai_mw.max() * 1.10:,.0f}", "Est. Cost ($B)": f"${(hourly_ai_mw.max() * 1.4) / 1000:,.2f}"},
    {"Power Source": "Solar + 8hr Battery Storage", "Capacity (MW)": f"{hourly_ai_mw.max() * 4.5:,.0f}", "Est. Cost ($B)": f"${(hourly_ai_mw.max() * 3.2) / 1000:,.2f}"}
])
st.table(infra_df)
