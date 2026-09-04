"""Turns .idl text into a Product. Line-oriented, indentation-based."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .model import Input, Product


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


BLOCKS = {
    "inputs": parse_inputs,
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
