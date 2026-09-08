"""The expression sub-language: `rider_age < 25 and security is gold`, `10% of claim`.

parse_expr() works on a token list (from parser.tokens) and returns (node, remaining tokens).
Nodes are plain tuples so they are easy to print and test.
"""
from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal


class ExprError(Exception):
    pass


CMP = {"<", "<=", ">", ">=", "is"}

FUNCTIONS = {"exp": 1, "ln": 1, "sqrt": 1, "round": 2, "min": -2, "max": -2}  # arity; negative = at least


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
        while self.peek() in ("+", "-", "less"):
            op = self.take()
            node = ("-" if op == "less" else op, node, self.term())  # `net less Fire` reads as the policy wording does
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
        return self.power()

    def power(self):
        node = self.postfix()
        if self.peek() == "^":
            self.take()
            node = ("^", node, self.unary())  # right-associative: 2 ^ 3 ^ 2 is 2 ^ 9
        return node

    def postfix(self):
        node = self.primary()
        if self.peek() == "%":
            self.take()
            node = ("pct", node)
            if self.peek() == "of":
                self.take()
                node = ("*", node, self.sum())  # `12% of net less Fire` is 12% of the difference, as it reads
        if self.peek() == "selected":
            self.take()
            node = ("selected", node)
        if node[0] == "name" and self.peek() == "from" and self.toks[self.i + 1:self.i + 2] and self.toks[self.i + 1].startswith('"'):
            self.take()
            node = ("lookup", node[1], self.take()[1:-1])  # rate from "Motor rates"
            if self.peek() == "interpolated":
                self.take()
                method = "linearly"
                if self.peek() != "on":
                    method = self.take()
                    if method not in ("linearly", "geometrically"):
                        raise ExprError(f"interpolated linearly or geometrically, not {method!r}")
                if self.take() != "on":
                    raise ExprError("expected 'interpolated [linearly | geometrically] on <key>'")
                node = ("interp", node[1], node[2], self.take(), method)
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
        if t[0].isalpha() and self.toks[self.i:self.i + 1] == ["("]:
            return self.call(t)
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


    def call(self, name):
        """name ( arg, arg ): a fixed set of functions; commas are read even where they would otherwise stop."""
        if name not in FUNCTIONS:
            raise ExprError(f"unknown function {name!r}")
        self.i += 1
        args = [self.or_()]
        while self.i < len(self.toks) and self.toks[self.i] == ",":
            self.i += 1
            args.append(self.or_())
        if self.i >= len(self.toks) or self.toks[self.i] != ")":
            raise ExprError(f"expected ) after the arguments of {name}")
        self.i += 1
        arity = FUNCTIONS[name]
        if (arity >= 0 and len(args) != arity) or (arity < 0 and len(args) < -arity):
            raise ExprError(f"{name} takes {'at least ' if arity < 0 else ''}{abs(arity)} argument{'s' if abs(arity) != 1 else ''}")
        return ("fn", name, args)


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
    if kind in ("lookup", "interp"):
        return set()
    if kind == "fn":
        return set().union(*(names(a) for a in node[2]))
    return set().union(*(names(c) for c in node[1:]))


def lookups(node: tuple) -> set[tuple[str, str]]:
    """Every (column, table) the expression takes from a lookup table."""
    if node[0] in ("lookup", "interp"):
        return {(node[1], node[2])}
    if node[0] == "fn":
        return set().union(*(lookups(a) for a in node[2]))
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
    if kind in ("lookup", "interp"):
        table = ctx.get("tables", {}).get(node[2])
        if table is None:
            raise ExprError(f"no table called {node[2]!r}")
        if kind == "interp":
            return table.interpolate(ctx, node[1], node[3], node[4])
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
    if kind == "^":
        return _num(node[1], ctx) ** _num(node[2], ctx)
    if kind == "fn":
        args = [_num(a, ctx) for a in node[2]]
        name = node[1]
        if name == "exp": return args[0].exp()
        if name == "ln": return args[0].ln()
        if name == "sqrt": return args[0].sqrt()
        if name == "round": return args[0].quantize(args[1], ROUND_HALF_UP)
        return min(args) if name == "min" else max(args)
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
