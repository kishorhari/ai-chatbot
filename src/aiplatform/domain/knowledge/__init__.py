"""Knowledge domain — documents, chunks, and the retrieval contracts (Milestone 3).

Pure domain (ADR-0001/0011): value objects, the ``KnowledgeDocument`` aggregate,
and the ``EmbeddingProvider`` / ``VectorStore`` / ``KnowledgeRepository`` ports —
no I/O, no embedding SDK, no vector client, no ``numpy``. The embedding *vector*
is a first-class value object, but a chunk's stored vector is an infrastructure
representation held by the vector store, not a field on the domain aggregate
(ADR-0011). Existing value objects (``Role``, ``TokenUsage``) are reused, not
duplicated; the frozen M1/M2 ports are untouched.
"""
