import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# --- PAGE SETUP ---
st.set_page_config(page_title="2030 AI Power Nexus", layout="wide")
st.title("AI Power Nexus: 2030 Summer Peak Simulation")

# --- 1. DATA CONNECTIONS (MASTER LOG V4) ---
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
        df.columns = df.iloc[0].astype(str).str.strip()
        return df[1:].reset_index(drop=True)

    return extract_table('State'), extract_table('Variable_Name'), extract_table('Technology'), extract_table('Archetype')

df_demo, df_globals, df_tech, df_bench = load_master_log(SHEET_ID)

# --- 2. GLOBAL VARIABLE EXTRACTION ---
# Clean data conversion
def to_num(df, row_name, col_search='Variable_Name', val_col='Value'):
    try:
        val = df.loc[df[col_search].str.contains(row_name, na=False, case=False), val_col].values[0]
        return float(str(val).replace(',', '').replace('$', ''))
    except: return None

US_POP_2030 = to_num(df_globals, 'Pop') or 340000000.0
SOCIAL_CARBON_TAX = to_num(df_globals, 'Social') or 200.0

# EIA 2030 Summer Peak Map (MW)
SUMMER_PEAK_MAP = {
    'Texas': 92400, 'California': 56100, 'Florida': 52800, 'New York': 33500,
    'Pennsylvania': 30100, 'Virginia': 28200, 'Ohio': 26800, 'Illinois': 24500,
    'North Carolina': 23500, 'Georgia': 22100, 'New Jersey': 20400, 
    'Michigan': 19800, 'Massachusetts': 14100
}

# --- 3. SIDEBAR: GEOGRAPHY & ADOPTION ---
st.sidebar.header("1. 2030 Population & Adoption")
if not df_demo.empty:
    selected_state = st.sidebar.selectbox("Select Target State", df_demo['State'].tolist())
    s_row = df_demo[df_demo['State'] == selected_state].iloc[0]
    def p2f(v): return float(str(v).replace('%','')) / 100.0 if '%' in str(v) else float(v)
    pop_share = p2f(s_row.iloc[1])
    age_pct   = p2f(s_row.iloc[2])
else:
    selected_state, pop_share, age_pct = "New Jersey", 0.028, 0.75

adoption_rate = st.sidebar.slider("AI Adoption Rate (2030)", 0.1, 1.0, 0.85)
state_users = US_POP_2030 * pop_share * age_pct * adoption_rate

# --- 4. SIDEBAR: ARCHETYPE MIX ---
st.sidebar.header("2. Archetype Mix (%)")
with st.sidebar.expander("ℹ️ About Archetypes & Peak Timing"):
    st.markdown("""
    - **Searcher:** Text retrieval. Low Energy. Peaks Mid-day.
    - **Thinker:** Reasoning/Coding. Med Energy. Peaks 9AM-5PM.
    - **Creator:** Video/Agents. High Energy. Peaks 6PM-11PM.
    """)

thinker_pct = st.sidebar.slider("The Thinker (Reasoning) %", 0, 100, 25)
creator_max = 100 - thinker_pct
if creator_max > 0:
    creator_pct = st.sidebar.slider("The Creator (Video/Agent) %", 0, creator_max, min(15, creator_max))
else:
    creator_pct = 0
searcher_pct = 100 - (thinker_pct + creator_pct)

# --- 5. SIDEBAR: INTENSITY & EFFICIENCY ---
st.sidebar.header("3. Efficiency & Baseload")
pue_slider = st.sidebar.slider("Data Center PUE (Efficiency)", 1.05, 1.50, 1.12, help="1.0 is perfect efficiency. 2030 targets are <1.15.")
training_baseload = st.sidebar.number_input("State Training Baseload (MW)", 0, 15000, 3500 if selected_state in ['Virginia', 'Texas', 'California'] else 1200)

# --- 6. GRID ENGINE: REGIONAL LOAD SHAPES ---
def get_gaussian(peak_hour, spread):
    x = np.arange(24)
    c = np.exp(-0.5 * ((x - peak_hour) / spread) ** 2)
    return c / np.sum(c)

# Baseline Shape Logic
if selected_state == 'California':
    # The "Duck Curve": Mid-day dip due to massive solar
    base_shape = np.array([0.7, 0.65, 0.62, 0.6, 0.62, 0.68, 0.75, 0.7, 0.6, 0.5, 0.45, 0.48, 0.52, 0.6, 0.75, 0.9, 1.0, 0.98, 0.92, 0.85, 0.8, 0.78, 0.75, 0.72])
elif selected_state in ['New York', 'Massachusetts', 'New Jersey']:
    # Northeast "Dual Peak": Morning and Evening spikes
    base_shape = np.array([0.65, 0.6, 0.58, 0.58, 0.62, 0.75, 0.88, 0.92, 0.9, 0.88, 0.85, 0.85, 0.88, 0.92, 0.95, 0.98, 1.0, 0.98, 0.95, 0.9, 0.85, 0.78, 0.72, 0.68])
else:
    # Standard Summer Peak (Hot regions: TX, FL)
    base_shape = np.array([0.6, 0.55, 0.52, 0.51, 0.55, 0.62, 0.7, 0.78, 0.85, 0.9, 0.93, 0.96, 0.98, 1.0, 0.99, 0.98, 0.97, 0.94, 0.9, 0.85, 0.8, 0.75, 0.7, 0.65])

state_peak_2030 = SUMMER_PEAK_MAP.get(selected_state, 20000)
grid_base = base_shape * state_peak_2030

# AI Demand Math
u_s, u_t, u_c = state_users * (searcher_pct/100), state_users * (thinker_pct/100), state_users * (creator_pct/100)
mwh_s = (u_s * 80 * 0.3 * pue_slider) / 1_000_000
mwh_t = (u_t * 40 * 15.0 * pue_slider) / 1_000_000
mwh_c = (u_c * 15 * 100.0 * pue_slider) / 1_000_000

hourly_ai_mw = (mwh_s * get_gaussian(13, 4)) + (mwh_t * get_gaussian(14, 3)) + (mwh_c * get_gaussian(21, 3)) + training_baseload

# --- 7. DYNAMIC INFRASTRUCTURE PATHWAYS ---
peak_ai = hourly_ai_mw.max()
total_daily_mwh = hourly_ai_mw.sum()

def get_tech_data(tech_name):
    try:
        row = df_tech[df_tech['Technology'].str.contains(tech_name, na=False)].iloc[0]
        capex = float(str(row['Est_CAPEX_per_MW']).replace('$','').replace(',',''))
        reserve = float(row['Nameplate_Multiplier'])
        return capex, reserve
    except: return 0, 1.0

# Lookup from Sheet
smr_capex, smr_res = get_tech_data('Nuclear')
gas_capex, gas_res = get_tech_data('Gas')
solar_capex, _ = get_tech_data('Solar')

# Solar Multiplier Logic (Time-of-Use Tax)
peak_hour = np.argmax(hourly_ai_mw)
solar_res = 5.5 if (peak_hour >= 18 or peak_hour <= 6) else 3.5

infra_options = [
    {"Pathway": "SMR (Nuclear)", "MW Needed": peak_ai * smr_res, "CAPEX ($B)": (peak_ai * smr_res * smr_capex) / 1e9, "Carbon Cost ($M/yr)": 0},
    {"Pathway": "Natural Gas", "MW Needed": peak_ai * gas_res, "CAPEX ($B)": (peak_ai * gas_res * gas_capex) / 1e9, "Carbon Cost ($M/yr)": (total_daily_mwh * 365 * 0.430 * SOCIAL_CARBON_TAX) / 1e6},
    {"Pathway": "Solar + Storage", "MW Needed": peak_ai * solar_res, "CAPEX ($B)": (peak_ai * solar_res * solar_capex) / 1e9, "Carbon Cost ($M/yr)": 0}
]

# --- 8. VISUALIZATION ---
col1, col2 = st.columns([2, 1])
with col1:
    st.subheader(f"2030 Summer Peak: {selected_state}")
    fig = go.Figure()
    fig.add_trace(go.Scatter(y=grid_base, name=f"{selected_state} Base", stackgroup='one', fillcolor='rgba(131, 192, 238, 0.4)', line=dict(width=0)))
    fig.add_trace(go.Scatter(y=hourly_ai_mw, name="AI System Load", stackgroup='one', fillcolor='rgba(255, 99, 71, 0.8)', line=dict(width=0)))
    fig.update_layout(yaxis_title="MW", xaxis_title="Hour", hovermode="x unified", template="plotly_white")
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.markdown("### Grid Impact Metrics")
    st.metric("Peak AI Demand", f"{peak_ai:,.0f} MW")
    st.metric("Grid Stress Increase", f"{(peak_ai / grid_base.max() * 100):.2f}%")
    st.markdown("---")
    st.markdown("### 2030 User Breakdown")
    st.table(pd.DataFrame([
        {"Archetype": "Searcher", "Pop": f"{u_s:,.0f}", "%": f"{searcher_pct:.0f}%"},
        {"Archetype": "Thinker", "Pop": f"{u_t:,.0f}", "%": f"{thinker_pct:.0f}%"},
        {"Archetype": "Creator", "Pop": f"{u_c:,.0f}", "%": f"{creator_pct:.0f}%"}
    ]))

st.subheader("Infrastructure Pathways (Mutually Exclusive)")
st.table(pd.DataFrame(infra_options).style.format({"MW Needed": "{:,.0f}", "CAPEX ($B)": "${:,.2f}", "Carbon Cost ($M/yr)": "${:,.1f}"}))

with st.expander("📚 Methodology & Data Sources"):
    st.markdown("""
    - **Grid Baselines:** EIA AEO 2030 Projections with regional load shapes (Duck Curve for CA, Dual-Peak for NE).
    - **Costs & Tech:** Pulled dynamically from Master Log V4 (NREL 2024 ATB Basis).
    - **Carbon Logic:** EPA Social Cost of Carbon estimate.
    """)

st.markdown("---")
st.markdown("<div style='text-align: center; color: gray; font-size: 0.8em;'>Created by Jay Shah</div>", unsafe_allow_html=True)

