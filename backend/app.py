import os
import sys

# Force UTF-8 output on Windows to prevent emoji print crashes
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# MUST BE FIRST: Disable telemetry to prevent crashes on Python 3.9
os.environ["CHROMA_TELEMETRY_IMPL"] = "INMEMORY"
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["POSTHOG_DISABLED"] = "1"

"""
LazyBIZ RAG Dashboard - Main Flask Application
Cloud-Native Edition (MongoDB Atlas)
"""

# Monkey-patch sqlite3 for ChromaDB compatibility on older systems
try:
    __import__('pysqlite3')
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass

import json
import datetime
import threading
import uuid
import traceback
from functools import wraps

from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
from pymongo import MongoClient
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import jwt
import bcrypt

from rag import RAGEngine
from llm import LLMClient
from mcp_tools import (
    validate_csv, list_uploaded_files, get_upload_metadata,
    clean_data, analyze_data, visualize_data
)

# Load environment variables
load_dotenv(override=True)

# --- App Configuration ---
app = Flask(
    __name__,
    static_folder="../frontend",
    static_url_path=""
)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB limit
CORS(app, resources={r"/api/*": {"origins": "*"}})

app.config["SECRET_KEY"] = os.getenv("JWT_SECRET", "lazybiz_default_secret")
app.config["UPLOAD_FOLDER"] = os.path.abspath(os.getenv("UPLOAD_FOLDER", "../data"))
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500MB max upload

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# --- Initialize Services ---
rag_engine = RAGEngine()
llm_client = LLMClient()

import certifi

# --- MongoDB Connection ---
mongo_uri = os.getenv("MONGO_URI")
if not mongo_uri:
    print("WARNING: MONGO_URI not found in environment!")

# Use certifi for SSL/TLS certificates to fix handshake issues on Windows
ca = certifi.where()
mongo_client = MongoClient(mongo_uri, tlsCAFile=ca, tlsAllowInvalidCertificates=True) if mongo_uri else None
db = mongo_client.lazybiz if mongo_client else None

class LocalMockCollection:
    def __init__(self):
        self.data = []
    def insert_one(self, doc):
        self.data.append(doc)
    def find_one(self, query, projection=None):
        for item in self.data:
            match = True
            for k, v in query.items():
                if item.get(k) != v:
                    match = False
                    break
            if match:
                if projection and "_id" in projection and projection["_id"] == 0:
                    return {k:v for k,v in item.items() if k != "_id"}
                return item
        return None
    def find(self, query={}, projection=None):
        results = []
        for item in self.data:
            match = True
            for k, v in query.items():
                if item.get(k) != v:
                    match = False
                    break
            if match:
                if projection and "_id" in projection and projection["_id"] == 0:
                    results.append({k:v for k,v in item.items() if k != "_id"})
                else:
                    results.append(item)
        class Cursor:
            def __init__(self, res): self.res = res
            def sort(self, key, direction):
                self.res.sort(key=lambda x: x.get(key, ""), reverse=(direction == -1))
                return self.res
            def __iter__(self): return iter(self.res)
        return Cursor(results)
    def update_one(self, query, update, upsert=False):
        doc = self.find_one(query)
        if doc:
            if "$set" in update:
                doc.update(update["$set"])
        elif upsert:
            new_doc = query.copy()
            if "$set" in update:
                new_doc.update(update["$set"])
            self.insert_one(new_doc)
    def delete_one(self, query):
        doc = self.find_one(query)
        if doc: self.data.remove(doc)
    def delete_many(self, query):
        docs = [d for d in self.find(query)]
        for d in docs: self.data.remove(d)

if db is not None:
    try:
        uploads_col = db.uploads
        jobs_col = db.jobs
        reports_col = db.reports
        
        # Test connection by calling ping
        mongo_client.admin.command('ping')
        
        uploads_col.create_index("file_id", unique=True)
        jobs_col.create_index("job_id", unique=True)
        reports_col.create_index("file_id", unique=True)
        print("MongoDB: Connected and Indices created.")
    except Exception as e:
        print(f"MongoDB Connection Warning: {e}")
        print("Falling back to local in-memory database.")
        uploads_col = LocalMockCollection()
        jobs_col = LocalMockCollection()
        reports_col = LocalMockCollection()
else:
    print("MongoDB: FAILED TO CONNECT. Falling back to local in-memory database.")
    uploads_col = LocalMockCollection()
    jobs_col = LocalMockCollection()
    reports_col = LocalMockCollection()

# --- Helper Functions ---
def _new_job(job_id: str, file_id: str):
    if jobs_col is not None:
        jobs_col.insert_one({
            "job_id": job_id,
            "file_id": file_id,
            "status": "queued",
            "progress": 0,
            "message": "Queued...",
            "steps": {
                "clean": "pending",
                "analyze": "pending",
                "visualize": "pending",
                "rag": "pending",
                "llm": "pending"
            },
            "created_at": datetime.datetime.utcnow().isoformat(),
            "started_at": None,
            "completed_at": None,
            "error": None
        })

def _update_job(job_id: str, **kwargs):
    if jobs_col is not None:
        jobs_col.update_one({"job_id": job_id}, {"$set": kwargs})

def _run_pipeline(job_id: str, file_id: str, filepath: str, filename: str):
    import traceback
    try:
        _update_job(job_id, status="running", progress=5, message="🔧 MCP Tool: Cleaning data...", steps={"clean": "running", "analyze": "pending", "visualize": "pending", "rag": "pending", "llm": "pending"}, started_at=datetime.datetime.utcnow().isoformat())
        
        # 1. Clean
        cleaned_df, clean_report = clean_data(filepath)
        _update_job(job_id, progress=20, message="📊 MCP Tool: Analyzing data...", steps={"clean": "completed", "analyze": "running", "visualize": "pending", "rag": "pending", "llm": "pending"})

        # 2. Analyze
        analysis = analyze_data(cleaned_df)
        _update_job(job_id, progress=50, message="📈 MCP Tool: Generating visualizations...", steps={"clean": "completed", "analyze": "completed", "visualize": "running", "rag": "pending", "llm": "pending"})

        # 3. Visualize
        print(f"\n[PIPELINE] STARTING VISUALIZATION STEP FOR: {filename}")
        viz = visualize_data(cleaned_df, analysis)
        print(f"[PIPELINE] VISUALIZATION COMPLETED FOR: {filename}\n")
        _update_job(job_id, progress=75, message="🧠 RAG: Embedding insights...", steps={"clean": "completed", "analyze": "completed", "visualize": "completed", "rag": "running", "llm": "pending"})

        # 4. RAG Ingestion
        try:
            rag_result = rag_engine.ingest_csv(filepath, filename, df=cleaned_df)
        except Exception:
            rag_result = {}

        try:
            summary_text = analysis.get("summary_text", "")
            if summary_text:
                rag_engine.collection.upsert(
                    documents=[summary_text],
                    metadatas=[{"source": filename, "type": "analysis_summary", "file_hash": rag_result.get("file_hash", ""), "row_index": -2}],
                    ids=[f"{rag_result.get('file_hash', job_id)}_summary"]
                )
        except Exception as e:
            print(f"RAG Summary Ingestion Error: {e}")
        _update_job(job_id, progress=90, message="✨ LLM: Generating business insights...", steps={"clean": "completed", "analyze": "completed", "visualize": "completed", "rag": "completed", "llm": "running"})

        # 5. LLM Insights
        context = summary_text
        if rag_engine.get_stats()["total_documents"] > 0:
            rag_ctx = rag_engine.query(
                "overall business performance revenue trends top products sentiment", 
                n_results=8,
                where={"source": filename}
            )
            if rag_ctx["context"]:
                context = rag_ctx["context"] + "\n\n" + summary_text

        insights = llm_client.generate_insights(context)
        
        # Save Final Report
        if reports_col is not None:
            reports_col.update_one(
                {"file_id": file_id},
                {"$set": {
                    "file_id": file_id,
                    "job_id": job_id,
                    "clean_report": clean_report,
                    "analysis": analysis,
                    "charts": viz["charts"],
                    "chart_count": viz["chart_count"],
                    "insights": insights,
                    "created_at": datetime.datetime.utcnow().isoformat()
                }},
                upsert=True
            )

        _update_job(job_id, status="done", progress=100, message="✅ Pipeline complete!", completed_at=datetime.datetime.utcnow().isoformat(), steps={"clean": "completed", "analyze": "completed", "visualize": "completed", "rag": "completed", "llm": "completed"})

    except Exception as e:
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        print(f"PIPELINE ERROR: {error_msg}")
        _update_job(job_id, status="failed", progress=0, message="Pipeline failed.", error=error_msg[:1000])

# --- User Management (Local for simplicity, could be Mongo) ---
USERS_FILE = os.path.join(app.config["UPLOAD_FOLDER"], "users.json")

def _load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            try: return json.load(f)
            except: return {}
    return {}

def _save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

# --- JWT Auth Decorator ---
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

        if not token:
            return jsonify({"error": "Authentication token required"}), 401

        try:
            payload = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
            request.user_email = payload.get("email", "")
        except:
            return jsonify({"error": "Invalid or expired token"}), 401

        return f(*args, **kwargs)
    return decorated

# ========================================
# ROUTES
# ========================================

@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    name, email, password = data.get("name"), data.get("email"), data.get("password")
    if not all([name, email, password]): return jsonify({"error": "Missing fields"}), 400
    
    users = _load_users()
    if email in users: return jsonify({"error": "User exists"}), 409
    
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    users[email] = {"name": name, "email": email, "password_hash": hashed}
    _save_users(users)
    
    token = jwt.encode({"email": email, "name": name, "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7)}, app.config["SECRET_KEY"], algorithm="HS256")
    return jsonify({"token": token, "user": {"name": name, "email": email}}), 201

@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    email, password = data.get("email"), data.get("password")
    users = _load_users()
    user = users.get(email)
    if not user or not bcrypt.checkpw(password.encode("utf-8"), user["password_hash"].encode("utf-8")):
        return jsonify({"error": "Invalid credentials"}), 401
    
    token = jwt.encode({"email": email, "name": user["name"], "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7)}, app.config["SECRET_KEY"], algorithm="HS256")
    return jsonify({"token": token, "user": {"name": user["name"], "email": email}})

@app.route("/api/upload", methods=["POST"])
@token_required
def upload_csv():
    if "file" not in request.files: return jsonify({"error": "No file"}), 400
    file = request.files["file"]
    if not file.filename.lower().endswith(".csv"): return jsonify({"error": "CSV only"}), 400
    
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    print(f"UPLOADING: {filename} to {filepath}...")
    file.save(filepath)
    print(f"UPLOAD COMPLETE: {filename} ({os.path.getsize(filepath)} bytes)")
    
    is_valid, msg, _ = validate_csv(filepath)
    if not is_valid: 
        os.remove(filepath)
        return jsonify({"error": msg}), 400
        
    fid = str(uuid.uuid4())
    if uploads_col is not None:
        uploads_col.insert_one({
            "file_id": fid, "file_name": filename, "filepath": filepath,
            "file_size": os.path.getsize(filepath), "upload_time": datetime.datetime.utcnow().isoformat(),
            "status": "uploaded"
        })
    return jsonify({"file_id": fid, "file_name": filename, "message": "Uploaded"}), 201

@app.route("/api/uploads", methods=["GET"])
@token_required
def list_uploads():
    if uploads_col is None: return jsonify({"files": []})
    files = list(uploads_col.find({}, {"_id": 0}).sort("upload_time", -1))
    for f in files:
        f["uploaded_at"] = f.get("upload_time")
        f["filename"] = f.get("file_name")
        f["size"] = f"{f.get('file_size',0)//1024} KB"
    return jsonify({"files": files})

@app.route("/api/upload/<fid>", methods=["DELETE"])
@token_required
def delete_upload(fid):
    """Delete a data source and its associated jobs/reports."""
    if uploads_col is not None:
        uploads_col.delete_one({"file_id": fid})
    if jobs_col is not None:
        jobs_col.delete_many({"file_id": fid})
    if reports_col is not None:
        reports_col.delete_one({"file_id": fid})
    return jsonify({"message": "Deleted successfully"})

@app.route("/api/start-analysis", methods=["POST"])
@token_required
def start_analysis():
    data = request.get_json() or {}
    fid = data.get("file_id")
    if not fid or uploads_col is None: return jsonify({"error": "Invalid request"}), 400
    
    fdoc = uploads_col.find_one({"file_id": fid})
    if not fdoc: return jsonify({"error": "File not found"}), 404
    
    jid = str(uuid.uuid4())
    _new_job(jid, fid)
    uploads_col.update_one({"file_id": fid}, {"$set": {"status": "processing"}})
    
    threading.Thread(target=_run_pipeline, args=(jid, fid, fdoc["filepath"], fdoc["file_name"]), daemon=True).start()
    return jsonify({"job_id": jid}), 202

@app.route("/api/job/<jid>", methods=["GET"])
@token_required
def get_job(jid):
    if jobs_col is None: return jsonify({"error": "DB error"}), 500
    job = jobs_col.find_one({"job_id": jid}, {"_id": 0})
    return jsonify(job) if job else (jsonify({"error": "Not found"}), 404)

@app.route("/api/report/<fid>", methods=["GET"])
@token_required
def get_report(fid):
    if reports_col is None: return jsonify({"error": "DB error"}), 500
    rep = reports_col.find_one({"file_id": fid}, {"_id": 0})
    return jsonify(rep) if rep else (jsonify({"error": "Not found"}), 404)

# ========================================
# DASHBOARD & INSIGHTS
# ========================================

# ========================================
# ACCOUNT & SYSTEM
# ========================================

@app.route("/api/chat", methods=["POST"])
@token_required
def chat():
    data = request.get_json() or {}
    q = data.get("question")
    filename = data.get("filename")
    if not q: return jsonify({"error": "Question required"}), 400
    
    where_clause = {"source": filename} if filename else None
    
    # Increase n_results for better coverage and search for the summary specifically
    rctx = rag_engine.query(q, n_results=15, where=where_clause)
    
    # If a specific filename is selected, also try to fetch its global statistical summary
    # to provide the AI with the 'big picture' (total rows, columns, general stats)
    if filename:
        try:
            # Query ChromaDB for the 'analysis_summary' document for this source
            summary_res = rag_engine.collection.get(
                where={"$and": [{"source": filename}, {"type": "analysis_summary"}]}
            )
            if summary_res and summary_res["documents"]:
                summary_text = summary_res["documents"][0]
                # Prepend the global summary to the context
                rctx["context"] = f"GLOBAL DATASET SUMMARY:\n{summary_text}\n\nRELEVANT DATA SNIPPETS:\n{rctx['context']}"
        except Exception as e:
            print(f"Chat: Could not fetch summary for {filename}: {e}")

    ans = llm_client.chat_with_context(q, rctx["context"], rctx["sources"])
    return jsonify({"answer": ans, "sources": rctx["sources"]})

@app.route("/")
def index(): return send_from_directory(app.static_folder, "index.html")

@app.route("/<path:path>")
def static_proxy(path):
    fp = os.path.join(app.static_folder, path)
    return send_from_directory(app.static_folder, path) if os.path.exists(fp) else send_from_directory(app.static_folder, "index.html")

@app.route("/api/health")
def health(): return jsonify({"status": "ready", "db": db is not None})

if __name__ == "__main__":
    try:
        port = int(os.environ.get("PORT", 5001))
        print(f"\n[LazyBIZ] Initializing Server on port {port}...")
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
    except Exception as e:
        print(f"\n[FATAL SERVER ERROR] {e}")
        import traceback
        traceback.print_exc()
