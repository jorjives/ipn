"""`python -m ideclare check FILE` runs a product's scenarios; `quote` prices one risk; `batch` prices a book."""
from __future__ import annotations

import csv
from decimal import Decimal
import os
import sys

from .engine import check_eligibility, cover_state, instalments, rate
from .expr import ExprError
from .parser import Line, ParseError, given_value, items_from_file, parse, with_defaults
from .scenarios import run_all
from .tables import TableError
from .versions import History


def load(path: str):
    return parse(open(path, encoding="utf-8").read(), os.path.dirname(path))


def check(path: str) -> int:
    try:
        history = History.for_file(path)
        product = history.versions[-1]  # the file itself: its history is the versions published before it
    except ParseError as e:
        print(e)  # the history names the file, which may be a sibling version
        return 1
    results = run_all(product, history)
    for r in results:
        print(("PASS " if r.passed else "FAIL ") + r.scenario.name)
        for f in r.failures:
            print("     " + f)
    failed = sum(not r.passed for r in results)
    print(f"{product.name}: {len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


def risk_inputs(product, pairs: list[tuple[str, str]], line: Line) -> tuple[dict, set[str]]:
    """Inputs and selected covers from name=value pairs; a collection's value is a CSV file of its items."""
    inputs, selected = {}, set()
    for name, value in pairs:
        if name == "select":
            selected |= {v.strip() for v in value.split(";") if v.strip()}
        elif product.inputs[name].kind == "collection":
            inputs[name] = items_from_file(line, product.inputs[name], value, product.base)
        else:
            inputs[name] = given_value(line, product.inputs[name], value)
    return with_defaults(product.inputs, inputs), selected


def missing_inputs(product, inputs: dict) -> list[str]:
    return [n for n, i in product.inputs.items() if n not in inputs and i.kind not in ("text", "calculated", "collection") and not i.provided]


def quote(path: str, args: list[str]) -> int:
    """quote FILE name=value ... [select=Cover ...] [items=file.csv]"""
    product = load(path)
    pairs = [arg.partition("=")[::2] for arg in args]
    unknown = [n for n, _ in pairs if n != "select" and n not in product.inputs]
    if unknown:
        print(f"unknown input {unknown[0]!r}; expected one of {', '.join(product.inputs)}")
        return 2
    inputs, selected = risk_inputs(product, pairs, Line(0, 0, ""))
    missing = missing_inputs(product, inputs)
    if missing:
        print(f"missing: {' '.join(f'{n}=...' for n in missing)}")
        return 2
    e = check_eligibility(product, inputs, selected)
    print(f"Eligibility: {e.outcome}" + (f" ({'; '.join(e.reasons)})" if e.reasons else ""))
    for cover in product.covers:  # a per-item cover is reported once per item
        coll = product.collection_for(cover.item) if cover.item else None
        for n, item in enumerate(inputs.get(coll.name, []) if coll else [None], start=1):
            c = cover_state(product, cover, inputs, selected, item)
            where = f" on {cover.item} {n}" if item is not None else ""
            print(f"  {c.name}{where}: {c.status}" + (f" ({c.reason})" if c.reason else "") + (f", limit {c.limit:.2f}" if c.limit is not None else ""))
    try:
        q = rate(product, inputs, selected)
    except (TableError, ExprError) as e:
        print(f"Premium: {e}")
        return 1
    print("Premium:")
    for t in q.trail:
        print(f"  {t.label:<20} {t.applied:>10}  = {t.net:.2f}")
    print(f"  {'net':<20} {'':>10}  = {q.net:f}")
    for label, amount in q.lines:
        print(f"  {label:<20} {'':>10}  + {amount:f}")
    print(f"  {'total':<20} {'':>10}  = {q.total:f} {q.currency}")
    for label, amount in q.commission:
        print(f"  of which {label} commission {amount:f}")
    lc = product.lifecycle
    if lc.instalments:
        charge, parts = instalments(q.total, lc.instalments, lc.instalment_charge, product.quantum_for(inputs.get('territory', '')))
        print(f"  or {lc.instalments} monthly: {parts[0]:f} then {parts[1]:f} (credit charge {charge:f})")
    return 0


def batch(path: str, risks: str, out=None) -> int:
    """batch FILE RISKS.csv: one risk per row in, one row per risk out with eligibility and the premium lines.

    A risk that cannot be priced (an answer missing, a cell off the table) is reported in its own row's
    error column; the others still price. Columns are the input names plus an optional `select`, cover
    names separated by ';'.
    """
    product = load(path)
    writer = csv.writer(out or sys.stdout, lineterminator="\n")
    with open(risks, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        columns = [c.strip() for c in reader.fieldnames or []]
        unknown = [c for c in columns if c != "select" and c not in product.inputs]
        if unknown:
            writer.writerow([f"unknown column {unknown[0]!r}; expected input names and select"])
            return 2
        steps = [s for step in product.rating for s in ([step] + step.steps)]  # a tax may sit inside 'for each'
        lines = list(dict.fromkeys(s.label for s in steps if s.kind in ("tax", "fee")))
        commission = [s.label for s in steps if s.kind == "commission"]
        writer.writerow(["risk", "eligibility", "reasons", "net", *lines, "total", "currency", *commission, "error"])
        for n, record in enumerate(reader, start=1):
            blank = [""] * (len(lines) + len(commission) + 5)
            try:
                inputs, selected = risk_inputs(product, [(k.strip(), v.strip()) for k, v in record.items() if k and v and v.strip()], Line(n, 0, f"row {n}"))
                missing = missing_inputs(product, inputs)
                if missing:
                    raise ParseError(f"missing {', '.join(missing)}")
                e = check_eligibility(product, inputs, selected)
                q = rate(product, inputs, selected)
            except (ParseError, TableError, ExprError) as err:
                writer.writerow([n, *blank, str(err).removeprefix(f"line {n}: ")])
                continue
            by_label, split, none = dict(q.lines), dict(q.commission), Decimal(0).quantize(q.net)
            writer.writerow([n, e.outcome, "; ".join(e.reasons), f"{q.net:f}", *(f"{by_label.get(l, none):f}" for l in lines), f"{q.total:f}", q.currency,
                             *(f"{split.get(l, none):f}" for l in commission), ""])
    return 0


def main(argv: list[str]) -> int:
    try:
        if len(argv) == 2 and argv[0] == "check":
            return check(argv[1])
        if len(argv) >= 2 and argv[0] == "quote":
            return quote(argv[1], argv[2:])
        if len(argv) == 3 and argv[0] == "batch":
            return batch(argv[1], argv[2])
    except ParseError as e:
        print(f"{argv[1]}: {e}")
        return 1
    print("usage: python -m ideclare check FILE.idl\n"
          "       python -m ideclare quote FILE.idl input=value ... [select=Cover] [items=file.csv]\n"
          "       python -m ideclare batch FILE.idl RISKS.csv")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
