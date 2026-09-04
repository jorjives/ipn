"""Runs the `scenario` blocks of a product and reports what did not match."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from . import engine
from .model import Product, Scenario, Step
from .parser import unquote


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
        raise ValueError("no lifecycle events yet")

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
