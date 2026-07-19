"""Deterministic policy guards shared by Lead and Verification."""

from __future__ import annotations

_UNSUPPORTED_CAUSAL_PHRASES = (
    "attributable to",
    "because of",
    "cause of",
    "caused",
    "causes",
    "causing",
    "driven by",
    "driven primarily by",
    "due to",
    "explains the",
    "implies",
    "implying",
    "indicating",
    "led to",
    "responsible for",
    "resulted in",
    "results in",
    "suggesting",
    "suggests",
)


def unsupported_causal_phrases(statement: str) -> tuple[str, ...]:
    """Return unsupported causal markers present in one diagnostic claim."""

    normalized = " ".join(statement.casefold().split())
    return tuple(
        phrase for phrase in _UNSUPPORTED_CAUSAL_PHRASES if phrase in normalized
    )
