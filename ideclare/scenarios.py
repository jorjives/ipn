"""Runs the `scenario` blocks of a product and reports what did not match."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from . import engine
from .model import Product, Scenario, Step
from .parser import Line, given_value, unquote


@dataclass
class Result:
    scenario: Scenario
    failures: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failures


def run_all(product: Product) -> list[Result]:
    return [Run(product, s).run() for s in product.scenarios]


def money(v: Decimal) -> str:
    return f"{v:.2f}"


class Run:
    def __init__(self, product: Product, scenario: Scenario):
        self.product, self.scenario = product, scenario
        self.inputs = dict(scenario.given)
        self.selected = set(scenario.selected)
        self.result = Result(scenario)
        self.policy = engine.Policy(product, self.inputs, self.selected)
        self.last_date: date | None = None
        self.last_amount: Decimal | None = None

    def run(self) -> Result:
        for inp in self.product.inputs.values():  # free text is informational only
            if inp.kind == "text":
                self.inputs.setdefault(inp.name, "")
        missing = [n for n in self.product.inputs if n not in self.inputs]
        if missing:
            self.fail(self.scenario.line, f"given is missing {', '.join(missing)}")
            return self.result
        for step in self.scenario.steps:
            try:
                (self.when if step.tokens[0] == "when" else self.expect)(step)
            except Exception as e:  # a bad step must not stop the other scenarios
                self.fail(step.line, f"do not understand {' '.join(step.tokens)!r} ({e})")
        return self.result

    def fail(self, line: int, msg: str) -> None:
        self.result.failures.append(f"line {line}: {msg}")

    def check(self, step: Step, label: str, expected, actual) -> None:
        if expected != actual:
            self.fail(step.line, f"expected {label} {expected}, got {actual}")

    # --- when ---------------------------------------------------------------

    def when(self, step: Step) -> None:
        toks = step.tokens[1:]
        handler = getattr(self, "when_" + toks[0], None)
        if handler is None:
            raise ValueError("unknown event")
        on = date.fromisoformat(toks[toks.index("on") + 1])
        self.last_date = on
        handler(step, on, toks)

    def when_bound(self, step, on, toks):
        self.policy.bind(on, paid="unpaid" not in toks)

    def when_paid(self, step, on, toks):
        self.policy.pay(on)

    def when_cancelled(self, step, on, toks):
        self.last_amount = self.policy.cancel(on, toks[toks.index("by") + 1])

    def when_adjusted(self, step, on, toks):
        pairs = [t for t in toks[toks.index("with") + 1:] if t != ","]
        changes = {}
        for name, value in zip(pairs[::2], pairs[1::2]):
            changes[name] = given_value(Line(step.line, 0, ""), self.product.inputs[name], value)
        self.last_amount = self.policy.adjust(on, changes)

    def when_renewed(self, step, on, toks):
        offer = self.policy.renew()
        if offer.declined:
            self.fail(step.line, f"renewal was declined: {offer.declined}")
        else:
            self.policy.accept_renewal()

    # --- expect -------------------------------------------------------------

    def expect(self, step: Step) -> None:
        toks = step.tokens[1:]
        handler = getattr(self, "expect_" + toks[0], None)
        if handler is None:
            raise ValueError("unknown expectation")
        handler(step, toks[1:])

    def expect_eligible(self, step, rest):
        self._eligibility(step, "eligible")

    def expect_declined(self, step, rest):
        self._eligibility(step, "declined", rest)

    def expect_referred(self, step, rest):
        self._eligibility(step, "referred", rest)

    def _eligibility(self, step, outcome, rest=()):
        e = engine.check_eligibility(self.product, self.inputs)
        actual = e.outcome + (f" ({'; '.join(e.reasons)})" if e.reasons else "")
        if e.outcome != outcome:
            self.fail(step.line, f"expected {outcome}, got {actual}")
        elif rest and unquote(rest[0]) not in e.reasons:
            self.fail(step.line, f"expected reason {unquote(rest[0])!r}, got {actual}")

    def expect_cover(self, step, rest):
        name = unquote(rest[0])
        state = next(s for s in engine.cover_states(self.product, self.inputs, self.selected) if s.name == name)
        if rest[1] == "limit":
            self.check(step, f"{name} limit", Decimal(rest[2]), state.limit)
            return
        status = " ".join(unquote(t) for t in rest[1:2])
        actual = state.status + (f" ({state.reason})" if state.reason else "")
        if state.status != status:
            self.fail(step.line, f"expected {name} {status}, got {actual}")
        elif len(rest) > 2 and unquote(rest[2]) != state.reason:
            self.fail(step.line, f"expected {name} {status} {unquote(rest[2])!r}, got {actual}")

    # --- rating ---------------------------------------------------------------

    def quote(self) -> engine.Quote:
        return self.policy.quote

    def expect_premium(self, step, rest):
        self.check(step, "premium", money(Decimal(rest[0])), money(self.quote().total))

    def expect_net(self, step, rest):
        self.check(step, "net", money(Decimal(rest[0])), money(self.quote().net))

    def expect_tax(self, step, rest):
        self._line(step, "tax", rest)

    def expect_fee(self, step, rest):
        self._line(step, "fee", rest)

    def _line(self, step, kind, rest):
        label = unquote(rest[0])
        actual = dict(self.quote().lines).get(label)
        if actual is None:
            self.fail(step.line, f"no {kind} called {label!r} in the quote")
        else:
            self.check(step, f"{kind} {label}", money(Decimal(rest[1])), money(actual))

    def expect_factor(self, step, rest):
        label = unquote(rest[0])
        hit = next((t for t in self.quote().trail if t.label == label), None)
        if hit is None:
            self.fail(step.line, f"factor {label!r} was not applied")
        else:
            self.check(step, f"factor {label}", " ".join(rest[1:]), hit.applied)

    # --- lifecycle ------------------------------------------------------------

    def expect_status(self, step, rest):
        on = date.fromisoformat(rest[2]) if rest[1:2] == ["on"] else self.last_date or date.today()
        self.check(step, "status", rest[0], self.policy.status(on))

    def expect_expiry(self, step, rest):
        self.check(step, "expiry", rest[0], self.policy.expiry.isoformat())

    def expect_refund(self, step, rest):
        self.check(step, "refund", money(Decimal(rest[0])), money(self.last_amount))

    def expect_additional(self, step, rest):  # additional premium X
        self.check(step, "additional premium", money(Decimal(rest[1])), money(self.last_amount))

    def expect_return(self, step, rest):  # return premium X
        self.check(step, "return premium", money(Decimal(rest[1])), money(-self.last_amount))

    def expect_renewal(self, step, rest):
        offer = self.policy.renew()
        what = rest[0]
        if what == "declined":
            if not offer.declined:
                self.fail(step.line, f"expected renewal declined, got offered at {money(offer.premium)}")
            elif len(rest) > 1 and unquote(rest[1]) != offer.declined:
                self.fail(step.line, f"expected renewal declined {unquote(rest[1])!r}, got {offer.declined!r}")
        elif offer.declined:
            self.fail(step.line, f"expected renewal {' '.join(rest)}, got declined: {offer.declined}")
        elif what == "premium":
            self.check(step, "renewal premium", money(Decimal(rest[1])), money(offer.premium))
        elif what == "invite":
            self.check(step, "renewal invite", rest[1], offer.invite_date.isoformat())
        elif what != "offered":
            raise ValueError("expected renewal premium|invite|declined|offered")
