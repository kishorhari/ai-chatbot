"""Knowledge repository adapters — the ``KnowledgeDocument`` record store (ADR-0016).

The relational record of ingested documents/chunks (metadata, status, provenance),
distinct from the vector search index (ADR-0013). In-memory now; SQLAlchemy/pgvector
at M3.7, proven against the same contract suite.
"""
