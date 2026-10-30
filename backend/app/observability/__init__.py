"""Observability foundations for INVARIUS."""

from backend.app.observability.diagnostics import (
    DiagnosticEvent,
    DiagnosticSeverity,
    emit_diagnostic_event,
)

__all__ = [
    "DiagnosticEvent",
    "DiagnosticSeverity",
    "emit_diagnostic_event",
]
