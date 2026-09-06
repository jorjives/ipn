"""Turns .idl text into a Product. Line-oriented, indentation-based."""
from __future__ import annotations

import copy
import csv
import os
import re
from datetime import date
from decimal import Decimal
from dataclasses import dataclass, field

from .expr import ExprError, lookups, names, parse_expr
from .tables import TableError, load_table
from .model import Enrichment, Cancellation, ClaimRule, Cover, Excess, FactorRow, Input, Product, RatingStep, Rule, Scenario, Step


class ParseError(Exception):
    pass


@dataclass
class Line:
    number: int
    indent: int
    text: str
    children: list["Line"] = field(default_factory=list)

    def error(self, msg: str) -> ParseError:
        return ParseError(f"line {self.number}: {msg}")


def _strip_comment(raw: str) -> str:
    out, quoted = [], False
    for ch in raw:
        if ch == '"':
            quoted = not quoted
        if ch == "#" and not quoted:
            break
        out.append(ch)
    return "".join(out).rstrip()


def build_tree(text: str) -> list[Line]:
    """Nest lines by indentation. Any deeper indent is a child; dedent must match an ancestor."""
    root = Line(0, -1, "")
    stack = [root]
    for number, raw in enumerate(text.splitlines(), start=1):
        body = _strip_comment(raw)
        if not body.strip():
            continue
        indent = len(body) - len(body.lstrip(" "))
        line = Line(number, indent, body.strip())
        while stack[-1].indent >= indent:
            stack.pop()
        parent = stack[-1]
        if parent.children and parent.children[-1].indent != indent:
            raise line.error("inconsistent indentation")
        parent.children.append(line)
        stack.append(line)
    return root.children


# --- statement tokens -------------------------------------------------------

DATE_TOKEN = re.compile(r'\d{4}-\d{2}-\d{2}')
TOKEN = re.compile(r'\s*(?:(?P<str>"[^"]*")|(?P<date>\d{4}-\d{2}-\d{2})|(?P<num>\d+(?:\.\d+)?)|(?P<id>co-payment|[A-Za-z_][A-Za-z0-9_/]*)|(?P<op><=|>=|[<>:,%()+\-*/^]))')


def tokens(line: Line) -> list[str]:
    out, pos = [], 0
    while pos < len(line.text):
        m = TOKEN.match(line.text, pos)
        if not m or m.end() == pos:
            raise line.error(f"cannot read {line.text[pos:]!r}")
        out.append(m.group(0).strip())
        pos = m.end()
    return out


def unquote(tok: str) -> str:
    return tok[1:-1] if tok.startswith('"') else tok


# --- blocks -----------------------------------------------------------------

INPUT_KINDS = {"money", "integer", "number", "text", "yes/no", "date"}


def parse_product_header(line: Line, product: Product) -> None:
    for child in line.children:
        toks = tokens(child)
        key = toks[0]
        if key == "territory" and len(toks) == 2:
            product.territory = toks[1]
        elif key == "currency" and len(toks) == 2:
            product.currency = toks[1]
        elif key == "term" and len(toks) == 3 and toks[2] in ("days", "months", "years"):
            product.term = (parse_expr([toks[1]])[0], toks[2])
        elif key == "term" and toks[1:2] == ["until"] and len(toks) == 3:
            product.term = (parse_expr([toks[2]])[0], "until")
        else:
            raise child.error(f"unknown product setting {child.text!r}")


def parse_inputs(line: Line, product: Product) -> None:
    product.inputs.update(parse_input_lines(line.children))
    for coll in product.collections:
        clash = set(coll.fields) & (set(product.inputs) - {coll.name})
        if clash:
            raise line.error(f"{coll.name} field {sorted(clash)[0]!r} has the same name as an input")
    # Calculated fields are parsed once every input is known, so their steps can use the other fields.
    for child in line.children:
        toks = tokens(child)
        if toks[2:] == ["calculated"]:
            product.inputs[toks[0]].steps = calculated_steps(child, product)
        for sub in child.children:
            toks = tokens(sub)
            if toks[2:] == ["calculated"]:
                product.inputs[tokens(child)[0]].fields[toks[0]].steps = calculated_steps(sub, product)


def calculated_steps(line: Line, product: Product) -> list[RatingStep]:
    if not line.children:
        raise line.error(f"{tokens(line)[0]} needs its steps indented below it, e.g. base value")
    return parse_rating_steps(line.children, product, per_item=True)


def parse_input_lines(lines: list[Line], nested: bool = False) -> dict[str, Input]:
    inputs = {}
    for child in lines:
        toks = tokens(child)
        if len(toks) < 3 or toks[1] != ":":
            raise child.error("expected 'name: type'")
        name, kind = toks[0], toks[2]
        if kind == "choice":
            if len(toks) < 5 or toks[3] != "of":
                raise child.error("expected 'choice of a, b, c'")
            inputs[name] = Input(name, "choice", [t for t in toks[4:] if t != ","])
        elif kind == "collection" and not nested:
            inputs[name] = parse_collection(child, name, toks[3:])
        elif kind in INPUT_KINDS and len(toks) == 3:
            inputs[name] = Input(name, kind)
        elif kind == "calculated" and len(toks) == 3:
            inputs[name] = Input(name, "calculated")
        else:
            raise child.error(f"unknown input type {' '.join(toks[2:])!r}")
    return inputs


def parse_collection(line: Line, name: str, toks: list[str]) -> Input:
    """collection of bike[, 1 to 5 | , at least 1 | , at most 5] with the item's fields indented below."""
    if toks[:1] != ["of"] or len(toks) < 2:
        raise line.error("expected 'collection of <item name>'")
    coll = Input(name, "collection", singular=toks[1], fields=parse_input_lines(line.children, nested=True))
    bounds = toks[2:]
    if bounds[:1] == [","]:
        bounds = bounds[1:]
    if not bounds:
        pass
    elif len(bounds) == 3 and bounds[1] == "to":
        coll.min_items, coll.max_items = int(bounds[0]), int(bounds[2])
    elif len(bounds) == 3 and bounds[:2] == ["at", "least"]:
        coll.min_items = int(bounds[2])
    elif len(bounds) == 3 and bounds[:2] == ["at", "most"]:
        coll.max_items = int(bounds[2])
    else:
        raise line.error("expected ', 1 to 5', ', at least 1' or ', at most 5'")
    if not coll.fields:
        raise line.error(f"{name} needs at least one field indented below it")
    return coll


# --- expressions and rules ---------------------------------------------------

# Words an expression may use besides inputs, choices and cover names.
CONTEXT_WORDS = {"claim", "claimed", "yes", "no", "claims_in_term", "days_to_report", "days_since_inception", "months_since_inception", "days_in_force", "months_in_force"}


def fold_phrases(toks: list[str]) -> list[str]:
    """Rewrites English phrases into the words the expression language understands."""
    out, i = [], 0
    while i < len(toks):
        if toks[i:i + 3] == ["claims", "in", "term"]:
            out.append("claims_in_term")
            i += 3
        elif toks[i:i + 2] == ["reported", "after"] and toks[i + 3:i + 4] == ["days"]:
            out += ["days_to_report", ">", toks[i + 2]]
            i += 4
        elif toks[i:i + 1] == ["within"] and toks[i + 2:i + 3] in (["days"], ["months"]) and toks[i + 3:i + 5] == ["of", "inception"]:
            out += [f"{toks[i + 2]}_since_inception", "<", toks[i + 1]]
            i += 5
        elif toks[i:i + 1] in (["days"], ["months"]) and toks[i + 1:i + 3] == ["in", "force"]:
            out.append(f"{toks[i]}_in_force")
            i += 3
        else:
            out.append(toks[i])
            i += 1
    return out


TIME_WORDS = {"days_in_force", "months_in_force"}  # the policy's age, known when it is cancelled


def find_input(product: Product, name: str) -> Input | None:
    """An input, item field or enrichment-provided field by name; the policy's age reads as a number."""
    if name in product.inputs:
        return product.inputs[name]
    if name in TIME_WORDS:
        return Input(name, "number")
    return next((c.fields[name] for c in product.collections if name in c.fields), None)


def known_words(product: Product) -> set[str]:
    words = set(CONTEXT_WORDS) | set(product.inputs)
    for inp in product.inputs.values():
        words |= set(inp.choices)
        if inp.kind == "collection":
            words.add(inp.singular)
            words |= set(inp.fields)
            for f in inp.fields.values():
                words |= set(f.choices)
    words |= {c.name for c in product.covers}
    return words


def expression(line: Line, toks: list[str], product: Product, stop: set[str] = frozenset(), extra: set[str] = frozenset()) -> tuple[tuple, list[str]]:
    try:
        node, rest = parse_expr(fold_phrases(toks), stop)
    except ExprError as e:
        raise line.error(str(e))
    unknown = names(node) - known_words(product) - extra
    if unknown:
        raise line.error(f"unknown word {sorted(unknown)[0]!r}")
    for column, table in sorted(lookups(node)):
        if table not in product.tables:
            raise line.error(f"unknown table {table!r}")
        if column not in product.tables[table].values:
            raise line.error(f"{table!r} has no column {column!r}; its values are {', '.join(product.tables[table].values)}")
    for table, key in interpolations(node):
        if key not in product.tables[table].keys:
            raise line.error(f"{table!r} is not keyed on {key}; its keys are {', '.join(product.tables[table].keys)}")
    return node, rest


def interpolations(node: tuple) -> set[tuple[str, str]]:
    """Every (table, key) the expression interpolates on."""
    if node[0] == "interp":
        return {(node[2], node[3])}
    if node[0] == "fn":
        return set().union(*(interpolations(a) for a in node[2]))
    return set().union(*(interpolations(c) for c in node[1:] if isinstance(c, tuple)))


def rule(line: Line, kind: str, toks: list[str], product: Product, extra: set[str] = frozenset()) -> Rule:
    """`<kind> when <condition> because "reason"`; toks start after <kind>."""
    if toks[:1] != ["when"]:
        raise line.error(f"expected '{kind} when ...'")
    cond, rest = expression(line, toks[1:], product, stop={"because"}, extra=extra)
    if len(rest) != 2 or rest[0] != "because" or not rest[1].startswith('"'):
        raise line.error('expected because "reason"')
    return Rule(kind, cond, unquote(rest[1]), line.number)


def parse_eligibility(line: Line, product: Product) -> None:
    for child in line.children:
        toks = tokens(child)
        if toks[0] not in ("decline", "refer"):
            raise child.error("expected 'decline when ...' or 'refer when ...'")
        product.eligibility.append(rule(child, toks[0], toks[1:], product))


def parse_cover(line: Line, product: Product) -> None:
    toks = tokens(line)
    if len(toks) not in (2, 3) or (len(toks) == 3 and toks[2] != "optional"):
        raise line.error('expected: cover Name [optional]')
    cover = Cover(unquote(toks[1]), optional=len(toks) == 3)
    product.covers.append(cover)  # before parsing children so "X selected" can name it
    for child in line.children:
        toks = tokens(child)
        key = "excess" if toks[0] == "deductible" else toks[0]
        if key == "limit":
            cover.limit, rest = expression(child, toks[1:], product, stop={"per"})
            if rest == ["per", "term"]:
                cover.aggregate, rest = True, []
        elif key == "excess" and len(toks) == 1 and child.children:
            # A table of rows may use facts a claim asks for, which are declared later: parse it last.
            product.deferred.append(lambda line=child: parse_excess_table(line, cover, product))
            rest = []
        elif key == "excess":
            cover.excess.amount, rest = expression(child, toks[1:], product, stop={","})
            for bound in ("minimum", "maximum"):
                if rest[:2] == [",", bound]:
                    node, rest = expression(child, rest[2:], product, stop={","})
                    setattr(cover.excess, bound, node)
        elif key == "excludes":
            cover.exclusions.append(rule(child, "excludes", toks[1:], product))
            rest = []
        elif key == "available" and toks[1:2] == ["when"]:
            cover.available, rest = expression(child, toks[2:], product)
        elif toks[:3] == ["in", "force", "from"]:
            cover.from_, rest = expression(child, toks[3:], product)
        elif toks[:3] == ["in", "force", "until"]:
            cover.until, rest = expression(child, toks[3:], product)
        elif toks[:2] == ["waiting", "period"] and toks[3:] == ["days"]:
            cover.waiting_days, rest = int(toks[2]), []
        else:
            raise child.error(f"unknown cover setting {child.text!r}")
        if rest:
            raise child.error(f"unexpected {' '.join(rest)!r}")
    used = set().union(*(names(n) for n in (cover.limit, cover.available, cover.from_, cover.until, cover.excess.amount, cover.excess.minimum) if n is not None),
                       *(names(r.condition) for r in cover.exclusions))
    cover.item = next((c.singular for c in product.collections if used & set(c.fields)), "")


def claim_facts(product: Product, cover: str) -> set[str]:
    """Words a claim on this cover asks for: the fact names and their choice values."""
    rule_ = product.claims.get(cover)
    return set(rule_.asks) | {c for f in rule_.asks.values() for c in f.choices} if rule_ else set()


def parse_excess_table(line: Line, cover: Cover, product: Product) -> None:
    """Rows of `condition: amount` with `otherwise: amount` last, like a factor without the x."""
    facts = claim_facts(product, cover.name)
    for child in line.children:
        toks = tokens(child)
        if cover.excess.rows and cover.excess.rows[-1].condition is None:
            raise child.error("'otherwise' must be the last row")
        if toks[:2] == ["otherwise", ":"]:
            cond, rest = None, toks[2:]
        else:
            cond, rest = expression(child, toks, product, stop={":"}, extra=facts)
            rest = rest[1:]
        amount, rest = expression(child, rest, product, extra=facts)
        if rest:
            raise child.error(f"unexpected {' '.join(rest)!r}")
        cover.excess.rows.append(FactorRow(cond, "=", amount))
    if not cover.excess.rows or cover.excess.rows[-1].condition is not None:
        raise line.error("an excess table must end with an 'otherwise' row; a claim no row matches would otherwise carry no excess")


def parse_factor(line: Line, label: str, product: Product, extra: set[str] = frozenset()) -> RatingStep:
    step = RatingStep("factor", label, line=line.number)
    for child in line.children:
        toks = tokens(child)
        if step.rows and step.rows[-1].condition is None:
            raise child.error("'otherwise' must be the last row")
        if toks[:2] == ["otherwise", ":"]:
            cond, rest = None, toks[2:]
        else:
            cond, rest = expression(child, toks, product, stop={":"}, extra=extra)
            rest = rest[1:]
        if len(rest) < 2 or rest[0] not in ("x", "+", "-"):
            raise child.error("expected ': x 1.25' or ': + 10' or ': - 10'")
        op = rest[0]
        amount, rest = expression(child, rest[1:], product, extra=extra)
        if rest:
            raise child.error(f"unexpected {' '.join(rest)!r}")
        step.rows.append(FactorRow(cond, op, amount))
    if not step.rows:
        raise line.error("factor needs at least one row")
    return step


def parse_rating(line: Line, product: Product) -> None:
    product.rating.extend(parse_rating_steps(line.children, product))


PER_ITEM_STEPS = {"base", "factor", "add", "discount", "load", "minimum", "maximum"}


ITEM_WORDS = {"position"}  # words only meaningful inside 'for each'


def parse_order(line: Line, toks: list[str], product: Product) -> list[tuple[tuple, bool]]:
    """`ordered by <key> [descending], <key> [descending] ...`; toks start after `ordered by`."""
    order = []
    while toks:
        key, toks = expression(line, toks, product, stop={",", "descending"})
        descending = toks[:1] == ["descending"]
        order.append((key, descending))
        toks = toks[1:] if descending else toks
        if toks[:1] == [","]:
            toks = toks[1:]
        elif toks:
            raise line.error(f"unexpected {' '.join(toks)!r}")
    if not order:
        raise line.error("expected 'ordered by <field>'")
    return order


def parse_rating_steps(lines: list[Line], product: Product, per_item: bool = False, extra: set[str] = frozenset()) -> list[RatingStep]:
    steps = []
    for child in lines:
        toks = tokens(child)
        kind, rest = toks[0], toks[1:]
        label = ""
        if rest and rest[0].startswith('"'):
            label, rest = unquote(rest[0]), rest[1:]
        step = RatingStep(kind, label, line=child.number)
        if per_item and kind not in PER_ITEM_STEPS:
            raise child.error(f"{kind!r} cannot be used inside 'for each'; only {', '.join(sorted(PER_ITEM_STEPS))}")
        if toks[:2] == ["for", "each"] and len(toks) >= 3 and not per_item:
            if product.collection_for(toks[2]) is None:
                raise child.error(f"unknown item {toks[2]!r}; declare a collection of {toks[2]}")
            order = []
            if toks[3:6] == [",", "ordered", "by"]:
                order = parse_order(child, toks[6:], product)
            elif toks[3:]:
                raise child.error(f"unexpected {' '.join(toks[3:])!r}; use 'for each {toks[2]}, ordered by ...'")
            step = RatingStep("each", toks[2], steps=parse_rating_steps(child.children, product, per_item=True, extra=ITEM_WORDS), order=order, line=child.number)
        elif kind == "factor" and rest and rest[0] in ("x", "+", "-"):  # one row: factor "Label" x <amount> [when ...]
            op, rest = rest[0], rest[1:]
            amount, rest = expression(child, rest, product, stop={"when"}, extra=extra)
            step.rows = [FactorRow(None, op, amount)]
            if rest[:1] == ["when"]:
                step.condition, rest = expression(child, rest[1:], product, extra=extra)
            if rest:
                raise child.error(f"unexpected {' '.join(rest)!r}")
        elif kind == "factor":
            step = parse_factor(child, label, product, extra)
        elif kind in ("base", "add", "discount", "load", "minimum", "maximum"):
            step.amount, rest = expression(child, rest, product, stop={"when"}, extra=extra)
            if rest[:1] == ["when"]:
                step.condition, rest = expression(child, rest[1:], product, extra=extra)
            if rest:
                raise child.error(f"unexpected {' '.join(rest)!r}")
        elif kind in ("tax", "fee", "commission"):
            if kind == "tax" and not label and rest and rest[0][0].isalpha():
                label, rest = rest[0], rest[1:]  # tax IPT 12%
            if not label:
                raise child.error(f'{kind} needs a name, e.g. {kind} "Label" ...')
            step.label = label
            step.amount, rest = expression(child, rest, product)
            if rest:
                raise child.error(f"unexpected {' '.join(rest)!r}")
        elif kind == "round" and rest[:1] == ["to"]:
            step.amount, rest = expression(child, rest[1:], product)
        else:
            raise child.error(f"unknown rating step {kind!r}")
        steps.append(step)
    return steps


def parse_lifecycle(line: Line, product: Product) -> None:
    lc = product.lifecycle
    for child in line.children:
        toks = tokens(child)
        words = " ".join(toks)
        if toks[:2] == ["cooling", "off"] and toks[3:] == ["days", ",", "full", "refund"]:
            lc.cooling_off_days = int(toks[2])
        elif toks[:2] == ["cancellation", "by"] and toks[2] in ("customer", "insurer") and toks[3] == ":":
            lc.cancellation[toks[2]] = parse_cancellation(child, toks[4:], product)
        elif toks[:2] == ["adjustment", ":"]:
            if toks[2:] == ["not", "allowed"]:
                lc.adjustment_allowed = False
            elif toks[2:8] == ["reprice", ",", "charge", "pro", "rata", "difference"]:
                lc.adjustment_allowed = True
                lc.adjustment_fee = parse_fee(child, toks[8:])
            else:
                raise child.error("expected 'adjustment: reprice, charge pro rata difference[, fee N]' or 'adjustment: not allowed'")
        elif toks[:4] == ["lapse", "when", "unpaid", "after"] and toks[5:] == ["days"]:
            lc.lapse_days = int(toks[4])
        elif toks == ["renewal"]:
            parse_renewal(child, product)
        elif toks == ["renewal", ":", "none"]:
            lc.renewable = False
        elif toks[:1] == ["instalments"]:
            well_formed = len(toks) > 2 and toks[1].isdigit() and toks[2] == "monthly" and (not toks[3:] or toks[3:5] == [",", "charge"] and toks[6:] == ["%"])
            if not well_formed:
                raise child.error("expected 'instalments N monthly' optionally ', charge P%'")
            lc.instalments = int(toks[1])
            if toks[3:]:
                lc.instalment_charge = Decimal(toks[5]) / 100
        else:
            raise child.error(f"unknown lifecycle setting {words!r}")


def parse_fee(line: Line, toks: list[str]) -> Decimal:
    if not toks:
        return Decimal(0)
    if len(toks) == 3 and toks[:2] == [",", "fee"]:
        return Decimal(toks[2])
    raise line.error(f"expected ', fee N' not {' '.join(toks)!r}")


def parse_cancellation(line: Line, toks: list[str], product: Product) -> Cancellation:
    if toks[:3] == ["refund", "pro", "rata"]:
        return Cancellation("pro rata", parse_fee(line, toks[3:]))
    if toks[:2] == ["full", "refund"]:
        return Cancellation("full", parse_fee(line, toks[2:]))
    if toks[:2] == ["no", "refund"]:
        return Cancellation("none", parse_fee(line, toks[2:]))
    if toks[:1] == ["refund"] and len(toks) > 1:  # a share of the earning premium: 50%, or a short-rate table over months in force
        amount, rest = expression(line, toks[1:], product, stop={","})
        return Cancellation("amount", parse_fee(line, rest), amount)
    raise line.error("expected 'refund pro rata', 'full refund', 'no refund' or 'refund <share>', optionally ', fee N'")


def parse_renewal(line: Line, product: Product) -> None:
    lc = product.lifecycle
    for child in line.children:
        toks = tokens(child)
        if toks[:1] == ["invite"] and toks[2:] == ["days", "before", "expiry"]:
            lc.renewal_invite_days = int(toks[1])
        elif toks[:3] == ["increase", "capped", "at"] and toks[4:] == ["%"]:
            lc.renewal_cap = Decimal(toks[3]) / 100
        elif toks[:3] == ["decrease", "collared", "at"] and toks[4:] == ["%"]:
            lc.renewal_collar = Decimal(toks[3]) / 100
        elif toks[:1] == ["decline"]:
            lc.renewal_decline.append(rule(child, "decline", toks[1:], product))
        elif toks[:1] == ["index"] and "by" in toks:
            lc.renewal_index = [ix for ix in lc.renewal_index if ix[0] != ".".join(toks[1:toks.index("by")])]  # restating replaces
            lc.renewal_index.append(parse_index(child, toks, product))
        else:
            raise child.error(f"unknown renewal setting {child.text!r}")


def parse_index(line: Line, toks: list[str], product: Product) -> tuple:
    """`index <input> by <amount>[%][, at least A][, at most B]` -> (input, "%" or "+", amount expression, at least, at most).

    The amount may use `claims in term`, so a claims count can roll forward: `index previous_claims by claims in term`.
    """
    target, rest = toks[1:toks.index("by")], toks[toks.index("by") + 1:]
    coll = product.collection_for(target[0]) if len(target) == 2 else None
    inp = coll.fields.get(target[1]) if coll else product.inputs.get(target[0]) if len(target) == 1 else None
    if inp is None or inp.kind not in ("money", "number", "integer"):
        raise line.error(f"index needs a money, number or integer input, not {' '.join(target)!r}")
    if not rest:
        raise line.error("expected 'index <input> by N', 'by N%', 'by -N' or 'by claims in term'")
    amount, rest = expression(line, rest, product, stop={","})
    how = "+"
    if amount[0] == "pct":
        how, amount = "%", amount[1]
    bounds = {"least": None, "most": None}
    while rest[:2] == [",", "at"] and rest[2:3] and rest[2] in bounds and len(rest) >= 4:
        bounds[rest[2]], rest = Decimal(rest[3]), rest[4:]
    if rest:
        raise line.error(f"unexpected {' '.join(rest)!r}; use ', at least N' or ', at most N'")
    return (".".join(target), how, amount, bounds["least"], bounds["most"])


def parse_claims(line: Line, product: Product) -> None:
    for child in line.children:
        toks = tokens(child)
        if toks[:1] == ["claim"] and len(toks) == 2:
            name = unquote(toks[1])
            if product.cover(name) is None:
                raise child.error(f"unknown cover {name!r}")
            product.claims[name] = parse_claim(child, name, product)
        elif toks[:1] == ["after"] and toks[2] in ("claim", "claims") and toks[3:9] == ["in", "term", ":", "renewal", "load", "x"] and len(toks) >= 10:
            product.claims_loading.append((int(toks[1]), Decimal(toks[9]), parse_unless(child, toks[10:], product)))
        elif toks[:1] == ["after"] and toks[2] in ("claim", "claims") and toks[3:5] == ["in", "term"] and child.children:
            # Terms imposed once that many claims have been paid: lifecycle lines that override the product's own.
            unless = parse_unless(child, toks[5:], product)
            original, product.lifecycle = product.lifecycle, copy.deepcopy(product.lifecycle)
            try:
                parse_lifecycle(child, product)
                product.claims_terms.append((int(toks[1]), product.lifecycle, unless))
            finally:
                product.lifecycle = original
        else:
            raise child.error("expected 'claim Cover', 'after N claims in term: renewal load x M [unless ...]' or 'after N claims in term [unless ...]' with lifecycle lines below")


def parse_unless(line: Line, toks: list[str], product: Product) -> tuple | None:
    """An optional `unless <condition>`: the line does not apply when the condition holds."""
    if not toks:
        return None
    if toks[0] != "unless":
        raise line.error(f"unexpected {' '.join(toks)!r}; use 'unless <condition>'")
    cond, rest = expression(line, toks[1:], product)
    if rest:
        raise line.error(f"unexpected {' '.join(rest)!r}")
    return cond


def parse_claim(line: Line, name: str, product: Product) -> ClaimRule:
    rule_ = ClaimRule(name)
    for child in line.children:  # facts first, so the other lines can use them
        if tokens(child) == ["asks"]:
            rule_.asks = parse_input_lines(child.children, nested=True)
            for f in rule_.asks.values():
                if f.kind in ("calculated", "collection") or f.name in known_words(product):
                    raise child.error(f"{f.name!r} cannot be asked in a claim; it is already known or not a plain type")
    facts = set(rule_.asks) | {c for f in rule_.asks.values() for c in f.choices}
    for child in line.children:
        toks = tokens(child)
        if toks == ["asks"]:
            continue
        if toks[:1] == ["requires"]:
            rule_.requires = [t for t in toks[1:] if t != ","]
        elif toks[:3] == ["pays", "claimed", "amount"]:
            rule_.pays = parse_pays(child, toks[3:])
        elif toks[:1] == ["pays"]:
            rule_.pays_amount, rest = expression(child, toks[1:], product, stop={","}, extra=facts)
            rule_.pays = parse_pays(child, rest)
        elif toks[:1] == ["co-payment"]:
            step = RatingStep("co-payment", line=child.number)
            step.amount, rest = expression(child, toks[1:], product, stop={"when"}, extra=facts)
            if rest[:1] == ["when"]:
                step.condition, rest = expression(child, rest[1:], product, extra=facts)
            if rest:
                raise child.error(f"unexpected {' '.join(rest)!r}")
            rule_.co_payments.append(step)
        elif toks[:1] == ["decline"]:
            rule_.decline.append(rule(child, "decline", toks[1:], product, extra=facts))
        elif toks in (["depreciation"], ["settlement"]):
            rule_.depreciation = parse_factor(child, toks[0], product, extra=facts).rows
        elif toks == ["does", "not", "count", "towards", "claims", "in", "term"]:
            rule_.counts = ("bool", False)
        elif toks[:6] == ["counts", "towards", "claims", "in", "term", "when"]:
            rule_.counts, rest = expression(child, toks[6:], product, extra=facts)
            if rest:
                raise child.error(f"unexpected {' '.join(rest)!r}")
        else:
            raise child.error(f"unknown claim setting {child.text!r}")
    return rule_


PAYS_CLAUSES = {("up", "to", "limit"): "limit", ("less", "excess"): "excess", ("less", "deductible"): "excess", ("less", "co-payment"): "co-payment"}


def parse_pays(line: Line, toks: list[str]) -> list[str]:
    """`pays claimed amount[, up to limit][, less excess]` in any order; the order written is the order applied."""
    clauses, rest = [], [t for t in toks if t != ","]
    while rest:
        hit = next((words for words in PAYS_CLAUSES if tuple(rest[:len(words)]) == words), None)
        if hit is None:
            raise line.error(f"expected 'up to limit', 'less excess' or 'less co-payment', not {' '.join(rest)!r}")
        clauses.append(PAYS_CLAUSES[hit])
        rest = rest[len(hit):]
    return clauses


def given_value(line: Line, inp: Input, tok: str):
    if inp.kind in ("money", "integer", "number") and tok[0].isdigit():
        return Decimal(tok)
    if inp.kind == "yes/no" and tok in ("yes", "no"):
        return tok == "yes"
    if inp.kind == "choice" and tok in inp.choices:
        return tok
    if inp.kind == "text":
        return unquote(tok)
    if inp.kind == "date" and DATE_TOKEN.fullmatch(tok):
        return date.fromisoformat(tok)
    raise line.error(f"{inp.name} is {inp.kind}, cannot be {tok!r}")


def given_item(line: Line, coll: Input, pairs: list[tuple[str, str]]) -> dict:
    """One item from (field, value) pairs, checked for unknown and missing fields."""
    item = {}
    for name, value in pairs:
        if name not in coll.fields:
            raise line.error(f"unknown {coll.singular} field {name!r}")
        item[name] = given_value(line, coll.fields[name], value)
    missing = [f for f in coll.fields if f not in item and coll.fields[f].kind not in ("text", "calculated") and not coll.fields[f].provided]
    if missing:
        raise line.error(f"{coll.singular} is missing {', '.join(missing)}")
    return item


def items_from_file(line: Line, coll: Input, path: str, base: str) -> list[dict]:
    """Items from a CSV whose columns are the fields; a blank cell is a field not given."""
    full = os.path.join(base, path)
    try:
        with open(full, encoding="utf-8", newline="") as f:
            records = list(csv.DictReader(f))
    except OSError:
        raise line.error(f"cannot read {path!r}")
    items = []
    for n, record in enumerate(records, start=2):
        try:
            items.append(given_item(line, coll, [(k.strip(), v.strip()) for k, v in record.items() if k and v and v.strip()]))
        except ParseError as e:
            raise line.error(f"{path} row {n}: {str(e).removeprefix(f'line {line.number}: ')}")
    return items


def parse_scenario(line: Line, product: Product) -> None:
    toks = tokens(line)
    if len(toks) != 2 or not toks[1].startswith('"'):
        raise line.error('expected: scenario "Name"')
    sc = Scenario(unquote(toks[1]), line.number)
    for child in line.children:
        toks = tokens(child)
        if toks[0] == "given" and len(toks) == 4 and toks[2] == "from" and toks[3].startswith('"') and toks[1] in product.inputs and product.inputs[toks[1]].kind == "collection":
            coll = product.inputs[toks[1]]
            sc.given.setdefault(coll.name, []).extend(items_from_file(child, coll, unquote(toks[3]), product.base))
        elif toks[0] == "given" and len(toks) > 1 and product.collection_for(toks[1]) is not None:
            coll = product.collection_for(toks[1])
            pairs = [t for t in toks[2:] if t != ","]
            sc.given.setdefault(coll.name, []).append(given_item(child, coll, list(zip(pairs[::2], pairs[1::2]))))
        elif toks[0] == "given":
            pairs = [t for t in toks[1:] if t != ","]
            if len(pairs) % 2:
                raise child.error("expected 'given name value, name value'")
            for name, value in zip(pairs[::2], pairs[1::2]):
                if name not in product.inputs or product.inputs[name].kind == "calculated":
                    raise child.error(f"unknown input {name!r}" if name not in product.inputs else f"{name} is calculated, not given")
                sc.given[name] = given_value(child, product.inputs[name], value)
        elif toks[0] == "select":
            for name in toks[1:]:
                if name == ",":
                    continue
                if product.cover(unquote(name)) is None:
                    raise child.error(f"unknown cover {unquote(name)!r}")
                sc.selected.add(unquote(name))
        elif toks[0] in ("when", "expect"):
            sc.steps.append(Step(child.number, toks))
        else:
            raise child.error("expected given, select, when or expect")
    product.scenarios.append(sc)


def parse_enrichment(line: Line, product: Product) -> None:
    """enrichment "Name" [for each bike] from key[, key] with provides / when unavailable / held for the term."""
    toks = tokens(line)
    if len(toks) < 4 or not toks[1].startswith('"'):
        raise line.error('expected enrichment "Name" [for each <item>] from <input>, ...')
    e = Enrichment(unquote(toks[1]), [], line=line.number)
    rest = toks[2:]
    fields = product.inputs
    if rest[:2] == ["for", "each"]:
        coll = product.collection_for(rest[2]) if len(rest) > 2 else None
        if coll is None:
            raise line.error(f"unknown item {rest[2:3] and rest[2]!r}; declare a collection first")
        e.item, fields, rest = coll.singular, coll.fields, rest[3:]
    if rest[:1] != ["from"]:
        raise line.error("expected 'from <input>, ...'")
    e.keys = [t for t in rest[1:] if t != ","]
    for k in e.keys:
        if k not in fields or fields[k].provided:
            raise line.error(f"unknown input {k!r}; enrichment keys must be inputs")
    for child in line.children:
        ctoks = tokens(child)
        if ctoks == ["provides"]:
            e.provides = parse_input_lines(child.children, nested=True)
            for f in e.provides.values():
                if f.kind == "calculated":
                    raise child.error("an enrichment provides plain fields, not calculated ones")
                if f.name in fields or f.name in product.inputs:
                    raise child.error(f"{f.name!r} is already an input")
                f.provided = e.name
            fields.update(e.provides)
        elif ctoks[:3] == ["when", "unavailable", ":"] and ctoks[3:4] and ctoks[3] in ("refer", "decline"):
            if ctoks[4:5] != ["because"] or len(ctoks) != 6:
                raise child.error(f'expected {ctoks[3]} because "reason"')
            e.unavailable, e.reason = ctoks[3], unquote(ctoks[5])
        elif ctoks[:3] == ["when", "unavailable", ":"]:
            pairs = [t for t in ctoks[3:] if t != ","]
            if len(pairs) % 3 or any(pairs[i + 1] != "is" for i in range(0, len(pairs), 3)):
                raise child.error("expected 'when unavailable: field is value, ...' or 'refer/decline because \"reason\"'")
            for name, _, value in zip(pairs[::3], pairs[1::3], pairs[2::3]):
                if name not in e.provides:
                    raise child.error(f"{name!r} is not provided by this enrichment; put 'provides' first")
                e.defaults[name] = given_value(child, e.provides[name], value)
        elif ctoks == ["held", "for", "the", "term"]:
            e.held = True
        else:
            raise child.error(f"unknown enrichment setting {child.text!r}")
    if not e.provides:
        raise line.error("an enrichment needs a 'provides' section")
    product.enrichments.append(e)


def parse_table(line: Line, product: Product) -> None:
    """table "Name" [from "file.csv"] keyed on input, input; rows indented below when there is no file."""
    toks = tokens(line)
    if len(toks) < 5 or not toks[1].startswith('"'):
        raise line.error('expected table "Name" [from "file.csv"] keyed on <input>, ...')
    name, rest = unquote(toks[1]), toks[2:]
    if name in product.tables:
        raise line.error(f"table {name!r} is already declared")
    path = None
    if rest[:1] == ["from"] and rest[1:2] and rest[1].startswith('"'):
        path, rest = os.path.join(product.base, unquote(rest[1])), rest[2:]
    if rest[:2] != ["keyed", "on"]:
        raise line.error("expected 'keyed on <input>, ...'")
    keys = [t for t in fold_phrases(rest[2:]) if t != ","]
    kinds = {}
    for k in keys:
        inp = find_input(product, k)
        if inp is None:
            raise line.error(f"unknown input {k!r}; table keys must be inputs")
        kinds[k] = inp.choices if inp.kind == "choice" else inp.kind
    if path is not None and line.children:
        raise line.error("a table comes from a file or from the rows below it, not both")
    if path is not None:
        try:
            with open(path, encoding="utf-8") as f:
                rows = f.read().splitlines()
        except OSError:
            raise line.error(f"cannot read {os.path.relpath(path, product.base)!r}")
    else:
        rows = [c.text for c in line.children]
    try:
        product.tables[name] = load_table(name, keys, rows, line.number, kinds)
    except TableError as e:
        raise line.error(str(e))


BLOCKS = {
    "inputs": parse_inputs,
    "enrichment": parse_enrichment,
    "table": parse_table,
    "eligibility": parse_eligibility,
    "cover": parse_cover,
    "rating": parse_rating,
    "lifecycle": parse_lifecycle,
    "claims": parse_claims,
    "scenario": parse_scenario,
}


def parse(text: str, base: str = ".") -> Product:
    """Parses a product. Table files named in it are read relative to base."""
    product = None
    for line in build_tree(text):
        toks = tokens(line)
        if toks[0] == "product":
            if len(toks) != 2:
                raise line.error('expected: product "Name"')
            product = Product(unquote(toks[1]), base=base)
            parse_product_header(line, product)
            continue
        if product is None:
            raise line.error("file must start with product \"Name\"")
        handler = BLOCKS.get(toks[0])
        if handler is None:
            raise line.error(f"unknown block {toks[0]!r}")
        handler(line, product)
    if product is None:
        raise ParseError("empty file: expected product \"Name\"")
    for work in product.deferred:
        work()
    unknown = names(product.term[0]) - set(product.inputs)
    if unknown:
        raise ParseError(f"term refers to {sorted(unknown)[0]!r}, which is not an input")
    return product
