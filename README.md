# LazyBIZ — Enterprise-Grade Cloud-Native Business Intelligence Platform

LazyBIZ is a production-ready, cloud-native Business Intelligence platform that transforms raw data into high-value business insights. The platform leverages a state-of-the-art Model Context Protocol (MCP) architecture, stateful Agentic workflows (LangGraph), and cloud-hosted vector search (Supabase + pgvector) to provide automated data cleaning, statistical analysis, interactive charts, and natural-language data querying.

---

## 🚀 Key Architectural Upgrades

### 1. Cloud-Native Vector DB: Supabase + pgvector
*   **ChromaDB completely replaced.** Local sqlite3-based vector databases are lost when platforms like Render restart. LazyBIZ now stores embeddings persistently in a cloud-hosted **PostgreSQL instance on Supabase** using the `pgvector` extension.
*   **768-Dimension Embeddings:** Uses the full output range of Gemini's `text-embedding-004` model.
*   **Fast Indexing:** Uses an `IVFFlat` cosine distance index on Supabase for sub-millisecond retrieval.
*   **User Isolation:** Data is fully partitioned on retrieval, update, and deletion based on JWT authentication. Users only see and query their own datasets and history.

### 2. Model Context Protocol (MCP) Server
*   LazyBIZ exposes its core business intelligence tools (`clean_dataset`, `analyze_dataset`, `visualize_dataset`, `query_business_data`) through a standardized **MCP Server** (`backend/mcp_tools/mcp_server.py`).
*   This server implements the JSON-RPC 2.0 protocol over standard input/output (`stdio`), allowing compatible AI hosts like **Claude Desktop** and **Cursor IDE** to directly consume your business analysis engine.

### 3. LangGraph Agentic Workflow
*   Replaces basic `if/else` logic with a stateful, directed graph agent:
    *   **Classify Node:** Detects query intent (data vs. visualization vs. general).
    *   **RAG Retrieve Node:** Connects to Supabase to fetch context and pre-generated analysis summaries.
    *   **Visualization Node:** Automatically guides users to interactive charts.
    *   **Generate Node:** Calls the generative model to write context-grounded business answers.

### 4. MLOps CI/CD Pipeline
*   Configured inside `.github/workflows/mlops_pipeline.yml`.
*   Every push or pull request to the `main` branch triggers:
    1.  Ruff code checking.
    2.  Pytest backend unit tests.
    3.  Schema validation on LLM output.
    4.  Automatic webhook trigger for Render deployment.

---

## 🛠️ Technology Stack

*   **Backend:** FastAPI (Python 3.11)
*   **Database:** MongoDB Atlas (User data/reports), Supabase pgvector (Vector store)
*   **Orchestration:** LangGraph & LangChain Core
*   **MCP Protocol:** FastMCP Server
*   **Primary LLM Model:** Gemini Flash (`gemini-1.5-flash`) & Gemini Embedding (`text-embedding-004`)
*   **Frontend:** Vanilla ES6+ SPA, Chart.js, Vanilla CSS Glassmorphism

---

## 📦 Local Installation

### 1. Requirements
*   Python 3.11
*   MongoDB Atlas Account
*   Supabase Account (with pgvector enabled)
*   Gemini API Key (and optionally Groq / OpenRouter)

### 2. Environment Setup
Create `backend/.env` containing:
```env
JWT_SECRET=your_jwt_secret
MONGO_URI=your_mongodb_atlas_uri
GEMINI_API_KEY=your_gemini_api_key

# Supabase pgvector DB Urls
# Local (Direct / IPv6):
SUPABASE_DB_URL=postgresql://postgres:[PASSWORD]@db.xmkbjytyabwufumunhkb.supabase.co:5432/postgres
# Render (Session pooler / IPv4):
SUPABASE_DB_URL_IPV4=postgresql://postgres.xmkbjytyabwufumunhkb:[PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres
```

### 3. Create & Install Virtual Environment
```bash
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
```

### 4. Run the Platform
```bash
.\venv\Scripts\python.exe run.py
```
Open `http://localhost:5001` in your browser.

---

## 🔒 Security & Privacy Enforcements
*   **JWT Protected:** Authorization Bearer tokens guard all API operations.
*   **Strict Scope Querying:** Database queries explicitly query by `user_email` mapped from the verified JWT payload. Uploads and reports cannot leak across accounts.
