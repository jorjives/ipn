"""`python -m ideclare check FILE` runs a product's scenarios."""
from __future__ import annotations

import sys

from .parser import ParseError, parse
from .scenarios import run_all


def check(path: str) -> int:
    try:
        product = parse(open(path, encoding="utf-8").read())
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


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[0] == "check":
        return check(argv[1])
    print("usage: python -m ideclare check FILE.idl")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
