import json
from typing import List, Dict
import httpx

from app.core.config import settings

SYSTEM_PROMPT = """You are an enterprise document assistant. Answer only using provided context.
If context is insufficient, clearly say you do not have enough information from the uploaded documents.
Return concise, factual responses."""

class LLMServiceError(Exception):
    pass


def build_context(chunks: List[Dict]) -> str:
    blocks = []
    for c in chunks:
        snippet = c["content"][:1500]
        blocks.append(
            f"[Doc: {c['filename']} | Page: {c['page_number']} | ChunkId: {c['chunk_id']}]\n{snippet}"
        )
    return "\n\n".join(blocks)


async def generate_answer(query: str, chunks: List[Dict], history: List[Dict]) -> str:
    context = build_context(chunks)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history[-6:])
    messages.append(
        {
            "role": "user",
            "content": f"Question: {query}\n\nContext:\n{context}\n\nAnswer with grounded facts and mention if uncertain.",
        }
    )

    payload = {
        "model": settings.ollama_model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.1},
    }
    # No timeout: allow model generation to complete regardless of duration.
    async with httpx.AsyncClient(timeout=None) as client:
        models_resp = await client.get(f"{settings.ollama_base_url}/api/tags")
        models_resp.raise_for_status()
        models = models_resp.json().get("models", [])
        available_names = [m.get("name") for m in models if m.get("name")]
        configured_model = payload["model"]
        if configured_model not in available_names and available_names:
            payload["model"] = available_names[0]

        resp = await client.post(f"{settings.ollama_base_url}/api/chat", json=payload)
        if resp.status_code >= 400:
            error_text = ""
            try:
                error_text = resp.json().get("error", "")
            except ValueError:
                error_text = resp.text

            # Try a smaller installed model when memory is insufficient.
            if "requires more system memory" in error_text and models:
                sorted_models = sorted(
                    models,
                    key=lambda m: m.get("size", 1 << 62)
                )
                for candidate in sorted_models:
                    candidate_name = candidate.get("name")
                    if not candidate_name or candidate_name == payload["model"]:
                        continue
                    payload["model"] = candidate_name
                    retry_resp = await client.post(f"{settings.ollama_base_url}/api/chat", json=payload)
                    if retry_resp.status_code < 400:
                        data = retry_resp.json()
                        return data.get("message", {}).get("content", "")

            raise LLMServiceError(error_text or f"Ollama request failed with status {resp.status_code}.")

        data = resp.json()
    return data.get("message", {}).get("content", "")


def citations_from_chunks(chunks: List[Dict]):
    return [
        {
            "document_id": c["document_id"],
            "filename": c["filename"],
            "page_number": c["page_number"],
            "chunk_id": c["chunk_id"],
            "snippet": c["content"][:250],
        }
        for c in chunks
    ]


def dump_citations(citations) -> str:
    return json.dumps(citations)
