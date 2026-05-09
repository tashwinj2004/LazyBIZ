import sys
import os
import pandas as pd
sys.path.append(os.path.abspath("backend"))

from mcp_tools.data_cleaner import clean_data
from mcp_tools.data_analyzer import analyze_data

FILE_PATH = r"e:\Engineering\Internship\VTU\Project\Major # project\LazyBIZ\data\data001.csv"

try:
    print(f"--- CLEANING DATA: {FILE_PATH} ---")
    df_clean, report = clean_data(FILE_PATH)
    print("Cleaning success!")
    print(f"Shape: {df_clean.shape}")
    
    print("\n--- ANALYZING DATA ---")
    analysis = analyze_data(df_clean)
    print("Analysis success!")
    print(f"KPIs: {analysis.get('kpis')}")
    print(f"Forecast: {bool(analysis.get('future_forecast'))}")
    
except Exception as e:
    print(f"\nCRITICAL ERROR: {e}")
    import traceback
    traceback.print_exc()
