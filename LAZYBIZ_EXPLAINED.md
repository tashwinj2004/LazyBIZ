# LazyBIZ: Project Overview & Technical Breakdown

**LazyBIZ** is a cloud-native, AI-powered Business Intelligence (BI) platform that automates the transition from raw data to actionable insights. It combines modern data engineering pipelines with **Retrieval-Augmented Generation (RAG)** to allow users to interact with their datasets using natural language.

---

## 🚀 Core Features
- **One-Click BI Pipeline**: Automated data cleaning, statistical analysis, and visualization.
- **Conversational Analytics**: Ask questions like *"Why did revenue drop in Q3?"* and get data-backed answers.
- **RAG-Powered Memory**: Uses a vector database to remember context across large datasets.
- **Modular MCP Architecture**: Extensible "Model Context Protocol" tools for data processing.

---

## 🛠️ Technology Stack

### 1. Programming Languages & Core
- **Python (3.11+)**: Backend engine for data processing and AI integration.
- **JavaScript (ES6+)**: Interactive frontend logic for real-time dashboard updates.
- **HTML5 & CSS3**: Modern UI with a focus on usability and data visualization.

### 2. Frameworks & Web
- **FastAPI**: Modern, high-performance web framework for API management with native Pydantic validation and asynchronous routing.
- **CORSMiddleware**: Handles cross-origin resource sharing for secure frontend-backend communication.
- **Uvicorn**: Asynchronous ASGI server for production deployment.

### 3. Artificial Intelligence (AI) & LLMs
- **Primary LLM**: Groq API (`llama-3.3-70b-versatile`) for ultra-fast reasoning.
- **Fallback LLM**: Google Gemini (`gemini-1.5-flash`) via direct REST API integration.
- **Embedding Model**: `all-MiniLM-L6-v2` (SentenceTransformer) for converting text into high-dimensional vectors.
- **Retrieval Strategy**: Vectorized RAG using **ChromaDB** with Cosine Similarity.

### 4. Data Engineering & Databases
- **MongoDB Atlas**: Cloud-native NoSQL database for user accounts, job status, and persistence.
- **ChromaDB**: High-performance vector database for semantic search and RAG.
- **Pandas & NumPy**: Core libraries for high-speed data manipulation and numerical computation.
- **Scikit-learn**: Used for advanced statistical analysis and data preprocessing.

### 5. Visualization & UI
- **Matplotlib & Seaborn**: Backend generation of data insights and statistical charts.
- **CSS3 Variables**: Theming system (Primary color: `#096C6C`).

---

## 📖 Component Explanations (With Examples)

### **A. Retrieval-Augmented Generation (RAG)**
*   **What it is**: Instead of the AI "guessing," RAG looks up the exact numbers in your data first and then explains them.
*   **Example**: When you ask "Who is my top customer?", the system searches the **ChromaDB** vector store for the customer with the highest sales, retrieves the name "John Doe" and total "$50k," and then the LLM answers: *"Your top customer is John Doe with a total spend of $50,000."*

### **B. Data Ingestion Pipeline**
*   **What it is**: A multi-step process that cleans, analyzes, and indexes data automatically.
*   **Example**: If you upload a CSV with a column `Sales_Date` containing messy strings like "2023/01/01" and "Jan-22-2023", the **Data Cleaner** tool uses `pandas` to standardize them into a single format before analysis begins.

### **C. Modular MCP Tools**
*   **What it is**: A "plug-and-play" architecture where different tools handle specific tasks (Clean, Analyze, Visualize).
*   **Example**: The `DataVisualizer` tool detects that your data has a "Date" and "Revenue" column and automatically decides to generate a **Time-Series Line Chart** to show sales trends.

### **D. Multi-Provider LLM Switching**
*   **What it is**: A smart router that switches between AI providers if one is slow or down.
*   **Example**: If **Groq** hits a rate limit while you are chatting, the system automatically redirects the request to **Google Gemini** in the background, ensuring you never see an error message.

---

## 📊 Database Schema Summary
- **MongoDB**: Stores `users`, `uploads` (metadata), `jobs` (pipeline status), and `reports` (final AI results).
- **ChromaDB**: Stores `documents` (data snippets), `metadatas` (source file, row index), and `embeddings` (vector representation).

---

## 🔒 Security & Auth
- **JWT (JSON Web Tokens)**: Secure, stateless authentication for all API endpoints.
- **Bcrypt**: Industrial-grade password hashing for user data protection.
