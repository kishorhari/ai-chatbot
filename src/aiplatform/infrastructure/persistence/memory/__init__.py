"""In-memory persistence — the reference ``ConversationRepository`` (ADR-0005).

A process-local, dependency-free repository used for development and for fast,
database-free tests. It is the first of two implementations proven against the
shared repository contract suite; PostgreSQL (M2.5) is the second.
"""
