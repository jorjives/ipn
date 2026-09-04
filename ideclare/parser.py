"""Turns .idl text into a Product. Line-oriented, indentation-based."""
from __future__ import annotations

import re
from decimal import Decimal
from dataclasses import dataclass, field

from .expr import ExprError, names, parse_expr
from .model import Cover, Excess, Input, Product, Rule, Scenario, Step


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

TOKEN = re.compile(r'\s*(?:(?P<str>"[^"]*")|(?P<num>\d+(?:\.\d+)?)|(?P<id>[A-Za-z_][A-Za-z0-9_/]*)|(?P<op><=|>=|[<>:,%()+\-*/]))')


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

INPUT_KINDS = {"money", "integer", "number", "text", "yes/no"}


def parse_product_header(line: Line, product: Product) -> None:
    for child in line.children:
        toks = tokens(child)
        key = toks[0]
        if key == "territory" and len(toks) == 2:
            product.territory = toks[1]
        elif key == "currency" and len(toks) == 2:
            product.currency = toks[1]
        elif key == "term" and len(toks) == 3 and toks[2] == "months":
            product.term_months = int(toks[1])
        else:
            raise child.error(f"unknown product setting {child.text!r}")


def parse_inputs(line: Line, product: Product) -> None:
    for child in line.children:
        toks = tokens(child)
        if len(toks) < 3 or toks[1] != ":":
            raise child.error("expected 'name: type'")
        name, kind = toks[0], toks[2]
        if kind == "choice":
            if len(toks) < 5 or toks[3] != "of":
                raise child.error("expected 'choice of a, b, c'")
            choices = [t for t in toks[4:] if t != ","]
            product.inputs[name] = Input(name, "choice", choices)
        elif kind in INPUT_KINDS and len(toks) == 3:
            product.inputs[name] = Input(name, kind)
        else:
            raise child.error(f"unknown input type {' '.join(toks[2:])!r}")


# --- expressions and rules ---------------------------------------------------

# Words an expression may use besides inputs, choices and cover names.
CONTEXT_WORDS = {"claim", "claimed", "yes", "no"}


def known_words(product: Product) -> set[str]:
    words = set(CONTEXT_WORDS) | set(product.inputs)
    for inp in product.inputs.values():
        words |= set(inp.choices)
    words |= {c.name for c in product.covers}
    return words


def expression(line: Line, toks: list[str], product: Product, stop: set[str] = frozenset()) -> tuple[tuple, list[str]]:
    try:
        node, rest = parse_expr(toks, stop)
    except ExprError as e:
        raise line.error(str(e))
    unknown = names(node) - known_words(product)
    if unknown:
        raise line.error(f"unknown word {sorted(unknown)[0]!r}")
    return node, rest


def rule(line: Line, kind: str, toks: list[str], product: Product) -> Rule:
    """`<kind> when <condition> because "reason"`; toks start after <kind>."""
    if toks[:1] != ["when"]:
        raise line.error(f"expected '{kind} when ...'")
    cond, rest = expression(line, toks[1:], product, stop={"because"})
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
        key = toks[0]
        if key == "limit":
            cover.limit, rest = expression(child, toks[1:], product)
        elif key == "excess":
            cover.excess.amount, rest = expression(child, toks[1:], product, stop={","})
            if rest[:2] == [",", "minimum"]:
                cover.excess.minimum, rest = expression(child, rest[2:], product)
        elif key == "excludes":
            cover.exclusions.append(rule(child, "excludes", toks[1:], product))
            rest = []
        elif key == "available" and toks[1:2] == ["when"]:
            cover.available, rest = expression(child, toks[2:], product)
        else:
            raise child.error(f"unknown cover setting {child.text!r}")
        if rest:
            raise child.error(f"unexpected {' '.join(rest)!r}")


def given_value(line: Line, inp: Input, tok: str):
    if inp.kind in ("money", "integer", "number") and tok[0].isdigit():
        return Decimal(tok)
    if inp.kind == "yes/no" and tok in ("yes", "no"):
        return tok == "yes"
    if inp.kind == "choice" and tok in inp.choices:
        return tok
    if inp.kind == "text":
        return unquote(tok)
    raise line.error(f"{inp.name} is {inp.kind}, cannot be {tok!r}")


def parse_scenario(line: Line, product: Product) -> None:
    toks = tokens(line)
    if len(toks) != 2 or not toks[1].startswith('"'):
        raise line.error('expected: scenario "Name"')
    sc = Scenario(unquote(toks[1]), line.number)
    for child in line.children:
        toks = tokens(child)
        if toks[0] == "given":
            pairs = [t for t in toks[1:] if t != ","]
            if len(pairs) % 2:
                raise child.error("expected 'given name value, name value'")
            for name, value in zip(pairs[::2], pairs[1::2]):
                if name not in product.inputs:
                    raise child.error(f"unknown input {name!r}")
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


BLOCKS = {
    "inputs": parse_inputs,
    "eligibility": parse_eligibility,
    "cover": parse_cover,
    "scenario": parse_scenario,
}


def parse(text: str) -> Product:
    product = None
    for line in build_tree(text):
        toks = tokens(line)
        if toks[0] == "product":
            if len(toks) != 2:
                raise line.error('expected: product "Name"')
            product = Product(unquote(toks[1]))
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
    return product
