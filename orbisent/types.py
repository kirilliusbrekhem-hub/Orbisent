"""Shared data types for Orbisent 1.0 (ARCHITECTURE_1.0.md §5).

Every type here is immutable:
    - dataclasses are frozen, so fields can't be reassigned;
    - sequences are stored as tuples;
    - mappings are stored as FrozenMap: a private copy that can't be changed.

Because of that, these types can be compared, hashed, copied, deep-copied,
pickled and passed to dataclasses.asdict().

Mapping values are limited to JSON-compatible scalars of exactly these types:
str, int, bool and None. Floats and subclasses (such as IntEnum) are rejected.
That keeps them safe to print, compare and, later, hash (§4.8.4).

Only the types used by the components implemented so far live here. The other
types listed in §5 are added together with the components that use them.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Optional, Tuple

# Exact types only: bool is listed separately because it is not "an int" for our purposes,
# and subclasses (str subclasses, IntEnum, ...) could change how values print or compare.
SCALAR_TYPES = (str, int, bool, type(None))


class FrozenMap(Mapping):
    """A small immutable mapping from strings to scalar values.

    It behaves like a read-only dict: m["key"], len(m), iteration in insertion
    order, and equality with any mapping that has the same items. Unlike a dict
    or a MappingProxyType, it is hashable, and it can be deep-copied and pickled.

        m = FrozenMap({"project_name": "bakery"})
        m["project_name"]         # "bakery"
        m["x"] = 1                # TypeError: no item assignment
    """

    __slots__ = ("_data", "_hash")

    def __init__(self, data=None, *, name="FrozenMap"):
        """Copy `data` after checking it. `name` is only used in error messages."""
        if data is None:
            data = {}
        if not isinstance(data, Mapping):
            raise TypeError(f"{name} must be a mapping, not {type(data).__name__}")
        copied = {}
        for key, value in data.items():
            if type(key) is not str:
                raise TypeError(f"{name} keys must be strings, not {type(key).__name__}")
            if type(value) not in SCALAR_TYPES:
                raise TypeError(f"{name}[{key!r}] must be str, int, bool or None, not {type(value).__name__}")
            copied[key] = value
        object.__setattr__(self, "_data", copied)
        object.__setattr__(self, "_hash", None)

    def __getitem__(self, key):
        return self._data[key]

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def __eq__(self, other):
        if not isinstance(other, Mapping):
            return NotImplemented
        return self._data == dict(other.items())

    def __hash__(self):
        # Order-independent, like equality. Computed once; safe because the data can't change.
        if self._hash is None:
            object.__setattr__(self, "_hash", hash(frozenset(self._data.items())))
        return self._hash

    def __setattr__(self, name, value):
        raise AttributeError("FrozenMap is immutable")

    def __delattr__(self, name):
        raise AttributeError("FrozenMap is immutable")

    def __reduce__(self):
        # Used by pickle, copy.copy and copy.deepcopy: rebuild from a plain dict of scalars.
        return (FrozenMap, (dict(self._data),))

    def __repr__(self):
        return f"FrozenMap({self._data!r})"


def frozen_strings(value, name):
    """Return `value` as a tuple of strings, after checking every item."""
    if isinstance(value, (str, bytes)):
        raise TypeError(f"{name} must be a sequence of strings, not a single {type(value).__name__}")
    items = tuple(value)
    for item in items:
        if type(item) is not str:
            raise TypeError(f"{name} must contain only strings, not {type(item).__name__}")
    return items


@dataclass(frozen=True)
class Request:
    """What the user asked for, exactly as it arrived (CLI -> Core)."""

    text: str                            # The goal as typed. Not cleaned here.
    explicit_task: Optional[str] = None  # The value of --task, if given.
    options: FrozenMap = field(default_factory=FrozenMap)  # Other CLI options, e.g. {"name": "bakery"}.

    def __post_init__(self):
        if type(self.text) is not str:
            raise TypeError(f"text must be a string, not {type(self.text).__name__}")
        if self.explicit_task is not None and type(self.explicit_task) is not str:
            raise TypeError(f"explicit_task must be a string or None, not {type(self.explicit_task).__name__}")
        # Frozen dataclasses block normal assignment; object.__setattr__ is the standard way to
        # normalise a field once, during construction.
        object.__setattr__(self, "options", FrozenMap(self.options, name="options"))


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
    parameters: FrozenMap = field(default_factory=FrozenMap)  # e.g. {"project_name": "bakery"}.
    ambiguities: Tuple[str, ...] = ()    # Why it couldn't decide; shown to the user.
    candidates: Tuple[str, ...] = ()     # Task types that matched, when more than one did.

    def __post_init__(self):
        if type(self.text) is not str:
            raise TypeError(f"text must be a string, not {type(self.text).__name__}")
        if self.task_type is not None and not (type(self.task_type) is str and self.task_type):
            raise TypeError("task_type must be a non-empty string or None")
        if not (type(self.source) is str and self.source):
            raise TypeError("source must be a non-empty string")
        if isinstance(self.confidence, bool) or not isinstance(self.confidence, (int, float)):
            raise TypeError("confidence must be a number")
        if not 0.0 <= self.confidence <= 1.0:  # Also rejects NaN.
            raise ValueError("confidence must be between 0.0 and 1.0")
        object.__setattr__(self, "confidence", float(self.confidence))
        object.__setattr__(self, "parameters", FrozenMap(self.parameters, name="parameters"))
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
