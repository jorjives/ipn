"""Applies a Product to a risk: eligibility, covers, rating, lifecycle and claims."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

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
