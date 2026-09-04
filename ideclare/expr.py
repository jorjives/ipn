"""The expression sub-language: `rider_age < 25 and security is gold`, `10% of claim`.

parse_expr() works on a token list (from parser.tokens) and returns (node, remaining tokens).
Nodes are plain tuples so they are easy to print and test.
"""
from __future__ import annotations

from decimal import Decimal


class ExprError(Exception):
    pass


CMP = {"<", "<=", ">", ">=", "is"}


def parse_expr(toks: list[str], stop: set[str] = frozenset()) -> tuple[tuple, list[str]]:
    p = _Parser(toks, stop)
    node = p.or_()
    return node, toks[p.i:]


class _Parser:
    def __init__(self, toks, stop):
        self.toks, self.stop, self.i = toks, stop, 0

    def peek(self):
        t = self.toks[self.i] if self.i < len(self.toks) else None
        return None if t in self.stop else t

    def take(self):
        t = self.peek()
        if t is None:
            raise ExprError("unexpected end of expression")
        self.i += 1
        return t

    def or_(self):
        node = self.and_()
        while self.peek() == "or":
            self.take()
            node = ("or", node, self.and_())
        return node

    def and_(self):
        node = self.not_()
        while self.peek() == "and":
            self.take()
            node = ("and", node, self.not_())
        return node

    def not_(self):
        if self.peek() == "not":
            self.take()
            return ("not", self.not_())
        return self.cmp()

    def cmp(self):
        node = self.sum()
        t = self.peek()
        if t in CMP:
            op = self.take()
            if op == "is" and self.peek() == "not":
                self.take()
                op = "is not"
            node = (op, node, self.sum())
        return node

    def sum(self):
        node = self.term()
        while self.peek() in ("+", "-"):
            node = (self.take(), node, self.term())
        return node

    def term(self):
        node = self.unary()
        while self.peek() in ("*", "/"):
            node = (self.take(), node, self.unary())
        return node

    def unary(self):
        if self.peek() == "-":
            self.take()
            return ("neg", self.unary())
        return self.postfix()

    def postfix(self):
        node = self.primary()
        if self.peek() == "%":
            self.take()
            node = ("pct", node)
            if self.peek() == "of":
                self.take()
                node = ("*", node, self.unary())
        if self.peek() == "selected":
            self.take()
            node = ("selected", node)
        return node

    def primary(self):
        t = self.take()
        if t == "(":
            node = self.or_()
            if self.take() != ")":
                raise ExprError("expected )")
            return node
        if t[0].isdigit():
            return ("num", Decimal(t))
        if t.startswith('"'):
            return ("name", t[1:-1])
        if t == "yes":
            return ("bool", True)
        if t == "no":
            return ("bool", False)
        if t[0].isalpha() or t[0] == "_":
            return ("name", t)
        raise ExprError(f"unexpected {t!r}")


def names(node: tuple) -> set[str]:
    """Every identifier the expression refers to (inputs, choice values, cover names)."""
    kind = node[0]
    if kind == "name":
        return {node[1]}
    if kind in ("num", "bool"):
        return set()
    return set().union(*(names(c) for c in node[1:]))


def evaluate(node: tuple, ctx: dict):
    kind = node[0]
    if kind == "num" or kind == "bool":
        return node[1]
    if kind == "name":
        # Unbound words are choice values: `security is gold` compares against "gold".
        return ctx.get(node[1], node[1])
    if kind == "selected":
        return node[1][1] in ctx.get("selected", set())
    if kind == "not":
        return not evaluate(node[1], ctx)
    if kind == "neg":
        return -_num(node[1], ctx)
    if kind == "pct":
        return _num(node[1], ctx) / 100
    if kind == "and":
        return evaluate(node[1], ctx) and evaluate(node[2], ctx)
    if kind == "or":
        return evaluate(node[1], ctx) or evaluate(node[2], ctx)
    if kind == "is":
        return evaluate(node[1], ctx) == evaluate(node[2], ctx)
    if kind == "is not":
        return evaluate(node[1], ctx) != evaluate(node[2], ctx)
    left, right = _num(node[1], ctx), _num(node[2], ctx)
    if kind == "<": return left < right
    if kind == "<=": return left <= right
    if kind == ">": return left > right
    if kind == ">=": return left >= right
    if kind == "+": return left + right
    if kind == "-": return left - right
    if kind == "*": return left * right
    if kind == "/": return left / right
    raise ExprError(f"cannot evaluate {kind}")


def _num(node, ctx) -> Decimal:
    v = evaluate(node, ctx)
    if isinstance(v, bool) or not isinstance(v, (int, Decimal)):
        raise ExprError(f"{_show(node)} is not a number (got {v!r})")
    return Decimal(v)


def _show(node) -> str:
    if node[0] in ("num", "name", "bool"):
        return str(node[1])
    return " ".join(_show(c) if isinstance(c, tuple) else str(c) for c in node[1:])
