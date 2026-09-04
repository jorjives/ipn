"""Applies a Product to a risk: eligibility, covers, rating, lifecycle and claims."""
from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from .expr import evaluate
from .model import Cover, Product


def context(inputs: dict, selected: set[str], **extra) -> dict:
    return {**inputs, "selected": selected, **extra}


@dataclass
class Eligibility:
    outcome: str  # eligible | referred | declined
    reasons: list[str] = field(default_factory=list)


def check_eligibility(product: Product, inputs: dict) -> Eligibility:
    ctx = context(inputs, set())
    fired = [r for r in product.eligibility if evaluate(r.condition, ctx)]
    if any(r.kind == "decline" for r in fired):
        return Eligibility("declined", [r.reason for r in fired])
    if fired:
        return Eligibility("referred", [r.reason for r in fired])
    return Eligibility("eligible")


@dataclass
class CoverState:
    name: str
    status: str  # included | excluded | not selected | not available
    reason: str = ""
    limit: Decimal | None = None


def cover_state(cover: Cover, inputs: dict, selected: set[str]) -> CoverState:
    ctx = context(inputs, selected)
    if cover.optional and cover.name not in selected:
        return CoverState(cover.name, "not selected")
    if cover.available is not None and not evaluate(cover.available, ctx):
        return CoverState(cover.name, "not available")
    for rule in cover.exclusions:
        if evaluate(rule.condition, ctx):
            return CoverState(cover.name, "excluded", rule.reason)
    limit = evaluate(cover.limit, ctx) if cover.limit is not None else None
    return CoverState(cover.name, "included", limit=limit)


def cover_states(product: Product, inputs: dict, selected: set[str]) -> list[CoverState]:
    return [cover_state(c, inputs, selected) for c in product.covers]


# --- rating -----------------------------------------------------------------

ROUNDING = ROUND_HALF_UP


@dataclass
class Trail:
    label: str
    applied: str
    net: Decimal


@dataclass
class Quote:
    net: Decimal
    lines: list[tuple[str, Decimal]]  # taxes and fees, in order
    total: Decimal
    earning: Decimal  # net plus taxes: the part that earns over the term and is refundable pro rata
    trail: list[Trail] = field(default_factory=list)


def rate(product: Product, inputs: dict, selected: set[str]) -> Quote:
    ctx = context(inputs, selected)
    net, lines, trail = Decimal(0), [], []
    quantum = Decimal("0.01")

    def value(node):
        return Decimal(evaluate(node, ctx))

    for step in product.rating:
        if step.condition is not None and not evaluate(step.condition, ctx):
            continue
        if step.kind == "base":
            net = value(step.amount)
            trail.append(Trail("base", f"{net:.2f}", net))
        elif step.kind == "factor":
            row = next((r for r in step.rows if r.condition is None or evaluate(r.condition, ctx)), None)
            if row is None:
                continue
            amount = value(row.amount)
            net = net * amount if row.op == "x" else net + amount if row.op == "+" else net - amount
            trail.append(Trail(step.label, f"{row.op} {amount}", net))
        elif step.kind == "add":
            amount = value(step.amount)
            net += amount
            trail.append(Trail(step.label or "add", f"+ {amount}", net))
        elif step.kind in ("discount", "load"):
            pct = value(step.amount)
            mult = (1 - pct) if step.kind == "discount" else (1 + pct)
            net *= mult
            trail.append(Trail(step.label or step.kind, f"x {mult}", net))
        elif step.kind == "minimum":
            floor = value(step.amount)
            net = max(net, floor)
            trail.append(Trail(step.label or "minimum", str(floor), net))
        elif step.kind in ("tax", "fee"):
            lines.append((step.kind, step.label, value(step.amount)))
        elif step.kind == "round":
            quantum = value(step.amount)

    net = net.quantize(quantum, ROUNDING)  # tax is charged on the rounded net, as on an invoice
    lines = [(kind, label, (net * amount if kind == "tax" else amount).quantize(quantum, ROUNDING)) for kind, label, amount in lines]
    taxes = sum((a for kind, _, a in lines if kind == "tax"), Decimal(0))
    fees = sum((a for kind, _, a in lines if kind == "fee"), Decimal(0))
    return Quote(net, [(label, a) for _, label, a in lines], net + taxes + fees, net + taxes, trail)


# --- lifecycle --------------------------------------------------------------

def add_months(d: date, months: int) -> date:
    month = d.month - 1 + months
    year, month = d.year + month // 12, month % 12 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def pence(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), ROUNDING)


@dataclass
class RenewalOffer:
    invite_date: date
    premium: Decimal
    uncapped: Decimal
    declined: str | None = None


@dataclass
class ClaimResult:
    status: str  # paid | declined
    amount: Decimal = Decimal(0)
    reason: str = ""


class Policy:
    """One policy's history: bind, pay, cancel, adjust, claim, renew. Status is derived per date."""

    def __init__(self, product: Product, inputs: dict, selected: set[str]):
        self.product, self.inputs, self.selected = product, dict(inputs), set(selected)
        self.inception: date | None = None
        self.paid_on: date | None = None
        self.cancelled_on: date | None = None
        self.expiring_premium = Decimal(0)  # the annual total the customer is currently on
        self.claims: list = []
        self.previous_terms: list[tuple[date, date]] = []

    # -- derived ------------------------------------------------------------

    @property
    def quote(self) -> Quote:
        return rate(self.product, self.inputs, self.selected)

    @property
    def refundable(self) -> Decimal:
        """Fees are earned on day one; only net plus taxes earn over the term."""
        return self.quote.earning

    @property
    def expiry(self) -> date:
        return add_months(self.inception, self.product.term_months)

    def term_days(self) -> int:
        return (self.expiry - self.inception).days

    def days_remaining(self, on: date) -> int:
        return max(0, (self.expiry - on).days)

    def status(self, on: date) -> str:
        lc = self.product.lifecycle
        if self.inception is None:
            return "quoted"
        if self.cancelled_on is not None and on >= self.cancelled_on:
            return "cancelled"
        for start, end in self.previous_terms:
            if start <= on < end:
                return "renewed"
        if on < self.inception:
            return "bound"
        if on >= self.expiry:
            return "expired"
        if lc.lapse_days is not None and self.paid_on is None and (on - self.inception).days > lc.lapse_days:
            return "lapsed"
        return "live"

    # -- events -------------------------------------------------------------

    def bind(self, on: date, paid: bool = True) -> None:
        self.inception = on
        self.paid_on = on if paid else None
        self.expiring_premium = self.quote.total

    def pay(self, on: date) -> None:
        self.paid_on = on

    def cancel(self, on: date, by: str) -> Decimal:
        lc = self.product.lifecycle
        terms = lc.cancellation.get(by)
        if terms is None:
            raise ValueError(f"cancellation by {by} is not declared in the lifecycle")
        self.cancelled_on = on
        if (on - self.inception).days < lc.cooling_off_days:
            return pence(self.quote.total)
        if terms.refund == "full":
            refund = self.refundable
        elif terms.refund == "pro rata":
            refund = self.refundable * self.days_remaining(on) / self.term_days()
        else:
            refund = Decimal(0)
        return pence(max(Decimal(0), refund - terms.fee))

    def adjust(self, on: date, changes: dict) -> Decimal:
        """Applies changes; returns the amount to charge (negative = return premium)."""
        lc = self.product.lifecycle
        if not lc.adjustment_allowed:
            raise ValueError("adjustment is not allowed")
        before = self.refundable
        self.inputs.update(changes)
        difference = (self.refundable - before) * self.days_remaining(on) / self.term_days()
        self.expiring_premium = self.quote.total
        return pence(difference + lc.adjustment_fee)

    def renew(self) -> RenewalOffer:
        lc = self.product.lifecycle
        ctx = context(self.inputs, self.selected, claims_in_term=len(self.claims))
        new = pence(self.quote.total * self.claims_loading())
        offer = RenewalOffer(self.expiry - timedelta(days=lc.renewal_invite_days), new, new)
        if lc.renewal_cap is not None:
            offer.premium = min(new, pence(self.expiring_premium * (1 + lc.renewal_cap)))
        for r in lc.renewal_decline:
            if evaluate(r.condition, ctx):
                offer.declined = r.reason
                break
        return offer

    def claims_loading(self) -> Decimal:
        applicable = [m for count, m in self.product.claims_loading if len(self.claims) >= count]
        return applicable[-1] if applicable else Decimal(1)

    def claim(self, cover: str, claimed: Decimal, on: date, reported: date, evidence: set[str]) -> "ClaimResult":
        rules = self.product.claims.get(cover)
        if rules is None:
            return ClaimResult("declined", reason=f"claims on {cover} are not declared")
        status = self.status(on)
        if status != "live":
            return ClaimResult("declined", reason=f"policy was {status} on {on.isoformat()}")
        state = cover_state(self.product.cover(cover), self.inputs, self.selected)
        if state.status != "included":
            return ClaimResult("declined", reason=f"{cover} is {state.status}" + (f": {state.reason}" if state.reason else ""))
        for name in rules.requires:
            if name not in evidence:
                return ClaimResult("declined", reason=f"{name} is required")
        ctx = context(self.inputs, self.selected, claim=claimed, claimed=claimed,
                      days_to_report=(reported - on).days, claims_in_term=len(self.claims))
        for r in rules.decline:
            if evaluate(r.condition, ctx):
                return ClaimResult("declined", reason=r.reason)
        payout = min(claimed, state.limit) if state.limit is not None else claimed
        if rules.less_excess:
            excess = self.product.cover(cover).excess
            amount = Decimal(evaluate(excess.amount, ctx)) if excess.amount is not None else Decimal(0)
            if excess.minimum is not None:
                amount = max(amount, Decimal(evaluate(excess.minimum, ctx)))
            payout -= amount
        result = ClaimResult("paid", pence(max(Decimal(0), payout)))
        self.claims.append(result)
        return result

    def accept_renewal(self) -> None:
        offer = self.renew()
        if offer.declined:
            raise ValueError(f"renewal declined: {offer.declined}")
        self.previous_terms.append((self.inception, self.expiry))
        self.inception = self.paid_on = self.expiry
        self.expiring_premium = offer.premium
        self.claims = []
