import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
from datetime import datetime

# --- PAGE SETUP ---
st.set_page_config(page_title="The AI Power Nexus", layout="wide")
st.title("The AI Power Nexus: 2026-2030")
st.markdown("Simulate the physical grid impact and societal cost of human-driven AI demand using live grid data.")

# --- 1. DATA CONNECTIONS (GOOGLE SHEETS & API) ---
SHEET_ID = "1oRgI3uZP8WINBRU6GfybW0K8BUvoz2YHXuQ0Y02QLCY"
EIA_API_KEY = "egUujavB2YGwnp3NE2Wa6qgJzLzHkWPJXVEZ3FDn"

@st.cache_data(ttl=600)
def load_master_log(sheet_id):
    # Fetch the flat CSV from the single sheet
    base_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv"
    raw_df = pd.read_csv(base_url, header=None, names=list(range(10)))
    
    # Parse the single sheet into our distinct DataFrames based on the "TAB:" markers
    tab_indices = raw_df[raw_df[0].astype(str).str.startswith("TAB:")].index.tolist()
    tab_indices.append(len(raw_df))
    
    dataframes = {}
    for i in range(len(tab_indices) - 1):
        start_idx = tab_indices[i]
        end_idx = tab_indices[i+1]
        tab_name = str(raw_df.iloc[start_idx, 0]).replace("TAB:", "").strip()
        
        # Extract the chunk and set the headers
        chunk = raw_df.iloc[start_idx+1 : end_idx].dropna(how='all')
        if not chunk.empty:
            # Force all column names to strings and strip away invisible spaces
            chunk.columns = chunk.iloc[0].astype(str).str.strip()
            chunk = chunk[1:].dropna(axis=1, how='all').reset_index(drop=True)
            dataframes[tab_name] = chunk
            
    # Assign the parsed chunks
    df_demo = dataframes.get("State_Demographics", pd.DataFrame())
    df_tech = dataframes.get("Tech_Costs_LCOE_2026", pd.DataFrame())
    df_benchmarks = dataframes.get("AI_Demand_Benchmarks", pd.DataFrame())
    df_globals = dataframes.get("Global_Variables", pd.DataFrame())
    
    # Clean the demographic percentages
    for col in ['Pop_Share_Pct', 'Addressable_Age_Pct', 'AI_Adoption_Pct', 'Casual_Pct', 'Thinker_Pct', 'Creator_Pct', 'Architect_Pct']:
        if col in df_demo.columns:
            df_demo[col] = df_demo[col].astype(str).str.rstrip('%').astype('float') / 100.0
            
    # Convert benchmark numbers
    for col in ['Tasks_Per_Day', 'Energy_Per_Task_Wh', 'Cooling_Tax_PUE']:
        if col in df_benchmarks.columns:
