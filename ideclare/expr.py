"""The expression sub-language: `rider_age < 25 and security is gold`, `10% of claim`.

parse_expr() works on a token list (from parser.tokens) and returns (node, remaining tokens).
Nodes are plain tuples so they are easy to print and test.
"""
from __future__ import annotations

from datetime import date
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
        if node[0] == "name" and self.peek() == "from" and self.toks[self.i + 1:self.i + 2] and self.toks[self.i + 1].startswith('"'):
            self.take()
            node = ("lookup", node[1], self.take()[1:-1])  # rate from "Motor rates"
        return node

    def primary(self):
        t = self.take()
        if t == "count" and self.peek() == "of":
            self.take()
            return ("count", self.take())
        if t in ("total", "highest", "lowest") and self.toks[self.i + 1:self.i + 2] == ["of"]:
            field_, _, coll = self.take(), self.take(), self.take()
            return ("agg", t, field_, coll)
        if t in ("any", "every") and self.toks[self.i + 1:self.i + 2] == ["where"]:
            name, _ = self.take(), self.take()
            return (t, name, self.or_())
        if t == "(":
            node = self.or_()
            if self.take() != ")":
                raise ExprError("expected )")
            return node
        if len(t) == 10 and t[4] == "-" and t[7] == "-":
            return ("date", date.fromisoformat(t))
        if t[0].isdigit():
            return ("num", Decimal(t))
        if t.startswith('"'):
            return ("str", t[1:-1])
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
    if kind in ("num", "bool", "str", "date"):
        return set()
    if kind == "selected":
        return {node[1][1]}
    if kind == "count":
        return {node[1]}
    if kind == "agg":
        return {node[2], node[3]}
    if kind in ("any", "every"):
        return {node[1]} | names(node[2])
    if kind == "lookup":
        return set()
    return set().union(*(names(c) for c in node[1:]))


def lookups(node: tuple) -> set[tuple[str, str]]:
    """Every (column, table) the expression takes from a lookup table."""
    if node[0] == "lookup":
        return {(node[1], node[2])}
    return set().union(*(lookups(c) for c in node[1:] if isinstance(c, tuple)))


def evaluate(node: tuple, ctx: dict):
    kind = node[0]
    if kind in ("num", "bool", "str", "date"):
        return node[1]
    if kind == "name":
        # Unbound words are choice values: `security is gold` compares against "gold".
        return ctx.get(node[1], node[1])
    if kind == "selected":
        return node[1][1] in ctx.get("selected", set())
    if kind == "lookup":
        table = ctx.get("tables", {}).get(node[2])
        if table is None:
            raise ExprError(f"no table called {node[2]!r}")
        return table.lookup(ctx)[node[1]]
    if kind == "count":
        return Decimal(len(_items(node[1], ctx)))
    if kind == "agg":
        values = [Decimal(item[node[2]]) for item in _items(node[3], ctx)]
        if not values:
            return Decimal(0)
        return sum(values) if node[1] == "total" else max(values) if node[1] == "highest" else min(values)
    if kind in ("any", "every"):
        results = [evaluate(node[2], {**ctx, **item}) for item in _items(node[1], ctx)]
        return any(results) if kind == "any" else all(results)
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
    left, right = evaluate(node[1], ctx), evaluate(node[2], ctx)
    if isinstance(left, date) and isinstance(right, date):
        if kind == "-":
            return Decimal((left - right).days)
    else:
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


def _items(name: str, ctx: dict) -> list[dict]:
    items = ctx.get(name)
    if not isinstance(items, list):
        raise ExprError(f"{name} is not a collection here")
    return items


def _num(node, ctx) -> Decimal:
    v = evaluate(node, ctx)
    if isinstance(v, bool) or not isinstance(v, (int, Decimal)):
        raise ExprError(f"{_show(node)} is not a number (got {v!r})")
    return Decimal(v)


def _show(node) -> str:
    if node[0] in ("num", "name", "bool"):
        return str(node[1])
    return " ".join(_show(c) if isinstance(c, tuple) else str(c) for c in node[1:])
