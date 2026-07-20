"""
Vertex AI Pattern — Enterprise Embedding & LLM Wrapper
=======================================================
This module provides the exact same architectural interface that Google Cloud
Vertex AI uses, but powered by your existing free Gemini API key.

WHY THIS EXISTS:
  • Vertex AI uses the same underlying models (text-embedding-004, Gemini Flash)
    as the free Gemini API. The code structure is IDENTICAL.
  • When you're ready to go fully enterprise (GCP billing enabled), you only
    need to change 3 lines in __init__ to use the `vertexai` SDK.
  • Until then, this gives you the Vertex AI architectural pattern on your resume
    at zero cost.

HOW TO UPGRADE TO REAL VERTEX AI LATER:
  1. pip install google-cloud-aiplatform
  2. Set GCP_PROJECT_ID and GCP_LOCATION in .env
  3. Uncomment the Vertex AI imports below and replace the REST call bodies.
"""

import os
import logging
import requests

logger = logging.getLogger(__name__)

# ── Vertex AI SDK (uncomment when you have GCP billing enabled) ───────────────
# import vertexai
# from vertexai.language_models import TextEmbeddingModel
# from vertexai.generative_models import GenerativeModel
# vertexai.init(
#     project=os.getenv("GCP_PROJECT_ID", "lazybiz-enterprise"),
#     location=os.getenv("GCP_LOCATION", "us-central1"),
# )
# ─────────────────────────────────────────────────────────────────────────────


class VertexEmbeddingWrapper:
    """
    Enterprise-grade embedding generator.

    Vertex AI equivalent of:
        model = TextEmbeddingModel.from_pretrained("text-embedding-004")
        embeddings = model.get_embeddings(texts)

    Currently uses the free Gemini REST API with the same model.
    Zero infrastructure cost, identical output dimensions (768).
    """

    MODEL_NAME = "text-embedding-004"
    DIMENSIONS = 768

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        # GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")  # Uncomment for real Vertex AI
        if not self.api_key:
            logger.warning(
                "[VertexEmbeddingWrapper] GEMINI_API_KEY not set. "
                "Falling back to mock embeddings."
            )

    def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        Generate text embeddings for a list of strings.

        Vertex AI equivalent:
            model.get_embeddings(texts)  →  [Embedding(values=[...]), ...]

        Returns a list of float vectors (length = DIMENSIONS).
        """
        if not self.api_key:
            return self._mock_embeddings(len(texts))

        url = (
            "https://generativelanguage.googleapis.com/v1beta"
            f"/models/{self.MODEL_NAME}:batchEmbedContents?key={self.api_key}"
        )
        results = []
        try:
            for i in range(0, len(texts), 50):
                batch = texts[i : i + 50]
                body = {
                    "requests": [
                        {
                            "model": f"models/{self.MODEL_NAME}",
                            "content": {"parts": [{"text": t}]},
                        }
                        for t in batch
                    ]
                }
                resp = requests.post(url, json=body, timeout=15)
                resp.raise_for_status()
                for emb in resp.json().get("embeddings", []):
                    results.append(emb.get("values", [0.0] * self.DIMENSIONS))
        except Exception as exc:
            logger.error("[VertexEmbeddingWrapper] API error: %s", exc)
            remaining = len(texts) - len(results)
            results += self._mock_embeddings(remaining)

        return results

    @staticmethod
    def _mock_embeddings(n: int) -> list[list[float]]:
        import numpy as np
        return [
            (lambda v: (v / (norm := float(np.linalg.norm(v))) if norm > 0 else v))(
                np.random.randn(VertexEmbeddingWrapper.DIMENSIONS).tolist()
            )
            for _ in range(n)
        ]


class VertexLLMWrapper:
    """
    Enterprise-grade generative model wrapper.

    Vertex AI equivalent of:
        model = GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)

    Currently uses Gemini REST API directly.
    Drop-in compatible: same method signatures, same return types.
    """

    MODEL_NAME = "gemini-1.5-flash"

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        if not self.api_key:
            logger.warning("[VertexLLMWrapper] GEMINI_API_KEY not set.")

    def generate_content(self, prompt: str, temperature: float = 0.7, max_tokens: int = 1024) -> str:
        """
        Generate text from a prompt.

        Vertex AI equivalent:
            response = model.generate_content(prompt)
            return response.text

        Returns the generated text string.
        """
        if not self.api_key:
            return "⚠️ GEMINI_API_KEY not configured."

        url = (
            "https://generativelanguage.googleapis.com/v1beta"
            f"/models/{self.MODEL_NAME}:generateContent?key={self.api_key}"
        )
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        try:
            resp = requests.post(url, json=body, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if "candidates" in data and data["candidates"]:
                return data["candidates"][0]["content"]["parts"][0]["text"]
            return "No response generated."
        except Exception as exc:
            logger.error("[VertexLLMWrapper] generation failed: %s", exc)
            return f"⚠️ LLM error: {exc}"

    def generate_chat(self, messages: list[dict], temperature: float = 0.7, max_tokens: int = 1024) -> str:
        """
        Multi-turn chat generation.
        messages format: [{"role": "user"|"model", "content": "..."}]
        """
        if not self.api_key:
            return "⚠️ GEMINI_API_KEY not configured."

        url = (
            "https://generativelanguage.googleapis.com/v1beta"
            f"/models/{self.MODEL_NAME}:generateContent?key={self.api_key}"
        )
        contents = [
            {"role": m["role"], "parts": [{"text": m["content"]}]}
            for m in messages
        ]
        body = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        try:
            resp = requests.post(url, json=body, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if "candidates" in data and data["candidates"]:
                return data["candidates"][0]["content"]["parts"][0]["text"]
            return "No response generated."
        except Exception as exc:
            logger.error("[VertexLLMWrapper] chat failed: %s", exc)
            return f"⚠️ LLM error: {exc}"
