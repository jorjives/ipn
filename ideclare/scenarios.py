"""Runs the `scenario` blocks of a product and reports what did not match."""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from datetime import date
from decimal import Decimal

from . import engine
from .model import Product, Scenario, Step
from .parser import Line, given_value, unquote, with_defaults


DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


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
        self.inputs = with_defaults(product.inputs, scenario.given)
        self.selected = set(scenario.selected)
        self.result = Result(scenario)
        self.policy = engine.Policy(product, self.inputs, self.selected)
        self.last_date: date | None = None
        self.last_amount: Decimal | None = None
        self.last_claim: engine.ClaimResult | None = None
        self.last_refusal: str | None = None

    def run(self) -> Result:
        for inp in self.product.inputs.values():
            if inp.kind == "text":  # free text is informational only
                self.inputs.setdefault(inp.name, "")
            elif inp.kind == "collection":  # bounds are checked by eligibility
                self.inputs.setdefault(inp.name, [])
        missing = [n for n, inp in self.product.inputs.items() if n not in self.inputs and not inp.provided and inp.kind != "calculated"]  # a missing provided field is an unavailable lookup
        if missing:
            self.fail(self.scenario.line, f"given is missing {', '.join(missing)}")
            return self.result
        for i, step in enumerate(self.scenario.steps):
            following = self.scenario.steps[i + 1].tokens[:2] if i + 1 < len(self.scenario.steps) else []
            try:
                if step.tokens[0] == "when":
                    self.last_refusal = None
                    self.when(step)
                else:
                    self.expect(step)
            except ValueError as e:
                if step.tokens[0] == "when" and following == ["expect", "refused"]:
                    self.last_refusal = str(e)  # the scenario says this event should be refused
                else:
                    self.fail(step.line, f"do not understand {' '.join(step.tokens)!r} ({e})")
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
        dates = [t for t in toks if DATE.fullmatch(t)]
        if not dates:
            raise ValueError("every event needs 'on YYYY-MM-DD'")
        on = date.fromisoformat(dates[0])
        self.last_date = on
        handler(step, on, toks)

    def when_bound(self, step, on, toks):
        self.policy.bind(on, paid="unpaid" not in toks)

    def when_paid(self, step, on, toks):
        self.policy.pay(on)

    def when_accepted(self, step, on, toks):
        # accepted by underwriter on DATE [with load N% | discount N% | excess AMOUNT on Cover | excluding Cover, ...]
        if toks[1:3] != ["by", "underwriter"]:
            raise ValueError("expected 'accepted by underwriter on DATE [with ...]'")
        terms = engine.Underwriting()
        groups = [[]]
        for t in toks[toks.index("with") + 1:] if "with" in toks else []:
            groups.append([]) if t == "," else groups[-1].append(t)
        for words in filter(None, groups):
            if len(words) == 3 and words[0] in ("load", "discount") and words[2] == "%":
                terms.load += Decimal(words[1]) * Decimal("0.01") * (1 if words[0] == "load" else -1)  # 20 -> 0.20, so the trail reads x 1.20
            elif len(words) == 4 and words[0] == "excess" and words[2] == "on":
                terms.excess[unquote(words[3])] = Decimal(words[1])
            elif len(words) == 2 and words[0] == "excluding":
                terms.excluded.add(unquote(words[1]))
            else:
                raise ValueError(f"underwriter terms are 'load N%', 'discount N%', 'excess AMOUNT on Cover' or 'excluding Cover', not {' '.join(words)!r}")
        for name in list(terms.excess) + list(terms.excluded):
            self.product.cover(name)  # unknown covers are an error here, not at the claim
        self.policy.accept(terms)

    def when_reinstated(self, step, on, toks):  # reinstated Cover on DATE
        self.last_amount = self.policy.reinstate(unquote(toks[1]), on)

    def when_declined(self, step, on, toks):
        if toks[1:3] != ["by", "underwriter"]:
            raise ValueError("expected 'declined by underwriter on DATE'")
        self.policy.decline_by_underwriter()

    def when_cancelled(self, step, on, toks):
        self.last_amount = self.policy.cancel(on, toks[toks.index("by") + 1])

    def item(self, toks: list[str]) -> tuple[str, dict]:
        """`... on bike 2 ...` -> (collection name, that item)."""
        singular = toks[toks.index("on") + 1]
        coll = self.product.collection_for(singular)
        if coll is None:
            raise ValueError(f"{singular!r} is not an item")
        number = int(toks[toks.index("on") + 2])
        items = self.policy.inputs[coll.name]
        if not 1 <= number <= len(items):
            raise ValueError(f"there is no {singular} {number}; the policy has {len(items)}")
        return coll.name, items[number - 1]

    def when_adjusted(self, step, on, toks):
        # adjusted on DATE with a 1, b 2 | adding <item> a 1, b 2 | removing <item> N
        line = Line(step.line, 0, "")
        how = next((t for t in toks if t in ("with", "adding", "removing")), None)
        if how is None:
            raise ValueError("expected 'with ...', 'adding <item> ...' or 'removing <item> N'")
        rest = toks[toks.index(how) + 1:]
        changes = {}
        if how == "with":
            pairs = [t for t in rest if t != ","]
            for name, value in zip(pairs[::2], pairs[1::2]):
                changes[name] = given_value(line, self.product.inputs[name], value)
        else:
            coll = self.product.collection_for(rest[0])
            if coll is None:
                raise ValueError(f"{rest[0]!r} is not an item")
            items = self.policy.inputs[coll.name]
            if how == "adding":
                pairs = [t for t in rest[1:] if t != ","]
                item = {name: given_value(line, coll.fields[name], value) for name, value in zip(pairs[::2], pairs[1::2])}
                changes[coll.name] = items + [item]
            else:
                number = int(rest[1])
                if not 1 <= number <= len(items):
                    raise ValueError(f"there is no {rest[0]} {number}; the policy has {len(items)}")
                changes[coll.name] = items[:number - 1] + items[number:]
        self.last_amount = self.policy.adjust(on, changes)

    def when_claim(self, step, on, toks):
        # claim <Cover> [on <item> N] for <amount> on <date> [reported <date>] [with a, b]
        cover = unquote(toks[1])
        amount = Decimal(toks[toks.index("for") + 1]) if "for" in toks else Decimal(0)  # a fixed benefit claims nothing
        item = self.item(toks)[1] if toks[2:3] == ["on"] and not DATE.fullmatch(toks[3]) else None
        reported = date.fromisoformat(toks[toks.index("reported") + 1]) if "reported" in toks else on
        evidence, facts = set(), {}
        asks = self.product.claims[cover].asks if cover in self.product.claims else {}
        groups = [[]]
        for t in toks[toks.index("with") + 1:] if "with" in toks else []:
            groups.append([]) if t == "," else groups[-1].append(t)
        for words in filter(None, groups):
            if len(words) == 2 and words[0] in asks:
                facts[words[0]] = given_value(Line(step.line, 0, ""), asks[words[0]], words[1])
            elif len(words) == 1:
                evidence.add(words[0])
            else:
                raise ValueError(f"expected an evidence word or 'fact value' after with, not {' '.join(words)!r}")
        self.last_claim = self.policy.claim(cover, amount, on, reported, evidence, item, facts)
        self.last_amount = self.last_claim.amount

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

    def expect_refused(self, step, rest):
        if self.last_refusal is None:
            self.fail(step.line, "the last event was not refused")
        elif rest and unquote(rest[0]) != self.last_refusal:
            self.fail(step.line, f"expected refused {unquote(rest[0])!r}, got {self.last_refusal!r}")

    def expect_eligible(self, step, rest):
        self._eligibility(step, "eligible")

    def expect_declined(self, step, rest):
        self._eligibility(step, "declined", rest)

    def expect_referred(self, step, rest):
        self._eligibility(step, "referred", rest)

    def _eligibility(self, step, outcome, rest=()):
        e = engine.check_eligibility(self.product, self.inputs, self.selected)
        actual = e.outcome + (f" ({'; '.join(e.reasons)})" if e.reasons else "")
        if e.outcome != outcome:
            self.fail(step.line, f"expected {outcome}, got {actual}")
        elif rest and unquote(rest[0]) not in e.reasons:
            self.fail(step.line, f"expected reason {unquote(rest[0])!r}, got {actual}")

    def expect_cover(self, step, rest):
        name = unquote(rest[0])
        item = None
        if rest[1:2] == ["on"]:
            item, rest = self.item(rest)[1], rest[:1] + rest[4:]
        state = self.policy.cover_state(name, item)
        if rest[1] == "limit":
            self.check(step, f"{name} limit", Decimal(rest[2]), state.limit)
            return
        if rest[1:3] == ["excess", "remaining"]:
            self.check(step, f"{name} excess remaining", money(Decimal(rest[3])), money(self.policy.excess_remaining(name)))
            return
        if rest[1] == "remaining":  # remaining X [for <fact> value]
            facts = {}
            if rest[3:4] == ["for"]:
                asks = self.product.claims[name].asks
                facts[rest[4]] = given_value(Line(step.line, 0, ""), asks[rest[4]], rest[5])
            self.check(step, f"{name} remaining", money(Decimal(rest[2])), money(self.policy.remaining(name, item, facts)))
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
        self.check(step, "premium", money(Decimal(rest[0])), money(self.policy.premium))

    def expect_instalment(self, step, rest):  # instalment charge X | instalment N X
        lc = self.product.lifecycle
        if not lc.instalments:
            raise ValueError("the product has no instalments line in its lifecycle")
        charge, parts = engine.instalments(self.policy.premium, lc.instalments, lc.instalment_charge)
        if rest[0] == "charge":
            self.check(step, "instalment charge", money(Decimal(rest[1])), money(charge))
        elif rest[0].isdigit() and 1 <= int(rest[0]) <= len(parts):
            self.check(step, f"instalment {rest[0]}", money(Decimal(rest[1])), money(parts[int(rest[0]) - 1]))
        else:
            raise ValueError(f"expected 'instalment charge X' or 'instalment N X' with N from 1 to {len(parts)}")

    def expect_net(self, step, rest):  # net X | net for <item> N X
        if rest[:1] == ["for"]:
            label = f"{rest[1]} {rest[2]}"
            hit = next((t for t in self.quote().trail if t.label == label and t.applied == "net"), None)
            if hit is None:
                self.fail(step.line, f"no {label} was rated")
            else:
                self.check(step, f"net for {label}", money(Decimal(rest[3])), money(hit.net))
            return
        self.check(step, "net", money(Decimal(rest[0])), money(self.quote().net))

    def expect_currency(self, step, rest):
        self.check(step, "currency", rest[0], self.quote().currency)

    def expect_tax(self, step, rest):
        self._line(step, "tax", rest)

    def expect_fee(self, step, rest):
        self._line(step, "fee", rest)

    def expect_commission(self, step, rest):
        self._line(step, "commission", rest)

    def _line(self, step, kind, rest):
        label = unquote(rest[0])
        q = self.quote()
        actual = dict(q.commission if kind == "commission" else q.lines).get(label)
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
        if rest[1:2] == ["on"]:
            on = date.fromisoformat(rest[2])
        elif self.last_date is not None:
            on = self.last_date
        else:
            raise ValueError("say 'expect status X on YYYY-MM-DD' before any event has happened")
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

    # --- claims ---------------------------------------------------------------

    def expect_payout(self, step, rest):
        c = self.last_claim
        if c.status != "paid":
            self.fail(step.line, f"expected payout {rest[0]}, got declined: {c.reason}")
        else:
            self.check(step, "payout", money(Decimal(rest[0])), money(c.amount))

    def expect_benefit(self, step, rest):  # benefit paid AMOUNT by DATE
        if rest[:1] != ["paid"] or rest[2:3] != ["by"]:
            raise ValueError("expected 'benefit paid AMOUNT by YYYY-MM-DD'")
        self.check(step, f"benefit paid by {rest[3]}", money(Decimal(rest[1])), money(self.policy.paid_by(date.fromisoformat(rest[3]))))

    def expect_claim(self, step, rest):
        c = self.last_claim
        actual = c.status + (f": {c.reason}" if c.reason else f" {money(c.amount)}")
        if rest[0] != c.status:
            self.fail(step.line, f"expected claim {rest[0]}, got {actual}")
        elif len(rest) > 1 and unquote(rest[1]) != c.reason:
            self.fail(step.line, f"expected claim declined {unquote(rest[1])!r}, got {actual}")

    def expect_claims(self, step, rest):  # claims in term N
        self.check(step, "claims in term", int(rest[-1]), self.policy.claims_in_term)
