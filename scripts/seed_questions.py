"""
Seed script: insert 20 sample interview questions into Qdrant questions_bank.
Run inside Docker:  docker exec local_backend python scripts/seed_questions.py
Or locally:         python scripts/seed_questions.py
"""
import asyncio
import sys
import os

# Ensure the backend app is importable when running from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.services.qdrant_service import QdrantService

SAMPLE_QUESTIONS = [
    # ── Python / Technical ──────────────────────────────────────────────
    {
        "question_text": "Explain the difference between a list and a tuple in Python. When would you use one over the other?",
        "domain": "python",
        "type": "technical",
        "level": "junior",
        "source": "seed",
    },
    {
        "question_text": "What are Python decorators and how do they work internally? Give an example with *args and **kwargs.",
        "domain": "python",
        "type": "technical",
        "level": "mid",
        "source": "seed",
    },
    {
        "question_text": "Describe Python's GIL. How does it affect multi-threaded CPU-bound workloads and what strategies exist to work around it?",
        "domain": "python",
        "type": "technical",
        "level": "senior",
        "source": "seed",
    },
    {
        "question_text": "What is the difference between `__str__` and `__repr__` in Python? How does Python decide which one to call?",
        "domain": "python",
        "type": "technical",
        "level": "junior",
        "source": "seed",
    },
    # ── System Design ───────────────────────────────────────────────────
    {
        "question_text": "Design a URL shortener service like bit.ly. Discuss the data model, hashing strategy, and how you would handle billions of URLs.",
        "domain": "system_design",
        "type": "technical",
        "level": "mid",
        "source": "seed",
    },
    {
        "question_text": "How would you design a real-time chat application that supports group conversations, read receipts, and message delivery guarantees?",
        "domain": "system_design",
        "type": "technical",
        "level": "senior",
        "source": "seed",
    },
    {
        "question_text": "Design a simple notification service. How would you handle push, email, and SMS channels with retry logic?",
        "domain": "system_design",
        "type": "technical",
        "level": "junior",
        "source": "seed",
    },
    {
        "question_text": "You need to design a distributed rate limiter for an API gateway handling 100k req/s. Walk through your approach.",
        "domain": "system_design",
        "type": "technical",
        "level": "senior",
        "source": "seed",
    },
    # ── Behavioral (STAR) ───────────────────────────────────────────────
    {
        "question_text": "Tell me about a time you had a conflict with a teammate. How did you resolve it and what was the outcome?",
        "domain": "behavioral",
        "type": "behavioral",
        "level": "junior",
        "source": "seed",
    },
    {
        "question_text": "Describe a situation where you had to make a critical technical decision under tight deadlines. What was your approach?",
        "domain": "behavioral",
        "type": "behavioral",
        "level": "mid",
        "source": "seed",
    },
    {
        "question_text": "Give an example of a time you mentored a junior developer. How did you adapt your communication style?",
        "domain": "behavioral",
        "type": "behavioral",
        "level": "senior",
        "source": "seed",
    },
    {
        "question_text": "Tell me about a project you are most proud of. What challenges did you face and how did you overcome them?",
        "domain": "behavioral",
        "type": "behavioral",
        "level": "junior",
        "source": "seed",
    },
    # ── SQL ──────────────────────────────────────────────────────────────
    {
        "question_text": "What is the difference between INNER JOIN, LEFT JOIN, and FULL OUTER JOIN? Provide examples of when you would use each.",
        "domain": "sql",
        "type": "technical",
        "level": "junior",
        "source": "seed",
    },
    {
        "question_text": "Explain query execution plans. How would you diagnose and optimise a slow SQL query with millions of rows?",
        "domain": "sql",
        "type": "technical",
        "level": "mid",
        "source": "seed",
    },
    {
        "question_text": "Describe the trade-offs between normalisation and denormalisation. When would you violate 3NF in a production system?",
        "domain": "sql",
        "type": "technical",
        "level": "senior",
        "source": "seed",
    },
    {
        "question_text": "What are window functions in SQL? Write a query using ROW_NUMBER(), RANK(), and PARTITION BY.",
        "domain": "sql",
        "type": "technical",
        "level": "mid",
        "source": "seed",
    },
    # ── API Design ──────────────────────────────────────────────────────
    {
        "question_text": "What are the key differences between REST and GraphQL? When would you choose one over the other?",
        "domain": "api_design",
        "type": "technical",
        "level": "junior",
        "source": "seed",
    },
    {
        "question_text": "How would you version a public REST API? Discuss URL versioning vs header versioning and their trade-offs.",
        "domain": "api_design",
        "type": "technical",
        "level": "mid",
        "source": "seed",
    },
    {
        "question_text": "Design a pagination strategy for an API returning large datasets. Compare offset-based, cursor-based, and keyset pagination.",
        "domain": "api_design",
        "type": "technical",
        "level": "senior",
        "source": "seed",
    },
    {
        "question_text": "Explain idempotency in the context of REST APIs. How would you make a payment endpoint idempotent?",
        "domain": "api_design",
        "type": "technical",
        "level": "mid",
        "source": "seed",
    },
]


async def main():
    service = QdrantService.get_instance()

    # Ensure collections exist
    await service.init_collections()

    # Upsert all sample questions
    count = await service.upsert_questions(SAMPLE_QUESTIONS)
    print(f"✅ Successfully seeded {count} questions into Qdrant 'questions_bank' collection.")

    # Quick verification
    info = service.client.get_collection("questions_bank")
    print(f"   Collection points count: {info.points_count}")


if __name__ == "__main__":
    asyncio.run(main())
