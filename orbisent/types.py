"""Shared data types for Orbisent 1.0 (ARCHITECTURE_1.0.md §5).

Every type here is immutable:
    - dataclasses are frozen, so fields can't be reassigned;
    - sequences are stored as tuples;
    - mappings are stored as read-only views of a private copy, so changing the
      dict you passed in has no effect.

Mapping values are limited to JSON-compatible scalars (str, int, bool, None).
That keeps them safe to print, compare and, later, hash (§4.8.4).

Only the types used by the components implemented so far live here. The other
types listed in §5 are added together with the components that use them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping, Optional, Tuple

SCALAR_TYPES = (str, int, bool, type(None))  # bool is a subclass of int; floats are deliberately excluded.


def frozen_mapping(value, name):
    """Return a read-only copy of `value`, after checking keys and values."""
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping, not {type(value).__name__}")
    for key, item in value.items():
        if not isinstance(key, str):
            raise TypeError(f"{name} keys must be strings, not {type(key).__name__}")
        if not isinstance(item, SCALAR_TYPES) or isinstance(item, float):
            raise TypeError(f"{name}[{key!r}] must be str, int, bool or None, not {type(item).__name__}")
    return MappingProxyType(dict(value))


def frozen_strings(value, name):
    """Return `value` as a tuple of strings, after checking every item."""
    if isinstance(value, str):
        raise TypeError(f"{name} must be a sequence of strings, not a single string")
    items = tuple(value)
    for item in items:
        if not isinstance(item, str):
            raise TypeError(f"{name} must contain only strings, not {type(item).__name__}")
    return items


@dataclass(frozen=True)
class Request:
    """What the user asked for, exactly as it arrived (CLI -> Core)."""

    text: str                            # The goal as typed. Not cleaned here.
    explicit_task: Optional[str] = None  # The value of --task, if given.
    options: Mapping[str, object] = field(default_factory=dict)  # Other CLI options, e.g. {"name": "bakery"}.

    def __post_init__(self):
        if not isinstance(self.text, str):
            raise TypeError(f"text must be a string, not {type(self.text).__name__}")
        if self.explicit_task is not None and not isinstance(self.explicit_task, str):
            raise TypeError(f"explicit_task must be a string or None, not {type(self.explicit_task).__name__}")
        # Frozen dataclasses block normal assignment; object.__setattr__ is the standard way to
        # normalise a field once, during construction.
        object.__setattr__(self, "options", frozen_mapping(self.options, "options"))


@dataclass(frozen=True)
class GoalSpec:
    """A goal turned into structure, or a clear statement that it couldn't be (ARCHITECTURE_1.0.md §4.3).

    A GoalSpec is either *decided* (task_type is set) or *unclear* (task_type is None,
    with at least one reason in `ambiguities`). Use GoalSpec.decided() or
    GoalSpec.unclear() to build one.
    """

    text: str                            # Cleaned goal text.
    task_type: Optional[str]             # e.g. "prepare_project"; None means "needs clarification".
    source: str                          # "explicit" | "rules" | "chain"; later "model:<provider>".
    confidence: float = 0.0              # 1.0 for an exact rule or explicit match; 0.0 when unclear.
    parameters: Mapping[str, object] = field(default_factory=dict)  # e.g. {"project_name": "bakery"}.
    ambiguities: Tuple[str, ...] = ()    # Why it couldn't decide; shown to the user.
    candidates: Tuple[str, ...] = ()     # Task types that matched, when more than one did.

    def __post_init__(self):
        if not isinstance(self.text, str):
            raise TypeError(f"text must be a string, not {type(self.text).__name__}")
        if self.task_type is not None and not (isinstance(self.task_type, str) and self.task_type):
            raise TypeError("task_type must be a non-empty string or None")
        if not (isinstance(self.source, str) and self.source):
            raise TypeError("source must be a non-empty string")
        if isinstance(self.confidence, bool) or not isinstance(self.confidence, (int, float)):
            raise TypeError("confidence must be a number")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        object.__setattr__(self, "confidence", float(self.confidence))
        object.__setattr__(self, "parameters", frozen_mapping(self.parameters, "parameters"))
        object.__setattr__(self, "ambiguities", frozen_strings(self.ambiguities, "ambiguities"))
        object.__setattr__(self, "candidates", frozen_strings(self.candidates, "candidates"))

        # The two shapes a GoalSpec may have. Anything in between is a bug.
        if self.task_type is None:
            if not self.ambiguities:
                raise ValueError("an unclear GoalSpec must explain why (ambiguities is empty)")
            if self.confidence != 0.0:
                raise ValueError("an unclear GoalSpec must have confidence 0.0")
        else:
            if self.ambiguities or self.candidates:
                raise ValueError("a decided GoalSpec can't have ambiguities or candidates")
            if self.confidence == 0.0:
                raise ValueError("a decided GoalSpec must have confidence above 0.0")

    @property
    def needs_clarification(self):
        return self.task_type is None

    @classmethod
    def decided(cls, text, task_type, source, confidence=1.0, parameters=None):
        return cls(text=text, task_type=task_type, source=source, confidence=confidence,
                   parameters=parameters or {})

    @classmethod
    def unclear(cls, text, source, reasons, candidates=()):
        return cls(text=text, task_type=None, source=source, confidence=0.0,
                   ambiguities=tuple(reasons), candidates=tuple(candidates))
