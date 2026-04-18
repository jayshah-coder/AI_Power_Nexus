import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# --- PAGE SETUP ---
st.set_page_config(page_title="2030 AI Power Nexus", layout="wide")
st.title("AI Power Nexus: 2030 Summer Peak Simulation")

# --- 1. DATA CONNECTIONS (MASTER LOG V4) ---
SHEET_ID = "1oRgI3uZP8WINBRU6GfybW0K8BUvoz2YHXuQ0Y02QLCY"

@st.cache_data(ttl=60)
def load_master_log(sheet_id):
    base_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv"
    try:
        raw_df = pd.read_csv(base_url, header=None).fillna("")
    except Exception as e:
        st.error(f"Spreadsheet Connection Error: {e}")
        return None, None, None, None
    
    def extract_table(marker):
        matches = raw_df[raw_df[0].astype(str).str.strip().str.lower() == marker.lower()]
        if matches.empty: return pd.DataFrame()
        
        start = matches.index[0]
        current = start
        while current < len(raw_df):
            row_vals = [str(x).strip() for x in raw_df.iloc[current] if str(x).strip() != ""]
            if len(row_vals) >= 2: break
            current += 1
        
        header_idx = current
        rows = []
        for i in range(header_idx, len(raw_df)):
            first_val = str(raw_df.iloc[i, 0]).strip().lower()
            if i > header_idx and (first_val == '' or first_val == 'nan' or first_val.startswith('tab:')):
                break
            rows.append(raw_df.iloc[i].values)
            
        if not rows: return pd.DataFrame()
        df = pd.DataFrame(rows)
        cols = []
        for i, val in enumerate(df.iloc[0]):
            name = str(val).strip() if str(val).strip() != "" else f"Col_{i}"
            cols.append(f"{name}_{i}" if name in cols else name)
        df.columns = cols
        return df[1:].reset_index(drop=True)

    return (extract_table('State'), extract_table('Variable_Name'), 
            extract_table('Technology'), extract_table('Archetype'))

df_demo, df_globals, df_tech, df_bench = load_master_log(SHEET_ID)

# --- 2. GLOBAL CONSTANTS ---
def get_global(name, default):
    try:
        mask = df_globals.iloc[:, 0].astype(str).str.contains(name, case=False, na=False)
        return float(str(df_globals[mask].iloc[0, 1]).replace('$','').replace(',','').replace('%',''))
    except: return default

US_POP = get_global('Pop', 340000000.0)
CARBON_TAX = get_global('Social', 200.0)

SUMMER_PEAK_MAP = {
    'Texas': 92400, 'California': 56100, 'Florida': 52800, 'New York': 33500,
    'Pennsylvania': 30100, 'Virginia': 28200, 'Ohio': 26800, 'Illinois': 24500,
    'North Carolina': 23500, 'Georgia': 22100, 'New Jersey': 20400, 
    'Michigan': 19800, 'Massachusetts': 14100
}

# --- 3. SIDEBAR: ADOPTION & ARCHETYPES ---
st.sidebar.header("1. Population & Adoption")
if df_demo is not None and not df_demo.empty:
    selected_state = st.sidebar.selectbox("Select State", df_demo.iloc[:, 0].tolist())
    s_row = df_demo[df_demo.iloc[:, 0] == selected_state].iloc[0]
    def p2f(v): 
        try: return float(str(v).replace('%','')) / 100.0 if '%' in str(v) else float(v)
        except: return 0.0
    pop_share, age_pct = p2f(s_row.iloc[1]), p2f(s_row.iloc[2])
else:
    selected_state, pop_share, age_pct = "New Jersey", 0.028, 0.75

adoption = st.sidebar.slider("AI Adoption Rate (2030)", 0.1, 1.0, 0.85)
state_users = US_POP * pop_share * age_pct * adoption

st.sidebar.header("2. Archetype Mix (%)")
with st.sidebar.expander("ℹ️ About Archetypes & Timing"):
    st.markdown("""
    - **Searcher:** Text retrieval (~0.3 Wh). Peaks mid-day.
    - **Thinker:** Reasoning tasks (~15 Wh). Peaks 9AM-5PM.
    - **Creator:** Video/Agents (~100 Wh). Peaks 6PM-11PM.
    """)

thinker_pct = st.sidebar.slider("The Thinker %", 0, 100, 25)
creator_max = 100 - thinker_pct
creator_pct = st.sidebar.slider("The Creator %", 0, creator_max, min(15, creator_max))
searcher_pct = 100 - (thinker_pct + creator_pct)
st.sidebar.info(f"The Searcher (Baseline): {searcher_pct}% (Remainder)")

st.sidebar.header("3. Intensity & Efficiency")
q_s = st.sidebar.slider("Searcher Daily Volume", 1, 300, 80)
q_t = st.sidebar.slider("Thinker Daily Volume", 1, 200, 40)
q_c = st.sidebar.slider("Creator Daily Volume", 1, 100, 15)
pue = st.sidebar.slider("Data Center PUE", 1.05, 1.5, 1.12)
training = st.sidebar.number_input("Baseload (MW)", 0, 15000, 3500 if selected_state in ['Virginia', 'Texas', 'California'] else 1200)

# --- 4. GRID CALCULATIONS ---
def get_shape(peak_hour, spread):
    x = np.arange(24)
    c = np.exp(-0.5 * ((x - peak_hour) / spread) ** 2)
    return c / np.sum(c)

# Regional Baselines (Duck Curve vs Dual Peak)
if selected_state == 'California':
    base_shape = np.array([0.7, 0.65, 0.62, 0.6, 0.62, 0.68, 0.75, 0.7, 0.6, 0.5, 0.45, 0.48, 0.52, 0.6, 0.75, 0.9, 1.0, 0.98, 0.92, 0.85, 0.8, 0.78, 0.75, 0.72])
elif selected_state in ['New York', 'Massachusetts', 'New Jersey']:
    base_shape = np.array([0.65, 0.6, 0.58, 0.58, 0.62, 0.75, 0.88, 0.92, 0.9, 0.88, 0.85, 0.85, 0.88, 0.92, 0.95, 0.98, 1.0, 0.98, 0.95, 0.9, 0.85, 0.78, 0.72, 0.68])
else:
    base_shape = np.array([0.6, 0.55, 0.52, 0.51, 0.55, 0.62, 0.7, 0.78, 0.85, 0.9, 0.93, 0.96, 0.98, 1.0, 0.99, 0.98, 0.97, 0.94, 0.9, 0.85, 0.8, 0.75, 0.7, 0.65])

grid_base = base_shape * SUMMER_PEAK_MAP.get(selected_state, 20000)

# AI Load (MW)
u_s_count, u_t_count, u_c_count = state_users * (searcher_pct/100), state_users * (thinker_pct/100), state_users * (creator_pct/100)
hourly_ai_mw = ( (u_s_count * q_s * 0.3 * pue / 1e6) * get_shape(13, 4) +
                 (u_t_count * q_t * 15.0 * pue / 1e6) * get_shape(14, 3) +
                 (u_c_count * q_c * 100.0 * pue / 1e6) * get_shape(21, 3) +
                 training )

# --- 5. INFRASTRUCTURE COST LOOKUP ---
def get_tech_data(name, default_cap, default_res):
    if df_tech is None or df_tech.empty: return default_cap, default_res
    try:
        row = df_tech[df_tech.iloc[:,0].astype(str).str.contains(name, case=False, na=False)].iloc[0]
        cols = [str(c).lower() for c in df_tech.columns]
        c_idx = next((i for i, c in enumerate(cols) if any(k in c for k in ['capex', 'cost', 'price'])), None)
        m_idx = next((i for i, c in enumerate(cols) if any(k in c for k in ['multi', 'res', 'nameplate'])), None)
        
        cap = float(str(row.iloc[c_idx]).replace('$','').replace(',','').strip()) if c_idx is not None else default_cap
        res = float(str(row.iloc[m_idx]).replace('%','').strip()) if m_idx is not None else default_res
        if res > 10: res /= 100.0
        return cap, res
    except: return default_cap, default_res

peak_ai, daily_mwh = hourly_ai_mw.max(), hourly_ai_mw.sum()
peak_hr = np.argmax(hourly_ai_mw)

# Fallback Industry Defaults
smr_cap, smr_res = get_tech_data('Nuclear', 8500000, 1.05)
gas_cap, gas_res = get_tech_data('Gas', 1400000, 1.10)
sol_cap, _ = get_tech_data('Solar', 3200000, 3.5)
sol_res = 5.5 if (peak_hr >= 18 or peak_hr <= 6) else 3.5

infra = [
    {"Pathway": "SMR (Nuclear)", "MW Needed": peak_ai * smr_res, "CAPEX ($B)": (peak_ai * smr_res * smr_cap)/1e9, "Carbon Cost ($M/yr)": 0},
    {"Pathway": "Natural Gas", "MW Needed": peak_ai * gas_res, "CAPEX ($B)": (peak_ai * gas_res * gas_cap)/1e9, "Carbon Cost ($M/yr)": (daily_mwh * 365 * 0.43 * CARBON_TAX)/1e6},
    {"Pathway": "Solar + Storage", "MW Needed": peak_ai * sol_res, "CAPEX ($B)": (peak_ai * sol_res * sol_cap)/1e9, "Carbon Cost ($M/yr)": 0}
]

# --- 6. RENDER ---
c1, c2 = st.columns([2, 1])
with c1:
    st.subheader(f"2030 Summer Peak: {selected_state}")
    fig = go.Figure()
    fig.add_trace(go.Scatter(y=grid_base, name="Base Grid", stackgroup='one', fillcolor='rgba(131, 192, 238, 0.4)', line=dict(width=0)))
    fig.add_trace(go.Scatter(y=hourly_ai_mw, name="AI System Load", stackgroup='one', fillcolor='rgba(255, 99, 71, 0.8)', line=dict(width=0)))
    fig.update_layout(yaxis_title="MW", xaxis_title="Hour", hovermode="x unified", template="plotly_white")
    st.plotly_chart(fig, use_container_width=True)

with c2:
    st.markdown("### Grid Impact Metrics")
    st.metric("Peak AI Demand", f"{peak_ai:,.0f} MW")
    st.metric("Grid Stress Increase", f"{(peak_ai / grid_base.max() * 100):.2f}%")
    st.markdown("---")
    st.markdown("### 2030 User Breakdown")
    st.table(pd.DataFrame([
        {"Archetype": "Searchers", "Count": f"{u_s_count:,.0f}", "%": f"{searcher_pct:.0f}%"},
        {"Archetype": "Thinkers", "Pop": f"{u_t_count:,.0f}", "%": f"{thinker_pct:.0f}%"},
        {"Archetype": "Creators", "Pop": f"{u_c_count:,.0f}", "%": f"{creator_pct:.0f}%"}
    ]))

st.subheader("Infrastructure Pathways (Mutually Exclusive Options)")
st.markdown("*Requirements and costs firmed for 2030 reliability.*")
st.table(pd.DataFrame(infra).style.format({"MW Needed": "{:,.0f}", "CAPEX ($B)": "${:,.2f}", "Carbon Cost ($M/yr)": "${:,.1f}"}))

with st.expander("📚 Data Sources & Methodology"):
    st.markdown("""
    - **Base Grid Baselines:** EIA AEO 2030 projections & regional load shapes.
    - **Usage Intensity:** EPRI 'Powering Intelligence' 2024 scaling models.
    - **Infrastructure Costs:** NREL 2024 Annual Technology Baseline (ATB).
    - **Carbon Logic:** EPA Social Cost of Carbon estimate ($200/metric ton baseline).
    """)

st.markdown("---")
st.markdown("<div style='text-align: center; color: gray; font-size: 0.8em;'>Created by Jay Shah</div>", unsafe_allow_html=True)
