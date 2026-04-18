import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# --- PAGE SETUP ---
st.set_page_config(page_title="2030 AI Power Nexus", layout="wide")
st.title("AI Power Nexus: 2030 Summer Peak Simulation")

# --- 1. DATA CONNECTIONS ---
SHEET_ID = "1oRgI3uZP8WINBRU6GfybW0K8BUvoz2YHXuQ0Y02QLCY"

@st.cache_data(ttl=60)
def load_master_log(sheet_id):
    # Standard CSV export pulls the FIRST tab by default
    base_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv"
    try:
        raw_df = pd.read_csv(base_url, header=None)
    except Exception as e:
        st.error(f"Spreadsheet Connection Error: {e}")
        return None, None, None, None
    
    def extract_table(marker):
        idx = raw_df[raw_df[0].astype(str).str.strip().str.lower() == marker.lower()].index
        if idx.empty: return pd.DataFrame()
        
        start = idx[0]
        # Find the actual header row
        while start < len(raw_df) and raw_df.iloc[start].isna().sum() > (len(raw_df.columns) - 2):
            start += 1
            
        rows = []
        for i in range(start, len(raw_df)):
            val = str(raw_df.iloc[i, 0]).strip().lower()
            if i > start and (val == '' or val == 'nan' or val.startswith('tab:')):
                break
            rows.append(raw_df.iloc[i].values)
            
        if not rows: return pd.DataFrame()
        df = pd.DataFrame(rows)
        
        # DEDUPLICATE COLUMNS: Fixes the ValueError
        raw_cols = df.iloc[0].astype(str).str.strip().tolist()
        clean_cols = []
        for i, col in enumerate(raw_cols):
            new_name = col if (col != 'nan' and col != '') else f"Col_{i}"
            if new_name in clean_cols:
                clean_cols.append(f"{new_name}_{i}")
            else:
                clean_cols.append(new_name)
        
        df.columns = clean_cols
        return df[1:].reset_index(drop=True)

    return (extract_table('State'), extract_table('Variable_Name'), 
            extract_table('Technology'), extract_table('Archetype'))

df_demo, df_globals, df_tech, df_bench = load_master_log(SHEET_ID)

# --- 2. GLOBAL CONSTANTS ---
def get_global(name, default):
    if df_globals.empty: return default
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

# --- 3. SIDEBAR ---
st.sidebar.header("1. Population & Adoption")
if not df_demo.empty:
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
with st.sidebar.expander("ℹ️ Archetype Details"):
    st.markdown("- **Searcher:** (~0.3 Wh)\n- **Thinker:** (~15 Wh)\n- **Creator:** (~100 Wh)")

thinker_pct = st.sidebar.slider("The Thinker %", 0, 100, 25)
creator_max = 100 - thinker_pct
creator_pct = st.sidebar.slider("The Creator %", 0, creator_max, min(15, creator_max))
searcher_pct = 100 - (thinker_pct + creator_pct)
st.sidebar.info(f"The Searcher: {searcher_pct}% (Remainder)")

st.sidebar.header("3. Query Volume & Efficiency")
q_s = st.sidebar.slider("Searcher Queries/Day", 1, 300, 80)
q_t = st.sidebar.slider("Thinker Queries/Day", 1, 200, 40)
q_c = st.sidebar.slider("Creator Queries/Day", 1, 100, 15)
pue = st.sidebar.slider("Data Center PUE", 1.05, 1.5, 1.12)
training = st.sidebar.number_input("Baseload (MW)", 0, 15000, 3500 if selected_state in ['Virginia', 'Texas', 'California'] else 1200)

# --- 4. GRID ENGINE ---
def get_shape(peak_hour, spread):
    x = np.arange(24)
    c = np.exp(-0.5 * ((x - peak_hour) / spread) ** 2)
    return c / np.sum(c)

if selected_state == 'California':
    base_shape = np.array([0.7, 0.65, 0.62, 0.6, 0.62, 0.68, 0.75, 0.7, 0.6, 0.5, 0.45, 0.48, 0.52, 0.6, 0.75, 0.9, 1.0, 0.98, 0.92, 0.85, 0.8, 0.78, 0.75, 0.72])
elif selected_state in ['New York', 'Massachusetts', 'New Jersey']:
    base_shape = np.array([0.65, 0.6, 0.58, 0.58, 0.62, 0.75, 0.88, 0.92, 0.9, 0.88, 0.85, 0.85, 0.88, 0.92, 0.95, 0.98, 1.0, 0.98, 0.95, 0.9, 0.85, 0.78, 0.72, 0.68])
else:
    base_shape = np.array([0.6, 0.55, 0.52, 0.51, 0.55, 0.62, 0.7, 0.78, 0.85, 0.9, 0.93, 0.96, 0.98, 1.0, 0.99, 0.98, 0.97, 0.94, 0.9, 0.85, 0.8, 0.75, 0.7, 0.65])

grid_base = base_shape * SUMMER_PEAK_MAP.get(selected_state, 20000)

u_s_count, u_t_count, u_c_count = state_users * (searcher_pct/100), state_users * (thinker_pct/100), state_users * (creator_pct/100)
hourly_ai_mw = ( (u_s_count * q_s * 0.3 * pue / 1e6) * get_shape(13, 4) +
                 (u_t_count * q_t * 15.0 * pue / 1e6) * get_shape(14, 3) +
                 (u_c_count * q_c * 100.0 * pue / 1e6) * get_shape(21, 3) +
                 training )

# --- 5. TECH LOOKUP ---
def get_tech_data(name):
    if df_tech.empty: return 0.0, 1.0
    try:
        # Fuzzy find the row
        row = df_tech[df_tech.iloc[:,0].astype(str).str.contains(name, case=False, na=False)].iloc[0]
        # Fuzzy find the columns
        capex_col = [c for c in df_tech.columns if 'capex' in c.lower()][0]
        mult_col = [c for c in df_tech.columns if 'multi' in c.lower() or 'res' in c.lower() or 'nameplate' in c.lower()][0]
        
        cap = float(str(row[capex_col]).replace('$','').replace(',','').strip())
        res = float(str(row[mult_col]).replace('%','').strip())
        if res > 10: res /= 100.0
        return cap, res
    except: return 0.0, 1.0

peak_ai, daily_mwh = hourly_ai_mw.max(), hourly_ai_mw.sum()
peak_hr = np.argmax(hourly_ai_mw)

smr_cap, smr_res = get_tech_data('Nuclear')
gas_cap, gas_res = get_tech_data('Gas')
sol_cap, _ = get_tech_data('Solar')
sol_res = 5.5 if (peak_hr >= 18 or peak_hr <= 6) else 3.5

infra = [
    {"Pathway": "SMR (Nuclear)", "MW": peak_ai * smr_res, "CAPEX ($B)": (peak_ai * smr_res * smr_cap)/1e9, "Carbon ($M)": 0},
    {"Pathway": "Natural Gas", "MW": peak_ai * gas_res, "CAPEX ($B)": (peak_ai * gas_res * gas_cap)/1e9, "Carbon ($M)": (daily_mwh * 365 * 0.43 * CARBON_TAX)/1e6},
    {"Pathway": "Solar + Storage", "MW": peak_ai * sol_res, "CAPEX ($B)": (peak_ai * sol_res * sol_cap)/1e9, "Carbon ($M)": 0}
]

# --- 6. UI ---
c1, c2 = st.columns([2, 1])
with c1:
    st.subheader(f"2030 Peak Simulation: {selected_state}")
    fig = go.Figure()
    fig.add_trace(go.Scatter(y=grid_base, name="Base Grid", stackgroup='one', fillcolor='rgba(131, 192, 238, 0.4)', line=dict(width=0)))
    fig.add_trace(go.Scatter(y=hourly_ai_mw, name="AI System Load", stackgroup='one', fillcolor='rgba(255, 99, 71, 0.8)', line=dict(width=0)))
    fig.update_layout(yaxis_title="MW", xaxis_title="Hour", hovermode="x unified", template="plotly_white")
    st.plotly_chart(fig, use_container_width=True)

with c2:
    st.markdown("### Grid Metrics")
    st.metric("Peak AI Demand", f"{peak_ai:,.0f} MW")
    st.metric("Grid Stress Increase", f"{(peak_ai / grid_base.max() * 100):.2f}%")
    st.markdown("---")
    st.table(pd.DataFrame([
        {"Archetype": "Searchers", "Pop": f"{u_s_count:,.0f}", "%": f"{searcher_pct:.0f}%"},
        {"Archetype": "Thinkers", "Pop": f"{u_t_count:,.0f}", "%": f"{thinker_pct:.0f}%"},
        {"Archetype": "Creators", "Pop": f"{u_c_count:,.0f}", "%": f"{creator_pct:.0f}%"}
    ]))

st.subheader("Infrastructure Pathways (Mutually Exclusive Options)")
st.table(pd.DataFrame(infra).style.format({"MW": "{:,.0f}", "CAPEX ($B)": "${:,.2f}", "Carbon ($M)": "${:,.1f}"}))

with st.expander("🔍 DATA INSPECTOR"):
    st.write("**Technology Table Headers:**", df_tech.columns.tolist() if not df_tech.empty else "Empty")
    st.dataframe(df_tech)
    st.write("**Global Variables:**")
    st.dataframe(df_globals)

with st.expander("📚 Data Sources & Methodology"):
    st.markdown("""
    - **Grid Baselines:** EIA AEO 2030 projections & regional load shapes.
    - **Usage Intensity:** EPRI 'Powering Intelligence' models.
    - **Costing:** NREL 2024 ATB & EPA Social Cost of Carbon ($200/ton).
    """)

st.markdown("---")
st.markdown("<div style='text-align: center; color: gray; font-size: 0.8em;'>Created by Jay Shah</div>", unsafe_allow_html=True)
