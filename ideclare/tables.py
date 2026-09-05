"""Lookup tables: long-format CSV rows, one per cell, matched on key columns.

A cell is an exact value (`gold`, `12`, `yes`), an inclusive band (`17-20`, `65+`) or `*` for
anything. Loaded once at parse time; looked up by evaluate() for `<column> from "Table"`.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from decimal import Decimal


class TableError(Exception):
    pass


NUMBER = re.compile(r"-?\d+(?:\.\d+)?")
BAND = re.compile(rf"({NUMBER.pattern})\s*-\s*({NUMBER.pattern})")
OPEN_BAND = re.compile(rf"({NUMBER.pattern})\s*\+")


def cell(text: str):
    """The typed form of one cell: Decimal, str, ("band", lo, hi | None) or ("any",)."""
    text = text.strip()
    if text == "*":
        return ("any",)
    if NUMBER.fullmatch(text):
        return Decimal(text)
    if m := BAND.fullmatch(text):
        return ("band", Decimal(m.group(1)), Decimal(m.group(2)))
    if m := OPEN_BAND.fullmatch(text):
        return ("band", Decimal(m.group(1)), None)
    return text


def matches(cell_value, value) -> bool:
    if isinstance(cell_value, tuple):
        if cell_value[0] == "any":
            return True
        if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
            return False
        _, lo, hi = cell_value
        return lo <= value and (hi is None or value <= hi)
    if isinstance(value, bool):
        return cell_value == ("yes" if value else "no")
    return cell_value == value


@dataclass
class Table:
    name: str
    keys: list[str]
    values: list[str]
    rows: list[dict] = field(default_factory=list)  # column -> typed cell
    line: int = 0

    def lookup(self, ctx: dict) -> dict:
        """The one row whose key cells all match the context's values."""
        # ponytail: a scan of every row; index the exact-valued columns if tables reach tens of thousands of rows
        hits = [r for r in self.rows if all(matches(r[k], ctx.get(k)) for k in self.keys)]
        where = ", ".join(f"{k} {ctx.get(k)}" for k in self.keys)
        if not hits:
            raise TableError(f"no row in {self.name} for {where}")
        wildcards = [sum(r[k] == ("any",) for k in self.keys) for r in hits]
        hits = [r for r, w in zip(hits, wildcards) if w == min(wildcards)]  # the most specific row wins
        if len(hits) > 1:
            raise TableError(f"{self.name} is ambiguous for {where}")
        return hits[0]

    def interpolate(self, ctx: dict, column: str, key: str, method: str):
        """The column's value at ctx[key], between the two knots that bracket it on the rows whose other keys match."""
        others = [k for k in self.keys if k != key]
        rows = [r for r in self.rows if all(matches(r[k], ctx.get(k)) for k in others)]
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


def load_table(name: str, keys: list[str], lines: list[str], line: int = 0) -> Table:
    """Builds a Table from CSV lines, header first. Every non-key column is a value column."""
    records = [r for r in csv.reader(l for l in lines if l.strip()) if r]
    if not records:
        raise TableError(f"{name} has no rows")
    header = [h.strip() for h in records[0]]
    for k in keys:
        if k not in header:
            raise TableError(f"{name} has no column {k!r}; columns are {', '.join(header)}")
    values = [h for h in header if h not in keys]
    if not values:
        raise TableError(f"{name} has no value column; every column is a key")
    table = Table(name, keys, values, line=line)
    if len(records) == 1:
        raise TableError(f"{name} has no rows")
    seen = {}
    for n, record in enumerate(records[1:], start=2):
        if len(record) != len(header):
            raise TableError(f"{name} row {n} has {len(record)} cells, expected {len(header)}")
        row = {h: cell(v) for h, v in zip(header, record)}
        key = tuple(record[header.index(k)].strip() for k in keys)
        if key in seen:
            raise TableError(f"{name} row {n} repeats the keys of row {seen[key]}")
        seen[key] = n
        table.rows.append(row)
    return table
