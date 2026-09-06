"""Applies a Product to a risk: eligibility, covers, rating, lifecycle and claims."""
from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from .expr import evaluate, names
from .model import Cover, Input, Lifecycle, Product, RatingStep


def context(product: Product, inputs: dict, selected: set[str], item: dict | None = None, **extra) -> dict:
    """Evaluation context: inputs, singular aliases for collections, the current item's fields."""
    inputs, _, _ = enriched(product, inputs)
    ctx = {**inputs, "selected": selected, "tables": product.tables, **extra}
    for inp in product.inputs.values():
        if inp.kind == "calculated":
            ctx[inp.name], _ = run_steps(product, inp.steps, ctx, Decimal(0), [], [])
    for coll in product.collections:
        ctx[coll.name] = ctx[coll.singular] = [calculated(product, coll, i, ctx) for i in ctx.get(coll.name, [])]
        if item and set(item) >= {f.name for f in coll.fields.values() if f.kind not in ("text", "calculated")}:
            item = calculated(product, coll, item, ctx)
    if item:
        ctx.update(item)
    return ctx


def enriched(product: Product, inputs: dict) -> tuple[dict, list[tuple[str, str]], set[str]]:
    """Inputs with enrichment defaults filled in, (refer|decline, reason) for lookups that could not answer,
    and the names of the provided fields still missing as a result."""
    inputs = {k: [dict(i) for i in v] if isinstance(v, list) else v for k, v in inputs.items()}
    outcomes, missing = [], set()
    for e in product.enrichments:
        targets = inputs.get(product.collection_for(e.item).name, []) if e.item else [inputs]
        for target in targets:
            if all(f in target for f in e.provides):
                continue
            if e.unavailable == "default":
                for f in e.provides:
                    target.setdefault(f, e.defaults.get(f))
            else:
                missing |= set(e.provides)
                if (e.unavailable, e.reason) not in outcomes:
                    outcomes.append((e.unavailable, e.reason))
    return inputs, outcomes, missing


def calculated(product: Product, coll: Input, item: dict, ctx: dict) -> dict:
    """The item with its calculated fields filled in, in declaration order."""
    item = dict(item)
    for f in coll.fields.values():
        if f.kind == "calculated":
            item[f.name], _ = run_steps(product, f.steps, {**ctx, **item}, Decimal(0), [], [])
    return item


@dataclass
class Eligibility:
    outcome: str  # eligible | referred | declined
    reasons: list[str] = field(default_factory=list)


def check_eligibility(product: Product, inputs: dict, selected: set[str] = frozenset()) -> Eligibility:
    ctx = context(product, inputs, set(selected))
    reasons, declined = [], False
    _, outcomes, missing = enriched(product, inputs)
    for kind, reason in outcomes:
        reasons.append(reason)
        declined = declined or kind == "decline"
    for coll in product.collections:
        count = len(inputs.get(coll.name, []))
        if count < coll.min_items:
            reasons.append(f"{coll.name}: at least {coll.min_items} required")
        elif coll.max_items is not None and count > coll.max_items:
            reasons.append(f"{coll.name}: at most {coll.max_items} allowed")
        declined = declined or count < coll.min_items or (coll.max_items is not None and count > coll.max_items)
    for r in product.eligibility:
        if names(r.condition) & missing:
            continue  # the lookup's own refer or decline speaks for this rule
        if evaluate(r.condition, ctx):
            reasons.append(r.reason)
            declined = declined or r.kind == "decline"
    if declined:
        return Eligibility("declined", reasons)
    if reasons:
        return Eligibility("referred", reasons)
    return Eligibility("eligible")


@dataclass
class CoverState:
    name: str
    status: str  # included | excluded | not selected | not available
    reason: str = ""
    limit: Decimal | None = None


def cover_state(product: Product, cover: Cover, inputs: dict, selected: set[str], item: dict | None = None) -> CoverState:
    ctx = context(product, inputs, selected, item)
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
    return [cover_state(product, c, inputs, selected) for c in product.covers]


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
    commission: list[tuple[str, Decimal]] = field(default_factory=list)  # shares of the net owed to intermediaries; reported, never added


def run_steps(product: Product, steps, ctx: dict, net: Decimal, trail: list, lines: list, prefix: str = "") -> tuple[Decimal, Decimal]:
    """Runs rating steps in order against a running net. Returns the net and the rounding unit."""
    quantum = Decimal("0.01")

    def value(node):
        return Decimal(evaluate(node, ctx))

    def record(label, applied):
        trail.append(Trail(prefix + label, applied, net))

    for step in steps:
        if step.condition is not None and not evaluate(step.condition, ctx):
            continue
        if step.kind == "base":
            net = value(step.amount)
            record("base", f"{net:.2f}")
        elif step.kind == "each":
            coll = product.collection_for(step.label)
            total = Decimal(0)
            items = list(enumerate(ctx.get(coll.name, []), start=1))  # numbered as declared, so trail and claims agree
            for key, descending in reversed(step.order):  # stable sorts, last key first
                items.sort(key=lambda pair: evaluate(key, {**ctx, **pair[1]}), reverse=descending)
            for position, (i, item) in enumerate(items, start=1):
                sub, _ = run_steps(product, step.steps, {**ctx, **item, "position": position}, Decimal(0), trail, lines, f"{prefix}{step.label} {i} ")
                trail.append(Trail(f"{prefix}{step.label} {i}", "net", sub))  # the item's own share
                total += sub
            net += total
            record(coll.name, f"{total:.2f}")
        elif step.kind == "factor":
            row = next((r for r in step.rows if r.condition is None or evaluate(r.condition, ctx)), None)
            if row is None:
                continue
            net = apply_row(net, row, ctx)
            record(step.label, f"{row.op} {evaluate(row.amount, ctx)}")
        elif step.kind == "add":
            amount = value(step.amount)
            net += amount
            record(step.label or "add", f"+ {amount}")
        elif step.kind in ("discount", "load"):
            pct = value(step.amount)
            mult = (1 - pct) if step.kind == "discount" else (1 + pct)
            net *= mult
            record(step.label or step.kind, f"x {mult}")
        elif step.kind in ("minimum", "maximum"):
            bound = value(step.amount)
            net = max(net, bound) if step.kind == "minimum" else min(net, bound)
            record(step.label or step.kind, str(bound))
        elif step.kind in ("tax", "fee", "commission"):
            lines.append((step.kind, step.label, value(step.amount)))
        elif step.kind == "round":
            quantum = value(step.amount)
    return net, quantum


def apply_row(value: Decimal, row, ctx: dict) -> Decimal:
    amount = Decimal(evaluate(row.amount, ctx))
    return value * amount if row.op == "x" else value + amount if row.op == "+" else value - amount


def rate(product: Product, inputs: dict, selected: set[str], loading: Decimal = Decimal(1)) -> Quote:
    """Prices a risk. A claims loading is a final load on the net, so tax follows it and fees do not."""
    ctx = context(product, inputs, selected)
    lines, trail = [], []
    steps = product.rating + ([RatingStep("load", "Claims loading", amount=("num", loading - 1))] if loading != 1 else [])
    net, quantum = run_steps(product, steps, ctx, Decimal(0), trail, lines)
    net = net.quantize(quantum, ROUNDING)  # tax is charged on the rounded net, as on an invoice
    lines = [(kind, label, (amount if kind == "fee" else net * amount).quantize(quantum, ROUNDING)) for kind, label, amount in lines]
    taxes = sum((a for kind, _, a in lines if kind == "tax"), Decimal(0))
    fees = sum((a for kind, _, a in lines if kind == "fee"), Decimal(0))
    return Quote(net, [(label, a) for kind, label, a in lines if kind != "commission"], net + taxes + fees, net + taxes, trail,
                 [(label, a) for kind, label, a in lines if kind == "commission"])


# --- lifecycle --------------------------------------------------------------

def add_months(d: date, months: int) -> date:
    month = d.month - 1 + months
    year, month = d.year + month // 12, month % 12 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def months_between(start: date, on: date) -> int:
    """Whole months from start to on."""
    return (on.year - start.year) * 12 + on.month - start.month - (on.day < start.day)


def pence(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), ROUNDING)


def instalments(premium: Decimal, count: int, charge: Decimal) -> tuple[Decimal, list[Decimal]]:
    """The credit charge on the premium and the instalments that pay premium plus charge: equal
    to the penny, with the first taking any rounding so the sum is exact."""
    charge = pence(premium * charge)
    total = premium + charge
    each = pence(total / count)
    return charge, [total - each * (count - 1)] + [each] * (count - 1)


@dataclass
class RenewalOffer:
    invite_date: date
    premium: Decimal
    uncapped: Decimal
    inputs: dict  # the answers the offer was priced on, after indexation
    declined: str | None = None


@dataclass
class ClaimResult:
    status: str  # paid | declined
    amount: Decimal = Decimal(0)
    reason: str = ""
    cover: str = ""
    counted: bool = True  # towards claims in term
    bucket: object = None  # which per-condition or per-item limit this claim erodes


def excess_amount(excess, ctx: dict) -> Decimal:
    """One amount, or the first matching row of a table, floored at the minimum."""
    row = next((r for r in excess.rows if r.condition is None or evaluate(r.condition, ctx)), None)
    node = row.amount if row is not None else excess.amount
    amount = Decimal(evaluate(node, ctx)) if node is not None else Decimal(0)
    if excess.minimum is not None:
        amount = max(amount, Decimal(evaluate(excess.minimum, ctx)))
    if excess.maximum is not None:
        amount = min(amount, Decimal(evaluate(excess.maximum, ctx)))
    return amount


class Policy:
    """One policy's history: bind, pay, cancel, adjust, claim, renew. Status is derived per date."""

    @property
    def claims_in_term(self) -> int:
        return sum(c.counted for c in self.claims)

    def __init__(self, product: Product, inputs: dict, selected: set[str]):
        self.product, self.inputs, self.selected = product, dict(inputs), set(selected)
        self.inception: date | None = None
        self.first_inception: date | None = None  # the original start, kept across renewals for waiting periods
        self.paid_on: date | None = None
        self.cancelled_on: date | None = None
        self.charged = Decimal(0)  # the total charged for the current term: capped or loaded at renewal, repriced on adjustment
        self.claims: list = []
        self.previous_terms: list[tuple[date, date]] = []

    # -- derived ------------------------------------------------------------

    @property
    def quote(self) -> Quote:
        return rate(self.product, self.inputs, self.selected)

    @property
    def premium(self) -> Decimal:
        """What the customer pays for the term: the quote until bound, then what was actually charged."""
        return self.charged if self.inception is not None else self.quote.total

    @property
    def refundable(self) -> Decimal:
        """Fees are earned on day one; only net plus taxes earn over the term."""
        q = self.quote
        return self.premium - (q.total - q.earning)

    @property
    def expiry(self) -> date:
        amount, unit = self.product.term
        value = evaluate(amount, context(self.product, self.inputs, self.selected))
        if unit == "until":
            return value
        if unit == "days":
            return self.inception + timedelta(days=int(value))
        return add_months(self.inception, int(value) * (12 if unit == "years" else 1))

    def term_days(self) -> int:
        return (self.expiry - self.inception).days

    def days_remaining(self, on: date) -> int:
        return max(0, (self.expiry - on).days)

    @property
    def terms(self) -> "Lifecycle":
        """The lifecycle in force: the product's own, or the last set of terms imposed by paid claims."""
        imposed = [terms for count, terms, unless in self.product.claims_terms if self.claims_in_term >= count and not self.unless(unless)]
        return imposed[-1] if imposed else self.product.lifecycle

    def unless(self, condition: tuple | None) -> bool:
        """Whether an 'unless' condition switches a claims consequence off for this policy."""
        return condition is not None and bool(evaluate(condition, context(self.product, self.inputs, self.selected)))

    def status(self, on: date) -> str:
        lc = self.terms
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
        self.inception = self.first_inception = on
        self.paid_on = on if paid else None
        self.charged = self.quote.total

    def pay(self, on: date) -> None:
        self.paid_on = on

    def cancel(self, on: date, by: str) -> Decimal:
        lc = self.terms
        terms = lc.cancellation.get(by)
        if terms is None:
            raise ValueError(f"cancellation by {by} is not declared in the lifecycle")
        self.cancelled_on = on
        if (on - self.inception).days < lc.cooling_off_days:
            return pence(self.premium)
        if terms.refund == "full":
            refund = self.refundable
        elif terms.refund == "pro rata":
            refund = self.refundable * self.days_remaining(on) / self.term_days()
        elif terms.refund == "amount":
            ctx = context(self.product, self.inputs, self.selected, days_in_force=Decimal((on - self.inception).days), months_in_force=Decimal(months_between(self.inception, on)))
            refund = self.refundable * Decimal(evaluate(terms.amount, ctx))
        else:
            refund = Decimal(0)
        return pence(max(Decimal(0), refund - terms.fee))

    def adjust(self, on: date, changes: dict) -> Decimal:
        """Applies changes; returns the amount to charge (negative = return premium)."""
        lc = self.terms
        if not lc.adjustment_allowed:
            raise ValueError("adjustment is not allowed")
        before = self.refundable
        for e in self.product.enrichments:
            if not e.held:
                continue
            if e.item:
                name = self.product.collection_for(e.item).name
                old_items, new_items = self.inputs.get(name, []), changes.get(name, self.inputs.get(name, []))
                # ponytail: items have no identity, so a fleet that changed size is not checked
                pairs = zip(old_items, new_items) if len(old_items) == len(new_items) else []
            else:
                pairs = [(self.inputs, {**self.inputs, **changes})]
            for old, new in pairs:
                changed = [f for f in e.provides if f in old and new.get(f, old[f]) != old[f]]
                if changed:
                    raise ValueError(f"{changed[0]} is held for the term")
        self.inputs.update(changes)
        self.charged = self.quote.total
        difference = (self.refundable - before) * self.days_remaining(on) / self.term_days()
        return pence(difference + lc.adjustment_fee)

    def renew(self) -> RenewalOffer:
        lc = self.terms
        inputs = {k: [dict(i) for i in v] if isinstance(v, list) else v for k, v in self.inputs.items()}
        before = context(self.product, self.inputs, self.selected, claims_in_term=self.claims_in_term)

        def indexed(v, how, node, least, most):
            amount = Decimal(evaluate(node, before))
            v = pence(v * (1 + amount / 100)) if how == "%" else v + amount
            v = v if least is None else max(v, least)
            return v if most is None else min(v, most)

        for name, *how in lc.renewal_index:
            if "." in name:
                singular, field_ = name.split(".")
                for item in inputs.get(self.product.collection_for(singular).name, []):
                    item[field_] = indexed(item[field_], *how)
            else:
                inputs[name] = indexed(inputs[name], *how)
        ctx = context(self.product, inputs, self.selected, claims_in_term=self.claims_in_term)
        new = rate(self.product, inputs, self.selected, self.claims_loading()).total
        offer = RenewalOffer(self.expiry - timedelta(days=lc.renewal_invite_days), new, new, inputs)
        if not lc.renewable:
            offer.declined = "The policy is not renewable"
            return offer
        if lc.renewal_cap is not None:
            offer.premium = min(offer.premium, pence(self.charged * (1 + lc.renewal_cap)))
        if lc.renewal_collar is not None:
            offer.premium = max(offer.premium, pence(self.charged * (1 - lc.renewal_collar)))
        for r in lc.renewal_decline:
            if evaluate(r.condition, ctx):
                offer.declined = r.reason
                break
        return offer

    def bucket(self, section: Cover, item: dict | None, facts: dict) -> object:
        """Which of a cover's per-X limits a claim falls into: the fact's value, or the item's position."""
        if not section.per:
            return None
        if section.per in facts:
            return facts[section.per]
        items = self.inputs[self.product.collection_for(section.per).name]
        return next(n for n, x in enumerate(items, start=1) if x is item)

    def remaining(self, cover: str, item: dict | None = None, facts: dict | None = None) -> Decimal | None:
        """What is left of an aggregate limit this term; None when the cover has no such limit."""
        section = self.product.cover(cover)
        state = cover_state(self.product, section, self.inputs, self.selected, item)
        if not section.aggregate or state.limit is None:
            return None
        bucket = self.bucket(section, item, facts or {})
        return max(Decimal(0), state.limit - sum((c.amount for c in self.claims if c.cover == cover and c.bucket == bucket), Decimal(0)))

    def claims_loading(self) -> Decimal:
        applicable = [m for count, m, unless in self.product.claims_loading if self.claims_in_term >= count and not self.unless(unless)]
        return applicable[-1] if applicable else Decimal(1)

    def claim(self, cover: str, claimed: Decimal, on: date, reported: date, evidence: set[str], item: dict | None = None, facts: dict | None = None) -> "ClaimResult":
        facts = facts or {}
        rules = self.product.claims.get(cover)
        if rules is None:
            return ClaimResult("declined", reason=f"claims on {cover} are not declared")
        status = self.status(on)
        if status != "live":
            return ClaimResult("declined", reason=f"policy was {status} on {on.isoformat()}")
        section = self.product.cover(cover)
        if section.item and item is None:
            return ClaimResult("declined", reason=f"{cover} is per {section.item}; say which {section.item} the claim is on")
        state = cover_state(self.product, section, self.inputs, self.selected, item)
        if state.status != "included":
            return ClaimResult("declined", reason=f"{cover} is {state.status}" + (f": {state.reason}" if state.reason else ""))
        first = self.first_inception
        ctx = context(self.product, self.inputs, self.selected, item, claim=claimed, claimed=claimed, **facts,
                      days_to_report=(reported - on).days, claims_in_term=self.claims_in_term,
                      days_since_inception=(on - first).days, months_since_inception=months_between(first, on))
        if (section.from_ is not None and on < evaluate(section.from_, ctx)) or (section.until is not None and on >= evaluate(section.until, ctx)):
            return ClaimResult("declined", reason=f"{cover} is not in force on {on.isoformat()}")
        if (on - first).days < section.waiting_days:
            return ClaimResult("declined", reason=f"{cover} is within the {section.waiting_days} day waiting period")
        for name in rules.requires + [f for f in rules.asks if f not in facts]:
            if name not in evidence:
                return ClaimResult("declined", reason=f"{name} is required")
        for r in rules.decline:
            if evaluate(r.condition, ctx):
                return ClaimResult("declined", reason=r.reason)
        payout = Decimal(evaluate(rules.pays_amount, ctx)) if rules.pays_amount is not None else claimed
        row = next((r for r in rules.depreciation if r.condition is None or evaluate(r.condition, ctx)), None)
        if row is not None:
            payout = apply_row(payout, row, ctx)
        limit = self.remaining(cover, item, facts) if section.aggregate else state.limit
        if section.aggregate and limit == 0:
            where = f" for {section.per} {self.bucket(section, item, facts)}" if section.per else ""
            return ClaimResult("declined", reason=f"{cover} limit for the term is used up{where}")
        for clause in rules.pays:  # in the order the wording gives them
            if clause == "limit" and limit is not None:
                payout = min(payout, limit)
            elif clause == "excess":
                payout -= excess_amount(section.excess, ctx)
            elif clause == "co-payment":
                for cp in rules.co_payments:
                    if cp.condition is None or evaluate(cp.condition, ctx):
                        payout *= 1 - Decimal(evaluate(cp.amount, ctx))
        if payout <= 0:
            return ClaimResult("declined", reason="nothing is payable after the excess")
        result = ClaimResult("paid", pence(payout), cover=cover, counted=bool(evaluate(rules.counts, ctx)), bucket=self.bucket(section, item, facts))
        self.claims.append(result)
        return result

    def accept_renewal(self) -> None:
        offer = self.renew()
        if offer.declined:
            raise ValueError(f"renewal declined: {offer.declined}")
        self.previous_terms.append((self.inception, self.expiry))
        self.inputs = offer.inputs
        self.inception = self.paid_on = self.expiry
        self.charged = offer.premium
        self.claims = []
