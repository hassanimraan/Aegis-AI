import numpy as np

from google import genai
from google.genai import types

from config.settings import get_gemini_api_key
from rag.knowledge_base import load_knowledge_base


MODEL = "gemini-embedding-001"
DIMENSIONS = 768


def get_embedding(text):
    if not text or not str(text).strip():
        raise ValueError("Embedding query cannot be empty.")

    client = genai.Client(
        api_key=get_gemini_api_key()
    )

    result = client.models.embed_content(
        model=MODEL,
        contents=str(text),
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=DIMENSIONS
        )
    )

    if not result.embeddings:
        raise ValueError(
            "Gemini returned no embedding for the supplied query."
        )

    embedding = np.array(
        result.embeddings[0].values,
        dtype=np.float32
    )

    if embedding.size != DIMENSIONS:
        raise ValueError(
            f"Unexpected embedding dimension: "
            f"{embedding.size}. Expected {DIMENSIONS}."
        )

    return embedding


def cosine_similarity(a, b):
    if a.size == 0 or b.size == 0:
        return 0.0

    if a.shape != b.shape:
        raise ValueError(
            "Embedding dimensions do not match."
        )

    denominator = (
        np.linalg.norm(a) *
        np.linalg.norm(b)
    )

    if denominator == 0:
        return 0.0

    return float(
        np.dot(a, b) / denominator
    )


def search_policies(query, top_k=5):
    if not query or not str(query).strip():
        return []

    if top_k <= 0:
        return []

    knowledge_base = load_knowledge_base()

    if not knowledge_base:
        return []

    query_embedding = get_embedding(query)

    results = []

    for item in knowledge_base:

        if "embedding" not in item:
            continue

        policy_embedding = np.array(
            item["embedding"],
            dtype=np.float32
        )

        if policy_embedding.size != DIMENSIONS:
            continue

        similarity = cosine_similarity(
            query_embedding,
            policy_embedding
        )

        results.append({
            "policy_id": item["policy_id"],
            "policy_name": item["policy_name"],
            "section_id": item["section_id"],
            "section_title": item["section_title"],
            "content": item["content"],
            "version": item["version"],
            "effective_date": item["effective_date"],
            "similarity": similarity
        })

    results.sort(
        key=lambda x: x["similarity"],
        reverse=True
    )

    return results[:top_k]
