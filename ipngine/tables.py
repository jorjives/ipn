"""Lookup tables: long-format CSV rows, one per cell, matched on key columns.

A cell is an exact value (`gold`, `12`, `yes`), a percentage (`80%`), an inclusive band
(`17-20`, `65+`) or `*` for anything. Loaded once at parse time; looked up by evaluate()
for `<column> from "Table"`.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from decimal import Decimal


class TableError(Exception):
    pass


NUMBER = re.compile(r"-?\d+(?:\.\d+)?")
PERCENT = re.compile(rf"({NUMBER.pattern})\s*%")
BAND = re.compile(rf"({NUMBER.pattern})\s*-\s*({NUMBER.pattern})")
OPEN_BAND = re.compile(rf"({NUMBER.pattern})\s*\+")

NUMERIC_KINDS = ("money", "integer", "number")


def cell(text: str):
    """The typed form of one cell: Decimal, str, ("band", lo, hi | None) or ("any",)."""
    text = text.strip()
    if text == "*":
        return ("any",)
    if NUMBER.fullmatch(text):
        return Decimal(text)
    if m := PERCENT.fullmatch(text):
        return Decimal(m.group(1)) / 100
    if m := BAND.fullmatch(text):
        return ("band", Decimal(m.group(1)), Decimal(m.group(2)))
    if m := OPEN_BAND.fullmatch(text):
        return ("band", Decimal(m.group(1)), None)
    return text


def check_cell(cell_value, kind) -> str | None:
    """Why a key cell does not fit the input it is matched against; None when it does."""
    if cell_value == ("any",):
        return None
    if isinstance(kind, list):
        return None if cell_value in kind else f"is not one of {', '.join(kind)}"
    if kind == "yes/no":
        return None if cell_value in ("yes", "no") else "is not yes, no or *"
    if kind in NUMERIC_KINDS:
        return None if isinstance(cell_value, (Decimal, tuple)) else "is not a number, a band like 17-20 or 65+, or *"
    return None


def matches(cell_value, value) -> bool:
    if isinstance(cell_value, tuple):
        if cell_value[0] == "any":
            return True
        if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
            return False
        _, lo, hi = cell_value
        return lo <= value and (hi is None or value <= hi)
    return cell_value == _exact(value)


def _exact(value):
    """A context value as it would appear in an exact cell."""
    return ("yes" if value else "no") if isinstance(value, bool) else value


@dataclass
class Table:
    name: str
    keys: list[str]
    values: list[str]
    rows: list[dict] = field(default_factory=list)  # column -> typed cell
    line: int = 0
    # per key: exact cell value -> row numbers, and the row numbers whose cell is a band or *
    exact: dict[str, dict] = field(default_factory=dict, repr=False)
    wild: dict[str, set[int]] = field(default_factory=dict, repr=False)

    def index(self) -> None:
        self.exact = {k: {} for k in self.keys}
        self.wild = {k: set() for k in self.keys}
        for n, row in enumerate(self.rows):
            for k in self.keys:
                if isinstance(row[k], tuple):
                    self.wild[k].add(n)
                else:
                    self.exact[k].setdefault(row[k], set()).add(n)

    def candidates(self, ctx: dict, keys: list[str]) -> list[dict]:
        """The rows that can match on these keys: an exact hit or a band or * cell on every one."""
        if not keys:
            return list(self.rows)
        sets = sorted(((self.exact[k].get(_exact(ctx.get(k)), frozenset()), self.wild[k]) for k in keys), key=lambda pair: len(pair[0]) + len(pair[1]))
        found = sets[0][0] | sets[0][1]  # start from the narrowest key and never copy the wide ones
        for hits, wild in sets[1:]:
            found = {n for n in found if n in hits or n in wild}
        return [self.rows[n] for n in sorted(found)]

    def lookup(self, ctx: dict) -> dict:
        """The one row whose key cells all match the context's values."""
        hits = [r for r in self.candidates(ctx, self.keys) if all(matches(r[k], ctx.get(k)) for k in self.keys)]
        where = ", ".join(f"{k} {ctx.get(k)}" for k in self.keys)
        if not hits:
            raise TableError(f"no row in {self.name} for {where}")
        wildcards = [sum(r[k] == ("any",) for k in self.keys) for r in hits]
        hits = [r for r, w in zip(hits, wildcards) if w == min(wildcards)]  # the most specific row wins
        if len(hits) > 1:
            raise TableError(f"{self.name} is ambiguous for {where}")
        return hits[0]

    def values_for(self, column: str, keys: list[str], ctx: dict) -> list:
        """The distinct cells of the column, in file order, on the rows whose named keys match the context."""
        rows = [r for r in self.candidates(ctx, keys) if all(matches(r[k], ctx.get(k)) for k in keys)]
        return list(dict.fromkeys(r[column] for r in rows))

    def interpolate(self, ctx: dict, column: str, key: str, method: str):
        """The column's value at ctx[key], between the two knots that bracket it on the rows whose other keys match."""
        others = [k for k in self.keys if k != key]
        rows = [r for r in self.candidates(ctx, others) if all(matches(r[k], ctx.get(k)) for k in others)]
        if not rows:
            raise TableError(f"no rows in {self.name} for " + ", ".join(f"{k} {ctx.get(k)}" for k in others))
        for r in rows:
            if not isinstance(r[key], Decimal):
                raise TableError(f"{self.name} cannot be interpolated on {key}: the cell {_show(r[key])!r} is not a single number")
        if len(rows) < 2:
            raise TableError(f"{self.name} needs at least two knots on {key}")
        knots = sorted((r[key], r[column]) for r in rows)
        x = ctx.get(key)
        if not isinstance(x, Decimal) or not knots[0][0] <= x <= knots[-1][0]:
            raise TableError(f"{key} {x} is outside {self.name}, whose knots run from {knots[0][0]} to {knots[-1][0]}")
        (x0, y0), (x1, y1) = next((a, b) for a, b in zip(knots, knots[1:]) if a[0] <= x <= b[0])
        if x == x0:
            return y0
        t = (x - x0) / (x1 - x0)
        if method == "linearly":
            return y0 + (y1 - y0) * t
        for kx, ky in ((x0, y0), (x1, y1)):
            if ky <= 0:
                raise TableError(f"{self.name} cannot be interpolated geometrically: {column} is {ky} at {key} {kx}")
        return y0 * (y1 / y0) ** t


def _show(cell_value) -> str:
    if isinstance(cell_value, tuple):
        return "*" if cell_value[0] == "any" else f"{cell_value[1]}-{cell_value[2]}" if cell_value[2] is not None else f"{cell_value[1]}+"
    return str(cell_value)


def load_table(name: str, keys: list[str], lines: list[str], line: int = 0, kinds: dict | None = None,
               text_columns: set[str] = frozenset(), allow_no_values: bool = False) -> Table:
    """Builds a Table from CSV lines, header first. Every non-key column is a value column.

    kinds says what each key is matched against (a list of choices, "yes/no", a numeric kind or text),
    so a cell that could never match is an error at load rather than a row that never fires.
    text_columns are key columns a choice lists: every cell is kept as written, and `*` or a band is an error.
    allow_no_values lets a table be keys alone: a list with nothing to look up.
    """
    records = [r for r in csv.reader(l for l in lines if l.strip()) if r]
    if not records:
        raise TableError(f"{name} has no rows")
    header = [h.strip() for h in records[0]]
    for k in keys:
        if k not in header:
            raise TableError(f"{name} has no column {k!r}; columns are {', '.join(header)}")
    values = [h for h in header if h not in keys]
    if not values and not allow_no_values:
        raise TableError(f"{name} has no value column; every column is a key")
    table = Table(name, keys, values, line=line)
    if len(records) == 1:
        raise TableError(f"{name} has no rows")
    seen = {}
    for n, record in enumerate(records[1:], start=2):
        if len(record) != len(header):
            raise TableError(f"{name} row {n} has {len(record)} cells, expected {len(header)}")
        row = {h: v.strip() if h in text_columns else cell(v) for h, v in zip(header, record)}
        for h in text_columns:
            if isinstance(cell(row[h]), tuple):
                raise TableError(f"{name} row {n}: {row[h]!r} is not a value; {h} lists choices")
        for k in keys:
            if kinds and k in kinds and k not in text_columns and (why := check_cell(row[k], kinds[k])):
                raise TableError(f"{name} row {n}: {record[header.index(k)].strip()!r} {why}")
        key = tuple(record[header.index(k)].strip() for k in keys)
        if key in seen:
            raise TableError(f"{name} row {n} repeats the keys of row {seen[key]}")
        seen[key] = n
        table.rows.append(row)
    table.index()
    return table
