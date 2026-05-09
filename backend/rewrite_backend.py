import os
import re

app_path = 'app.py'
with open(app_path, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Add pymongo import
if 'from pymongo import MongoClient' not in text:
    text = text.replace('from flask_cors import CORS\n', 'from flask_cors import CORS\nfrom pymongo import MongoClient\n')

# 2. Replace In-Memory Job store with Mongo Connection
mongo_code = """
# --- MongoDB Connection ---
mongo_uri = os.getenv("MONGO_URI")
if not mongo_uri:
    print("WARNING: MONGO_URI not found in environment!")
mongo_client = MongoClient(mongo_uri) if mongo_uri else None
db = mongo_client.lazybiz if mongo_client else None

if db is not None:
    uploads_col = db.uploads
    jobs_col = db.jobs
    reports_col = db.reports
    
    uploads_col.create_index("file_id", unique=True)
    jobs_col.create_index("job_id", unique=True)
    reports_col.create_index("file_id", unique=True)
else:
    uploads_col = jobs_col = reports_col = None

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
            "started_at": datetime.datetime.utcnow().isoformat(),
            "completed_at": None,
            "error": None
        })

def _update_job(job_id: str, **kwargs):
    if jobs_col is not None:
        jobs_col.update_one({"job_id": job_id}, {"$set": kwargs})
"""

# Find the block where PIPELINE_JOBS is
start_idx = text.find('# --- In-memory Pipeline Job Store ---')
if start_idx != -1:
    end_idx = text.find('# --- In-memory User Store', start_idx)
    text = text[:start_idx] + mongo_code + '\n\n' + text[end_idx:]

# 3. Rewrite _run_pipeline
pipeline_func = """
def _run_pipeline(job_id: str, file_id: str, filepath: str, filename: str):
    import traceback
    try:
        _update_job(job_id, status="running", progress=5, message="🔧 MCP Tool: Cleaning data...", steps={"clean": "running", "analyze": "pending", "visualize": "pending", "rag": "pending", "llm": "pending"})
        cleaned_df, clean_report = clean_data(filepath)
        _update_job(job_id, progress=20, message="📊 MCP Tool: Analyzing data...", steps={"clean": "completed", "analyze": "running", "visualize": "pending", "rag": "pending", "llm": "pending"})

        analysis = analyze_data(cleaned_df)
        _update_job(job_id, progress=50, message="📈 MCP Tool: Generating visualizations...", steps={"clean": "completed", "analyze": "completed", "visualize": "running", "rag": "pending", "llm": "pending"})

        viz = visualize_data(cleaned_df, analysis)
        _update_job(job_id, progress=75, message="🧠 RAG: Embedding insights into vector store...", steps={"clean": "completed", "analyze": "completed", "visualize": "completed", "rag": "running", "llm": "pending"})

        # RAG Ingestion
        try:
            rag_result = rag_engine.ingest_csv(filepath, filename)
        except Exception:
            rag_result = {}

        summary_text = analysis.get("summary_text", "")
        if summary_text:
            rag_engine.collection.upsert(
                documents=[summary_text],
                metadatas=[{"source": filename, "type": "analysis_summary", "file_hash": rag_result.get("file_hash", ""), "row_index": -2}],
                ids=[f"{rag_result.get('file_hash', job_id)}_summary"]
            )
        _update_job(job_id, progress=90, message="✨ LLM: Generating business insights...", steps={"clean": "completed", "analyze": "completed", "visualize": "completed", "rag": "completed", "llm": "running"})

        context = analysis.get("summary_text", "")
        if rag_engine.get_stats()["total_documents"] > 0:
            rag_ctx = rag_engine.query("overall business performance revenue trends top products sentiment", n_results=8)
            if rag_ctx["context"]:
                context = rag_ctx["context"] + "\\n\\n" + context

        insights = llm_client.generate_insights(context)
        _update_job(job_id, status="done", progress=100, message="✅ Pipeline complete!", completed_at=datetime.datetime.utcnow().isoformat(), steps={"clean": "completed", "analyze": "completed", "visualize": "completed", "rag": "completed", "llm": "completed"})

        # Save to reports collection
        if reports_col is not None:
            reports_col.insert_one({
                "file_id": file_id,
                "job_id": job_id,
                "clean_report": clean_report,
                "analysis": analysis,
                "charts": viz["charts"],
                "chart_count": viz["chart_count"],
                "insights": insights,
                "created_at": datetime.datetime.utcnow().isoformat()
            })

    except Exception as e:
        _update_job(job_id, status="failed", progress=0, message="Pipeline failed.", error=str(e) + "\\n" + traceback.format_exc()[:800])
"""

text = re.sub(r'def _run_pipeline\(.*?\):.*?# --- In-memory User Store', pipeline_func.strip() + '\n\n\n# --- In-memory User Store', text, flags=re.DOTALL)

# 4. Now modify API endpoints
routes_code = """
# ========================================
# DATA UPLOAD ENDPOINTS
# ========================================

import uuid

@app.route("/api/upload", methods=["POST"])
@token_required
def upload_csv():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400
    if not file.filename.lower().endswith(".csv"):
        return jsonify({"error": "Only CSV files are supported"}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    is_valid, msg, stats = validate_csv(filepath)
    if not is_valid:
        os.remove(filepath)
        return jsonify({"error": msg}), 400

    file_id = str(uuid.uuid4())
    file_size = os.path.getsize(filepath)

    if uploads_col is not None:
        uploads_col.insert_one({
            "file_id": file_id,
            "file_name": filename,
            "filepath": filepath,
            "file_size": file_size,
            "upload_time": datetime.datetime.utcnow().isoformat(),
            "status": "uploaded"
        })

    return jsonify({"message": f"Successfully uploaded {filename}", "file_id": file_id}), 201

@app.route("/api/uploads", methods=["GET"])
@token_required
def get_uploads():
    if uploads_col is not None:
        files = list(uploads_col.find({}, {"_id": 0}).sort("upload_time", -1))
        # Add 'uploaded_at' alias for frontend compatibility
        for f in files:
            f["uploaded_at"] = f.get("upload_time")
            f["filename"] = f.get("file_name")
            f["size"] = f"{f.get('file_size', 0) // 1024} KB"
        return jsonify({"files": files})
    return jsonify({"files": []})

@app.route("/api/start-analysis", methods=["POST"])
@token_required
def start_analysis():
    data = request.get_json() or {}
    file_id = data.get("file_id")
    if not file_id:
        return jsonify({"error": "file_id required"}), 400

    if uploads_col is None:
        return jsonify({"error": "Database not connected"}), 500

    file_doc = uploads_col.find_one({"file_id": file_id})
    if not file_doc:
        return jsonify({"error": "File not found"}), 404

    job_id = str(uuid.uuid4())
    _new_job(job_id, file_id)
    uploads_col.update_one({"file_id": file_id}, {"$set": {"status": "processing"}})

    t = threading.Thread(target=_run_pipeline, args=(job_id, file_id, file_doc["filepath"], file_doc["file_name"]), daemon=True)
    t.start()
    return jsonify({"job_id": job_id, "message": "Pipeline started"}), 202

@app.route("/api/job/<job_id>", methods=["GET"])
@token_required
def get_job(job_id):
    if jobs_col is not None:
        job = jobs_col.find_one({"job_id": job_id}, {"_id": 0})
        if job:
            return jsonify(job)
    return jsonify({"error": "Job not found"}), 404

@app.route("/api/report/<file_id>", methods=["GET"])
@token_required
def get_report(file_id):
    if reports_col is not None:
        report = reports_col.find_one({"file_id": file_id}, {"_id": 0})
        if report:
            return jsonify(report)
    return jsonify({"error": "Report not found"}), 404

# ========================================
# DASHBOARD ENDPOINTS
# ========================================
"""
text = re.sub(r'# ========================================\n# DATA UPLOAD ENDPOINTS.*?# ========================================\n# DASHBOARD ENDPOINTS\n# ========================================', routes_code, text, flags=re.DOTALL)

with open(app_path, 'w', encoding='utf-8') as f:
    f.write(text)
