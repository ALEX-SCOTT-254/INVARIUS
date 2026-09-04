"""Core error types used throughout INVARIUS."""

from __future__ import annotations


class InvariusError(Exception):
    """Base exception for expected INVARIUS application errors."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "INVARIUS_ERROR",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class ConfigurationError(InvariusError):
    """Raised when application configuration is invalid."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            code="CONFIGURATION_ERROR",
        )


class ValidationError(InvariusError):
    """Raised when supplied data fails validation."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            code="VALIDATION_ERROR",
        )


class SecurityError(InvariusError):
    """Raised when a security boundary is violated."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            code="SECURITY_ERROR",
        )
