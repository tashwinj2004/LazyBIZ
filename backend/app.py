import os
import sys
import logging

# Monkey-patch sqlite3 for ChromaDB compatibility on older systems
try:
    __import__('pysqlite3')
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass

# Force unbuffered/line-buffered output so logs show up instantly on Render
try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Force UTF-8 output on Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# MUST BE FIRST: Disable telemetry and limit threads to prevent PyTorch deadlocks on Render
os.environ["CHROMA_TELEMETRY_IMPL"] = "INMEMORY"
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["POSTHOG_DISABLED"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

"""
LazyBIZ RAG Dashboard - Main FastAPI Application
Cloud-Native Edition (MongoDB Atlas)
"""

import json
import datetime
import threading
import uuid
import traceback

from fastapi import FastAPI, Request, HTTPException, Depends, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Union

from pymongo import MongoClient
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import jwt
import bcrypt
import certifi

# Lazy import inside helpers to prevent startup blocks
from mcp_tools import (
    validate_csv, list_uploaded_files, get_upload_metadata,
    clean_data, analyze_data, visualize_data
)

# Load environment variables
load_dotenv(override=True)

# --- App Configuration ---
SECRET_KEY = os.getenv("JWT_SECRET", "lazybiz_default_secret")
UPLOAD_FOLDER = os.path.abspath(os.getenv("UPLOAD_FOLDER", "../data"))
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../frontend"))

app = FastAPI(title="LazyBIZ RAG Dashboard", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static frontend files — only mount directories that actually exist
_static_dirs = {"js": "js", "css": "css", "assets": "assets", "images": "images", "fonts": "fonts"}
for _mount_name, _subdir in _static_dirs.items():
    _full_path = os.path.join(FRONTEND_DIR, _subdir)
    if os.path.isdir(_full_path):
        app.mount(f"/{_mount_name}", StaticFiles(directory=_full_path), name=_mount_name)

# --- Lazy Loading Helpers ---
_rag_engine = None
_llm_client = None

def get_rag_engine():
    global _rag_engine
    if _rag_engine is None:
        print("[LazyBIZ] Initializing RAG Engine (lazy-loaded)...")
        from rag import RAGEngine
        _rag_engine = RAGEngine()
    return _rag_engine

def get_llm_client():
    global _llm_client
    if _llm_client is None:
        print("[LazyBIZ] Initializing LLM Client (lazy-loaded)...")
        from llm import LLMClient
        _llm_client = LLMClient()
    return _llm_client

# --- MongoDB Connection ---
mongo_uri = os.getenv("MONGO_URI")
if not mongo_uri:
    print("WARNING: MONGO_URI not found in environment!")

ca = certifi.where()
mongo_client = MongoClient(mongo_uri, tlsCAFile=ca, tlsAllowInvalidCertificates=True, serverSelectionTimeoutMS=5000) if mongo_uri else None
db = mongo_client.lazybiz if mongo_client else None

class LocalMockCollection:
    def __init__(self):
        self.data = []
    def insert_one(self, doc):
        self.data.append(doc)
    def find_one(self, query, projection=None):
        for item in self.data:
            match = all(item.get(k) == v for k, v in query.items())
            if match:
                if projection and "_id" in projection and projection["_id"] == 0:
                    return {k: v for k, v in item.items() if k != "_id"}
                return item
        return None
    def find(self, query={}, projection=None):
        results = []
        for item in self.data:
            if all(item.get(k) == v for k, v in query.items()):
                if projection and "_id" in projection and projection["_id"] == 0:
                    results.append({k: v for k, v in item.items() if k != "_id"})
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
        if doc:
            self.data.remove(doc)
    def delete_many(self, query):
        docs = list(self.find(query))
        for d in docs:
            self.data.remove(d)

if db is not None:
    try:
        uploads_col = db.uploads
        jobs_col = db.jobs
        reports_col = db.reports
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
    jobs_col.insert_one({
        "job_id": job_id, "file_id": file_id, "status": "queued",
        "progress": 0, "message": "Queued...",
        "steps": {"clean": "pending", "analyze": "pending", "visualize": "pending", "rag": "pending", "llm": "pending"},
        "created_at": datetime.datetime.utcnow().isoformat(),
        "started_at": None, "completed_at": None, "error": None
    })

def _update_job(job_id: str, **kwargs):
    jobs_col.update_one({"job_id": job_id}, {"$set": kwargs})

def _run_pipeline(job_id: str, file_id: str, filepath: str, filename: str):
    try:
        _update_job(job_id, status="running", progress=5, message="🔧 MCP Tool: Cleaning data...",
                    steps={"clean": "running", "analyze": "pending", "visualize": "pending", "rag": "pending", "llm": "pending"},
                    started_at=datetime.datetime.utcnow().isoformat())

        # 1. Clean
        cleaned_df, clean_report = clean_data(filepath)
        _update_job(job_id, progress=20, message="📊 MCP Tool: Analyzing data...",
                    steps={"clean": "completed", "analyze": "running", "visualize": "pending", "rag": "pending", "llm": "pending"})

        # 2. Analyze
        analysis = analyze_data(cleaned_df)
        _update_job(job_id, progress=50, message="📈 MCP Tool: Generating visualizations...",
                    steps={"clean": "completed", "analyze": "completed", "visualize": "running", "rag": "pending", "llm": "pending"})

        # 3. Visualize
        print(f"\n[PIPELINE] STARTING VISUALIZATION STEP FOR: {filename}")
        viz = visualize_data(cleaned_df, analysis)
        print(f"[PIPELINE] VISUALIZATION COMPLETED FOR: {filename}\n")
        _update_job(job_id, progress=75, message="🧠 RAG: Embedding insights...",
                    steps={"clean": "completed", "analyze": "completed", "visualize": "completed", "rag": "running", "llm": "pending"})

        # 4. RAG Ingestion
        try:
            rag_result = get_rag_engine().ingest_csv(filepath, filename, df=cleaned_df)
        except Exception:
            rag_result = {}

        try:
            summary_text = analysis.get("summary_text", "")
            if summary_text:
                get_rag_engine().collection.upsert(
                    documents=[summary_text],
                    metadatas=[{"source": filename, "type": "analysis_summary", "file_hash": rag_result.get("file_hash", ""), "row_index": -2}],
                    ids=[f"{rag_result.get('file_hash', job_id)}_summary"]
                )
        except Exception as e:
            print(f"RAG Summary Ingestion Error: {e}")

        _update_job(job_id, progress=90, message="✨ LLM: Generating business insights...",
                    steps={"clean": "completed", "analyze": "completed", "visualize": "completed", "rag": "completed", "llm": "running"})

        # 5. LLM Insights
        context = analysis.get("summary_text", "")
        if get_rag_engine().get_stats()["total_documents"] > 0:
            rag_ctx = get_rag_engine().query(
                "overall business performance revenue trends top products sentiment",
                n_results=8, where={"source": filename}
            )
            if rag_ctx["context"]:
                context = rag_ctx["context"] + "\n\n" + context

        insights = get_llm_client().generate_insights(context)

        reports_col.update_one(
            {"file_id": file_id},
            {"$set": {
                "file_id": file_id, "job_id": job_id,
                "clean_report": clean_report, "analysis": analysis,
                "charts": viz["charts"], "chart_count": viz["chart_count"],
                "insights": insights,
                "created_at": datetime.datetime.utcnow().isoformat()
            }},
            upsert=True
        )

        _update_job(job_id, status="done", progress=100, message="✅ Pipeline complete!",
                    completed_at=datetime.datetime.utcnow().isoformat(),
                    steps={"clean": "completed", "analyze": "completed", "visualize": "completed", "rag": "completed", "llm": "completed"})

    except Exception as e:
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        print(f"PIPELINE ERROR: {error_msg}")
        _update_job(job_id, status="failed", progress=0, message="Pipeline failed.", error=error_msg[:1000])

# --- User Management ---
USERS_FILE = os.path.join(UPLOAD_FOLDER, "users.json")

def _load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            try:
                return json.load(f)
            except Exception:
                return {}
    return {}

def _save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

# --- JWT Auth ---
security = HTTPBearer(auto_error=False)

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication token required")
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=["HS256"])
        return payload.get("email", "")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

# ========================================
# Pydantic Request Models
# ========================================

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class StartAnalysisRequest(BaseModel):
    file_id: str

class ChatRequest(BaseModel):
    question: str
    filename: Union[str, None] = None

# ========================================
# ROUTES
# ========================================

@app.post("/api/auth/register", status_code=201)
async def register(body: RegisterRequest):
    users = _load_users()
    if body.email in users:
        raise HTTPException(status_code=409, detail="User exists")
    hashed = bcrypt.hashpw(body.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    users[body.email] = {"name": body.name, "email": body.email, "password_hash": hashed}
    _save_users(users)
    token = jwt.encode(
        {"email": body.email, "name": body.name, "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7)},
        SECRET_KEY, algorithm="HS256"
    )
    return {"token": token, "user": {"name": body.name, "email": body.email}}

@app.post("/api/auth/login")
async def login(body: LoginRequest):
    users = _load_users()
    user = users.get(body.email)
    if not user or not bcrypt.checkpw(body.password.encode("utf-8"), user["password_hash"].encode("utf-8")):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = jwt.encode(
        {"email": body.email, "name": user["name"], "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7)},
        SECRET_KEY, algorithm="HS256"
    )
    return {"token": token, "user": {"name": user["name"], "email": body.email}}

@app.post("/api/upload", status_code=201)
async def upload_csv(file: UploadFile = File(...), user_email: str = Depends(get_current_user)):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="CSV only")

    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    print(f"UPLOADING: {filename} to {filepath}...")

    contents = await file.read()
    with open(filepath, "wb") as f:
        f.write(contents)
    print(f"UPLOAD COMPLETE: {filename} ({os.path.getsize(filepath)} bytes)")

    is_valid, msg, _ = validate_csv(filepath)
    if not is_valid:
        os.remove(filepath)
        raise HTTPException(status_code=400, detail=msg)

    fid = str(uuid.uuid4())
    uploads_col.insert_one({
        "file_id": fid, "file_name": filename, "filepath": filepath,
        "file_size": os.path.getsize(filepath),
        "upload_time": datetime.datetime.utcnow().isoformat(),
        "status": "uploaded"
    })
    return {"file_id": fid, "file_name": filename, "message": "Uploaded"}

@app.get("/api/uploads")
async def list_uploads(user_email: str = Depends(get_current_user)):
    files = list(uploads_col.find({}, {"_id": 0}).sort("upload_time", -1))
    for f in files:
        f["uploaded_at"] = f.get("upload_time")
        f["filename"] = f.get("file_name")
        f["size"] = f"{f.get('file_size', 0) // 1024} KB"
    return {"files": files}

@app.delete("/api/upload/{fid}")
async def delete_upload(fid: str, user_email: str = Depends(get_current_user)):
    uploads_col.delete_one({"file_id": fid})
    jobs_col.delete_many({"file_id": fid})
    reports_col.delete_one({"file_id": fid})
    return {"message": "Deleted successfully"}

@app.post("/api/start-analysis", status_code=202)
async def start_analysis(body: StartAnalysisRequest, background_tasks: BackgroundTasks, user_email: str = Depends(get_current_user)):
    fdoc = uploads_col.find_one({"file_id": body.file_id})
    if not fdoc:
        raise HTTPException(status_code=404, detail="File not found")

    jid = str(uuid.uuid4())
    _new_job(jid, body.file_id)
    uploads_col.update_one({"file_id": body.file_id}, {"$set": {"status": "processing"}})

    # FastAPI BackgroundTasks runs in a thread pool — equivalent to threading.Thread
    background_tasks.add_task(_run_pipeline, jid, body.file_id, fdoc["filepath"], fdoc["file_name"])
    return {"job_id": jid}

@app.get("/api/job/{jid}")
async def get_job(jid: str, user_email: str = Depends(get_current_user)):
    job = jobs_col.find_one({"job_id": jid}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Not found")
    return job

@app.get("/api/report/{fid}")
async def get_report(fid: str, user_email: str = Depends(get_current_user)):
    rep = reports_col.find_one({"file_id": fid}, {"_id": 0})
    if not rep:
        raise HTTPException(status_code=404, detail="Not found")
    return rep

@app.post("/api/chat")
async def chat(body: ChatRequest, user_email: str = Depends(get_current_user)):
    if not body.question:
        raise HTTPException(status_code=400, detail="Question required")

    where_clause = {"source": body.filename} if body.filename else None
    rctx = get_rag_engine().query(body.question, n_results=15, where=where_clause)

    if body.filename:
        try:
            summary_res = get_rag_engine().collection.get(
                where={"$and": [{"source": body.filename}, {"type": "analysis_summary"}]}
            )
            if summary_res and summary_res["documents"]:
                summary_text = summary_res["documents"][0]
                rctx["context"] = f"GLOBAL DATASET SUMMARY:\n{summary_text}\n\nRELEVANT DATA SNIPPETS:\n{rctx['context']}"
        except Exception as e:
            print(f"Chat: Could not fetch summary for {body.filename}: {e}")

    ans = get_llm_client().chat_with_context(body.question, rctx["context"], rctx["sources"])
    return {"answer": ans, "sources": rctx["sources"]}

@app.get("/api/health")
async def health():
    return {"status": "ready", "db": db is not None}

# --- Serve Frontend ---
@app.get("/")
async def index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/{full_path:path}")
async def catch_all(full_path: str):
    fp = os.path.join(FRONTEND_DIR, full_path)
    if os.path.isfile(fp):
        return FileResponse(fp)
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

# --- Entry Point ---
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 5001))
    print(f"\n[LazyBIZ] Starting FastAPI server on port {port}...")
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False, workers=1)
