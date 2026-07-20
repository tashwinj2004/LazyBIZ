# LazyBIZ — AI-Powered Business Intelligence & Analytics Platform

LazyBIZ is an enterprise-ready, cloud-native Business Intelligence (BI) platform that transforms raw business data into actionable visual insights and natural-language intelligence. Built using a modern cloud architecture, it automates data cleaning, generates professional statistical summaries, creates interactive dashboards, and provides a stateful AI Chatbot to converse with your datasets.

---

## 🌟 Key Features

### 📊 Automated Data Cleaning
*   **Missing Data Imputation:** Smart handling of missing values, nulls, and outliers.
*   **Format Standardization:** Automatically normalizes date formats and strips anomalous characters.
*   **Duplicate Elimination:** Instantly identifies and removes redundant data rows.

### 📈 Instant Analytics & Visualization
*   **KPI Generation:** Automatically extracts key business metrics (Revenue, sales growth, category breakdowns).
*   **Interactive Charts:** Powers rich data visualizations using Chart.js.
*   **Automated Forecasting:** Generates basic business forecasts and trend predictions.

### 💬 Stateful AI Chat Agent (RAG)
*   **Semantic Data Search:** Searches your data contextually using high-dimensional embeddings stored in a cloud vector database.
*   **Intent Classification:** Dynamically routes queries (e.g., distinguishing between requests for charts, calculations, or general chat).
*   **Grounded QA:** The chatbot answers questions strictly using your uploaded CSV data to prevent AI hallucinations.

### 🔒 Enterprise User Isolation
*   **Strict Partitioning:** Full account segregation. Users can only upload, list, delete, and query their own datasets and history.
*   **JWT Authorization:** Secure token-based access to all API routes.

### 🔌 Model Context Protocol (MCP) Server
*   **External Integration:** Exposes the data engine tools via the Model Context Protocol (MCP). Allows client editors like Cursor IDE or Claude Desktop to use LazyBIZ tools directly.

---

## 🛠️ Technology Stack

*   **Frontend:** Vanilla ES6+ JS, Chart.js, Responsive Glassmorphism CSS.
*   **Backend:** FastAPI (Python 3.11).
*   **Primary Database:** MongoDB Atlas (Handles user accounts, job status, and preprocessed reports).
*   **Vector Database:** Supabase PostgreSQL with `pgvector` extension (Stores document embeddings).
*   **AI Engine:** LangGraph (Stateful workflow orchestrator) & Google Gemini (`gemini-1.5-flash` / `text-embedding-004`).

---

## 🚀 Setup & Installation

### 1. Prerequisites
*   Python 3.11
*   MongoDB Atlas connection string
*   Supabase PostgreSQL instance
*   Gemini API Key

### 2. Configure Environment Variables
Create a `.env` file inside the `backend/` directory:
```env
JWT_SECRET=your_jwt_secret
MONGO_URI=your_mongodb_connection_string
GEMINI_API_KEY=your_gemini_api_key

# Supabase PostgreSQL connection strings
SUPABASE_DB_URL=postgresql://postgres:[PASSWORD]@db.yourhost.supabase.co:5432/postgres
SUPABASE_DB_URL_IPV4=postgresql://postgres.yourhost:[PASSWORD]@aws-0.pooler.supabase.com:5432/postgres
```

### 3. Installation
1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/tashwinj2004/LazyBIZ.git
    cd LazyBIZ
    ```
2.  **Create and Activate Virtual Environment:**
    ```bash
    python -m venv venv
    .\venv\Scripts\Activate.ps1
    ```
3.  **Install Dependencies:**
    ```bash
    pip install -r backend/requirements.txt
    ```

---

## 🏃 Running the Application

### Option A: Local Run (Development)
Activate your virtual environment and run the launcher:
```bash
.\venv\Scripts\python.exe run.py
```
Open **`http://localhost:5001`** in your browser.

### Option B: Docker Compose (Production)
Run the application in a detached background container:
```bash
docker compose up --build -d
```
Open **`http://localhost:5001`** in your browser.

---

## 📂 Project Structure
```text
├── backend/
│   ├── llm/                 # LangGraph Agent workflow & LLM prompt logic
│   ├── mcp_tools/           # MCP server & core business logic tools
│   ├── rag/                 # Supabase PostgreSQL + pgvector engine
│   ├── app.py               # Main FastAPI Application routes
│   └── requirements.txt     # Python backend dependencies
├── frontend/                # SPA files (HTML, CSS, JS, Assets)
├── .github/workflows/       # MLOps CI/CD test and lint pipelines
├── Dockerfile               # App container build definition
└── docker-compose.yml       # Multi-container orchestration schema
```
