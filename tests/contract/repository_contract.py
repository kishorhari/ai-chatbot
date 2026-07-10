"""The shared ConversationRepository contract suite (ADR-0008).

A single behavioural specification that **every** ``ConversationRepository``
implementation must satisfy. Backends opt in by subclassing
:class:`ConversationRepositoryContract` and overriding the ``repository`` fixture;
the inherited tests then run against that implementation. The in-memory repository
(M2.1) and the PostgreSQL repository (M2.5) passing this identical suite is the
executable proof that the persistence swap is real — mirroring the provider
contract suite (ADR-0004).

This module is intentionally **not** named ``test_*`` so pytest does not collect
the base class directly — only the ``Test*`` subclasses are collected.

Timestamps are fixed and timezone-aware for determinism; the domain rejects naive
times (ADR-0007), and the repository must preserve them faithfully.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from aiplatform.domain.conversation.conversation import Conversation
from aiplatform.domain.conversation.ids import ConversationId
from aiplatform.domain.conversation.ports import (
    ConversationAlreadyExistsError,
    ConversationNotFoundError,
    ConversationRepository,
)
from aiplatform.domain.llm.messages import Role
from aiplatform.domain.llm.responses import TokenUsage


def _ts(minute: int = 0) -> datetime:
    """A fixed, timezone-aware timestamp offset by ``minute`` minutes."""
    return datetime(2026, 7, 10, 12, minute, 0, tzinfo=UTC)


class ConversationRepositoryContract:
    """Behavioural invariants every ``ConversationRepository`` must satisfy."""

    @pytest.fixture
    def repository(self) -> ConversationRepository:
        """The repository under test. Subclasses MUST override this."""
        raise NotImplementedError("contract subclasses must provide a `repository` fixture")

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _conversation(owner: str = "alice", *, with_messages: bool = True) -> Conversation:
        """Build a conversation, optionally seeded with a system/user/assistant turn."""
        convo = Conversation.start(owner=owner, created_at=_ts(0))
        if with_messages:
            convo.append_system("You are a helpful assistant.", created_at=_ts(1))
            convo.append_user("Hello there", created_at=_ts(2))
            convo.append_assistant(
                "Hi! How can I help?",
                created_at=_ts(3),
                usage=TokenUsage(prompt_tokens=5, completion_tokens=4),
            )
        return convo

    # -- round-trip fidelity -------------------------------------------------

    async def test_add_then_get_round_trips_faithfully(
        self, repository: ConversationRepository
    ) -> None:
        original = self._conversation(owner="alice")
        await repository.add(original)

        loaded = await repository.get(original.id)

        assert loaded.id == original.id
        assert loaded.owner == "alice"
        assert loaded.created_at == original.created_at
        assert loaded.message_count == original.message_count
        for saved, got in zip(original.messages, loaded.messages, strict=True):
            assert got.id == saved.id
            assert got.role == saved.role
            assert got.content == saved.content
            assert got.sequence == saved.sequence
            assert got.created_at == saved.created_at
            assert got.usage == saved.usage

    async def test_empty_conversation_round_trips(self, repository: ConversationRepository) -> None:
        original = self._conversation(with_messages=False)
        await repository.add(original)
        loaded = await repository.get(original.id)
        assert loaded.id == original.id
        assert loaded.message_count == 0

    async def test_sequence_order_is_preserved(self, repository: ConversationRepository) -> None:
        convo = Conversation.start(owner="alice", created_at=_ts(0))
        for i in range(6):
            convo.append_user(f"message {i}", created_at=_ts(i + 1))
        await repository.add(convo)

        loaded = await repository.get(convo.id)
        sequences = [m.sequence for m in loaded.messages]
        contents = [m.content for m in loaded.messages]
        assert sequences == [0, 1, 2, 3, 4, 5]
        assert contents == [f"message {i}" for i in range(6)]

    # -- not-found / already-exists -----------------------------------------

    async def test_get_unknown_raises_not_found(self, repository: ConversationRepository) -> None:
        with pytest.raises(ConversationNotFoundError):
            await repository.get(ConversationId.generate())

    async def test_add_duplicate_raises_already_exists(
        self, repository: ConversationRepository
    ) -> None:
        convo = self._conversation()
        await repository.add(convo)
        with pytest.raises(ConversationAlreadyExistsError):
            await repository.add(convo)

    async def test_save_unknown_raises_not_found(self, repository: ConversationRepository) -> None:
        with pytest.raises(ConversationNotFoundError):
            await repository.save(self._conversation())

    # -- save / append -------------------------------------------------------

    async def test_save_persists_appended_messages(
        self, repository: ConversationRepository
    ) -> None:
        convo = self._conversation()
        await repository.add(convo)

        loaded = await repository.get(convo.id)
        loaded.append_user("A follow-up question", created_at=_ts(4))
        loaded.append_assistant("An answer", created_at=_ts(5))
        await repository.save(loaded)

        reloaded = await repository.get(convo.id)
        assert reloaded.message_count == 5
        assert reloaded.messages[-1].content == "An answer"
        assert [m.sequence for m in reloaded.messages] == [0, 1, 2, 3, 4]

    # -- snapshot independence (part of the contract) ------------------------

    async def test_mutation_after_add_is_not_persisted(
        self, repository: ConversationRepository
    ) -> None:
        convo = self._conversation()
        await repository.add(convo)
        # Mutate the same instance AFTER adding, without saving.
        convo.append_user("Should not be stored", created_at=_ts(9))

        loaded = await repository.get(convo.id)
        assert loaded.message_count == 3  # the post-add append did not leak

    async def test_unsaved_mutation_of_loaded_copy_is_not_persisted(
        self, repository: ConversationRepository
    ) -> None:
        convo = self._conversation(owner="bob")
        await repository.add(convo)

        first = await repository.get(convo.id)
        first.append_user("Unsaved", created_at=_ts(9))  # mutate, do NOT save

        second = await repository.get(convo.id)
        assert second.message_count == 3  # loaded copy's mutation not stored

    async def test_get_returns_independent_instances(
        self, repository: ConversationRepository
    ) -> None:
        convo = self._conversation()
        await repository.add(convo)

        a = await repository.get(convo.id)
        b = await repository.get(convo.id)
        assert a is not b  # distinct objects
        a.append_user("only in a", created_at=_ts(9))
        assert b.message_count == 3  # mutating one loaded copy does not affect another

    # -- isolation between conversations ------------------------------------

    async def test_conversations_are_isolated(self, repository: ConversationRepository) -> None:
        alice = self._conversation(owner="alice")
        bob = Conversation.start(owner="bob", created_at=_ts(0))
        bob.append_user("bob's only message", created_at=_ts(1))
        await repository.add(alice)
        await repository.add(bob)

        loaded_alice = await repository.get(alice.id)
        loaded_bob = await repository.get(bob.id)
        assert loaded_alice.owner == "alice"
        assert loaded_alice.message_count == 3
        assert loaded_bob.owner == "bob"
        assert loaded_bob.message_count == 1
        assert loaded_bob.messages[0].role is Role.USER
