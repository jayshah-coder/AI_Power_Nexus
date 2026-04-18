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
    try:
        raw_df = pd.read_csv(base_url, header=None)
    except Exception as e:
        st.error(f"Failed to connect to spreadsheet: {e}")
        st.stop()
    
    def extract_table(header_marker):
        # 1. Find the marker row
        marker_idx = None
        for i, val in enumerate(raw_df[0].astype(str).str.strip()):
            if val.lower() == header_marker.lower():
                marker_idx = i
                break
        if marker_idx is None: return pd.DataFrame()
        
        # 2. Find the actual header row (skip titles/empty rows)
        header_idx = marker_idx
        while header_idx < len(raw_df):
            if raw_df.iloc[header_idx].notna().sum() >= 2:
                break
            header_idx += 1
        if header_idx >= len(raw_df): return pd.DataFrame()
            
        # 3. Collect data until a break
        rows = []
        for i in range(header_idx, len(raw_df)):
            first_val = str(raw_df.iloc[i, 0]).strip().lower()
            if i > header_idx and (first_val == '' or first_val == 'nan' or first_val.startswith('tab:')):
                break
            rows.append(raw_df.iloc[i].values)
        
        df = pd.DataFrame(rows)
        df.columns = df.iloc[0].astype(str).str.strip()
        return df[1:].reset_index(drop=True)

    return (extract_table('State'), extract_table('Variable_Name'), 
            extract_table('Technology'), extract_table('Archetype'))

df_demo, df_globals, df_tech, df_bench = load_master_log(SHEET_ID)

# --- 2. GLOBAL VARIABLE EXTRACTION ---
def to_num(df, row_name):
    try:
        mask = df.iloc[:, 0].astype(str).str.contains(row_name, na=False, case=False)
        val = df[mask].iloc[0, 1]
        return float(str(val).replace(',', '').replace('$', '').replace('%',''))
    except: return None

US_POP_2030 = to_num(df_globals, 'Pop') or 340000000.0
SOCIAL_CARBON_TAX = to_num(df_globals, 'Social') or 200.0

SUMMER_PEAK_MAP = {
    'Texas': 92400, 'California': 56100, 'Florida': 52800, 'New York': 33500,
    'Pennsylvania': 30100, 'Virginia': 28200, 'Ohio': 26800, 'Illinois': 24500,
    'North Carolina': 23500, 'Georgia': 22100, 'New Jersey': 20400, 
    'Michigan': 19800, 'Massachusetts': 14100
}

# --- 3. SIDEBAR: POPULATION & ADOPTION ---
st.sidebar.header("1. 2030 Population & Adoption")
if not df_demo.empty:
    selected_state = st.sidebar.selectbox("Select Target State", df_demo.iloc[:, 0].tolist())
    s_row = df_demo[df_demo.iloc[:, 0] == selected_state].iloc[0]
    def p2f(v): 
        try: return float(str(v).replace('%','')) / 100.0 if '%' in str(v) else float(v)
        except: return 0.0
    pop_share, age_pct = p2f(s_row.iloc[1]), p2f(s_row.iloc[2])
else:
    selected_state, pop_share, age_pct = "New Jersey", 0.028, 0.75

adoption_rate = st.sidebar.slider("AI Adoption Rate (2030)", 0.1, 1.0, 0.85)
state_users = US_POP_2030 * pop_share * age_pct * adoption_rate

# --- 4. SIDEBAR: ARCHETYPE MIX ---
st.sidebar.header("2. Archetype Mix (%)")
with st.sidebar.expander("ℹ️ About Archetypes & Timing"):
    st.markdown("""
    - **Searcher:** Text retrieval (~0.3 Wh). Peaks mid-day.
    - **Thinker:** Reasoning tasks (~15 Wh). Peaks 9AM-5PM.
    - **Creator:** Video/Agents (~100 Wh). Peaks 6PM-11PM.
    """)

thinker_pct = st.sidebar.slider("The Thinker (Reasoning) %", 0, 100, 25)
creator_max = 100 - thinker_pct
creator_pct = st.sidebar.slider("The Creator (Video) %", 0, creator_max, min(15, creator_max)) if creator_max > 0 else 0
searcher_pct = 100 - (thinker_pct + creator_pct)
st.sidebar.info(f"The Searcher (Baseline): {searcher_pct}% (Remainder)")

# --- 5. SIDEBAR: INTENSITY & EFFICIENCY ---
st.sidebar.header("3. Query Volume & Efficiency")
q_searcher = st.sidebar.slider("Searcher Queries/Day", 1, 300, 80)
q_thinker = st.sidebar.slider("Thinker Queries/Day", 1, 200, 40)
q_creator = st.sidebar.slider("Creator Queries/Day", 1, 100, 15)

pue_slider = st.sidebar.slider("Data Center PUE", 1.05, 1.50, 1.12, help="Liquid cooling targets are ~1.05.")
training_baseload = st.sidebar.number_input("State Training Baseload (MW)", 0, 15000, 3500 if selected_state in ['Virginia', 'Texas', 'California'] else 1200)

# --- 6. GRID ENGINE ---
def get_gaussian(peak_hour, spread):
    x = np.arange(24)
    c = np.exp(-0.5 * ((x - peak_hour) / spread) ** 2)
    return c / np.sum(c)

# State-Specific Grid Shapes
if selected_state == 'California':
    base_shape = np.array([0.7, 0.65, 0.62, 0.6, 0.62, 0.68, 0.75, 0.7, 0.6, 0.5, 0.45, 0.48, 0.52, 0.6, 0.75, 0.9, 1.0, 0.98, 0.92, 0.85, 0.8, 0.78, 0.75, 0.72])
elif selected_state in ['New York', 'Massachusetts', 'New Jersey']:
    base_shape = np.array([0.65, 0.6, 0.58, 0.58, 0.62, 0.75, 0.88, 0.92, 0.9, 0.88, 0.85, 0.85, 0.88, 0.92, 0.95, 0.98, 1.0, 0.98, 0.95, 0.9, 0.85, 0.78, 0.72, 0.68])
else:
    base_shape = np.array([0.6, 0.55, 0.52, 0.51, 0.55, 0.62, 0.7, 0.78, 0.85, 0.9, 0.93, 0.96, 0.98, 1.0, 0.99, 0.98, 0.97, 0.94, 0.9, 0.85, 0.8, 0.75, 0.7, 0.65])

grid_base = base_shape * SUMMER_PEAK_MAP.get(selected_state, 20000)

# Energy Calc (MW)
u_s, u_t, u_c = state_users * (searcher_pct/100), state_users * (thinker_pct/100), state_users * (creator_pct/100)
hourly_ai_mw = ( (u_s * q_searcher * 0.3 * pue_slider / 1e6) * get_gaussian(13, 4) +
                 (u_t * q_thinker * 15.0 * pue_slider / 1e6) * get_gaussian(14, 3) +
                 (u_c * q_creator * 100.0 * pue_slider / 1e6) * get_gaussian(21, 3) +
                 training_baseload )

# --- 7. FUZZY TECHNOLOGY LOOKUP ---
def get_tech_data(tech_name):
    if df_tech is None or df_tech.empty: return 0.0, 1.0
    try:
        # 1. Find columns by keyword (Resilient to spelling/spaces)
        cols = [str(c).lower().strip() for c in df_tech.columns]
        capex_idx = next((i for i, c in enumerate(cols) if 'capex' in c), None)
        mult_idx = next((i for i, c in enumerate(cols) if 'multiplier' in c or 'res' in c), None)
        
        # 2. Find row by Technology name
        mask = df_tech.iloc[:, 0].astype(str).str.contains(tech_name, na=False, case=False)
        if not mask.any(): return 0.0, 1.0
        row = df_tech[mask].iloc[0]
        
        # 3. Extract and clean values
        capex = float(str(row.iloc[capex_idx]).replace('$','').replace(',','').strip()) if capex_idx is not None else 0.0
        multiplier = 1.0
        if mult_idx is not None:
            mult_val = float(str(row.iloc[mult_idx]).replace('%','').strip())
            multiplier = mult_val / 100.0 if mult_val > 10 else mult_val
            
        return capex, multiplier
    except: return 0.0, 1.0

peak_ai, daily_mwh_total = hourly_ai_mw.max(), hourly_ai_mw.sum()
peak_hour = np.argmax(hourly_ai_mw)

smr_cap, smr_res = get_tech_data('Nuclear')
gas_cap, gas_res = get_tech_data('Gas')
solar_cap, _ = get_tech_data('Solar')
# Evening storage multiplier
solar_res = 5.5 if (peak_hour >= 18 or peak_hour <= 6) else 3.5

infra_options = [
    {"Pathway": "SMR (Nuclear)", "MW Needed": peak_ai * smr_res, "CAPEX ($B)": (peak_ai * smr_res * smr_cap) / 1e9, "Carbon ($M/yr)": 0},
    {"Pathway": "Natural Gas", "MW Needed": peak_ai * gas_res, "CAPEX ($B)": (peak_ai * gas_res * gas_cap) / 1e9, "Carbon ($M/yr)": (daily_mwh_total * 365 * 0.430 * SOCIAL_CARBON_TAX) / 1e6},
    {"Pathway": "Solar + Storage", "MW Needed": peak_ai * solar_res, "CAPEX ($B)": (peak_ai * solar_res * solar_cap) / 1e9, "Carbon ($M/yr)": 0}
]

# --- 8. UI RENDERING ---
col1, col2 = st.columns([2, 1])
with col1:
    st.subheader(f"2030 Summer Peak: {selected_state}")
    fig = go.Figure()
    fig.add_trace(go.Scatter(y=grid_base, name="Base Grid", stackgroup='one', fillcolor='rgba(131, 192, 238, 0.4)', line=dict(width=0)))
    fig.add_trace(go.Scatter(y=hourly_ai_mw, name="AI System Load", stackgroup='one', fillcolor='rgba(255, 99, 71, 0.8)', line=dict(width=0)))
    fig.update_layout(yaxis_title="MW", xaxis_title="Hour", hover
