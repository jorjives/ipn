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
