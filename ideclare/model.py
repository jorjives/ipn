"""Dataclasses describing a parsed product. Filled in by parser.py, read by engine.py."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class Input:
    name: str
    kind: str  # money | integer | number | text | yes/no | choice
    choices: list[str] = field(default_factory=list)


@dataclass
class Product:
    name: str
    territory: str = ""
    currency: str = ""
    term_months: int = 12
    inputs: dict[str, Input] = field(default_factory=dict)
    eligibility: list["Rule"] = field(default_factory=list)
    covers: list["Cover"] = field(default_factory=list)
    scenarios: list["Scenario"] = field(default_factory=list)

    def cover(self, name: str) -> "Cover | None":
        return next((c for c in self.covers if c.name == name), None)


@dataclass
class Rule:
    kind: str  # decline | refer | excludes
    condition: tuple
    reason: str
    line: int = 0


@dataclass
class Excess:
    amount: tuple | None = None
    minimum: tuple | None = None


@dataclass
class Cover:
    name: str
    optional: bool = False
    limit: tuple | None = None
    excess: Excess = field(default_factory=Excess)
    exclusions: list[Rule] = field(default_factory=list)
    available: tuple | None = None


@dataclass
class Step:
    line: int
    tokens: list[str]


@dataclass
class Scenario:
    name: str
    line: int
    given: dict = field(default_factory=dict)
    selected: set[str] = field(default_factory=set)
    steps: list[Step] = field(default_factory=list)
