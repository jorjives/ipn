"""Applies a Product to a risk: eligibility, covers, rating, lifecycle and claims."""
from __future__ import annotations

from dataclasses import dataclass, field
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
            trail.append(Trail(step.label, f"{row.op} {str(amount)}", net))
        elif step.kind == "add":
            amount = value(step.amount)
            net += amount
            trail.append(Trail(step.label or "add", f"+ {str(amount)}", net))
        elif step.kind in ("discount", "load"):
            pct = value(step.amount)
            mult = (1 - pct) if step.kind == "discount" else (1 + pct)
            net *= mult
            trail.append(Trail(step.label or step.kind, f"x {str(mult)}", net))
        elif step.kind == "minimum":
            floor = value(step.amount)
            net = max(net, floor)
            trail.append(Trail(step.label or "minimum", str(floor), net))
        elif step.kind == "tax":
            lines.append((step.label, net * value(step.amount)))
        elif step.kind == "fee":
            lines.append((step.label, value(step.amount)))
        elif step.kind == "round":
            quantum = value(step.amount)

    net = net.quantize(quantum, ROUNDING)
    lines = [(label, amount.quantize(quantum, ROUNDING)) for label, amount in lines]
    return Quote(net, lines, net + sum((a for _, a in lines), Decimal(0)), trail)
