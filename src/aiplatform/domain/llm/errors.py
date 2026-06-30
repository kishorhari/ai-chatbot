"""Provider-agnostic LLM error taxonomy.

Every adapter maps the failures of its transport/vendor onto this hierarchy so
that **no transport-native exception ever escapes the infrastructure layer**
(ADR-0002). Callers reason about failures through two stable signals:

* the **error type** — what kind of failure occurred, and
* the **``retryable`` flag** — whether retrying the same request could succeed.

The original exception is preserved on ``cause`` (and as ``__cause__``) for
diagnostics, typed only as :class:`BaseException` — the domain therefore keeps a
*reference* to the vendor exception without ever *importing* a vendor type, so
the hierarchy stays provider-agnostic.

This module is pure standard library: no pydantic, no I/O, no vendor imports.
"""

from __future__ import annotations

from typing import ClassVar


class LLMError(Exception):
    """Base class for all LLM failures surfaced by a provider.

    Concrete on purpose: adapters wrap any *unanticipated* exception in a plain
    ``LLMError`` so the "nothing transport-native escapes" guarantee holds even
    for failures no specific subtype anticipated. By default an error is treated
    as **non-retryable** — retrying is opt-in per failure mode, never assumed.

    Attributes:
        message: Human-readable, provider-agnostic description.
        retryable: Whether retrying the identical request might succeed.
        cause: The original underlying exception, if any.
    """

    #: Default retry disposition for this error class; subclasses override it.
    default_retryable: ClassVar[bool] = False

    def __init__(
        self,
        message: str,
        *,
        retryable: bool | None = None,
        cause: BaseException | None = None,
    ) -> None:
        """Initialise the error.

        Args:
            message: Provider-agnostic description of the failure.
            retryable: Override the class default retry disposition when given.
            cause: The original exception to preserve for diagnostics. Also set
                as ``__cause__`` so tracebacks chain even without ``raise ... from``.
        """
        super().__init__(message)
        self.message = message
        self.retryable: bool = self.default_retryable if retryable is None else retryable
        self.cause: BaseException | None = cause
        if cause is not None and self.__cause__ is None:
            self.__cause__ = cause

    def __repr__(self) -> str:
        """Return an unambiguous representation including the retry disposition."""
        return f"{type(self).__name__}(message={self.message!r}, retryable={self.retryable})"


class LLMTransportError(LLMError):
    """The provider could not be reached (connection refused, DNS, reset).

    Transient by nature, so retryable by default.
    """

    default_retryable: ClassVar[bool] = True


class LLMTimeoutError(LLMError):
    """The request exceeded its connect or total time budget.

    Retryable by default; a subsequent attempt may complete within budget.
    """

    default_retryable: ClassVar[bool] = True


class LLMProtocolError(LLMError):
    """The provider returned a malformed, truncated, or unexpected response.

    Not retryable by default: replaying the same request typically reproduces
    the same malformed reply.
    """

    default_retryable: ClassVar[bool] = False


class LLMAuthenticationError(LLMError):
    """Authentication failed or required credentials are missing/invalid.

    Not retryable: the request will keep failing until credentials are fixed.
    """

    default_retryable: ClassVar[bool] = False


class LLMRateLimitError(LLMError):
    """The provider throttled the request (quota or rate limit exceeded).

    Retryable by default, ideally after honouring ``retry_after`` when supplied.
    """

    default_retryable: ClassVar[bool] = True

    def __init__(
        self,
        message: str,
        *,
        retry_after: float | None = None,
        retryable: bool | None = None,
        cause: BaseException | None = None,
    ) -> None:
        """Initialise the rate-limit error.

        Args:
            message: Provider-agnostic description.
            retry_after: Suggested wait, in seconds, before retrying (if known).
            retryable: Override the class default retry disposition.
            cause: The original exception to preserve.
        """
        super().__init__(message, retryable=retryable, cause=cause)
        self.retry_after = retry_after


class LLMModelError(LLMError):
    """The requested model is unknown, unsupported, or rejected the request.

    Not retryable: the failure is intrinsic to the request, not transient.
    """

    default_retryable: ClassVar[bool] = False
