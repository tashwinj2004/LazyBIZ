"""
LazyBIZ MCP Server — Model Context Protocol Tool Registry
===========================================================
Exposes LazyBIZ's data processing tools (clean, analyze, visualize) as
standard MCP tools discoverable by any MCP-compatible AI client:
  • Claude Desktop
  • Cursor IDE
  • Any LLM agent using the open MCP standard

HOW TO RUN:
    python -m mcp_tools.mcp_server
    # or, in stdio mode for Claude Desktop / Cursor:
    python backend/mcp_tools/mcp_server.py

HOW TO CONNECT FROM CLAUDE DESKTOP:
    Add to claude_desktop_config.json:
    {
      "mcpServers": {
        "lazybiz": {
          "command": "python",
          "args": ["<absolute-path>/backend/mcp_tools/mcp_server.py"]
        }
      }
    }

PROTOCOL: JSON-RPC 2.0 over stdio (standard MCP transport).
"""

import os
import sys
import logging

# Ensure the backend directory is on the Python path when run directly
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

# ── Initialize the MCP Server ──────────────────────────────────────────────────
mcp = FastMCP(
    name="lazybiz-data-engine",
    instructions=(
        "You are connected to the LazyBIZ Business Intelligence engine. "
        "You can clean CSV datasets, run analytical calculations, and generate "
        "business data visualizations. Always clean data before analyzing it."
    ),
)


# ── Tool 1: Data Cleaner ───────────────────────────────────────────────────────

@mcp.tool()
def clean_dataset(filepath: str) -> str:
    """
    Standardize and clean a CSV dataset.

    Performs: date normalization, missing value imputation, outlier flagging,
    duplicate removal, and column type inference.

    Args:
        filepath: Absolute path to the CSV file to clean.

    Returns:
        A summary string describing what was cleaned and how many issues were fixed.
    """
    try:
        from mcp_tools.data_cleaner import clean_data
        import pandas as pd

        cleaned_df, report = clean_data(filepath)

        # Build a concise summary for the LLM
        summary_parts = [
            f"✅ Dataset cleaned successfully.",
            f"Rows processed: {len(cleaned_df)}",
            f"Columns: {', '.join(cleaned_df.columns.tolist())}",
        ]
        if isinstance(report, dict):
            if report.get("duplicates_removed"):
                summary_parts.append(f"Duplicates removed: {report['duplicates_removed']}")
            if report.get("missing_filled"):
                summary_parts.append(f"Missing values filled: {report['missing_filled']}")
            if report.get("dates_normalized"):
                summary_parts.append(f"Date columns normalized: {report['dates_normalized']}")

        return "\n".join(summary_parts)

    except FileNotFoundError:
        return f"❌ File not found: {filepath}"
    except Exception as exc:
        logger.error("clean_dataset MCP tool failed: %s", exc)
        return f"❌ Data cleaning failed: {str(exc)}"


# ── Tool 2: Data Analyzer ─────────────────────────────────────────────────────

@mcp.tool()
def analyze_dataset(filepath: str) -> str:
    """
    Run statistical and business KPI analysis on a cleaned CSV dataset.

    Calculates: revenue totals, averages, growth rates, top/bottom performers,
    at-risk item detection, and generates a natural-language summary.

    Args:
        filepath: Absolute path to the CSV file (ideally already cleaned).

    Returns:
        A detailed analysis report as a formatted string with key metrics and insights.
    """
    try:
        from mcp_tools.data_cleaner import clean_data
        from mcp_tools.data_analyzer import analyze_data
        import json

        cleaned_df, _ = clean_data(filepath)
        analysis = analyze_data(cleaned_df)

        # Extract the most important parts for the LLM
        summary = analysis.get("summary_text", "Analysis complete.")
        kpis = analysis.get("kpis", {})

        result_parts = [
            "📊 Analysis Results:",
            summary,
            "",
            "Key Metrics:",
        ]
        for key, value in kpis.items():
            if isinstance(value, (int, float)):
                result_parts.append(f"  • {key.replace('_', ' ').title()}: {value:,.2f}")
            else:
                result_parts.append(f"  • {key.replace('_', ' ').title()}: {value}")

        return "\n".join(result_parts)

    except FileNotFoundError:
        return f"❌ File not found: {filepath}"
    except Exception as exc:
        logger.error("analyze_dataset MCP tool failed: %s", exc)
        return f"❌ Analysis failed: {str(exc)}"


# ── Tool 3: Data Visualizer ───────────────────────────────────────────────────

@mcp.tool()
def visualize_dataset(filepath: str) -> str:
    """
    Generate business charts and visualizations from a CSV dataset.

    Creates: revenue trends, product performance charts, category breakdowns,
    and saves them as base64-encoded PNG images.

    Args:
        filepath: Absolute path to the CSV file.

    Returns:
        A summary of the charts generated, including their types and output paths.
    """
    try:
        from mcp_tools.data_cleaner import clean_data
        from mcp_tools.data_analyzer import analyze_data
        from mcp_tools.data_visualizer import visualize_data

        cleaned_df, _ = clean_data(filepath)
        analysis = analyze_data(cleaned_df)
        viz_result = visualize_data(cleaned_df, analysis)

        chart_count = viz_result.get("chart_count", 0)
        charts = viz_result.get("charts", [])

        result_parts = [
            f"📈 Generated {chart_count} chart(s) successfully.",
        ]
        for chart in charts:
            chart_type = chart.get("type", "unknown")
            chart_title = chart.get("title", "Untitled")
            result_parts.append(f"  • {chart_type}: {chart_title}")

        return "\n".join(result_parts)

    except FileNotFoundError:
        return f"❌ File not found: {filepath}"
    except Exception as exc:
        logger.error("visualize_dataset MCP tool failed: %s", exc)
        return f"❌ Visualization failed: {str(exc)}"


# ── Tool 4: RAG Query ─────────────────────────────────────────────────────────

@mcp.tool()
def query_business_data(question: str, filename: str = "") -> str:
    """
    Ask a natural-language question about uploaded business data using RAG.

    Performs semantic search over the pgvector database and returns relevant
    context to answer questions about revenues, products, trends, and more.

    Args:
        question: The business question to answer.
        filename: Optional — scope the search to a specific CSV file.

    Returns:
        The relevant data context that answers the question.
    """
    try:
        from rag import RAGEngine
        engine = RAGEngine()

        where = {"source": filename} if filename else None
        result = engine.query(question, n_results=10, where=where)

        context = result.get("context", "No relevant data found.")
        sources = result.get("sources", [])

        parts = [context]
        if sources:
            parts.append(f"\nData sources: {', '.join(sources)}")
        return "\n".join(parts)

    except Exception as exc:
        logger.error("query_business_data MCP tool failed: %s", exc)
        return f"❌ RAG query failed: {str(exc)}"


# ── Entry Point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Run in stdio mode — standard transport for Claude Desktop and Cursor IDE
    print("[LazyBIZ MCP Server] Starting in stdio mode...", file=sys.stderr)
    mcp.run(transport="stdio")
