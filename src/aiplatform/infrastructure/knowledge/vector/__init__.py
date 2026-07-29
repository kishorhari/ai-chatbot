"""Vector-store adapters — concrete ``VectorStore`` implementations (ADR-0013).

The similarity-search index, kept distinct from the ``KnowledgeRepository`` record
so the vector backend is replaceable independently. The in-memory store is the
offline reference; pgvector (M3.7) is the production backend, proven against the
same contract suite.
"""
