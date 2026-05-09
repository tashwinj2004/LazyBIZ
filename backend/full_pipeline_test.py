import sys
import os
import json
import pandas as pd
from datetime import datetime

# Set up paths
backend_path = os.path.abspath("backend")
sys.path.append(backend_path)

# Mock environment variables
os.environ["UPLOAD_FOLDER"] = os.path.join(backend_path, "data")
os.environ["CHROMA_DB_PATH"] = os.path.join(backend_path, "data", "chroma_db")

try:
    from mcp_tools.data_cleaner import clean_data
    from mcp_tools.data_analyzer import analyze_data
    from mcp_tools.data_visualizer import visualize_data
    from rag import RAGEngine
    from llm import LLMClient

    FILE_PATH = r"e:\Engineering\Internship\VTU\Project\Major # project\LazyBIZ\data\data001.csv"
    FILENAME = "data001.csv"

    print(f"--- STARTING FULL PIPELINE TEST ---")
    
    # 1. Clean
    print("\n[1/5] Cleaning...")
    df_clean, clean_report = clean_data(FILE_PATH)
    print(f"Success. Rows: {len(df_clean)}")

    # 2. Analyze
    print("\n[2/5] Analyzing...")
    analysis = analyze_data(df_clean)
    print(f"Success. KPIs found: {list(analysis.get('kpis', {}).keys())}")
    if "future_forecast" in analysis:
        print(f"Forecast generated: {len(analysis['future_forecast'].get('forecast_values', []))} months")
    else:
        print("WARNING: No forecast generated!")

    # 3. Visualize
    print("\n[3/5] Visualizing...")
    viz = visualize_data(df_clean, analysis)
    print(f"Success. Charts generated: {viz['chart_count']}")
    chart_ids = [c['id'] for c in viz['charts'] if 'image' in c]
    print(f"IDs: {chart_ids}")

    # 4. RAG
    print("\n[4/5] RAG Ingestion...")
    rag = RAGEngine(persist_dir=os.environ["CHROMA_DB_PATH"])
    rag_res = rag.ingest_csv(FILE_PATH, FILENAME, df=df_clean)
    print(f"Success. Ingested chunks: {rag_res.get('chunks', 0)}")

    # 5. LLM
    print("\n[5/5] LLM Insights...")
    llm = LLMClient()
    if not llm.gemini_key:
        print("WARNING: Gemini key missing in env, using fallbacks.")
    
    summary = analysis.get("summary_text", "Business summary data.")
    insights = llm.generate_insights(summary)
    print(f"Success. Insights count: {len(insights)}")
    print(f"Sample Insight: {insights[0].get('title') if insights else 'None'}")

    print("\n--- PIPELINE PERFECTLY FINE ---")

except Exception as e:
    print(f"\n!!! PIPELINE FAILED !!!")
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
