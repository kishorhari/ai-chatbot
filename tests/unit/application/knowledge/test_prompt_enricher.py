"""Unit tests for the pure PromptEnricher (M3.5)."""

from __future__ import annotations

from datetime import UTC, datetime

from aiplatform.application.conversation.token_estimator import HeuristicTokenEstimator
from aiplatform.application.knowledge.prompt_enricher import _PREAMBLE, PromptEnricher
from aiplatform.domain.conversation.ids import MessageId
from aiplatform.domain.conversation.message import Message
from aiplatform.domain.knowledge.ids import KnowledgeChunkId, KnowledgeDocumentId
from aiplatform.domain.knowledge.metadata import Metadata
from aiplatform.domain.knowledge.retrieval import RetrievedChunk, RetrievedContext
from aiplatform.domain.llm.messages import Role

_TS = datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC)


def _message(role: Role, content: str, sequence: int) -> Message:
    return Message(
        id=MessageId.generate(), role=role, content=content, sequence=sequence, created_at=_TS
    )


def _context(*texts: str) -> RetrievedContext:
    chunks = [
        RetrievedChunk(
            chunk_id=KnowledgeChunkId.generate(),
            document_id=KnowledgeDocumentId.generate(),
            text=text,
            metadata=Metadata(),
            score=1.0 - index * 0.1,
        )
        for index, text in enumerate(texts)
    ]
    return RetrievedContext.ordered("q", chunks)


def _enricher(*, budget: int = 1024) -> PromptEnricher:
    return PromptEnricher(HeuristicTokenEstimator(), context_token_budget=budget)


def _system_messages(messages: tuple[Message, ...]) -> list[Message]:
    return [m for m in messages if m.role is Role.SYSTEM]


async def test_empty_context_returns_messages_unchanged() -> None:
    messages = (_message(Role.SYSTEM, "Base.", 0), _message(Role.USER, "Hi", 1))
    result = _enricher().enrich(messages, RetrievedContext.empty("q"))
    assert result == messages


def test_context_merges_into_existing_system_message() -> None:
    messages = (
        _message(Role.SYSTEM, "You are helpful.", 0),
        _message(Role.USER, "Where is Paris?", 1),
    )
    result = _enricher().enrich(messages, _context("Paris is the capital of France."))
    systems = _system_messages(result)
    assert len(systems) == 1  # single leading system message preserved
    assert result[0].role is Role.SYSTEM
    assert "You are helpful." in result[0].content
    assert "Paris is the capital of France." in result[0].content
    # The merged message keeps the original system message's identity.
    assert result[0].id == messages[0].id
    # User message is unchanged and still present.
    assert result[1] == messages[1]


def test_context_prepends_synthetic_system_when_none_exists() -> None:
    messages = (_message(Role.USER, "Where is Paris?", 0),)
    result = _enricher().enrich(messages, _context("Paris is in France."))
    assert len(result) == 2
    assert result[0].role is Role.SYSTEM
    assert "Paris is in France." in result[0].content
    assert result[1] == messages[0]
    assert len(_system_messages(result)) == 1


def test_zero_budget_injects_nothing() -> None:
    messages = (_message(Role.SYSTEM, "Base.", 0),)
    result = _enricher(budget=0).enrich(messages, _context("some retrieved text"))
    assert result == messages


def test_max_context_tokens_caps_injection() -> None:
    # A large history nearly fills a tiny window, leaving no room for context.
    big = "word " * 200
    messages = (_message(Role.USER, big, 0),)
    result = _enricher(budget=1024).enrich(
        messages, _context("extra context that will not fit"), max_context_tokens=10
    )
    assert result == messages  # nothing injected — the window is already full


def test_highest_scoring_passage_is_preferred_within_a_tight_budget() -> None:
    estimator = HeuristicTokenEstimator()
    # Budget fits the preamble plus exactly one passage.
    budget = estimator.estimate(_PREAMBLE) + estimator.estimate("alpha")
    messages = (_message(Role.SYSTEM, "Base.", 0),)
    result = _enricher(budget=budget).enrich(messages, _context("alpha", "beta", "gamma"))
    system = result[0].content
    assert "alpha" in system  # the top-scored passage is included
    assert "gamma" not in system  # the lowest-scored one did not fit
