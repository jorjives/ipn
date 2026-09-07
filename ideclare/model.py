"""Dataclasses describing a parsed product. Filled in by parser.py, read by engine.py."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from .tables import Table  # noqa: F401  (re-exported: a Product holds its tables)


# The currency each territory quotes in: a fact, not a product setting. A product sold
# somewhere not listed, or priced in another currency, says so with a `currency` line.
EURO = "AT BE BG CY DE EE ES FI FR GR HR IE IT LT LU LV MC MT NL PT SI SK".split()
CURRENCY = {**dict.fromkeys(EURO, "EUR"), "UK": "GBP", "GB": "GBP", "CH": "CHF", "LI": "CHF", "DK": "DKK", "NO": "NOK",
            "SE": "SEK", "IS": "ISK", "PL": "PLN", "CZ": "CZK", "HU": "HUF", "RO": "RON", "US": "USD", "CA": "CAD",
            "AU": "AUD", "NZ": "NZD", "JP": "JPY", "KW": "KWD", "BH": "BHD"}
MINOR_DIGITS = {"JPY": 0, "ISK": 0, "KWD": 3, "BHD": 3}  # ISO 4217 exponent where it is not 2


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
    line: int = 0


@dataclass
class Product:
    name: str
    published: date | None = None  # when this version went on sale; None is a lone product, live on every date
    territories: list[str] = field(default_factory=list)  # where it is sold; more than one makes `territory` a choice at quote
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
    upgrading: list["Upgrade"] = field(default_factory=list)  # how the previous version's answers become this version's
    tables: dict[str, "Table"] = field(default_factory=dict)
    allocation: list[tuple[str, Decimal]] = field(default_factory=list)  # (cover, proportion): how the unattributed premium is shared
    base: str = field(default=".", repr=False)  # directory that table files are read from
    deferred: list = field(default_factory=list, repr=False)  # parser work that needs the whole file first
    parsing: bool = field(default=True, repr=False)  # False once the file is read: a wording built later runs its own deferred work

    @property
    def attributed(self) -> bool:
        """Whether the premium is split by cover: a cover has a class, a step is for a cover, or the pool is allocated."""
        return bool(self.allocation) or any(c.class_ for c in self.covers) or any(s.cover for step in self.rating for s in [step] + step.steps)

    def currency_for(self, territory: str) -> str:
        return self.currency or CURRENCY.get(territory, "")

    def quantum_for(self, territory: str) -> Decimal:
        """The smallest unit of the currency the risk is quoted in: 0.01 for GBP, 1 for JPY."""
        return Decimal(1).scaleb(-MINOR_DIGITS.get(self.currency_for(territory), 2))

    def cover(self, name: str, on: date | None = None) -> "Cover | None":
        """The cover, as worded on that date; without a date, the undated wording."""
        c = next((c for c in self.covers if c.name == name), None)
        return c.as_of(on) if c is not None else None

    def claim(self, name: str, on: date | None = None) -> "ClaimRule | None":
        """The claim rule for a cover, as worded on that date."""
        r = self.claims.get(name)
        return r.as_of(on) if r is not None else None

    @property
    def collections(self) -> list["Input"]:
        return [i for i in self.inputs.values() if i.kind == "collection"]

    def collection_for(self, singular: str) -> "Input | None":
        return next((c for c in self.collections if c.singular == singular), None)


@dataclass
class Dated:
    """One line of a cover or claim block with the dates it is in effect: `from DATE`, `until DATE`, or neither."""
    line: object  # the parser's Line, with the dates stripped off
    key: str | None  # the setting a one-valued line sets (limit, excess, pays ...); None for a line that adds to a list
    from_: date | None = None
    until: date | None = None

    @property
    def dated(self) -> bool:
        return self.from_ is not None or self.until is not None

    def in_effect(self, on: date) -> bool:
        return (self.from_ is None or on >= self.from_) and (self.until is None or on < self.until)


def in_effect(lines: list[Dated], on: date) -> list[Dated]:
    """The lines in force on a date: every dated line whose window holds it, and the undated lines
    whose setting none of those replaces. A later line replaces an earlier one for the same setting."""
    dated = [d for d in lines if d.dated and d.in_effect(on)]
    replaced = {d.key for d in dated if d.key is not None}
    return [d for d in lines if not d.dated and d.key not in replaced] + dated


class Wording:
    """Mixin for a block whose lines may be dated: rebuilds itself as of a date, once per window."""
    lines: list  # of Dated
    build: object  # (list[Dated]) -> a fresh instance, set by the parser

    def as_of(self, on: date | None):
        if on is None or not any(d.dated for d in self.lines):
            return self
        boundaries = sorted({d for l in self.lines for d in (l.from_, l.until) if d is not None})
        window = sum(on >= b for b in boundaries)
        cache = self.__dict__.setdefault("_windows", {})
        if window not in cache:
            cache[window] = self.build(in_effect(self.lines, on))
        return cache[window]


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
class Cover(Wording):
    name: str
    optional: bool = False
    lines: list = field(default_factory=list, repr=False, compare=False)  # every line of the block, with its dates
    build: object = field(default=None, repr=False, compare=False)
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
    class_: str = ""  # the regulatory class the cover reports under; a word the engine does not interpret


@dataclass
class Step:
    line: int
    tokens: list[str]


@dataclass
class Scenario:
    name: str
    line: int
    given: dict = field(default_factory=dict)
    given_lines: list = field(default_factory=list)  # `given` lines left for the run to resolve, against the version bound under
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
    cover: str = ""  # `for Cover`: the step credits or scales that cover's share only
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
    cooling_off: tuple = ("num", Decimal(0))  # days, an expression evaluated against the risk
    cancellation: dict[str, Cancellation] = field(default_factory=dict)  # by customer | insurer
    adjustment_allowed: bool = True
    adjustment_upgrades: bool = False  # `reprice on the current version`: move to the version live that day before repricing
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
class ClaimRule(Wording):
    cover: str
    lines: list = field(default_factory=list, repr=False, compare=False)
    build: object = field(default=None, repr=False, compare=False)
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
class Upgrade:
    """How one input of this version is derived from the previous version's answers."""
    target: str
    rows: list[tuple] = field(default_factory=list)  # (condition or None for otherwise, value expression or ("ask",))
    item: str = ""  # `for each <old item>`: the target is a collection and fields holds the per-field upgrades
    fields: list["Upgrade"] = field(default_factory=list)
    line: int = 0


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
