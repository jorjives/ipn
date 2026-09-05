"""Dataclasses describing a parsed product. Filled in by parser.py, read by engine.py."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class Input:
    name: str
    kind: str  # money | integer | number | text | yes/no | choice | collection
    choices: list[str] = field(default_factory=list)
    # collection only
    singular: str = ""
    fields: dict[str, "Input"] = field(default_factory=dict)
    min_items: int = 0
    max_items: int | None = None


@dataclass
class Product:
    name: str
    territory: str = ""
    currency: str = ""
    term_months: int = 12
    inputs: dict[str, Input] = field(default_factory=dict)
    eligibility: list["Rule"] = field(default_factory=list)
    covers: list["Cover"] = field(default_factory=list)
    rating: list["RatingStep"] = field(default_factory=list)
    lifecycle: "Lifecycle" = field(default_factory=lambda: Lifecycle())
    claims: dict[str, "ClaimRule"] = field(default_factory=dict)
    claims_loading: list[tuple[int, Decimal]] = field(default_factory=list)  # (claims in term, multiplier)
    scenarios: list["Scenario"] = field(default_factory=list)

    def cover(self, name: str) -> "Cover | None":
        return next((c for c in self.covers if c.name == name), None)

    @property
    def collections(self) -> list["Input"]:
        return [i for i in self.inputs.values() if i.kind == "collection"]

    def collection_for(self, singular: str) -> "Input | None":
        return next((c for c in self.collections if c.singular == singular), None)


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


@dataclass
class FactorRow:
    condition: tuple | None  # None = otherwise
    op: str  # x | + | -
    amount: tuple


@dataclass
class RatingStep:
    kind: str  # base | factor | add | discount | load | minimum | maximum | tax | fee | round
    label: str = ""
    amount: tuple | None = None
    condition: tuple | None = None
    rows: list[FactorRow] = field(default_factory=list)
    steps: list["RatingStep"] = field(default_factory=list)  # kind == "each": label is the item name
    line: int = 0


@dataclass
class Cancellation:
    refund: str = "pro rata"  # pro rata | full | none
    fee: Decimal = Decimal(0)


@dataclass
class Lifecycle:
    cooling_off_days: int = 0
    cancellation: dict[str, Cancellation] = field(default_factory=dict)  # by customer | insurer
    adjustment_allowed: bool = True
    adjustment_fee: Decimal = Decimal(0)
    lapse_days: int | None = None
    renewal_invite_days: int = 0
    renewal_cap: Decimal | None = None
    renewal_collar: Decimal | None = None
    renewal_index: list[tuple[str, str, Decimal]] = field(default_factory=list)  # (input, "%" or "+", amount)
    renewal_decline: list[Rule] = field(default_factory=list)


@dataclass
class ClaimRule:
    cover: str
    requires: list[str] = field(default_factory=list)
    less_excess: bool = False
    decline: list[Rule] = field(default_factory=list)
    depreciation: list[FactorRow] = field(default_factory=list)
