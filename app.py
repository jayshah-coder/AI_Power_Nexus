import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# --- PAGE SETUP ---
st.set_page_config(page_title="2030 AI Power Nexus", layout="wide")
st.title("AI Power Nexus: 2030 Summer Peak Simulation")

# --- 1. DATA CONNECTIONS (V4 Master Log) ---
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
    # Helper to clean percentages or strings
    def clean(v): return float(str(v).replace('%','')) / 100.0 if '%' in str(v) else float(v)
    pop_share = clean(s_row.iloc[1])
    age_pct   = clean(s_row.iloc[2])
else:
    selected_state, pop_share, age_pct = "New Jersey", 0.028, 0.75

total_us_pop = 340_000_000 
adoption_rate = st.sidebar.slider("AI Adoption Rate (2030)", 0.1, 1.0, 0.85)
state_users = total_us_pop * pop_share * age_pct * adoption_rate

# --- 3. SIDEBAR: CONSTRAINED ARCHETYPE MIX ---
st.sidebar.header("2. Archetype Mix (%)")
st.sidebar.caption("Defines the user profile. 'Searcher' is the remainder.")

thinker_pct = st.sidebar.slider("The Thinker (Reasoning) %", 0, 100, 25)
creator_max = 100 - thinker_pct

# FIX: Conditional slider to prevent StreamlitAPIException when creator_max is 0
if creator_max > 0:
    creator_pct = st.sidebar.slider("The Creator (Video/Agent) %", 0, creator_max, min(15, creator_max))
else:
    st.sidebar.info("100% Thinker mix selected. No room for Creator.")
    creator_pct = 0

searcher_pct = 100 - (thinker_pct + creator_pct)
st.sidebar.info(f"The Searcher (Baseline): {searcher_pct}%")

# --- 4. SIDEBAR: USAGE INTENSITY ---
st.sidebar.header("3. Query Volume (Queries/Day)")
st.sidebar.caption("Default values represent 2030 industry projections.")
q_searcher = st.sidebar.slider("Searcher Daily Volume", 1, 300, 80)
q_thinker = st.sidebar.slider("Thinker Daily Volume", 1, 200, 40)
q_creator = st.sidebar.slider("Creator Daily Volume", 1, 100, 15)

# --- 5. INFRASTRUCTURE BASELOAD ---
st.sidebar.header("4. Infrastructure Baseload")
high_tier = ['Virginia', 'Texas', 'California', 'Ohio']
default_training = 3500 if selected_state in high_tier else 1200
st.sidebar.markdown(f"**Assumed 24/7 Training Load:** {default_training} MW")
st.sidebar.caption("Represents constant state-level draw for frontier model training clusters.")

# --- 6. CALCULATIONS ---
def get_curve(peak_hour, spread):
    x = np.arange(24)
    c = np.exp(-0.5 * ((x - peak_hour) / spread) ** 2)
    return c / np.sum(c)

# Archetype Curves
curve_search = get_curve(13, 4) 
curve_think = (get_curve(11, 2) + get_curve(15, 2)) / 2 
curve_create = get_curve(21, 3) # Creator peaks at 9 PM

# Energy Calculation
mwh_searcher = (state_users * (searcher_pct/100) * q_searcher * 0.3 * 1.12) / 1_000_000
mwh_thinker  = (state_users * (thinker_pct/100) * q_thinker * 15.0 * 1.12) / 1_000_000
mwh_creator  = (state_users * (creator_pct/100) * q_creator * 100.0 * 1.12) / 1_000_000

# Hourly Blended AI Load
hourly_ai_mw = (mwh_searcher * curve_search) + (mwh_thinker * curve_think) + (mwh_creator * curve_create) + default_training

# 2030 Summer Peak Grid Load (Simulated historical state peak)
grid_base = np.array([72000, 70000, 68000, 67500, 69000, 73000, 78000, 84000, 89000, 93000, 97000, 101000, 105000, 108000, 110500, 112000, 113000, 111000, 106000, 99000, 93000, 86000, 80000, 75000])

# --- 7. INFRASTRUCTURE OPTIONS & CARBON LOGIC ---
peak_hour_ai = np.argmax(hourly_ai_mw)
total_daily_energy = hourly_ai_mw.sum()
social_carbon_tax = 200 # EPA 2030 Estimate ($/ton)

# Logic: Solar/Storage sizing based on peak timing
# If the AI load peaks at night (e.g. Creator heavy), storage costs increase significantly
if peak_hour_ai >= 18 or peak_hour_ai <= 6:
    storage_multiplier = 1.9 # 90% premium for long-duration storage
    solar_label = "Solar + Storage (Evening Peak)"
else:
    storage_multiplier = 1.0
    solar_label = "Solar + Storage (Daytime Peak)"

infra_options = [
    {
        "Technology Pathway": "Modular Nuclear (SMR)",
        "Capacity Needed (MW)": hourly_ai_mw.max() * 1.05,
        "Est. CAPEX ($B)": (hourly_ai_mw.max() * 8.5) / 1000,
        "Annual Social Carbon Cost ($M)": 0,
        "Description": "24/7 zero-carbon baseload."
    },
    {
        "Technology Pathway": "Natural Gas (CCGT)",
        "Capacity Needed (MW)": hourly_ai_mw.max() * 1.10,
        "Est. CAPEX ($B)": (hourly_ai_mw.max() * 1.4) / 1000,
        "Annual Social Carbon Cost ($M)": (total_daily_energy * 365 * 0.430 * social_carbon_tax) / 1_000_000,
        "Description": "Fastest build, high carbon liability."
    },
    {
        "Technology Pathway": solar_label,
        "Capacity Needed (MW)": hourly_ai_mw.max() * 4.5,
        "Est. CAPEX ($B)": (hourly_ai_mw.max() * 3.2 * storage_multiplier) / 1000,
        "Annual Social Carbon Cost ($M)": 0,
        "Description": "Sized based on battery requirements."
    }
]

# --- 8. VISUALIZATION ---
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader(f"2030 Summer Peak Simulation: {selected_state}")
    fig = go.Figure()
    fig.add_trace(go.Scatter(y=grid_base, name="Base Grid Load", stackgroup='one', fillcolor='rgba(131, 192, 238, 0.4)', line=dict(width=0)))
    fig.add_trace(go.Scatter(y=hourly_ai_mw, name="AI System Load", stackgroup='one', fillcolor='rgba(255, 99, 71, 0.8)', line=dict(width=0)))
    fig.update_layout(yaxis_title="MW", xaxis_title="Hour", hovermode="x unified", template="plotly_white")
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.markdown("### Grid Impact Metrics")
    st.metric("Peak AI Demand", f"{hourly_ai_mw.max():,.0f} MW")
    st.metric("Total Daily Energy", f"{total_daily_energy:,.0f} MWh")
    st.metric("Grid Stress Increase", f"{(hourly_ai_mw.max() / grid_base.max() * 100):.2f}%")
    st.info(f"AI load peaks at hour **{peak_hour_ai}:00**. Infrastructure costs adjusted for time-of-use.")

st.subheader("Infrastructure Pathways (Mutually Exclusive Options)")
st.markdown("*Select one independent technology strategy to firm the incremental AI load.*")
st.table(pd.DataFrame(infra_options).style.format({
    "Capacity Needed (MW)": "{:,.0f}",
    "Est. CAPEX ($B)": "${:,.2f}",
    "Annual Social Carbon Cost ($M)": "${:,.1f}"
}))

st.markdown("---")
st.markdown("<div style='text-align: center; color: gray; font-size: 0.8em;'>Created by Jay Shah</div>", unsafe_allow_html=True)
