"""CLI chat — a minimal multi-turn conversation over the wired services.

A developer tool that exercises the full conversation use case without HTTP: it
boots the composition root, creates a conversation, and sends each turn through
``ChatService``, printing the assistant reply. Turns are supplied as arguments
(one per turn); with no arguments it reads one turn per line from stdin until EOF.
Delivery stays thin — it calls the application services and prints results, and
owns no orchestration (ADR-0010). Run e.g.::

    AIP__LLM__DEFAULT_PROVIDER=echo python -m aiplatform.interface.cli.chat "hello" "how are you"
"""

from __future__ import annotations

import asyncio
import sys

from aiplatform.composition.bootstrap import bootstrap, shutdown
from aiplatform.composition.container import Container
from aiplatform.domain.llm.errors import LLMError

_DEFAULT_OWNER = "cli-user"


async def _run(turns: list[str], *, owner: str = _DEFAULT_OWNER) -> int:
    """Create a conversation and send each turn, printing replies."""
    container = bootstrap()
    try:
        return await _converse(container, turns, owner=owner)
    finally:
        await shutdown(container)


async def _converse(container: Container, turns: list[str], *, owner: str) -> int:
    """Drive the conversation services for the given turns."""
    conversation = await container.conversation_service.start_conversation(owner=owner)
    sys.stdout.write(f"[conversation {conversation.id}]\n")
    try:
        for turn in turns:
            sys.stdout.write(f"you> {turn}\n")
            result = await container.chat_service.send_message(conversation.id, turn)
            sys.stdout.write(f"ai>  {result.content}\n")
            sys.stdout.flush()
        return 0
    except LLMError as exc:
        sys.stderr.write(f"\n[chat] {type(exc).__name__}: {exc}\n")
        return 1


def _read_turns(argv: list[str]) -> list[str]:
    """Turns come from args, or one-per-line from stdin when no args are given."""
    if argv:
        return [t for t in argv if t.strip()]
    return [line.strip() for line in sys.stdin if line.strip()]


def main(argv: list[str] | None = None) -> int:
    """Entry point: run a CLI chat session.

    Args:
        argv: Optional turn list (defaults to ``sys.argv[1:]`` / stdin).

    Returns:
        Process exit code (0 on success, 1 on a provider error).
    """
    args = list(sys.argv[1:] if argv is None else argv)
    turns = _read_turns(args)
    if not turns:
        sys.stderr.write("no turns provided\n")
        return 2
    return asyncio.run(_run(turns))


if __name__ == "__main__":
    raise SystemExit(main())
