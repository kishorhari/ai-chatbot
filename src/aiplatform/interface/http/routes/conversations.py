"""Conversation endpoints — create, append (chat turn), and fetch history.

Deliberately **thin** (ADR-0010): each handler parses/validates transport input,
calls exactly **one** application-service method resolved from the composition
root, and maps the returned application DTO to a wire model. No orchestration, no
provider or repository access, no aggregate reach-through. Domain/application
errors are translated to HTTP status by exception handlers registered on the app,
so the handlers themselves stay free of error plumbing.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from aiplatform.application.conversation.chat_service import ChatResult, ChatService
from aiplatform.application.conversation.conversation_service import (
    ConversationService,
    ConversationView,
    MessageView,
)
from aiplatform.composition.container import Container
from aiplatform.domain.conversation.ids import ConversationId
from aiplatform.domain.llm.responses import TokenUsage

router = APIRouter(prefix="/conversations", tags=["conversations"])


# --- wire models ------------------------------------------------------------


class CreateConversationRequest(BaseModel):
    """Body for creating a conversation."""

    owner: str = Field(min_length=1)
    system_prompt: str | None = None


class SendMessageRequest(BaseModel):
    """Body for appending a user turn and generating a reply."""

    text: str = Field(min_length=1)
    model: str | None = None


class UsageResponse(BaseModel):
    """Token accounting on the wire."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class MessageResponse(BaseModel):
    """A single message on the wire."""

    id: str
    role: str
    content: str
    sequence: int
    created_at: datetime
    usage: UsageResponse | None


class ConversationResponse(BaseModel):
    """A conversation and its ordered history on the wire."""

    id: str
    owner: str
    created_at: datetime
    messages: list[MessageResponse]


class ChatResponse(BaseModel):
    """The result of one chat turn on the wire."""

    conversation_id: str
    message_id: str
    content: str
    model: str
    usage: UsageResponse
    finish_reason: str | None
    created_at: datetime


# --- endpoints --------------------------------------------------------------


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_conversation(
    body: CreateConversationRequest, request: Request
) -> ConversationResponse:
    """Create a new conversation, optionally seeded with a system prompt."""
    view = await _conversation_service(request).start_conversation(
        owner=body.owner, system_prompt=body.system_prompt
    )
    return _conversation_response(view)


@router.get("/{conversation_id}")
async def get_conversation(conversation_id: str, request: Request) -> ConversationResponse:
    """Fetch a conversation and its full message history."""
    view = await _conversation_service(request).get_conversation(
        _parse_conversation_id(conversation_id)
    )
    return _conversation_response(view)


@router.post("/{conversation_id}/messages", status_code=status.HTTP_201_CREATED)
async def send_message(
    conversation_id: str, body: SendMessageRequest, request: Request
) -> ChatResponse:
    """Append a user message, generate a reply, and persist the turn atomically."""
    result = await _chat_service(request).send_message(
        _parse_conversation_id(conversation_id), body.text, model=body.model
    )
    return _chat_response(result)


# --- composition-resolved services -----------------------------------------


def _chat_service(request: Request) -> ChatService:
    """Resolve the wired ChatService from the composition root."""
    return _require_container(request).chat_service


def _conversation_service(request: Request) -> ConversationService:
    """Resolve the wired ConversationService from the composition root."""
    return _require_container(request).conversation_service


def _require_container(request: Request) -> Container:
    """Return the wired container, or 503 before composition completes."""
    container = getattr(request.app.state, "container", None)
    if container is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="service not ready"
        )
    return container


# --- transport helpers ------------------------------------------------------


def _parse_conversation_id(raw: str) -> ConversationId:
    """Parse a conversation id from a path segment, 400 on a malformed value."""
    try:
        return ConversationId.from_string(raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid conversation id"
        ) from exc


def _usage_response(usage: TokenUsage | None) -> UsageResponse | None:
    """Map token usage to its wire form."""
    if usage is None:
        return None
    return UsageResponse(
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
    )


def _message_response(message: MessageView) -> MessageResponse:
    """Map a message view to its wire form."""
    return MessageResponse(
        id=str(message.id),
        role=message.role.value,
        content=message.content,
        sequence=message.sequence,
        created_at=message.created_at,
        usage=_usage_response(message.usage),
    )


def _conversation_response(view: ConversationView) -> ConversationResponse:
    """Map a conversation view to its wire form."""
    return ConversationResponse(
        id=str(view.id),
        owner=view.owner,
        created_at=view.created_at,
        messages=[_message_response(m) for m in view.messages],
    )


def _chat_response(result: ChatResult) -> ChatResponse:
    """Map a chat result to its wire form."""
    return ChatResponse(
        conversation_id=str(result.conversation_id),
        message_id=str(result.message_id),
        content=result.content,
        model=result.model,
        usage=UsageResponse(
            prompt_tokens=result.usage.prompt_tokens,
            completion_tokens=result.usage.completion_tokens,
            total_tokens=result.usage.total_tokens,
        ),
        finish_reason=result.finish_reason.value if result.finish_reason else None,
        created_at=result.created_at,
    )
