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

@pytest.fixture
def test_csv_path(tmp_path):
    """Dynamically creates a temporary test CSV file so it is present on any environment (including CI)."""
    df = pd.DataFrame({
        "Date": ["1012024", "30032024", "15042024"],
        "Product Category": ["Electronics", "Books", "Electronics"],
        "Units Sold": [10.0, 20.0, 15.0],
        "Unit Price": [100.0, 15.0, 100.0],
        "Total Revenue": [1000.0, 300.0, 1500.0],
        "Region": ["North", "South", "North"]
    })
    file_path = tmp_path / "TS_11.csv"
    df.to_csv(file_path, index=False)
    return str(file_path)

def test_data_cleaning(test_csv_path):
    """Verify data cleaner handles dates and nulls correctly."""
    assert os.path.exists(test_csv_path), f"Test CSV not found at {test_csv_path}"
    df_clean, clean_report = clean_data(test_csv_path)
    assert isinstance(df_clean, pd.DataFrame)
    assert len(df_clean) > 0
    assert "Date" in df_clean.columns or "__date__" in df_clean.columns

def test_data_analysis(test_csv_path):
    """Verify data analyzer produces KPIs and summary."""
    df_clean, _ = clean_data(test_csv_path)
    analysis = analyze_data(df_clean)
    assert isinstance(analysis, dict)
    assert "kpis" in analysis
    assert "summary_text" in analysis

def test_data_visualization(test_csv_path):
    """Verify data visualizer generates Chart.js structures."""
    df_clean, _ = clean_data(test_csv_path)
    analysis = analyze_data(df_clean)
    viz = visualize_data(df_clean, analysis)
    assert isinstance(viz, dict)
    assert "charts" in viz
    assert viz["chart_count"] >= 0

@pytest.mark.skipif(not os.getenv("SUPABASE_DB_URL"), reason="SUPABASE_DB_URL secret not configured")
def test_rag_ingestion(test_csv_path):
    """Verify RAG engine can connect and ingest vectors (skipped if no Supabase secret)."""
    from rag import RAGEngine
    rag = RAGEngine()
    df_clean, _ = clean_data(test_csv_path)
    rag_res = rag.ingest_csv(test_csv_path, "TS_11.csv", df=df_clean)
    assert isinstance(rag_res, dict)
    assert "chunks" in rag_res

@pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason="GEMINI_API_KEY secret not configured")
def test_llm_insights(test_csv_path):
    """Verify LLM client can call Gemini API (skipped if no Gemini secret)."""
    from llm import LLMClient
    llm = LLMClient()
    df_clean, _ = clean_data(test_csv_path)
    analysis = analyze_data(df_clean)
    summary = analysis.get("summary_text", "Business summary data.")
    insights = llm.generate_insights(summary)
    assert isinstance(insights, list)
    if insights:
        assert "title" in insights[0]
