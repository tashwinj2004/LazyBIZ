"""
LangGraph Agentic Workflow — LazyBIZ Data Intelligence Agent
=============================================================
Replaces the hard-coded if/else routing in app.py with a stateful LangGraph
state machine. The agent:

  1. CLASSIFIES user intent (data_query / visualization / general)
  2. ROUTES to the appropriate processing node
  3. RETRIEVES RAG context if needed
  4. GENERATES a response via the multi-provider LLM client

Graph structure:
    [START] → classify → rag_retrieve  → generate_response → [END]
                      ↘ visualization  → generate_response → [END]
                      ↘ general        → generate_response → [END]
"""

import logging
from typing import TypedDict, Annotated
import operator

from langgraph.graph import StateGraph, END, START

logger = logging.getLogger(__name__)


# ── 1. Shared State Schema ─────────────────────────────────────────────────────

class AgentState(TypedDict):
    """
    The shared memory that flows through every node in the graph.
    Each node receives the current state and returns a partial update.
    """
    query: str                      # The user's raw question
    filename: str | None            # Which CSV file to scope the search to
    intent: str                     # Classified: 'data_query' | 'visualization' | 'general'
    rag_context: str                # Retrieved semantic context from pgvector
    sources: Annotated[list, operator.add]  # Source files found during retrieval
    response: str                   # Final answer to return to the user


# ── 2. Node Definitions ────────────────────────────────────────────────────────

def classify_node(state: AgentState) -> dict:
    """
    Node: Classify the user's intent using keyword heuristics + LLM fallback.

    In a fully productionized system, this would call the LLM to classify.
    For low-latency performance we use fast keyword matching first, with
    the LLM as a fallback for ambiguous cases.
    """
    query = state["query"].lower()

    visualization_keywords = [
        "chart", "graph", "plot", "visuali", "bar", "pie", "line",
        "trend", "histogram", "scatter",
    ]
    general_keywords = [
        "hello", "hi", "help", "what is", "who are you", "what can you",
        "how do you", "explain", "tell me about lazybiz",
    ]

    if any(kw in query for kw in visualization_keywords):
        intent = "visualization"
    elif any(kw in query for kw in general_keywords):
        intent = "general"
    else:
        intent = "data_query"

    logger.info("[Agent] Classified intent: '%s' for query: '%s'", intent, state["query"][:60])
    return {"intent": intent}


def rag_retrieve_node(state: AgentState) -> dict:
    """
    Node: Perform semantic search in pgvector for data-related queries.
    Injects the retrieved context and sources into the agent state.
    """
    # Import here to avoid circular imports at module load time
    from rag import RAGEngine
    engine = RAGEngine()

    where = {"source": state["filename"]} if state.get("filename") else None
    result = engine.query(state["query"], n_results=12, where=where)

    # Also retrieve the analysis summary if we have a specific file
    summary_prefix = ""
    if state.get("filename"):
        summary = engine.get_summary(state["filename"])
        if summary:
            summary_prefix = f"GLOBAL DATASET SUMMARY:\n{summary}\n\nRELEVANT DATA SNIPPETS:\n"

    logger.info("[Agent] RAG retrieved %d chars of context.", len(result["context"]))
    return {
        "rag_context": summary_prefix + result["context"],
        "sources": result["sources"],
    }


def visualization_node(state: AgentState) -> dict:
    """
    Node: Handle visualization intent.
    Charts are generated during the pipeline (upload + analysis step), not
    on-demand in chat. We guide the user to the dashboard instead.
    """
    response = (
        "📊 I can see you're asking about a chart or visualization. "
        "Charts are generated automatically when you upload and analyze a CSV file. "
        "Head to your **Dashboard** to view the interactive charts for your uploaded data. "
        "If you'd like a specific insight from the data, ask me a question like "
        "'What are the top 5 products by revenue?'"
    )
    return {"response": response, "rag_context": "", "sources": []}


def general_node(state: AgentState) -> dict:
    """
    Node: Handle general / off-topic questions that don't need data context.
    """
    return {
        "rag_context": (
            "The user is asking a general question (not related to their uploaded data). "
            "Introduce yourself briefly and offer to help with their business data."
        ),
        "sources": [],
    }


def generate_response_node(state: AgentState) -> dict:
    """
    Node: Generate the final AI response using the LLM client.
    Skipped if a node already set state['response'] (e.g., visualization_node).
    """
    # If a previous node already set the response, don't re-generate
    if state.get("response"):
        return {}

    from llm import LLMClient
    client = LLMClient()

    answer = client.chat_with_context(
        question=state["query"],
        rag_context=state["rag_context"],
        sources=state.get("sources"),
    )
    return {"response": answer}


# ── 3. Routing Function ────────────────────────────────────────────────────────

def route_by_intent(state: AgentState) -> str:
    """
    Conditional edge: reads the classified intent and returns the next node name.
    LangGraph uses this return value to choose which edge to follow.
    """
    intent = state.get("intent", "data_query")
    routing_map = {
        "data_query":   "rag_retrieve",
        "visualization": "visualization",
        "general":       "general",
    }
    return routing_map.get(intent, "rag_retrieve")


# ── 4. Build and Compile the Graph ────────────────────────────────────────────

def build_agent() -> StateGraph:
    """
    Construct the LangGraph state machine.

    Graph edges:
        START → classify → [conditional] → rag_retrieve    → generate_response → END
                                         → visualization   → generate_response → END
                                         → general         → generate_response → END
    """
    graph = StateGraph(AgentState)

    # Register nodes
    graph.add_node("classify", classify_node)
    graph.add_node("rag_retrieve", rag_retrieve_node)
    graph.add_node("visualization", visualization_node)
    graph.add_node("general", general_node)
    graph.add_node("generate_response", generate_response_node)

    # Entry point
    graph.add_edge(START, "classify")

    # Conditional routing after classification
    graph.add_conditional_edges(
        "classify",
        route_by_intent,
        {
            "rag_retrieve": "rag_retrieve",
            "visualization": "visualization",
            "general": "general",
        },
    )

    # All paths converge at generate_response → END
    graph.add_edge("rag_retrieve", "generate_response")
    graph.add_edge("visualization", "generate_response")
    graph.add_edge("general", "generate_response")
    graph.add_edge("generate_response", END)

    return graph.compile()


# ── 5. Convenience run function ────────────────────────────────────────────────

# Compile once at import time (reused across requests)
_agent = None

def get_agent():
    global _agent
    if _agent is None:
        _agent = build_agent()
    return _agent


def run_agent(query: str, filename: str | None = None) -> dict:
    """
    Entry point called by app.py's /api/chat endpoint.

    Args:
        query:    The user's chat message.
        filename: Optional CSV filename to scope the RAG search.

    Returns:
        {"answer": str, "sources": list[str], "intent": str}
    """
    initial_state: AgentState = {
        "query": query,
        "filename": filename,
        "intent": "",
        "rag_context": "",
        "sources": [],
        "response": "",
    }

    try:
        agent = get_agent()
        final_state = agent.invoke(initial_state)
        return {
            "answer": final_state.get("response", "No response generated."),
            "sources": final_state.get("sources", []),
            "intent": final_state.get("intent", "unknown"),
        }
    except Exception as exc:
        logger.error("[Agent] run_agent failed: %s", exc)
        return {
            "answer": (
                "⚠️ The AI agent encountered an error. "
                "Please try again or rephrase your question."
            ),
            "sources": [],
            "intent": "error",
        }
