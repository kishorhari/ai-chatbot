"""Persistence infrastructure — concrete ``ConversationRepository`` implementations.

Each backend (in-memory now, PostgreSQL/SQLAlchemy at M2.5) implements the domain
``ConversationRepository`` port and is selected at the composition root by
configuration (ADR-0008). Domain and application never import anything here.
"""
