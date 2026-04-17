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
    def clean(v): return float(str(v).replace('%','')) / 100.0 if '%' in str(v) else float(v)
    pop_share = clean(s_row.iloc[1])
    age_pct   = clean(s_row.iloc[2])
else:
    selected_state, pop_share, age_pct = "New Jersey", 0.028, 0.75

total_us_pop = 340_000_000 
adoption_rate = st.sidebar.slider("AI Adoption Rate (2030)", 0.1, 1.0, 0.85)
state_users = total_us_pop * pop_share * age_pct * adoption_rate

# --- 3. SIDEBAR: ARCHETYPE MIX & DESCRIPTIONS ---
st.sidebar.header("2. Archetype Mix (%)")
with st.sidebar.expander("ℹ️ About Archetypes & Peak Timing"):
    st.markdown("""
    **The Searcher:** Text-based info retrieval. Low energy (~0.3 Wh). Peaks mid-day.
    
    **The Thinker:** Reasoning & coding tasks. Med energy (~15 Wh). Peaks 9AM-5PM.
    
    **The Creator:** Video gen & autonomous agents. High energy (~100 Wh). Peaks 6PM-11PM.
    """)

thinker_pct = st.sidebar.slider("The Thinker (Reasoning) %", 0, 100, 25)
creator_max = 100 - thinker_pct

if creator_max > 0:
    creator_pct = st.sidebar.slider("The Creator (Video/Agent) %", 0, creator_max, min(15, creator_max))
else:
    st.sidebar.info("No room for Creator archetype.")
    creator_pct = 0

searcher_pct = 100 - (thinker_pct + creator_pct)
st.sidebar.info(f"The Searcher (Baseline): {searcher_pct}% (Remainder)")

# --- 4. SIDEBAR: USAGE INTENSITY ---
st.sidebar.header("3. Query Volume (Queries/Day)")
st.sidebar.caption("Typical values provided as defaults.")
q_searcher = st.sidebar.slider("Searcher Daily Volume", 1, 300, 80)
q_thinker = st.sidebar.slider("Thinker Daily Volume", 1, 200, 40)
q_creator = st.sidebar.slider("Creator Daily Volume", 1, 100, 15)

# --- 5. SIDEBAR: INFRASTRUCTURE BASELOAD ---
st.sidebar.header("4. Infrastructure Baseload")
high_tier = ['Virginia', 'Texas', 'California', 'Ohio']
default_training = 3500 if selected_state in high_tier else 1200
training_baseload = st.sidebar.number_input("Assumed Training Load (MW)", 0, 15000, default_training)

# --- 6. CALCULATIONS & CURVES ---
def get_curve(peak_hour, spread):
    x = np.arange(24)
    c = np.exp(-0.5 * ((x - peak_hour) / spread) ** 2)
    return c / np.sum(c)

curve_search = get_curve(13, 4) 
curve_think = (get_curve(11, 2) + get_curve(15, 2)) / 2 
curve_create = get_curve(21, 3) 

# User populations
u_searcher = state_users * (searcher_pct / 100.0)
u_thinker  = state_users * (thinker_pct / 100.0)
u_creator  = state_users * (creator_pct / 100.0)

# Energy usage constants (Wh)
WH_S, WH_T, WH_C = 0.3, 15.0, 100.0
PUE_VAL = 1.12

mwh_searcher = (u_searcher * q_searcher * WH_S * PUE_VAL) / 1_000_000
mwh_thinker  = (u_thinker * q_thinker * WH_T * PUE_VAL) / 1_000_000
mwh_creator  = (u_creator * q_creator * WH_C * PUE_VAL) / 1_000_000

hourly_ai_mw = (mwh_searcher * curve_search) + (mwh_thinker * curve_think) + (mwh_creator * curve_create) + training_baseload
grid_base = np.array([72000, 70000, 68000, 67500, 69000, 73000, 78000, 84000, 89000, 93000, 97000, 101000, 105000, 108000, 110500, 112000, 113000, 111000, 106000, 99000, 93000, 86000, 80000, 75000])

# --- 7. INFRASTRUCTURE & CARBON LOGIC ---
peak_hour_ai = np.argmax(hourly_ai_mw)
total_daily_energy = hourly_ai_mw.sum()
social_carbon_tax = 200 

if peak_hour_ai >= 18 or peak_hour_ai <= 6:
    storage_multiplier = 1.9 
    solar_label = "Solar + Storage (Evening Peak)"
else:
    storage_multiplier = 1.0
    solar_label = "Solar + Storage (Daytime Peak)"

infra_options = [
    {"Option": "Modular Nuclear (SMR)", "Capacity (MW)": hourly_ai_mw.max()*1.05, "CAPEX ($B)": (hourly_ai_mw.max()*8.5)/1000, "Carbon Cost ($M/yr)": 0},
    {"Option": "Natural Gas (CCGT)", "Capacity (MW)": hourly_ai_mw.max()*1.10, "CAPEX ($B)": (hourly_ai_mw.max()*1.4)/1000, "Carbon Cost ($M/yr)": (total_daily_energy*365*0.430*social_carbon_tax)/1_000_000},
    {"Option": solar_label, "Capacity (MW)": hourly_ai_mw.max()*4.5, "CAPEX ($B)": (hourly_ai_mw.max()*3.2*storage_multiplier)/1000, "Carbon Cost ($M/yr)": 0}
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
    
    st.markdown("---")
    st.markdown("### 2030 User Breakdown")
    st.write(f"**Total AI Users:** {state_users:,.0f}")
    
    pop_df = pd.DataFrame([
        {"Archetype": "Searchers", "Count": f"{u_searcher:,.0f}", "%": f"{searcher_pct:.1f}%"},
        {"Archetype": "Thinkers", "Count": f"{u_thinker:,.0f}", "%": f"{thinker_pct:.1f}%"},
        {"Archetype": "Creators", "Count": f"{u_creator:,.0f}", "%": f"{creator_pct:.1f}%"}
    ])
    st.table(pop_df)

st.subheader("Infrastructure Pathways (Mutually Exclusive Options)")
st.markdown("*Select one independent technology strategy to firm the incremental AI load.*")
st.table(pd.DataFrame(infra_options).style.format({"Capacity (MW)": "{:,.0f}", "CAPEX ($B)": "${:,.2f}", "Carbon Cost ($M/yr)": "${:,.1f}"}))

with st.expander("📚 Data Sources & Methodology"):
    st.markdown("""
    - **Base Grid:** EIA Hourly Grid Monitor projections for 2030 summer peaks.
    - **Energy Benchmarks:** EPRI 'Powering Intelligence' 2024 scaling models.
    - **Infrastructure Costs:** NREL Annual Technology Baseline (ATB) 2024.
    - **Carbon Logic:** EPA 2030 Social Cost of Carbon ($200/metric ton).
    """)

st.markdown("---")
st.markdown("<div style='text-align: center; color: gray; font-size: 0.8em;'>Created by Jay Shah</div>", unsafe_allow_html=True)
