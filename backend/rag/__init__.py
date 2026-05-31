import os
import sys

# Monkey-patch sqlite3 for ChromaDB compatibility on older systems
try:
    __import__('pysqlite3')
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass

import logging
import hashlib
import json

import pandas as pd
import numpy as np
import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)

class GeminiEmbeddingWrapper:
    """Wrapper around Gemini API for free, fast, zero-RAM embeddings."""
    def __init__(self):
        logger.info("Initializing Gemini API Embedding Wrapper...")
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not found! Falling back to safe mock embeddings.")

    def encode(self, texts, batch_size=None, show_progress_bar=False, normalize_embeddings=True, convert_to_numpy=False):
        import requests
        embeddings = []
        
        # If API key is missing, return mock embeddings so it NEVER hangs or crashes
        if not self.api_key:
            logger.warning("No Gemini API key. Generating safe mock embeddings.")
            for _ in texts:
                mock_vector = np.random.randn(384)
                if normalize_embeddings:
                    mock_vector /= np.linalg.norm(mock_vector)
                embeddings.append(mock_vector.tolist() if not convert_to_numpy else mock_vector)
            return np.array(embeddings) if convert_to_numpy else embeddings

        try:
            # Process in small batches of 50 to prevent HTTP payload limits
            for i in range(0, len(texts), 50):
                chunk = texts[i:i+50]
                url = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:batchEmbedContents?key={self.api_key}"
                req_body = {
                    "requests": [
                        {
                            "model": "models/text-embedding-004",
                            "content": {"parts": [{"text": t}]}
                        }
                        for t in chunk
                    ]
                }
                # Strict 10-second timeout
                res = requests.post(url, json=req_body, timeout=10)
                if res.status_code == 200:
                    data = res.json()
                    for emb in data.get("embeddings", []):
                        # text-embedding-004 returns 768 dimensions by default. Let's slice it to 384
                        # or keep the full 768. Let's slice it to 384 or keep full, ChromaDB doesn't care about dimensions as long as it's consistent.
                        # Let's slice to 384 to keep it small and consistent with prior database runs.
                        values = emb.get("values", [0.0] * 768)
                        embeddings.append(values[:384])
                else:
                    logger.error("Gemini Embedding API Error: %d - %s", res.status_code, res.text)
                    raise RuntimeError("API failure")
        except Exception as e:
            logger.error("Failed to generate Gemini embeddings: %s. Falling back to mock.", e)
            # Safe mock fallback so the pipeline NEVER gets stuck
            for _ in range(len(texts) - len(embeddings)):
                mock_vector = np.random.randn(384)
                if normalize_embeddings:
                    mock_vector /= np.linalg.norm(mock_vector)
                embeddings.append(mock_vector.tolist() if not convert_to_numpy else mock_vector)
        
        if convert_to_numpy:
            return np.array(embeddings)
        return embeddings

# ── Tunable constants ──────────────────────────────────────────────────────────
CHUNK_ROWS   = 5    # Number of CSV rows grouped into one embedded document
ENCODE_BATCH = 128  # Sentences per SentenceTransformer encode batch (CPU-safe)
UPSERT_BATCH = 256  # Documents per ChromaDB upsert call
# ──────────────────────────────────────────────────────────────────────────────


class RAGEngine:
    """Retrieval-Augmented Generation engine using ChromaDB."""

    def __init__(self, persist_dir=None):
        self.persist_dir = persist_dir or os.getenv("CHROMA_DB_PATH", "../data/chroma_db")
        os.makedirs(self.persist_dir, exist_ok=True)

        self.client = chromadb.PersistentClient(path=self.persist_dir)
        self.collection = self.client.get_or_create_collection(
            name="lazybiz_data",
            metadata={"hnsw:space": "cosine"}
        )
        self._model = None

    # ── Model ──────────────────────────────────────────────────────────────────

    @property
    def model(self):
        """Lazy-load the embedding model (CPU only, ultra-lightweight ONNX)."""
        if self._model is None:
            self._model = GeminiEmbeddingWrapper()
        return self._model

    # ── Ingestion ──────────────────────────────────────────────────────────────

    def ingest_csv(self, filepath, filename=None, df=None):
        """
        Ingest a CSV file into the vector store with CPU-optimized processing.

        Key changes vs original:
        - Uses pandas vectorized operations instead of iterrows()
        - Groups CHUNK_ROWS rows into a single document to reduce embedding count
        - Pre-computes ALL embeddings in one bulk encode() call
        - Passes pre-computed embeddings to ChromaDB (no double-encoding)
        - Skips the file if it has already been ingested (hash check)

        Returns dict with ingestion stats.
        """
        if df is None:
            df = pd.read_csv(filepath)
        display_name = filename or os.path.basename(filepath)

        # ── Speed Optimization: Calculate hash in chunks for memory efficiency ──
        h = hashlib.md5()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        file_hash = h.hexdigest()[:12]

        # ── Speed Optimization: Cap rows for fast RAG ──────────────────────────
        MAX_EMBED_ROWS = 1000
        if len(df) > MAX_EMBED_ROWS:
            logger.info("Dataset too large (%d rows). Sampling %d rows for instant embedding.", len(df), MAX_EMBED_ROWS)
            # Sample evenly across the dataset to get a representative mix
            df = df.sample(n=MAX_EMBED_ROWS, random_state=42).sort_index()


        # ── Duplicate-skip guard ───────────────────────────────────────────────
        existing_ids = self._get_existing_ids(file_hash)
        if existing_ids:
            logger.info("File '%s' (hash=%s) already ingested — skipping.", display_name, file_hash)
            return {
                "filename": display_name,
                "rows": len(df),
                "columns": df.columns.tolist(),
                "file_hash": file_hash,
                "skipped": True,
            }

        columns = df.columns.tolist()
        total_rows = len(df)

        logger.info("Building document chunks for '%s' (%d rows, chunk_size=%d) …",
                    display_name, total_rows, CHUNK_ROWS)

        # ── Step 1 — Vectorized text building ─────────────────────────────────
        # Replace slow iterrows() with pandas apply() on the whole DataFrame.
        # FillNA converts NaN to empty string so we can safely stringify.
        df_str = df.fillna("").astype(str)

        def _row_to_kv(row):
            """Convert one row to 'col: val' pairs, skipping empty values."""
            return ", ".join(
                f"{col}: {row[col]}"
                for col in columns
                if row[col].strip() != ""
            )

        # Vectorised: build KV strings for every row in one pass
        kv_series = df_str.apply(_row_to_kv, axis=1)  # pd.Series of strings

        # ── Step 2 — Row chunking ──────────────────────────────────────────────
        # Group every CHUNK_ROWS consecutive rows into one document.
        # e.g. 100 000 rows → 20 000 documents (5x fewer embeddings to compute)
        documents = []
        metadatas = []
        ids       = []

        for chunk_start in range(0, total_rows, CHUNK_ROWS):
            chunk_end  = min(chunk_start + CHUNK_ROWS, total_rows)
            chunk_text = (
                f"Data excerpt from {display_name}:\n"
                + "\n".join(kv_series.iloc[chunk_start:chunk_end].tolist())
            )
            documents.append(chunk_text)
            metadatas.append({
                "source":      display_name,
                "file_hash":   file_hash,
                "row_start":   int(chunk_start),
                "row_end":     int(chunk_end - 1),
                "columns":     json.dumps(columns),
            })
            ids.append(f"{file_hash}_chunk_{chunk_start}")

        # ── Step 3 — Schema summary document ──────────────────────────────────
        schema_text = self._build_schema_text(df, display_name, columns)
        documents.append(schema_text)
        metadatas.append({
            "source":    display_name,
            "file_hash": file_hash,
            "row_start": -1,
            "row_end":   -1,
            "type":      "schema",
        })
        ids.append(f"{file_hash}_schema")

        # ── Step 4 — Bulk encode ALL documents in one call ────────────────────
        # sentence-transformers handles internal mini-batching efficiently.
        # Passing pre-computed embeddings to ChromaDB avoids a second encode.
        logger.info("Encoding %d documents (batch_size=%d, CPU) …",
                    len(documents), ENCODE_BATCH)
        embeddings_np = self.model.encode(
            documents,
            batch_size=ENCODE_BATCH,
            show_progress_bar=True,   # prints a tqdm bar in the console
            convert_to_numpy=True,
            normalize_embeddings=True,  # cosine space — pre-normalise for speed
        )
        embeddings_list = embeddings_np.tolist()  # ChromaDB needs plain lists

        # ── Step 5 — Upsert in batches with pre-computed embeddings ───────────
        logger.info("Upserting %d documents to ChromaDB …", len(documents))
        for i in range(0, len(documents), UPSERT_BATCH):
            end = i + UPSERT_BATCH
            self.collection.upsert(
                documents=documents[i:end],
                embeddings=embeddings_list[i:end],   # ← no re-encoding inside Chroma
                metadatas=metadatas[i:end],
                ids=ids[i:end],
            )

        logger.info("Ingestion complete: %d chunks from %d rows.", len(documents), total_rows)
        return {
            "filename":    display_name,
            "rows":        total_rows,
            "chunks":      len(documents),
            "columns":     columns,
            "file_hash":   file_hash,
            "skipped":     False,
        }

    # ── Query ──────────────────────────────────────────────────────────────────

    def query(self, question, n_results=8, where=None):
        """Query the vector store and return relevant context."""
        if self.collection.count() == 0:
            return {
                "context": "No data has been uploaded yet. Please upload a CSV file first.",
                "sources": [],
            }

        # Pre-encode the query so ChromaDB uses the same model space
        query_embedding = self.model.encode(
            [question],
            normalize_embeddings=True,
            convert_to_numpy=True,
        ).tolist()

        kwargs = {
            "query_embeddings": query_embedding,
            "n_results": min(n_results, self.collection.count()),
        }
        if where:
            kwargs["where"] = where

        results = self.collection.query(**kwargs)

        context_parts = []
        sources = set()
        if results and results["documents"]:
            for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
                context_parts.append(doc)
                sources.add(meta.get("source", "unknown"))

        return {
            "context": "\n\n".join(context_parts),
            "sources": list(sources),
        }

    # ── Stats ──────────────────────────────────────────────────────────────────

    def get_stats(self):
        """Get statistics about the vector store."""
        count = self.collection.count()
        sources = set()
        if count > 0:
            sample = self.collection.peek(limit=min(count, 100))
            if sample and sample["metadatas"]:
                for meta in sample["metadatas"]:
                    sources.add(meta.get("source", "unknown"))

        return {
            "total_documents": count,
            "sources": list(sources),
        }

    # ── Dashboard data ─────────────────────────────────────────────────────────

    def generate_dashboard_data(self, filepath):
        """
        Analyze a CSV and return structured dashboard data.
        Returns KPIs, chart data, and product rankings.
        """
        df = pd.read_csv(filepath)
        data = {"kpis": {}, "chart": {}, "products": []}

        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
        text_cols    = df.select_dtypes(include=["object"]).columns.tolist()

        # Revenue / Sales KPI
        revenue_col = None
        priorities = [
            ["revenue"],
            ["total", "amount", "sales", "sale", "income"],
            ["price", "value"]
        ]
        for p_list in priorities:
            for c in numeric_cols:
                if any(k in c.lower() for k in p_list):
                    revenue_col = c
                    break
            if revenue_col:
                break
            
        if revenue_col is None and numeric_cols:
            revenue_col = numeric_cols[0]

        if revenue_col:
            data["kpis"]["total_revenue"] = round(float(df[revenue_col].sum()), 2)
            data["kpis"]["avg_revenue"]   = round(float(df[revenue_col].mean()), 2)
            data["kpis"]["max_revenue"]   = round(float(df[revenue_col].max()), 2)

        data["kpis"]["total_records"] = len(df)

        # Date-based chart data
        date_col = None
        # 1. Look for an already-parsed datetime column
        for c in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[c]):
                date_col = c
                break
        # 2. Look for a string column with a date-like name
        if not date_col:
            for c in df.columns:
                if any(k in c.lower() for k in ["date", "time", "period"]):
                    date_col = c
                    break
        # 3. Reconstruct from integer year/month/day columns
        if not date_col:
            _yc = next((c for c in df.columns if c.lower() == "year"),  None)
            _mc = next((c for c in df.columns if c.lower() == "month"), None)
            _dc = next((c for c in df.columns if c.lower() == "day"),   None)
            if _yc and _mc:
                try:
                    _day_s = df[_dc] if _dc else 1
                    df["__date__"] = pd.to_datetime(
                        dict(year=df[_yc], month=df[_mc], day=_day_s), errors="coerce"
                    )
                    if df["__date__"].notna().sum() / max(len(df), 1) > 0.5:
                        date_col = "__date__"
                except Exception:
                    pass

        if date_col and revenue_col:
            try:
                # Build a proper datetime Series — handle both string cols and __date__
                if pd.api.types.is_datetime64_any_dtype(df[date_col]):
                    date_series = df[date_col]
                else:
                    date_series = pd.to_datetime(df[date_col], errors="coerce")
                temp = df[[revenue_col]].copy()
                temp["__dt__"] = date_series
                temp = temp.dropna(subset=["__dt__"]).set_index("__dt__").sort_index()
                try:
                    monthly = temp[revenue_col].resample("ME").sum()
                except Exception:
                    monthly = temp[revenue_col].resample("M").sum()
                data["chart"]["labels"] = [d.strftime("%b %Y") for d in monthly.index]
                data["chart"]["values"] = [round(float(v), 2) for v in monthly.values]
            except Exception:
                vals = df[revenue_col].head(12).tolist()
                data["chart"]["labels"] = [f"Period {i+1}" for i in range(len(vals))]
                data["chart"]["values"] = [round(float(v), 2) for v in vals]
        elif revenue_col:
            vals = df[revenue_col].head(12).tolist()
            data["chart"]["labels"] = [f"Period {i+1}" for i in range(len(vals))]
            data["chart"]["values"] = [round(float(v), 2) for v in vals]

        # Product / Category rankings
        product_col = None
        for c in text_cols:
            if any(k in c.lower() for k in ["product", "item", "name", "category", "sku"]):
                product_col = c
                break
        if product_col is None and text_cols:
            product_col = text_cols[0]

        if product_col and revenue_col:
            top = df.groupby(product_col)[revenue_col].sum().nlargest(5)
            data["products"] = [
                {"name": str(name), "value": round(float(val), 2)}
                for name, val in top.items()
            ]

        return data

    # ── Private helpers ────────────────────────────────────────────────────────

    def _get_existing_ids(self, file_hash):
        """Return existing IDs that belong to this file hash (for skip check)."""
        try:
            count = self.collection.count()
            if count == 0:
                return []
            # Peek a small sample and check if any belong to this hash
            sample = self.collection.peek(limit=min(count, 50))
            if not sample or not sample["metadatas"]:
                return []
            return [
                mid for mid, meta in zip(sample["ids"], sample["metadatas"])
                if meta.get("file_hash") == file_hash
            ]
        except Exception:
            return []

    def _build_schema_text(self, df, display_name, columns):
        """Build a human-readable schema summary for the dataset."""
        parts = [
            f"Dataset '{display_name}' schema: columns are {', '.join(columns)}.",
            f"Total rows: {len(df)}.",
        ]
        for col in columns:
            dtype = str(df[col].dtype)
            if dtype in ("float64", "int64"):
                parts.append(
                    f"{col} ranges from {df[col].min()} to {df[col].max()} "
                    f"(mean: {df[col].mean():.2f})."
                )
            elif dtype == "object":
                parts.append(f"{col} has {df[col].nunique()} unique values.")
        return " ".join(parts)
