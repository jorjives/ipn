"""`python -m ideclare check FILE` runs a product's scenarios."""
from __future__ import annotations

import os
import sys

from .engine import check_eligibility, cover_states, rate
from .parser import Line, ParseError, given_value, parse
from .scenarios import run_all
from .tables import TableError


def check(path: str) -> int:
    try:
        product = parse(open(path, encoding="utf-8").read(), os.path.dirname(path))
    except ParseError as e:
        print(f"{path}: {e}")
        return 1
    results = run_all(product)
    for r in results:
        print(("PASS " if r.passed else "FAIL ") + r.scenario.name)
        for f in r.failures:
            print("     " + f)
    failed = sum(not r.passed for r in results)
    print(f"{product.name}: {len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


def quote(path: str, args: list[str]) -> int:
    """quote FILE name=value ... [select=Cover ...]"""
    product = parse(open(path, encoding="utf-8").read(), os.path.dirname(path))
    inputs, selected = {}, set()
    for arg in args:
        name, _, value = arg.partition("=")
        if name == "select":
            selected.add(value)
        elif name in product.inputs:
            inputs[name] = given_value(Line(0, 0, arg), product.inputs[name], value)
        else:
            print(f"unknown input {name!r}; expected one of {', '.join(product.inputs)}")
            return 2
    missing = [n for n in product.inputs if n not in inputs and product.inputs[n].kind not in ("text", "calculated")]
    if missing:
        print(f"missing: {' '.join(f'{n}=...' for n in missing)}")
        return 2
    e = check_eligibility(product, inputs)
    print(f"Eligibility: {e.outcome}" + (f" ({'; '.join(e.reasons)})" if e.reasons else ""))
    for c in cover_states(product, inputs, selected):
        print(f"  {c.name}: {c.status}" + (f" ({c.reason})" if c.reason else "") + (f", limit {c.limit:.2f}" if c.limit is not None else ""))
    try:
        q = rate(product, inputs, selected)
    except TableError as e:
        print(f"Premium: {e}")
        return 1
    print("Premium:")
    for t in q.trail:
        print(f"  {t.label:<20} {t.applied:>10}  = {t.net:.2f}")
    print(f"  {'net':<20} {'':>10}  = {q.net:.2f}")
    for label, amount in q.lines:
        print(f"  {label:<20} {'':>10}  + {amount:.2f}")
    print(f"  {'total':<20} {'':>10}  = {q.total:.2f} {product.currency}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[0] == "check":
        return check(argv[1])
    if len(argv) >= 2 and argv[0] == "quote":
        try:
            return quote(argv[1], argv[2:])
        except ParseError as e:
            print(f"{argv[1]}: {e}")
            return 1
    print("usage: python -m ideclare check FILE.idl\n       python -m ideclare quote FILE.idl input=value ... [select=Cover]")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
