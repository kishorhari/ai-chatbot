"""CLI knowledge probe — ingest a document, then query it (M3.6).

A developer tool that boots the composition root and exercises the knowledge
services without HTTP. It ingests a document and runs a retrieval query **in one
process**, which is what makes the in-memory backend usable (nothing persists
across separate invocations); against pgvector (M3.7) the two could be split. Run::

    AIP__KNOWLEDGE__ENABLED=true python -m aiplatform.interface.cli.ingest \
        "faq.md" "The capital of France is Paris." "What is the capital of France?"

Requires the knowledge feature to be enabled; otherwise it reports that and exits.
"""

from __future__ import annotations

import asyncio
import sys

from aiplatform.composition.bootstrap import bootstrap, shutdown
from aiplatform.composition.container import Container
from aiplatform.domain.knowledge.errors import KnowledgeError


async def _run(source: str, text: str, query: str) -> int:
    """Ingest ``text`` under ``source``, then print the chunks retrieved for ``query``."""
    container = bootstrap()
    try:
        return await _ingest_and_query(container, source, text, query)
    finally:
        await shutdown(container)


async def _ingest_and_query(container: Container, source: str, text: str, query: str) -> int:
    """Drive the knowledge services for a single ingest + query."""
    if container.knowledge is None:
        sys.stderr.write("knowledge feature is disabled (set AIP__KNOWLEDGE__ENABLED=true)\n")
        return 2
    try:
        result = await container.knowledge.indexing_service.index(source=source, text=text)
        sys.stdout.write(f"[indexed {result.document_id} — {result.chunk_count} chunk(s)]\n")
        context = await container.knowledge.retrieval_service.search(query)
    except KnowledgeError as exc:
        sys.stderr.write(f"\n[ingest] {type(exc).__name__}: {exc}\n")
        return 1

    if context.is_empty:
        sys.stdout.write("no relevant chunks found\n")
        return 0
    for chunk in context.chunks:
        sys.stdout.write(f"  ({chunk.score:.3f}) {chunk.text}\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point: ``ingest.py <source> <text> <query>``.

    Returns:
        Process exit code (0 success, 1 knowledge error, 2 misuse/disabled).
    """
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 3:
        sys.stderr.write("usage: ingest.py <source> <text> <query>\n")
        return 2
    source, text, query = args
    return asyncio.run(_run(source, text, query))


if __name__ == "__main__":
    raise SystemExit(main())
