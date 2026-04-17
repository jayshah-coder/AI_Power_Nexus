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

# Energy usage
mwh_searcher = (u_searcher * q_searcher * 0.3 * 1.12) / 1_000_000
mwh_thinker  = (u_thinker * q_thinker * 15.0 * 1.12) / 1_000_000
mwh_creator  = (u_creator * q_creator * 100.0 * 1.12) / 1_000_000

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
    solar_label = "
