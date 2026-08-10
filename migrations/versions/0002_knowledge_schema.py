"""knowledge schema (documents, chunks, pgvector vectors)

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-29

Creates the knowledge record tables (``knowledge_documents``,
``knowledge_chunks``) and the pgvector search table (``knowledge_vectors``), plus
the ``vector`` extension (ADR-0013/0016). The vector table is created via raw SQL
so this migration imports without the ``pgvector`` Python package; the ``vector``
column is dimensionless (any embedding dimension).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=1024), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_documents_source", "knowledge_documents", ["source"])

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["knowledge_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "ordinal", name="uq_knowledge_chunks_document_ordinal"),
    )
    op.create_index("ix_knowledge_chunks_document_id", "knowledge_chunks", ["document_id"])

    # Raw SQL: the pgvector `vector` type is not a core SQLAlchemy type, and this
    # keeps the migration importable without the pgvector package. Dimensionless.
    op.execute(
        "CREATE TABLE knowledge_vectors ("
        " chunk_id UUID NOT NULL PRIMARY KEY,"
        " document_id UUID NOT NULL,"
        " embedding vector NOT NULL,"
        " text TEXT NOT NULL,"
        " metadata JSON NOT NULL"
        ")"
    )
    op.create_index("ix_knowledge_vectors_document_id", "knowledge_vectors", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_vectors_document_id", table_name="knowledge_vectors")
    op.execute("DROP TABLE knowledge_vectors")
    op.drop_index("ix_knowledge_chunks_document_id", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
    op.drop_index("ix_knowledge_documents_source", table_name="knowledge_documents")
    op.drop_table("knowledge_documents")
