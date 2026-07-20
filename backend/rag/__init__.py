"""
LazyBIZ RAG Engine — pgvector Edition
======================================
Replaces ChromaDB with Supabase PostgreSQL + pgvector for cloud-native,
persistent vector storage. Key improvements over the ChromaDB version:

  • Data persists across Render restarts (no ephemeral disk dependency)
  • Full 768-dim Gemini embeddings (was incorrectly sliced to 384 before)
  • Standard SQL — inspect your data anytime in the Supabase dashboard
  • IVFFlat cosine index gives sub-millisecond similarity search at scale
  • Public API is unchanged: ingest_csv(), query(), get_stats() work as before
"""

import os
import uuid
import logging
import hashlib
import json

import pandas as pd
import numpy as np
import psycopg2
import psycopg2.extras
from pgvector.psycopg2 import register_vector

logger = logging.getLogger(__name__)

# ── Tunable constants ──────────────────────────────────────────────────────────
VECTOR_DIM  = 768   # Full Gemini text-embedding-004 output dimensions
CHUNK_ROWS  = 5     # CSV rows grouped into one embedded document
UPSERT_BATCH = 100  # Documents per INSERT batch (psycopg2 executemany)
MAX_EMBED_ROWS = 1000  # Max rows sampled from large CSVs for embedding
# ──────────────────────────────────────────────────────────────────────────────


# ── Table DDL ──────────────────────────────────────────────────────────────────
_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS lazybiz_documents (
    id           TEXT        PRIMARY KEY,
    document     TEXT        NOT NULL,
    embedding    vector(768),
    source       TEXT,
    file_hash    TEXT,
    row_start    INTEGER     DEFAULT 0,
    row_end      INTEGER     DEFAULT 0,
    doc_type     TEXT        DEFAULT 'chunk',
    columns_json TEXT,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
"""

_CREATE_INDEX_SQL = """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'lazybiz_documents'
          AND indexname  = 'lazybiz_embedding_idx'
    ) THEN
        CREATE INDEX lazybiz_embedding_idx
        ON lazybiz_documents
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100);
    END IF;
END$$;
"""
# ──────────────────────────────────────────────────────────────────────────────


class GeminiEmbeddingWrapper:
    """
    Wrapper around Gemini REST API for zero-RAM, cloud-based embeddings.
    Falls back to random unit vectors if the API key is missing or the
    network fails — so ingestion NEVER hangs or crashes.
    """

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not set — mock embeddings will be used.")

    def encode(self, texts, batch_size=None, show_progress_bar=False,
               normalize_embeddings=True, convert_to_numpy=False):
        import requests

        if not self.api_key:
            return self._mock(texts, normalize_embeddings, convert_to_numpy)

        embeddings = []
        try:
            url = (
                "https://generativelanguage.googleapis.com/v1beta"
                f"/models/text-embedding-004:batchEmbedContents?key={self.api_key}"
            )
            # Process in batches of 50 to stay within HTTP payload limits
            for i in range(0, len(texts), 50):
                chunk = texts[i : i + 50]
                body = {
                    "requests": [
                        {
                            "model": "models/text-embedding-004",
                            "content": {"parts": [{"text": t}]},
                        }
                        for t in chunk
                    ]
                }
                res = requests.post(url, json=body, timeout=15)
                if res.status_code == 200:
                    for emb in res.json().get("embeddings", []):
                        # Full 768 dimensions — no slicing needed with pgvector
                        embeddings.append(emb.get("values", [0.0] * VECTOR_DIM))
                else:
                    logger.error("Gemini API error %d: %s", res.status_code, res.text[:200])
                    raise RuntimeError("Gemini API failure")

        except Exception as exc:
            logger.error("Embedding generation failed: %s — falling back to mock.", exc)
            remaining = len(texts) - len(embeddings)
            embeddings += self._mock_list(remaining, normalize_embeddings)

        if convert_to_numpy:
            return np.array(embeddings)
        return embeddings

    # ── Private helpers ────────────────────────────────────────────────────────

    def _mock(self, texts, normalize, to_numpy):
        vecs = self._mock_list(len(texts), normalize)
        return np.array(vecs) if to_numpy else vecs

    @staticmethod
    def _mock_list(n, normalize):
        vecs = []
        for _ in range(n):
            v = np.random.randn(VECTOR_DIM).astype(float)
            if normalize:
                v /= np.linalg.norm(v)
            vecs.append(v.tolist())
        return vecs


class RAGEngine:
    """
    Retrieval-Augmented Generation engine backed by Supabase pgvector.

    Connection strategy:
      • Reads SUPABASE_DB_URL from the environment (set in .env).
      • Auto-creates the lazybiz_documents table and IVFFlat index on startup.
      • Re-connects automatically if the connection drops.
    """

    def __init__(self):
        self._db_url = os.getenv("SUPABASE_DB_URL", "")
        if not self._db_url:
            logger.error(
                "SUPABASE_DB_URL is not set in .env! "
                "Please replace [YOUR-PASSWORD] in .env and restart."
            )
        self._conn: psycopg2.extensions.connection | None = None
        self._model: GeminiEmbeddingWrapper | None = None
        self._init_db()

    # ── Connection management ──────────────────────────────────────────────────

    def _get_conn(self) -> psycopg2.extensions.connection:
        """Return a live psycopg2 connection, reconnecting if necessary."""
        try:
            if self._conn is None or self._conn.closed:
                if not self._db_url:
                    raise RuntimeError("SUPABASE_DB_URL is not configured.")
                logger.info("Connecting to Supabase pgvector …")
                self._conn = psycopg2.connect(
                    self._db_url,
                    connect_timeout=10,
                    options="-c statement_timeout=30000",  # 30-second query timeout
                )
                register_vector(self._conn)
                logger.info("pgvector connection established.")
            return self._conn
        except Exception as exc:
            logger.error("pgvector connection failed: %s", exc)
            raise

    def _init_db(self):
        """Create table and index if they don't already exist."""
        try:
            conn = self._get_conn()
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                cur.execute(_CREATE_TABLE_SQL)
                cur.execute(_CREATE_INDEX_SQL)
            conn.commit()
            logger.info("pgvector schema initialized (table + index ready).")
        except Exception as exc:
            logger.error("DB init failed: %s", exc)

    # ── Embedding model (lazy-loaded) ──────────────────────────────────────────

    @property
    def model(self) -> GeminiEmbeddingWrapper:
        if self._model is None:
            self._model = GeminiEmbeddingWrapper()
        return self._model

    # ── Ingestion ──────────────────────────────────────────────────────────────

    def ingest_csv(self, filepath, filename=None, df=None):
        """
        Ingest a CSV file into the pgvector store.

        Identical public API to the old ChromaDB version:
          - Groups CHUNK_ROWS rows into one document (reduces vector count)
          - Embeds all documents in one bulk API call
          - Skips re-ingestion if the file hash already exists
          - Injects a schema summary document tagged as doc_type='schema'

        Returns a dict with ingestion statistics.
        """
        if df is None:
            df = pd.read_csv(filepath)
        display_name = filename or os.path.basename(filepath)

        # ── File hash (duplicate guard) ────────────────────────────────────────
        h = hashlib.md5()
        with open(filepath, "rb") as fh:
            for chunk in iter(lambda: fh.read(8192), b""):
                h.update(chunk)
        file_hash = h.hexdigest()[:12]

        if self._hash_exists(file_hash):
            logger.info("File '%s' (hash=%s) already ingested — skipping.", display_name, file_hash)
            return {
                "filename": display_name,
                "rows": len(df),
                "columns": df.columns.tolist(),
                "file_hash": file_hash,
                "skipped": True,
            }

        # ── Cap rows for fast embedding ────────────────────────────────────────
        if len(df) > MAX_EMBED_ROWS:
            logger.info(
                "Dataset too large (%d rows). Sampling %d for embedding.", len(df), MAX_EMBED_ROWS
            )
            df = df.sample(n=MAX_EMBED_ROWS, random_state=42).sort_index()

        columns = df.columns.tolist()
        total_rows = len(df)
        df_str = df.fillna("").astype(str)

        def _row_to_kv(row):
            return ", ".join(
                f"{col}: {row[col]}" for col in columns if row[col].strip() != ""
            )

        kv_series = df_str.apply(_row_to_kv, axis=1)

        # ── Build document chunks ──────────────────────────────────────────────
        documents, metas, ids = [], [], []
        for chunk_start in range(0, total_rows, CHUNK_ROWS):
            chunk_end = min(chunk_start + CHUNK_ROWS, total_rows)
            text = (
                f"Data excerpt from {display_name}:\n"
                + "\n".join(kv_series.iloc[chunk_start:chunk_end].tolist())
            )
            documents.append(text)
            metas.append({
                "source": display_name,
                "file_hash": file_hash,
                "row_start": int(chunk_start),
                "row_end": int(chunk_end - 1),
                "doc_type": "chunk",
                "columns_json": json.dumps(columns),
            })
            ids.append(f"{file_hash}_chunk_{chunk_start}")

        # ── Schema summary document ────────────────────────────────────────────
        schema_text = self._build_schema_text(df, display_name, columns)
        documents.append(schema_text)
        metas.append({
            "source": display_name,
            "file_hash": file_hash,
            "row_start": -1,
            "row_end": -1,
            "doc_type": "schema",
            "columns_json": json.dumps(columns),
        })
        ids.append(f"{file_hash}_schema")

        # ── Bulk encode ────────────────────────────────────────────────────────
        logger.info("Encoding %d documents via Gemini API …", len(documents))
        embeddings = self.model.encode(
            documents,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )

        # ── Batch upsert into pgvector ─────────────────────────────────────────
        logger.info("Upserting %d documents to Supabase pgvector …", len(documents))
        self._bulk_upsert(ids, documents, embeddings, metas)

        logger.info("Ingestion complete: %d chunks from %d rows.", len(documents), total_rows)
        return {
            "filename": display_name,
            "rows": total_rows,
            "chunks": len(documents),
            "columns": columns,
            "file_hash": file_hash,
            "skipped": False,
        }

    def ingest_text(self, text: str, doc_id: str, metadata: dict):
        """
        Ingest a single text string (e.g., an analysis summary).
        Called from app.py after the pipeline generates summary text.
        Replaces the old direct `collection.upsert()` call.
        """
        embedding = self.model.encode(
            [text], normalize_embeddings=True, convert_to_numpy=True
        )
        self._bulk_upsert(
            ids=[doc_id],
            documents=[text],
            embeddings=embedding,
            metas=[metadata],
        )

    # ── Query ──────────────────────────────────────────────────────────────────

    def query(self, question: str, n_results: int = 8, where: dict = None):
        """
        Semantic similarity search using cosine distance (<=>).
        `where` can be {"source": "filename.csv"} to scope results to one file.
        Returns {"context": str, "sources": list}.
        """
        if self.get_stats()["total_documents"] == 0:
            return {
                "context": "No data has been uploaded yet. Please upload a CSV file first.",
                "sources": [],
            }

        query_vec = self.model.encode(
            [question], normalize_embeddings=True, convert_to_numpy=True
        )[0]

        try:
            conn = self._get_conn()
            with conn.cursor() as cur:
                if where and "source" in where:
                    cur.execute(
                        """
                        SELECT document, source
                        FROM lazybiz_documents
                        WHERE source = %s
                        ORDER BY embedding <=> %s
                        LIMIT %s
                        """,
                        (where["source"], np.array(query_vec), n_results),
                    )
                else:
                    cur.execute(
                        """
                        SELECT document, source
                        FROM lazybiz_documents
                        ORDER BY embedding <=> %s
                        LIMIT %s
                        """,
                        (np.array(query_vec), n_results),
                    )
                rows = cur.fetchall()
        except Exception as exc:
            logger.error("pgvector query failed: %s", exc)
            return {"context": "Vector search temporarily unavailable.", "sources": []}

        context_parts = [row[0] for row in rows]
        sources = list({row[1] for row in rows if row[1]})
        return {"context": "\n\n".join(context_parts), "sources": sources}

    def get_summary(self, filename: str) -> str | None:
        """
        Retrieve the pre-generated analysis summary for a specific file.
        Replaces the old direct `collection.get(where={"type": "analysis_summary"})` call.
        """
        try:
            conn = self._get_conn()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT document FROM lazybiz_documents
                    WHERE source = %s AND doc_type = 'analysis_summary'
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (filename,),
                )
                row = cur.fetchone()
                return row[0] if row else None
        except Exception as exc:
            logger.error("get_summary failed: %s", exc)
            return None

    # ── Stats ──────────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Return total document count and list of unique source files."""
        try:
            conn = self._get_conn()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*), ARRAY_AGG(DISTINCT source) FROM lazybiz_documents"
                )
                count, sources = cur.fetchone()
            return {
                "total_documents": count or 0,
                "sources": [s for s in (sources or []) if s],
            }
        except Exception as exc:
            logger.error("get_stats failed: %s", exc)
            return {"total_documents": 0, "sources": []}

    # ── Dashboard data (unchanged from ChromaDB version) ───────────────────────

    def generate_dashboard_data(self, filepath):
        """Analyze a CSV and return structured KPI + chart data for the dashboard."""
        df = pd.read_csv(filepath)
        data: dict = {"kpis": {}, "chart": {}, "products": []}

        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
        text_cols    = df.select_dtypes(include=["object"]).columns.tolist()

        # ── Revenue / Sales KPI ────────────────────────────────────────────────
        revenue_col = None
        for p_list in [["revenue"], ["total", "amount", "sales", "sale", "income"], ["price", "value"]]:
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

        # ── Date-based chart data ──────────────────────────────────────────────
        date_col = None
        for c in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[c]):
                date_col = c; break
        if not date_col:
            for c in df.columns:
                if any(k in c.lower() for k in ["date", "time", "period"]):
                    date_col = c; break
        if not date_col:
            _yc = next((c for c in df.columns if c.lower() == "year"), None)
            _mc = next((c for c in df.columns if c.lower() == "month"), None)
            _dc = next((c for c in df.columns if c.lower() == "day"), None)
            if _yc and _mc:
                try:
                    df["__date__"] = pd.to_datetime(
                        dict(year=df[_yc], month=df[_mc], day=df[_dc] if _dc else 1), errors="coerce"
                    )
                    if df["__date__"].notna().sum() / max(len(df), 1) > 0.5:
                        date_col = "__date__"
                except Exception:
                    pass

        if date_col and revenue_col:
            try:
                date_series = (
                    df[date_col]
                    if pd.api.types.is_datetime64_any_dtype(df[date_col])
                    else pd.to_datetime(df[date_col], errors="coerce")
                )
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

        # ── Product / Category rankings ────────────────────────────────────────
        product_col = None
        for c in text_cols:
            if any(k in c.lower() for k in ["product", "item", "name", "category", "sku"]):
                product_col = c; break
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

    def _hash_exists(self, file_hash: str) -> bool:
        """Check if any document with this file_hash already exists."""
        try:
            conn = self._get_conn()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM lazybiz_documents WHERE file_hash = %s LIMIT 1",
                    (file_hash,),
                )
                return cur.fetchone() is not None
        except Exception:
            return False

    def _bulk_upsert(self, ids, documents, embeddings, metas):
        """Batch-upsert documents into lazybiz_documents using ON CONFLICT DO UPDATE."""
        records = [
            (
                ids[i],
                documents[i],
                np.array(embeddings[i]),
                metas[i].get("source", ""),
                metas[i].get("file_hash", ""),
                metas[i].get("row_start", 0),
                metas[i].get("row_end", 0),
                metas[i].get("doc_type", "chunk"),
                metas[i].get("columns_json", "[]"),
            )
            for i in range(len(ids))
        ]

        sql = """
            INSERT INTO lazybiz_documents
                (id, document, embedding, source, file_hash, row_start, row_end, doc_type, columns_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                document     = EXCLUDED.document,
                embedding    = EXCLUDED.embedding,
                doc_type     = EXCLUDED.doc_type,
                columns_json = EXCLUDED.columns_json
        """
        try:
            conn = self._get_conn()
            with conn.cursor() as cur:
                for i in range(0, len(records), UPSERT_BATCH):
                    cur.executemany(sql, records[i : i + UPSERT_BATCH])
            conn.commit()
        except Exception as exc:
            logger.error("Bulk upsert failed: %s", exc)
            if self._conn:
                self._conn.rollback()
            raise

    @staticmethod
    def _build_schema_text(df, display_name, columns) -> str:
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
