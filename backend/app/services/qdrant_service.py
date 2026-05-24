"""
Qdrant vector database service for InterviewAI.
Manages questions_bank and candidate_memories collections.
"""
import os
import uuid
import hashlib
import logging
from typing import Optional, List, Dict, Any

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue,
    PayloadSchemaType,
)

logger = logging.getLogger(__name__)

QDRANT_HOST = os.environ.get("QDRANT_HOST", "qdrant")
QDRANT_PORT = int(os.environ.get("QDRANT_HTTP_PORT", "6333"))
VECTOR_SIZE = 768  # nomic-embed-text output dimension

# ---------------------------------------------------------------------------
# Embedding helper – uses nomic-embed-text via Groq API,
# falls back to a deterministic hash-based pseudo-embedding.
# ---------------------------------------------------------------------------

def _hash_embedding(text: str, size: int = VECTOR_SIZE) -> List[float]:
    """
    Deterministic pseudo-embedding based on SHA-512.
    Used as fallback when no embedding API is configured.
    Produces a normalised vector of the requested dimension.
    """
    h = hashlib.sha512(text.encode("utf-8")).digest()
    raw = []
    while len(raw) < size:
        h = hashlib.sha512(h).digest()
        raw.extend([b / 255.0 for b in h])
    vec = raw[:size]
    norm = max(sum(v * v for v in vec) ** 0.5, 1e-9)
    return [v / norm for v in vec]


class QdrantService:
    """Singleton service for Qdrant vector operations."""

    _instance: Optional["QdrantService"] = None

    def __init__(self):
        self.client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        self._groq_client = None

    @classmethod
    def get_instance(cls) -> "QdrantService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------
    # Embedding — nomic-embed-text via Groq
    # ------------------------------------------------------------------
    async def get_embedding(self, text: str) -> List[float]:
        """
        Return a 768-dim embedding vector using nomic-embed-text via Groq.
        Falls back to hash embedding if GROQ_API_KEY is not set.
        """
        api_key = os.environ.get("GROQ_API_KEY")
        if api_key:
            try:
                import httpx
                if self._groq_client is None:
                    self._groq_client = httpx.Client(
                        base_url="https://api.groq.com/openai/v1",
                        headers={"Authorization": f"Bearer {api_key}"},
                        timeout=30.0,
                    )
                resp = self._groq_client.post(
                    "/embeddings",
                    json={
                        "model": "nomic-embed-text-v1.5",
                        "input": text,
                    },
                )
                resp.raise_for_status()
                return resp.json()["data"][0]["embedding"]
            except Exception as exc:
                logger.warning("Groq nomic-embed-text failed, using fallback: %s", exc)
        return _hash_embedding(text)

    # ------------------------------------------------------------------
    # Collection management
    # ------------------------------------------------------------------
    async def init_collections(self) -> None:
        """Create the two required collections if they do not exist."""
        existing = [c.name for c in self.client.get_collections().collections]

        if "questions_bank" not in existing:
            self.client.create_collection(
                collection_name="questions_bank",
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            )
            # Define payload indexes for fast filtering
            for field in ("domain", "type", "level", "source"):
                self.client.create_payload_index(
                    collection_name="questions_bank",
                    field_name=field,
                    field_schema=PayloadSchemaType.KEYWORD,
                )
            logger.info("Created collection: questions_bank")

        if "candidate_memories" not in existing:
            self.client.create_collection(
                collection_name="candidate_memories",
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            )
            for field in ("user_id", "session_id"):
                self.client.create_payload_index(
                    collection_name="candidate_memories",
                    field_name=field,
                    field_schema=PayloadSchemaType.KEYWORD,
                )
            logger.info("Created collection: candidate_memories")

    # ------------------------------------------------------------------
    # Questions bank
    # ------------------------------------------------------------------
    async def search_questions(
        self,
        query: str,
        filters: Optional[Dict[str, str]] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Semantic search over the questions_bank collection."""
        query_vector = await self.get_embedding(query)

        must_conditions = []
        if filters:
            for key, value in filters.items():
                if value is not None:
                    must_conditions.append(
                        FieldCondition(key=key, match=MatchValue(value=value))
                    )

        search_filter = Filter(must=must_conditions) if must_conditions else None

        results = self.client.search(
            collection_name="questions_bank",
            query_vector=query_vector,
            query_filter=search_filter,
            limit=top_k,
            with_payload=True,
        )

        return [
            {
                "id": str(hit.id),
                "score": hit.score,
                **hit.payload,
            }
            for hit in results
        ]

    async def upsert_questions(self, questions: List[Dict[str, Any]]) -> int:
        """
        Upsert a batch of questions into questions_bank.
        Each dict must have: question_text, domain, type, level, source.
        Returns the number of points upserted.
        """
        points = []
        for q in questions:
            vector = await self.get_embedding(q["question_text"])
            point_id = str(uuid.uuid4())
            points.append(
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "question_text": q["question_text"],
                        "reference_answer": q.get("reference_answer", ""),
                        "domain": q["domain"],
                        "type": q["type"],
                        "level": q["level"],
                        "source": q.get("source", "seed"),
                    },
                )
            )
        self.client.upsert(collection_name="questions_bank", points=points)
        return len(points)

    async def compute_similarity(self, text1: str, text2: str) -> float:
        """Compute cosine similarity between two texts using the embedding service."""
        import math
        if not text1 or not text2:
            return 0.0
            
        vec1 = await self.get_embedding(text1)
        vec2 = await self.get_embedding(text2)
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
            
        return dot_product / (norm1 * norm2)

    # ------------------------------------------------------------------
    # Candidate memories
    # ------------------------------------------------------------------
    async def upsert_memory(
        self,
        user_id: str,
        session_id: str,
        question: str,
        answer_summary: str,
    ) -> None:
        """Store a candidate memory (question + answer summary) as a vector."""
        text = f"Q: {question}\nA: {answer_summary}"
        vector = await self.get_embedding(text)
        point_id = str(uuid.uuid4())
        self.client.upsert(
            collection_name="candidate_memories",
            points=[
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "user_id": user_id,
                        "session_id": session_id,
                        "question": question,
                        "answer_summary": answer_summary,
                    },
                )
            ],
        )

    async def search_memories(
        self,
        user_id: str,
        query: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Retrieve past candidate memories relevant to a query."""
        query_vector = await self.get_embedding(query)
        results = self.client.search(
            collection_name="candidate_memories",
            query_vector=query_vector,
            query_filter=Filter(
                must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
            ),
            limit=top_k,
            with_payload=True,
        )
        return [
            {
                "id": str(hit.id),
                "score": hit.score,
                **hit.payload,
            }
            for hit in results
        ]


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------
def get_qdrant_service() -> QdrantService:
    """FastAPI dependency that returns the QdrantService singleton."""
    return QdrantService.get_instance()
