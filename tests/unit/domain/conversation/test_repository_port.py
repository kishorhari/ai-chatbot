"""Unit tests for the ConversationRepository port and its error taxonomy (M2.1)."""

from __future__ import annotations

import pytest

from aiplatform.domain.conversation.ids import ConversationId
from aiplatform.domain.conversation.ports import (
    ConversationAlreadyExistsError,
    ConversationNotFoundError,
    ConversationRepository,
    RepositoryError,
)


def test_repository_port_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        ConversationRepository()  # type: ignore[abstract]


def test_not_found_error_carries_identity() -> None:
    cid = ConversationId.generate()
    error = ConversationNotFoundError(cid)
    assert isinstance(error, RepositoryError)
    assert error.conversation_id == cid
    assert str(cid) in str(error)


def test_already_exists_error_carries_identity() -> None:
    cid = ConversationId.generate()
    error = ConversationAlreadyExistsError(cid)
    assert isinstance(error, RepositoryError)
    assert error.conversation_id == cid
    assert str(cid) in str(error)
