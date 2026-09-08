"""Applies a Product to a risk: eligibility, covers, rating, lifecycle and claims."""
from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from .expr import ExprError, evaluate, names
from .model import Cover, Input, Lifecycle, Product, RatingStep


def context(product: Product, inputs: dict, selected: set[str], item: dict | None = None, **extra) -> dict:
    """Evaluation context: inputs, singular aliases for collections, the current item's fields."""
    inputs, _, _ = enriched(product, inputs)
    ctx = {**inputs, "selected": selected, "tables": product.tables, **extra}
    for inp in product.inputs.values():
        if inp.kind == "calculated":
            ctx[inp.name] = total(run_steps(product, inp.steps, ctx, [], [])[0])
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
            item[f.name] = total(run_steps(product, f.steps, {**ctx, **item}, [], [])[0])
    return item


@dataclass
class Eligibility:
    outcome: str  # eligible | referred | declined
    reasons: list[str] = field(default_factory=list)


def check_inputs(product: Product, inputs: dict) -> list[str]:
    """Why a risk's answers cannot be priced: inputs left out, and keyed choices not listed under their keys."""
    missing = [n for n, i in product.inputs.items() if n not in inputs and i.kind not in ("text", "calculated", "collection") and not i.provided]
    problems = [f"missing {', '.join(missing)}"] if missing else []
    problems += keyed_choice_problems(product, product.inputs, inputs, inputs)
    for coll in product.collections:
        for n, item in enumerate(inputs.get(coll.name, []), start=1):
            item_missing = [f for f, i in coll.fields.items()
                             if f not in item and i.kind not in ("text", "calculated", "collection") and not i.provided and i.default is None]
            if item_missing:
                problems.append(f"{coll.name} item {n}: missing {', '.join(item_missing)}")
            problems += [f"{coll.name} item {n}: {why}" for why in keyed_choice_problems(product, coll.fields, item, {**inputs, **item})]
    return problems


def keyed_choice_problems(product: Product, fields: dict[str, Input], record: dict, ctx: dict) -> list[str]:
    """Each keyed choice in the record whose value the table does not list under the record's keys."""
    out = []
    for f in fields.values():
        if f.source and f.source[2] and f.name in record:
            table, column, keys = f.source
            if record[f.name] not in product.tables[table].values_for(column, keys, ctx):
                where = ", ".join(f"{k} {show(ctx.get(k))}" for k in keys)
                out.append(f"{f.name} {show(record[f.name])} is not {'an' if column[0] in 'aeiou' else 'a'} {column} for {where}")
    return out


def show(value) -> str:
    """A value as a message names it: text in quotes, yes/no, or the number."""
    if isinstance(value, bool):
        return "yes" if value else "no"
    return f'"{value}"' if isinstance(value, str) else str(value)


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


def status_of(cover: Cover, ctx: dict) -> tuple[str, str]:
    """Whether the cover is on the risk in this context: (status, reason)."""
    if cover.optional and cover.name not in ctx["selected"]:
        return "not selected", ""
    if cover.available is not None and not evaluate(cover.available, ctx):
        return "not available", ""
    for rule in cover.exclusions:
        if evaluate(rule.condition, ctx):
            return "excluded", rule.reason
    return "included", ""


def cover_state(product: Product, cover: Cover, inputs: dict, selected: set[str], item: dict | None = None) -> CoverState:
    ctx = context(product, inputs, selected, item)
    status, reason = status_of(cover, ctx)
    if status != "included":
        return CoverState(cover.name, status, reason)
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
class Share:
    """One cover's part of a quote: its net and its part of each attributed line. `by_class` sums them by class."""
    name: str
    class_: str
    net: Decimal
    lines: list[tuple[str, Decimal]] = field(default_factory=list)
    commission: list[tuple[str, Decimal]] = field(default_factory=list)


@dataclass
class Quote:
    net: Decimal
    lines: list[tuple[str, Decimal]]  # taxes and fees, in order
    total: Decimal
    earning: Decimal  # net plus taxes: the part that earns over the term and is refundable pro rata
    trail: list[Trail] = field(default_factory=list)
    commission: list[tuple[str, Decimal]] = field(default_factory=list)  # shares of the net owed to intermediaries; reported, never added
    currency: str = ""
    shares: list[Share] = field(default_factory=list)  # one per cover with a share, in declaration order; empty when nothing is attributed

    def split(self, amount: Decimal) -> dict[str, Decimal]:
        """The amount shared by each cover's earning (its net plus its taxes), residue to the largest; a quote with
        no shares gives it all under one unnamed share. How a refund, an adjustment or a renewal premium is split."""
        if not self.shares:
            return {"": amount}
        quantum = Decimal(1).scaleb(self.net.as_tuple().exponent)
        return split(amount, {s.name: s.net + sum((a for _, a in s.lines), Decimal(0)) for s in self.shares}, quantum)

    def by_class(self) -> list[Share]:
        out: dict[str, Share] = {}
        for s in self.shares:
            c = out.setdefault(s.class_, Share(s.class_, s.class_, Decimal(0), [], []))
            c.net += s.net
            c.lines = merged(c.lines, s.lines)
            c.commission = merged(c.commission, s.commission)
        return list(out.values())


def merged(a: list[tuple[str, Decimal]], b: list[tuple[str, Decimal]]) -> list[tuple[str, Decimal]]:
    out = dict(a)
    for label, amount in b:
        out[label] = out.get(label, Decimal(0)) + amount
    return list(out.items())


def total(shares: dict[str, Decimal]) -> Decimal:
    return sum(shares.values(), Decimal(0))


def split(amount: Decimal, weights: dict[str, Decimal], quantum: Decimal) -> dict[str, Decimal]:
    """`amount` shared in proportion to `weights`, each part rounded, the residue to the largest weight (the first on a tie)."""
    if not weights:
        return {}
    base = total(weights)
    out = {k: (amount * w / base if base else Decimal(0)).quantize(quantum, ROUNDING) for k, w in weights.items()}
    largest = max(weights, key=weights.get)
    out[largest] += amount - total(out)
    return out


def allocated(product: Product, shares: dict[str, Decimal]) -> dict[str, Decimal]:
    """The shares with the pool shared out by `allocate`, unrounded. Done before any step that names a cover and at the end,
    so the key's position in the rating never matters."""
    if not product.allocation:
        return shares
    out = {**{c.name: shares.get(c.name, Decimal(0)) for c in product.covers}, "": Decimal(0)}
    for name, part in product.allocation:
        out[name] += shares.get("", Decimal(0)) * part
    return out


def attributed(product: Product, shares: dict[str, Decimal], quantum: Decimal, strict: bool = True) -> dict[str, Decimal]:
    """The covers' rounded shares of the rounded net; empty for a product that attributes nothing. Strict, the pool
    must be empty; a condition read part way through rating, or inside a cover premium or a calculated field, is not."""
    if not product.attributed:
        return {}
    shares = allocated(product, shares)
    pool = shares.get("", Decimal(0)).quantize(quantum, ROUNDING)
    if pool and strict:
        raise ExprError(f"{pool:f} of the premium is not attributed to a cover; add allocate")
    return split(total(shares).quantize(quantum, ROUNDING), {c.name: shares.get(c.name, Decimal(0)) for c in product.covers}, quantum)


def cover_premiums(product: Product, ctx: dict, trail: list, prefix: str, item: str) -> list[tuple[str, Decimal]]:
    """Each included cover's own price, for `add cover premiums`. Inside `for each <item>` it is the current item's
    premiums (the parser makes sure every priced cover is per that item); outside, every cover's, a per-item one
    summed over its items. A premium of one bare `base` leaves no trail of its own; a block's steps do."""
    out = []
    for cover in product.covers:
        if not cover.premium or (item and cover.premium_item != item):
            continue
        contexts = [ctx] if item or not cover.premium_item else [{**ctx, **i} for i in ctx[product.collection_for(cover.premium_item).name]]
        amount, included = Decimal(0), False
        for c in contexts:
            if status_of(cover, c)[0] != "included":
                continue
            included = True
            steps = [] if len(cover.premium) == 1 and cover.premium[0].kind == "base" else trail
            amount += total(run_steps(product, cover.premium, c, steps, [], f"{prefix}{cover.name} ")[0])
        if included:
            out.append((cover.name, amount))
    return out


def run_steps(product: Product, steps, ctx: dict, trail: list, lines: list, prefix: str = "") -> tuple[dict[str, Decimal], Decimal]:
    """Runs rating steps in order against a running net held as shares by cover ("" is the unattributed pool);
    the net is their sum. Returns the shares and the rounding unit. `lines` collects [kind, label, amount, shares]
    for every tax, fee and commission, evaluated where it stands."""
    quantum = product.quantum_for(ctx.get("territory", ""))
    shares: dict[str, Decimal] = {"": Decimal(0)}

    def value(node, **words):
        return Decimal(evaluate(node, {**ctx, **words} if words else ctx))

    def record(label, applied):
        trail.append(Trail(prefix + label, applied, total(shares)))

    def scale(mult: Decimal, cover: str) -> None:
        for k in shares if not cover else [cover]:
            shares[k] = shares.get(k, Decimal(0)) * mult

    def words_for(net: Decimal, covers: dict[str, Decimal], line_shares) -> dict:
        """What a line may read: the net as the customer sees it, net plus the lines above, each tax above, each cover's share."""
        above = sum((line_shares(l) for l in lines if l[0] != "commission"), Decimal(0))
        return {**{l[1]: line_shares(l) for l in lines if l[0] == "tax"}, **covers, "net": net, "premium": net + above}

    def line_words() -> dict:
        return words_for(total(shares).quantize(quantum, ROUNDING), attributed(product, shares, quantum, strict=False), lambda l: l[2])

    for step in steps:
        if step.kind == "round":
            quantum = value(step.amount)  # read before any step runs: the unit for every figure
    for step in steps:
        if step.condition is not None and not evaluate(step.condition, {**ctx, **line_words()}):
            continue
        key = step.cover or ""
        if key:
            shares = allocated(product, shares)  # a cover's share must hold its part of the pool before a step touches it
        if step.kind == "base":
            shares = {key: value(step.amount)}
            record("base", f"{total(shares):.2f}")
        elif step.kind == "each":
            coll = product.collection_for(step.label)
            added = Decimal(0)
            items = list(enumerate(ctx.get(coll.name, []), start=1))  # numbered as declared, so trail and claims agree
            for k, descending in reversed(step.order):  # stable sorts, last key first
                items.sort(key=lambda pair: evaluate(k, {**ctx, **pair[1]}), reverse=descending)
            for position, (i, item) in enumerate(items, start=1):
                own: list = []  # the item's lines: its second line reads its own first, not every item's
                sub, _ = run_steps(product, step.steps, {**ctx, **item, "position": position}, trail, own, f"{prefix}{step.label} {i} ")
                trail.append(Trail(f"{prefix}{step.label} {i}", "net", total(sub)))  # the item's own share
                for k, v in sub.items():
                    shares[k] = shares.get(k, Decimal(0)) + v
                for l in own:
                    merge_line(lines, *l)
                added += total(sub)
            record(coll.name, f"{added:.2f}")
        elif step.kind == "factor":
            row = next((r for r in step.rows if r.condition is None or evaluate(r.condition, ctx)), None)
            if row is None:
                continue
            amount = Decimal(evaluate(row.amount, ctx))
            if row.op == "x":
                scale(amount, key)
            else:
                shares[key] = shares.get(key, Decimal(0)) + (amount if row.op == "+" else -amount)
            record(step.label, f"{row.op} {amount}")
        elif step.kind == "add":
            amount = value(step.amount)
            shares[key] = shares.get(key, Decimal(0)) + amount
            record(step.label or "add", f"+ {amount}")
        elif step.kind == "premiums":
            for name, amount in cover_premiums(product, ctx, trail, prefix, step.label):
                shares[name] = shares.get(name, Decimal(0)) + amount
                record(name, f"+ {amount:.2f}")
        elif step.kind in ("discount", "load"):
            pct = value(step.amount)
            mult = (1 - pct) if step.kind == "discount" else (1 + pct)
            scale(mult, key)
            record(step.label or step.kind, f"x {mult}")
        elif step.kind in ("minimum", "maximum"):
            bound, net = value(step.amount), total(shares)
            target = max(net, bound) if step.kind == "minimum" else min(net, bound)
            if net:
                scale(target / net, "")
            else:
                shares = {"": target}
            record(step.label or step.kind, str(bound))
        elif step.kind in ("tax", "fee", "commission"):
            net, covers = total(shares).quantize(quantum, ROUNDING), attributed(product, shares, quantum)
            amount = value(step.amount, **words_for(net, covers, lambda l: l[2])).quantize(quantum, ROUNDING)
            parts = {}
            if covers and step.kind != "fee":  # attributed in proportion to the base worked out with each cover's figures
                weights = {c: value(step.amount, **words_for(covers[c], {k: covers[c] if k == c else Decimal(0) for k in covers}, lambda l: l[3].get(c, Decimal(0))))
                           for c in covers}
                parts = split(amount, weights, quantum)
            merge_line(lines, step.kind, step.label, amount, parts)
    return shares, quantum


def merge_line(lines: list, kind: str, label: str, amount: Decimal, parts: dict[str, Decimal]) -> None:
    """Adds a line; the same line across items, or repeated, is one line."""
    same = next((l for l in lines if l[0] == kind and l[1] == label), None)
    if same is None:
        lines.append([kind, label, amount, parts])
    else:
        same[2] += amount
        same[3] = {c: same[3].get(c, Decimal(0)) + parts.get(c, Decimal(0)) for c in [*same[3], *(c for c in parts if c not in same[3])]}


def apply_row(value: Decimal, row, ctx: dict) -> Decimal:
    amount = Decimal(evaluate(row.amount, ctx))
    return value * amount if row.op == "x" else value + amount if row.op == "+" else value - amount


def rate(product: Product, inputs: dict, selected: set[str], loading: Decimal = Decimal(1), underwriter: Decimal = Decimal(0)) -> Quote:
    """Prices a risk. A claims loading or an underwriter's load is a final load on the net, applied before the
    first tax, fee or commission line, so tax follows it and fees do not."""
    ctx = context(product, inputs, selected)
    lines, trail = [], []
    loads = [RatingStep("load", "Claims loading", amount=("num", loading - 1))] if loading != 1 else []
    loads += [RatingStep("load", "Underwriter load", amount=("num", underwriter))] if underwriter else []
    first = next((i for i, s in enumerate(product.rating) if s.kind in ("tax", "fee", "commission")), len(product.rating))
    steps = product.rating[:first] + loads + product.rating[first:]
    shares, quantum = run_steps(product, steps, ctx, trail, lines)
    net = total(shares).quantize(quantum, ROUNDING)
    taxes = sum((l[2] for l in lines if l[0] == "tax"), Decimal(0))
    fees = sum((l[2] for l in lines if l[0] == "fee"), Decimal(0))
    covers = attributed(product, shares, quantum)
    by_cover = [Share(c.name, c.class_, covers[c.name], [(l[1], l[3].get(c.name, Decimal(0))) for l in lines if l[0] == "tax"],
                      [(l[1], l[3].get(c.name, Decimal(0))) for l in lines if l[0] == "commission"]) for c in product.covers if c.name in covers]
    return Quote(net, [(l[1], l[2]) for l in lines if l[0] != "commission"], net + taxes + fees, net + taxes, trail,
                 [(l[1], l[2]) for l in lines if l[0] == "commission"], product.currency_for(ctx.get("territory", "")),
                 [s for s in by_cover if s.net or any(a for _, a in s.lines + s.commission)])


# --- lifecycle --------------------------------------------------------------

def add_months(d: date, months: int) -> date:
    month = d.month - 1 + months
    year, month = d.year + month // 12, month % 12 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def months_between(start: date, on: date) -> int:
    """Whole months from start to on."""
    return (on.year - start.year) * 12 + on.month - start.month - (on.day < start.day)


def round_money(v: Decimal, quantum: Decimal) -> Decimal:
    return v.quantize(quantum, ROUNDING)


def instalments(premium: Decimal, count: int, charge: Decimal, quantum: Decimal) -> tuple[Decimal, list[Decimal]]:
    """The credit charge on the premium and the instalments that pay premium plus charge: equal
    to the smallest unit of the currency, with the first taking any rounding so the sum is exact."""
    charge = round_money(premium * charge, quantum)
    total = premium + charge
    each = round_money(total / count, quantum)
    return charge, [total - each * (count - 1)] + [each] * (count - 1)


@dataclass
class RenewalOffer:
    invite_date: date
    premium: Decimal
    uncapped: Decimal
    inputs: dict  # the answers the offer was priced on, after indexation and any upgrade
    declined: str | None = None
    version: Product | None = None  # the version the new term would be on
    needs: list[str] = field(default_factory=list)  # answers the new version asks for before it can price; nothing else is decided while any remain
    quote: Quote | None = None  # what the offer was priced on, so its premium can be split by cover


@dataclass
class ClaimResult:
    status: str  # paid | declined
    amount: Decimal = Decimal(0)
    reason: str = ""
    cover: str = ""
    counted: bool = True  # towards claims in term
    bucket: object = None  # which per-condition or per-item limit this claim erodes
    excess: Decimal = Decimal(0)  # what the insured bore on this claim; erodes an aggregate excess
    payments: list = field(default_factory=list)  # (date, amount): when the money goes out; one entry for a lump sum


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


@dataclass
class Underwriting:
    """The terms an underwriter accepts a referred risk on. They hold for the life of the policy."""
    load: Decimal = Decimal(0)  # on the net: 0.20 for a 20% load, negative for a discount
    excess: dict[str, Decimal] = field(default_factory=dict)  # cover -> the excess imposed in place of the product's
    excluded: set[str] = field(default_factory=set)  # covers withdrawn


class Policy:
    """One policy's history: bind, pay, cancel, adjust, claim, renew. Status is derived per date."""

    @property
    def claims_in_term(self) -> int:
        return sum(c.counted for c in self.claims)

    def __init__(self, product: Product, inputs: dict, selected: set[str], history=None):
        self.product, self.inputs, self.selected = product, dict(inputs), set(selected)
        self.versions = history  # a History of the product's versions; None leaves the policy on this product for ever
        self.quantum = product.quantum_for(self.inputs.get("territory", ""))
        self.inception: date | None = None
        self.first_inception: date | None = None  # the original start, kept across renewals for waiting periods
        self.paid_on: date | None = None
        self.cancelled_on: date | None = None
        self.charged = Decimal(0)  # the total charged for the current term: capped or loaded at renewal, repriced on adjustment
        self.claims: list = []  # this term's
        self.history: list = []  # every paid claim, whose payments may run past the term
        self.previous_terms: list[tuple[date, date]] = []
        self.underwriting: Underwriting | None = None  # terms accepted on a referral
        self.reinstated: dict[str, Decimal] = {}  # cover -> what a reinstatement added to its aggregate this term
        self.underwriter_declined = False

    # -- derived ------------------------------------------------------------

    @property
    def version(self) -> date | None:
        """The published date of the version the policy is on."""
        return self.product.published

    def live_on(self, on: date) -> Product:
        return self.versions.live_on(on) if self.versions is not None else self.product

    @property
    def quote(self) -> Quote:
        return rate(self.product, self.inputs, self.selected, underwriter=self.underwriter_load)

    def split(self, amount: Decimal) -> dict[str, Decimal]:
        """An amount this policy produced (a refund, an adjustment's difference) by cover, as the quote now stands."""
        return self.quote.split(amount)

    @property
    def underwriter_load(self) -> Decimal:
        return self.underwriting.load if self.underwriting else Decimal(0)

    def section(self, cover: str, on: date | None = None) -> Cover | None:
        """The cover as worded for this policy on that date: its version's lines plus later versions' dated amendments."""
        return self.versions.cover(self.product, cover, on) if self.versions is not None else self.product.cover(cover, on)

    def rules(self, cover: str, on: date | None = None):
        return self.versions.claim(self.product, cover, on) if self.versions is not None else self.product.claim(cover, on)

    def cover_state(self, cover: str, item: dict | None = None, on: date | None = None) -> CoverState:
        """The product's view of the cover for this risk as worded on that date, less anything the underwriter withdrew."""
        state = cover_state(self.product, self.section(cover, on), self.inputs, self.selected, item)
        if self.underwriting and cover in self.underwriting.excluded and state.status == "included":
            return CoverState(cover, "excluded", "underwriter terms")
        return state

    def excess_for(self, section: Cover, ctx: dict) -> Decimal:
        if self.underwriting and section.name in self.underwriting.excess:
            return self.underwriting.excess[section.name]
        return excess_amount(section.excess, ctx)

    def accept(self, terms: Underwriting) -> None:
        self.underwriting, self.underwriter_declined = terms, False

    def decline_by_underwriter(self) -> None:
        self.underwriter_declined = True

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
        if self.underwriter_declined:
            raise ValueError("declined by the underwriter")
        self.product = self.live_on(on)
        e = check_eligibility(self.product, self.inputs, self.selected)
        if e.outcome == "declined":
            raise ValueError(f"declined: {'; '.join(e.reasons)}")
        if e.outcome == "referred" and self.underwriting is None:
            raise ValueError(f"referred: {'; '.join(e.reasons)}; the underwriter must accept it first")
        self.inception = self.first_inception = on
        self.paid_on = on if paid else None
        self.charged = self.quote.total

    def pay(self, on: date) -> None:
        self.paid_on = on

    def round(self, v: Decimal) -> Decimal:
        return round_money(v, self.quantum)

    def cancel(self, on: date, by: str) -> Decimal:
        lc = self.terms
        terms = lc.cancellation.get(by)
        if terms is None:
            raise ValueError(f"cancellation by {by} is not declared in the lifecycle")
        self.cancelled_on = on
        if (on - self.inception).days < evaluate(lc.cooling_off, context(self.product, self.inputs, self.selected)):
            return self.round(self.premium)
        if terms.refund == "full":
            refund = self.refundable
        elif terms.refund == "pro rata":
            refund = self.refundable * self.days_remaining(on) / self.term_days()
        elif terms.refund == "amount":
            ctx = context(self.product, self.inputs, self.selected, days_in_force=Decimal((on - self.inception).days), months_in_force=Decimal(months_between(self.inception, on)))
            refund = self.refundable * Decimal(evaluate(terms.amount, ctx))
        else:
            refund = Decimal(0)
        return self.round(max(Decimal(0), refund - terms.fee))

    def adjust(self, on: date, changes: dict) -> Decimal:
        """Applies changes; returns the amount to charge (negative = return premium).
        A lifecycle that reprices on the current version moves the policy to the version live that day
        first, the changes answering whatever its upgrade asked for."""
        lc = self.terms
        if not lc.adjustment_allowed:
            raise ValueError("adjustment is not allowed")
        before = self.refundable
        target = self.adjustment_target(on)
        if target is not self.product:
            inputs, needs = self.versions.upgrade(self.inputs, self.product, target)
            needs = [n for n in needs if n not in changes]
            if needs:
                raise ValueError(f"adjustment needs {', '.join(needs)}")
            self.inputs, self.product = inputs, target
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
        return self.round(difference + lc.adjustment_fee)

    def renewal_target(self) -> Product:
        return self.live_on(self.expiry)

    def adjustment_target(self, on: date) -> Product:
        """The version an adjustment on this date is priced on."""
        return self.live_on(on) if self.terms.adjustment_upgrades else self.product

    def renew(self, answers: dict | None = None) -> RenewalOffer:
        """The offer as things stand; answers fill in what the new version's upgrade asked for."""
        lc = self.terms
        inputs = {k: [dict(i) for i in v] if isinstance(v, list) else v for k, v in self.inputs.items()}
        before = context(self.product, self.inputs, self.selected, claims_in_term=self.claims_in_term)

        def indexed(v, how, node, least, most):
            amount = Decimal(evaluate(node, before))
            v = self.round(v * (1 + amount / 100)) if how == "%" else v + amount
            v = v if least is None else max(v, least)
            return v if most is None else min(v, most)

        for name, *how in lc.renewal_index:
            if "." in name:
                singular, field_ = name.split(".")
                for item in inputs.get(self.product.collection_for(singular).name, []):
                    item[field_] = indexed(item[field_], *how)
            else:
                inputs[name] = indexed(inputs[name], *how)
        target, needs = self.renewal_target(), []
        if target is not self.product:
            inputs, needs = self.versions.upgrade(inputs, self.product, target)
        for name, value in (answers or {}).items():
            if name not in needs:
                raise ValueError(f"{name} was not asked at renewal")
            inputs[name] = value
        needs = [n for n in needs if n not in (answers or {})]
        invite = self.expiry - timedelta(days=lc.renewal_invite_days)
        if needs:
            return RenewalOffer(invite, Decimal(0), Decimal(0), inputs, version=target, needs=needs)
        ctx = context(target, inputs, self.selected, claims_in_term=self.claims_in_term)
        priced = rate(target, inputs, self.selected, self.claims_loading(), self.underwriter_load)
        offer = RenewalOffer(invite, priced.total, priced.total, inputs, version=target, quote=priced)
        if not lc.renewable:
            offer.declined = "The policy is not renewable"
            return offer
        if lc.renewal_cap is not None:
            offer.premium = min(offer.premium, self.round(self.charged * (1 + lc.renewal_cap)))
        if lc.renewal_collar is not None:
            offer.premium = max(offer.premium, self.round(self.charged * (1 - lc.renewal_collar)))
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

    def remaining(self, cover: str, item: dict | None = None, facts: dict | None = None, on: date | None = None) -> Decimal | None:
        """What is left of an aggregate limit this term; None when the cover has no such limit."""
        section = self.section(cover, on)
        state = self.cover_state(cover, item, on)
        if not section.aggregate or state.limit is None:
            return None
        bucket = self.bucket(section, item, facts or {})
        limit = state.limit + self.reinstated.get(cover, Decimal(0))
        return max(Decimal(0), limit - sum((c.amount for c in self.claims if c.cover == cover and c.bucket == bucket), Decimal(0)))

    def reinstate(self, cover: str, on: date) -> Decimal:
        """Restores an eroded aggregate to its full amount; returns the additional premium for the rest of the term."""
        section = self.section(cover, on)
        if section.reinstatement is None:
            raise ValueError(f"{cover} has no reinstatement")
        if cover in self.reinstated:
            raise ValueError(f"{cover} has already been reinstated this term")
        state = self.cover_state(cover, on=on)
        self.reinstated[cover] = state.limit - self.remaining(cover, on=on)
        return self.round(self.refundable * section.reinstatement * self.days_remaining(on) / self.term_days())

    def excess_remaining(self, cover: str, on: date | None = None) -> Decimal | None:
        """What the insured still has to bear of an aggregate excess this term; None when the excess is per claim."""
        section = self.section(cover, on)
        if not section.excess.aggregate:
            return None
        ctx = context(self.product, self.inputs, self.selected)
        return max(Decimal(0), self.excess_for(section, ctx) - sum((c.excess for c in self.claims if c.cover == cover), Decimal(0)))

    def paid_by(self, on: date) -> Decimal:
        """Everything paid out on or before a date, whichever term the claim arose in."""
        return sum((a for c in self.history for d, a in c.payments if d <= on), Decimal(0))

    def claims_loading(self) -> Decimal:
        applicable = [m for count, m, unless in self.product.claims_loading if self.claims_in_term >= count and not self.unless(unless)]
        return applicable[-1] if applicable else Decimal(1)

    def claim(self, cover: str, claimed: Decimal, on: date, reported: date, evidence: set[str], item: dict | None = None, facts: dict | None = None) -> "ClaimResult":
        facts = facts or {}
        rules = self.rules(cover, on)  # the wording in force at the loss
        if rules is None:
            return ClaimResult("declined", reason=f"claims on {cover} are not declared")
        status = self.status(on)
        if status != "live":
            return ClaimResult("declined", reason=f"policy was {status} on {on.isoformat()}")
        section = self.section(cover, on)
        if section.item and item is None:
            return ClaimResult("declined", reason=f"{cover} is per {section.item}; say which {section.item} the claim is on")
        state = self.cover_state(cover, item, on)
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
        if rules.months is not None:
            monthly, payout = payout, payout * Decimal(evaluate(rules.months, ctx))
        row = next((r for r in rules.depreciation if r.condition is None or evaluate(r.condition, ctx)), None)
        if row is not None:
            payout = apply_row(payout, row, ctx)
        limit = self.remaining(cover, item, facts, on) if section.aggregate else state.limit
        if section.aggregate and limit == 0:
            where = f" for {section.per} {self.bucket(section, item, facts)}" if section.per else ""
            return ClaimResult("declined", reason=f"{cover} limit for the term is used up{where}")
        borne = Decimal(0)
        for clause in rules.pays:  # in the order the wording gives them
            if clause == "limit" and limit is not None:
                payout = min(payout, limit)
            elif isinstance(clause, tuple):  # ("cap", amount, condition): a sub-limit, for these claims only
                if clause[2] is None or evaluate(clause[2], ctx):
                    payout = min(payout, Decimal(evaluate(clause[1], ctx)))
            elif clause == "excess":
                borne = min(payout, self.excess_remaining(cover, on)) if section.excess.aggregate else self.excess_for(section, ctx)
                payout -= borne
            elif clause == "co-payment":
                for cp in rules.co_payments:
                    if cp.condition is None or evaluate(cp.condition, ctx):
                        payout *= 1 - Decimal(evaluate(cp.amount, ctx))
        if payout <= 0:
            if section.excess.aggregate:  # the claim still eats into what the insured bears this term
                self.claims.append(ClaimResult("declined", cover=cover, counted=False, excess=self.round(borne)))
            return ClaimResult("declined", reason="nothing is payable after the excess")
        result = ClaimResult("paid", self.round(payout), cover=cover, counted=bool(evaluate(rules.counts, ctx)), bucket=self.bucket(section, item, facts), excess=self.round(borne))
        result.payments = self.schedule(rules, ctx, on, result.amount, monthly) if rules.months is not None else [(on, result.amount)]
        self.claims.append(result)
        self.history.append(result)
        return result

    def schedule(self, rules, ctx: dict, on: date, total: Decimal, monthly: Decimal) -> list[tuple[date, Decimal]]:
        """A month's benefit at the end of each month after the deferred period, the last month's part last."""
        start = on
        if rules.after is not None:
            length, unit = int(evaluate(rules.after[0], ctx)), rules.after[1]
            start = add_months(on, length) if unit == "months" else on + timedelta(days=length * (7 if unit == "weeks" else 1))
        payments, paid, n = [], Decimal(0), 0
        while paid < total:
            n += 1
            amount = min(monthly, total - paid)
            payments.append((add_months(start, n), self.round(amount)))
            paid += amount
        return payments

    def accept_renewal(self, answers: dict | None = None) -> None:
        offer = self.renew(answers)
        if offer.needs:
            raise ValueError(f"renewal needs {', '.join(offer.needs)}")
        if offer.declined:
            raise ValueError(f"renewal declined: {offer.declined}")
        self.previous_terms.append((self.inception, self.expiry))
        self.inputs, self.product = offer.inputs, offer.version
        self.inception = self.paid_on = self.expiry
        self.charged = offer.premium
        self.claims = []
        self.reinstated = {}
