"""pgvector vector store — the PostgreSQL similarity-search backend (ADR-0013).

The second ``VectorStore`` implementation, over the pgvector extension, reusing
the M2 SQLAlchemy ``SessionProvider``. It has its **own** table (a dimensionless
``vector`` column, so the store works at whatever dimension the embedding model
uses) and is exercised only against real PostgreSQL/pgvector (CI) — SQLite has no
vector type. It passes the identical ``VectorStoreContract`` the in-memory store
passes.
"""
