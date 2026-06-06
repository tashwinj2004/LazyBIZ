# LazyBIZ — AI-Powered Enterprise BI Dashboard

LazyBIZ is a state-of-the-art Business Intelligence platform that transforms raw data into actionable insights using AI. It leverages a Retrieval-Augmented Generation (RAG) pipeline to provide deep analytics, automated visualizations, and a natural language chatbot for your CSV data.

![LazyBIZ Header](https://via.placeholder.com/1200x400/0b1326/ffffff?text=LazyBIZ+AI+Analytics)

## 🚀 Key Features

- **Automated Data Cleaning (MCP):** Automatically detects and fixes missing values, outliers, and formatting issues.
- **Dynamic Visualizations:** Generates insightful charts (Revenue trends, Product performance, etc.) using Chart.js.
- **RAG-Powered Chatbot:** "Ask LazyBIZ AI" allows you to query your data in natural language with source-specific grounding.
- **Dual-Provider LLM Strategy:** Seamless fallback between Groq and OpenRouter to ensure high availability.
- **Enterprise Design:** A premium, dark-mode dashboard built with glassmorphism and modern typography (Inter).
- **History Management:** Revisit previously uploaded datasets and their AI-generated reports instantly.

## 🛠️ Technology Stack

### Backend
- **Core:** Python (FastAPI)
- **Vector Database:** ChromaDB (local persistence)
- **Metadata Database:** MongoDB Atlas
- **Embeddings:** SentenceTransformers (`all-MiniLM-L6-v2`)
- **LLM Integration:** Groq (primary) & OpenRouter (fallback)
- **Data Processing:** Pandas, NumPy

### Frontend
- **Structure:** Single Page Application (SPA) architecture
- **Logic:** Vanilla JavaScript (ES6+)
- **Charts:** Chart.js
- **Styling:** Premium Vanilla CSS (Custom design system)
- **Icons:** Google Material Icons Outlined

## 📦 Setup & Installation

### 1. Prerequisites
- Python 3.9+
- MongoDB Atlas account (or local MongoDB)
- API Keys for **Groq** and/or **OpenRouter**

### 2. Clone the Repository
```bash
git clone <repository-url>
cd "LazyBIZ"
```

### 3. Install Dependencies
```bash
pip install -r backend/requirements.txt
```

### 4. Environment Configuration
Create a `.env` file in the root directory (or inside `backend/`):
```env
# API Keys
GROQ_API_KEY=your_groq_api_key
OPENROUTER_API_KEY=your_openrouter_api_key

# Database
MONGO_URI=your_mongodb_connection_string

# App Settings
JWT_SECRET=your_secret_key
UPLOAD_FOLDER=../data
CHROMA_DB_PATH=../data/chroma_db
```

## 🏃 Running the Application

1. **Start the Backend (Recommended):**
   ```bash
   python start.py
   ```
   *This automatically verifies/installs your venv dependencies and runs the FastAPI backend.*

   Alternatively, if you prefer manual startup:
   ```bash
   .\venv\Scripts\activate
   cd backend
   python app.py
   ```
   *The server will start on `http://localhost:5001`*

2. **Access the Dashboard:**
   Open your browser and navigate to `http://localhost:5001`.

## 📖 How to Use

1. **Sign Up / Login:** Create an account to secure your data.
2. **Upload CSV:** Drop a sales, review, or business dataset into the upload zone.
3. **Wait for Pipeline:** Watch the MCP tool clean data, generate charts, and embed context.
4. **Explore Insights:** View the auto-generated business recommendations.
5. **Chat with AI:** Use the chatbot to ask specific questions like *"What is our total revenue for Q3?"* or *"Identify the top 3 underperforming products."*

## 🔒 Security & Privacy
- **JWT Authentication:** All API endpoints are protected via JSON Web Tokens.
- **Local RAG:** Your raw data chunks are stored in a local vector database, and only relevant snippets are sent to the LLM for processing.

---
Built with ❤️ by the LazyBIZ Team.
