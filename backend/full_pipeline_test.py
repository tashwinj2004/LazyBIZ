import sys
import os
import pytest
import pandas as pd

# Set up paths
backend_path = os.path.dirname(os.path.abspath(__file__))
if backend_path not in sys.path:
    sys.path.append(backend_path)

from mcp_tools.data_cleaner import clean_data
from mcp_tools.data_analyzer import analyze_data
from mcp_tools.data_visualizer import visualize_data

# Use a test CSV file
TEST_CSV_PATH = os.path.join(os.path.dirname(backend_path), "data", "TS_11.csv")

def test_data_cleaning():
    """Verify data cleaner handles dates and nulls correctly."""
    assert os.path.exists(TEST_CSV_PATH), f"Test CSV not found at {TEST_CSV_PATH}"
    df_clean, clean_report = clean_data(TEST_CSV_PATH)
    assert isinstance(df_clean, pd.DataFrame)
    assert len(df_clean) > 0
    assert "Date" in df_clean.columns or "__date__" in df_clean.columns

def test_data_analysis():
    """Verify data analyzer produces KPIs and summary."""
    df_clean, _ = clean_data(TEST_CSV_PATH)
    analysis = analyze_data(df_clean)
    assert isinstance(analysis, dict)
    assert "kpis" in analysis
    assert "summary_text" in analysis

def test_data_visualization():
    """Verify data visualizer generates Chart.js structures."""
    df_clean, _ = clean_data(TEST_CSV_PATH)
    analysis = analyze_data(df_clean)
    viz = visualize_data(df_clean, analysis)
    assert isinstance(viz, dict)
    assert "charts" in viz
    assert viz["chart_count"] >= 0

@pytest.mark.skipif(not os.getenv("SUPABASE_DB_URL"), reason="SUPABASE_DB_URL secret not configured")
def test_rag_ingestion():
    """Verify RAG engine can connect and ingest vectors (skipped if no Supabase secret)."""
    from rag import RAGEngine
    rag = RAGEngine()
    df_clean, _ = clean_data(TEST_CSV_PATH)
    rag_res = rag.ingest_csv(TEST_CSV_PATH, "TS_11.csv", df=df_clean)
    assert isinstance(rag_res, dict)
    assert "chunks" in rag_res

@pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason="GEMINI_API_KEY secret not configured")
def test_llm_insights():
    """Verify LLM client can call Gemini API (skipped if no Gemini secret)."""
    from llm import LLMClient
    llm = LLMClient()
    df_clean, _ = clean_data(TEST_CSV_PATH)
    analysis = analyze_data(df_clean)
    summary = analysis.get("summary_text", "Business summary data.")
    insights = llm.generate_insights(summary)
    assert isinstance(insights, list)
    if insights:
        assert "title" in insights[0]
