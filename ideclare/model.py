"""Dataclasses describing a parsed product. Filled in by parser.py, read by engine.py."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from .tables import Table  # noqa: F401  (re-exported: a Product holds its tables)


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
    # calculated field only: per-item steps that produce its value
    steps: list["RatingStep"] = field(default_factory=list)
    provided: str = ""  # name of the enrichment that supplies this field, if any
    default: object = None  # the typed value assumed when the input is not given; None means it must be given


@dataclass
class Product:
    name: str
    territory: str = ""
    currency: str = ""
    term: tuple = (("num", Decimal(12)), "months")  # (amount expression, days | months | years | until)
    inputs: dict[str, Input] = field(default_factory=dict)
    eligibility: list["Rule"] = field(default_factory=list)
    covers: list["Cover"] = field(default_factory=list)
    rating: list["RatingStep"] = field(default_factory=list)
    lifecycle: "Lifecycle" = field(default_factory=lambda: Lifecycle())
    claims: dict[str, "ClaimRule"] = field(default_factory=dict)
    claims_loading: list[tuple[int, Decimal, tuple | None]] = field(default_factory=list)  # (claims in term, multiplier, unless condition)
    claims_terms: list[tuple[int, "Lifecycle", tuple | None]] = field(default_factory=list)  # (paid claims in term, lifecycle in force from then, unless condition)
    scenarios: list["Scenario"] = field(default_factory=list)
    enrichments: list["Enrichment"] = field(default_factory=list)
    tables: dict[str, "Table"] = field(default_factory=dict)
    base: str = field(default=".", repr=False)  # directory that table files are read from
    deferred: list = field(default_factory=list, repr=False)  # parser work that needs the whole file first

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
    aggregate: bool = False  # per term: the insured bears this much across the term's claims, not on each
    minimum: tuple | None = None
    maximum: tuple | None = None
    rows: list["FactorRow"] = field(default_factory=list)  # a table instead of one amount; op is unused


@dataclass
class Cover:
    name: str
    optional: bool = False
    limit: tuple | None = None
    aggregate: bool = False  # the limit is for the whole term, eroded by each paid claim
    per: str = ""  # aggregate == True: one limit per value of this asked fact, or per this item (e.g. condition, traveller)
    reinstatement: Decimal | None = None  # an eroded aggregate may be restored once a term for this share of the premium, pro rata
    excess: Excess = field(default_factory=Excess)
    exclusions: list[Rule] = field(default_factory=list)
    available: tuple | None = None
    from_: tuple | None = None  # date expression: the cover starts here rather than at inception
    until: tuple | None = None  # date expression: the cover stops here rather than at expiry
    waiting_days: int = 0  # losses this soon after the policy first started are not covered
    item: str = ""  # singular item name when the cover's terms use an item's fields, so claims must name the item


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
    kind: str  # base | factor | add | discount | load | minimum | maximum | tax | fee | commission | round
    label: str = ""
    amount: tuple | None = None
    condition: tuple | None = None
    rows: list[FactorRow] = field(default_factory=list)
    steps: list["RatingStep"] = field(default_factory=list)  # kind == "each": label is the item name
    order: list[tuple[tuple, bool]] = field(default_factory=list)  # kind == "each": (key, descending)
    line: int = 0


@dataclass
class Cancellation:
    refund: str = "pro rata"  # pro rata | full | none | amount
    fee: Decimal = Decimal(0)
    amount: tuple | None = None  # refund == "amount": the share of the earning premium returned, an expression over days/months in force


@dataclass
class Lifecycle:
    cooling_off_days: int = 0
    cancellation: dict[str, Cancellation] = field(default_factory=dict)  # by customer | insurer
    adjustment_allowed: bool = True
    adjustment_fee: Decimal = Decimal(0)
    lapse_days: int | None = None
    renewable: bool = True
    renewal_invite_days: int = 0
    renewal_cap: Decimal | None = None
    renewal_collar: Decimal | None = None
    renewal_index: list[tuple] = field(default_factory=list)  # (input, "%" or "+", amount, at least, at most)
    renewal_decline: list[Rule] = field(default_factory=list)
    instalments: int = 0  # 0: paid in one; else the number of monthly instalments
    instalment_charge: Decimal = Decimal(0)  # credit charge as a fraction of the premium


@dataclass
class ClaimRule:
    cover: str
    requires: list[str] = field(default_factory=list)
    asks: dict[str, Input] = field(default_factory=dict)  # facts asked when the claim is made
    pays: list[str] = field(default_factory=lambda: ["limit"])  # clauses in the order written: limit | excess | co-payment
    pays_amount: tuple | None = None  # a fixed benefit instead of the amount claimed
    months: tuple | None = None  # a benefit paid per month for this many months: pays_amount is the monthly amount
    after: tuple | None = None  # (amount expression, "days" | "weeks" | "months"): the deferred period before the benefit starts
    co_payments: list["RatingStep"] = field(default_factory=list)  # amount is the percentage, condition optional
    decline: list[Rule] = field(default_factory=list)
    depreciation: list[FactorRow] = field(default_factory=list)
    counts: tuple = ("bool", True)  # condition under which a paid claim counts towards claims in term


@dataclass
class Enrichment:
    """An external lookup: keyed on inputs, providing fields the product can use."""
    name: str
    keys: list[str]
    item: str = ""  # singular item name when the lookup is per item
    provides: dict[str, Input] = field(default_factory=dict)
    unavailable: str = "default"  # default | refer | decline
    reason: str = ""
    defaults: dict = field(default_factory=dict)
    held: bool = False  # values fixed at inception for the whole term
    line: int = 0
