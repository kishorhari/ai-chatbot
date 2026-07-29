"""SQLAlchemy knowledge repository — the PostgreSQL record store (ADR-0016).

The second ``KnowledgeRepository`` implementation, reusing the M2 SQLAlchemy
infrastructure (the shared ``SessionProvider`` and async session/transaction
management). It keeps the domain persistence-ignorant: models here, explicit
domain↔ORM mapping, and no ORM leakage into the aggregate. Proven against the same
knowledge-repository contract suite the in-memory store passes.
"""
