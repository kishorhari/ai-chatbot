"""CLI probe — stream one prompt to the default provider.

A developer tool that validates streaming and cancellation end-to-end without
the HTTP stack: it boots the composition root, resolves the configured default
provider (a port — it never names a concrete provider), streams a single prompt,
and prints each delta as it arrives. Run e.g.::

    AIP__LLM__DEFAULT_PROVIDER=echo python -m aiplatform.interface.cli.probe "hello world"
"""

from __future__ import annotations

import asyncio
import sys

from aiplatform.composition.bootstrap import bootstrap, shutdown
from aiplatform.composition.container import Container
from aiplatform.domain.llm.errors import LLMError
from aiplatform.domain.llm.messages import ChatMessage
from aiplatform.domain.llm.requests import CompletionRequest
from aiplatform.infrastructure.logging.context import correlation_id_scope

_DEFAULT_PROMPT = "Hello from the AI platform CLI probe."


async def _stream_prompt(container: Container, prompt: str) -> int:
    """Stream the prompt through the default provider, printing deltas."""
    provider = container.registry.get_default()
    request = CompletionRequest(messages=(ChatMessage.user(prompt),))
    try:
        with correlation_id_scope():
            async for chunk in provider.stream_chat(request):
                if chunk.delta:
                    sys.stdout.write(chunk.delta)
                    sys.stdout.flush()
        sys.stdout.write("\n")
        return 0
    except LLMError as exc:
        sys.stderr.write(f"\n[probe] {type(exc).__name__}: {exc}\n")
        return 1


async def _run(prompt: str) -> int:
    """Boot the container, stream the prompt, and always dispose on exit."""
    container = bootstrap()
    try:
        return await _stream_prompt(container, prompt)
    finally:
        await shutdown(container)


def main(argv: list[str] | None = None) -> int:
    """Entry point: stream the prompt given on the command line (or a default).

    Args:
        argv: Optional argument list (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code (0 on success, 1 on a provider error).
    """
    args = list(sys.argv[1:] if argv is None else argv)
    prompt = " ".join(args).strip() or _DEFAULT_PROMPT
    return asyncio.run(_run(prompt))


if __name__ == "__main__":
    raise SystemExit(main())
