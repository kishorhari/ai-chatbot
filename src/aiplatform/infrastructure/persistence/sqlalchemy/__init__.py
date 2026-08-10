"""PostgreSQL persistence via SQLAlchemy (ADR-0008).

The second ``ConversationRepository`` implementation. It keeps the domain wholly
persistence-ignorant: SQLAlchemy models live here, and explicit mapping functions
translate domain aggregate ↔ ORM rows (the same "map at the boundary" precedent as
the provider adapters, ADR-0002). Domain and application import nothing from this
package — the composition root selects it by configuration.

The repository is written against the async SQLAlchemy Core/ORM and is therefore
engine-agnostic; it is proven against the identical repository contract suite over
PostgreSQL (the authoritative run, in CI) and — for fast local evidence — over an
in-memory SQLite engine.
"""
