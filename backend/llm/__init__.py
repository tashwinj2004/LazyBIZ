"""
LLM Integration - Dual-provider client: OpenRouter (primary) → Groq (fallback).

Strategy:
  1. Try OpenRouter first (free models).
  2. On 429 / rate-limit → automatically switch to Groq API (free tier).
  3. Exponential backoff + retry on both providers.
  4. Throttle between calls to avoid triggering limits.
"""
import os
import time
import logging
import requests
import json
# REMOVED google-generativeai to prevent DLL crashes on Python 3.9

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
MAX_RETRIES      = 3
BASE_BACKOFF     = 2.0       # seconds, doubled each retry
INTER_CALL_DELAY = 1.0       # minimum gap between API calls

# Provider endpoints
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
GROQ_URL       = "https://api.groq.com/openai/v1/chat/completions"

# Models per provider
OPENROUTER_MODELS = [
    "google/gemma-4-31b-it:free",
    "mistralai/mistral-7b-instruct:free",
    "meta-llama/llama-3.1-8b-instruct:free",
]
GROQ_MODEL = "llama-3.3-70b-versatile"   # Groq free-tier model
# ─────────────────────────────────────────────────────────────────────────────


class LLMClient:
    """Multi-provider LLM client: Groq (Primary) → Gemini (Fallback) → OpenRouter (Last Resort)."""

    def __init__(self):
        self.gemini_key = os.getenv("GEMINI_API_KEY", "")
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
        self.groq_key       = os.getenv("GROQ_API_KEY", "")
        self._last_call     = 0.0

        if not self.gemini_key:
            logger.warning("GEMINI_API_KEY not set — will use fallbacks.")

    # ══════════════════════════════════════════════════════════════════════════
    # Core call router
    # ══════════════════════════════════════════════════════════════════════════

    def _call(self, messages, max_tokens=1024, temperature=0.7):
        """
        Try Groq first (fastest, most reliable).
        If Groq fails or rate-limits, fall back to Gemini then OpenRouter.
        """
        # ── Attempt 1: Groq (Primary) ──────────────────────────────────────
        if self.groq_key:
            result = self._try_provider(
                url=GROQ_URL,
                api_key=self.groq_key,
                model=GROQ_MODEL,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            if result is not None:
                return result
            logger.warning("Groq rate-limited or failed. Falling back to Gemini …")

        # ── Attempt 2: Gemini (Fallback) ────────────────────────────────────
        if self.gemini_key:
            result = self._gemini_call(messages)
            if result is not None:
                return result
            logger.warning("Gemini failed. Falling back to OpenRouter …")

        # ── Attempt 3: OpenRouter (Fallback) ───────────────────────────────
        if self.openrouter_key:
            for model in OPENROUTER_MODELS:
                result = self._try_provider(
                    url=OPENROUTER_URL,
                    api_key=self.openrouter_key,
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    extra_headers={
                        "HTTP-Referer": "https://lazybiz-rag.onrender.com",
                        "X-Title": "LazyBIZ RAG Dashboard",
                    },
                )
                if result is not None:
                    return result
                logger.warning("OpenRouter model '%s' rate-limited, trying next …", model)

            logger.error("All OpenRouter models exhausted.")

        # ── All providers down ────────────────────────────────────────────
        return (
            "⚠️ AI service is temporarily unavailable on all providers. "
            "Please wait a minute and try again. Your data is safe."
        )

    # ══════════════════════════════════════════════════════════════════════════
    # Single-provider retry loop
    # ══════════════════════════════════════════════════════════════════════════

    def _try_provider(self, url, api_key, model, messages,
                      max_tokens, temperature, extra_headers=None):
        """
        Call one provider/model up to MAX_RETRIES times.
        Returns content string on success, None on exhausted retries / 429.
        """
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type":  "application/json",
        }
        if extra_headers:
            headers.update(extra_headers)

        payload = {
            "model":       model,
            "messages":    messages,
            "max_tokens":  max_tokens,
            "temperature": temperature,
        }

        for attempt in range(1, MAX_RETRIES + 1):
            self._throttle()

            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=60)

                # ── Rate-limited ───────────────────────────────────────────
                if resp.status_code == 429:
                    wait = self._backoff(resp, attempt)
                    logger.warning(
                        "429 on %s [%s] attempt %d/%d — waiting %.1fs",
                        url.split("/")[2], model, attempt, MAX_RETRIES, wait,
                    )
                    if attempt < MAX_RETRIES:
                        time.sleep(wait)
                        continue
                    return None   # give up on this model

                resp.raise_for_status()

                data = resp.json()
                if "choices" in data and len(data["choices"]) > 0:
                    content = data["choices"][0]["message"].get("content")
                    provider = url.split("/")[2]
                    logger.info("✅ %s [%s] succeeded on attempt %d.", provider, model, attempt)
                    return content if content is not None else ""

                return "Unable to generate response at this time."

            except requests.exceptions.Timeout:
                logger.warning("Timeout on %s attempt %d.", model, attempt)
                if attempt < MAX_RETRIES:
                    time.sleep(BASE_BACKOFF * attempt)
                    continue
                return None

            except requests.exceptions.RequestException as e:
                logger.warning("Request error [%s] attempt %d: %s", model, attempt, e)
                if attempt < MAX_RETRIES:
                    time.sleep(BASE_BACKOFF * attempt)
                    continue
                return None

            except Exception as e:
                logger.error("Unexpected error: %s", e)
                return f"Unexpected error: {str(e)[:120]}"

        return None

    # ══════════════════════════════════════════════════════════════════════════
    # Helpers
    # ══════════════════════════════════════════════════════════════════════════

    def _backoff(self, response, attempt):
        """Read Retry-After header or fall back to exponential backoff."""
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return min(float(retry_after), 30.0)   # cap at 30s
            except ValueError:
                pass
        return BASE_BACKOFF ** attempt

    def _throttle(self):
        """Minimum gap between consecutive API calls."""
        now = time.monotonic()
        gap = INTER_CALL_DELAY - (now - self._last_call)
        if gap > 0:
            time.sleep(gap)
        self._last_call = time.monotonic()

    # ══════════════════════════════════════════════════════════════════════════
    # Public API (same interface — no changes needed in app.py)
    # ══════════════════════════════════════════════════════════════════════════

    def generate_insights(self, context_data):
        """
        Generate AI business insights from dashboard data context.
        Returns a list of insight objects.
        """
        system_prompt = """You are LazyBIZ AI, an enterprise business intelligence analyst. 
Analyze the provided data context and generate exactly 3 actionable business insights.

Return your response as a JSON array with exactly 3 objects, each having:
- "title": A short, impactful headline (max 8 words)
- "body": A detailed insight with specific numbers/recommendations (1-2 sentences)
- "type": One of "opportunity", "risk", "trend"

Example format:
[
  {"title": "Revenue Growth Acceleration", "body": "Q4 shows 15% above forecast driven by enterprise renewals. Consider expanding sales team.", "type": "trend"},
  {"title": "Customer Churn Risk Alert", "body": "3 enterprise accounts show 40% decreased usage. Immediate outreach recommended.", "type": "risk"},
  {"title": "Cross-Sell Opportunity", "body": "Users of Product A are 35% more likely to purchase Product B. Bundle pricing recommended.", "type": "opportunity"}
]

Return ONLY the JSON array, no other text."""

        user_prompt = f"Analyze this business data and generate insights:\n\n{context_data}"

        response = self._call([
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ], max_tokens=800, temperature=0.6)

        # Parse JSON response
        try:
            start = response.find("[")
            end   = response.rfind("]") + 1
            if start != -1 and end > start:
                insights = json.loads(response[start:end])
                if isinstance(insights, list) and len(insights) > 0:
                    return insights
        except (json.JSONDecodeError, ValueError):
            pass

        # Fallback insights if AI is completely down
        return [
            {
                "title": "Data Analysis In Progress",
                "body":  "AI is processing your data. Upload more data for deeper insights.",
                "type":  "trend",
            },
            {
                "title": "Upload More Data",
                "body":  "Add CSV files to unlock comprehensive trend analysis and predictions.",
                "type":  "opportunity",
            },
            {
                "title": "System Healthy",
                "body":  "All RAG pipelines operational. Vector store ready for queries.",
                "type":  "trend",
            },
        ]

    def chat_with_context(self, question, rag_context, sources=None):
        """Answer a user question using RAG context with strict product name rules."""
        system_prompt = """You are LazyBIZ AI Assistant, an expert business data analyst.
You have been provided with a GLOBAL DATASET SUMMARY and RELEVANT DATA SNIPPETS.

STRICT GUIDELINES:
1. Answer the user's question directly. DO NOT explain backend processes.
2. If asked about "products" or "highest sales", use the SPECIFIC PRODUCT NAME from the 'product_name' column. 
3. NEVER provide category names (like 'Machinery', 'Hardware', 'Tools') when a specific product name is requested. Categories are for broad grouping, but "Product" always refers to the specific item name.
4. For "highest sales", provide the EXACT PRODUCT NAME + TOTAL REVENUE.
5. If the user asks about at-risk items, refer to the specific product names and solutions in the summary.
6. Keep responses very concise (max 2 paragraphs). Answer first, then insight."""

        source_info = f"\nData sources: {', '.join(sources)}" if sources else ""
        user_prompt = f"Context:{source_info}\n\n{rag_context}\n\nQuestion: {question}"

        return self._call([
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ], max_tokens=1024, temperature=0.5)

    def summarize_dataset(self, schema_info):
        """Generate a human-readable summary of an uploaded dataset."""
        system_prompt = """You are a data analyst. Given dataset schema information, 
provide a brief, clear summary of what this dataset contains and what analyses are possible.
Keep it to 2-3 sentences."""

        return self._call([
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": f"Summarize this dataset:\n{schema_info}"},
        ], max_tokens=256, temperature=0.4)

    def _gemini_call(self, messages):
        """Invoke Gemini Pro via direct REST API (Stable for Python 3.9)."""
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_key}"
            
            # Convert messages to Gemini format
            contents = []
            for m in messages:
                role = "user" if m["role"] == "user" else "model"
                contents.append({"role": role, "parts": [{"text": m["content"]}]})
            
            payload = {"contents": contents}
            response = requests.post(url, json=payload, timeout=30)
            data = response.json()
            
            if "candidates" in data and len(data["candidates"]) > 0:
                return data["candidates"][0]["content"]["parts"][0]["text"]
            return None
        except Exception as e:
            logger.error("Gemini REST call failed: %s", e)
            return None
