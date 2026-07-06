"""Unit tests for conversation identifiers (M2.0)."""

from __future__ import annotations

from uuid import UUID

import pytest

from aiplatform.domain.conversation.ids import ConversationId, MessageId


def test_generate_produces_distinct_random_ids() -> None:
    a = ConversationId.generate()
    b = ConversationId.generate()
    assert a != b
    assert isinstance(a.value, UUID)


def test_from_string_round_trips() -> None:
    original = MessageId.generate()
    parsed = MessageId.from_string(str(original))
    assert parsed == original


def test_from_string_rejects_invalid_uuid() -> None:
    with pytest.raises(ValueError):
        ConversationId.from_string("not-a-uuid")


def test_str_is_canonical_uuid() -> None:
    uuid = UUID("12345678-1234-5678-1234-567812345678")
    assert str(ConversationId(uuid)) == "12345678-1234-5678-1234-567812345678"


def test_ids_of_different_types_never_compare_equal() -> None:
    uuid = UUID("12345678-1234-5678-1234-567812345678")
    assert ConversationId(uuid) != MessageId(uuid)


def test_ids_are_immutable() -> None:
    identifier = ConversationId.generate()
    with pytest.raises(AttributeError):
        identifier.value = UUID("12345678-1234-5678-1234-567812345678")  # type: ignore[misc]


def test_ids_are_hashable_by_value() -> None:
    uuid = UUID("12345678-1234-5678-1234-567812345678")
    assert ConversationId(uuid) in {ConversationId(uuid)}
