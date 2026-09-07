# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

iDeclare is a declarative language (`.idl` files) for defining insurance products end to end, plus a Python 3.12 sidecar engine that parses, evaluates and proves them. Standard library only; no dependencies.

The audience is insurance professionals, not developers. The DSL reads like English on purpose.

## Commands

```bash
# Run all engine tests
python3 -m unittest

# Run a single test file or test
python3 -m unittest tests.test_engine
python3 -m unittest tests.test_engine.TestRate.test_base_only

# Check all example products pass their scenarios
for f in examples/*.idl examples/versioned/*.idl; do python3 -m ideclare check "$f" | tail -1; done

# Check one product
python3 -m ideclare check examples/cycle.idl

# Quote a single risk (scalar inputs only; use scenarios for items)
python3 -m ideclare quote examples/cycle.idl bike_value=2000 rider_age=22 security=gold racing=no previous_claims=0
```

## Architecture

The pipeline is: **parser → model → engine**, with scenarios driving the engine through lifecycle events.

| Module | Role |
|---|---|
| `parser.py` (764 lines) | Line-oriented, indentation-based parser. Turns `.idl` text into a `Product`. Tokenises, builds an indent tree, then walks each block type. |
| `model.py` | Pure dataclasses (`Product`, `Input`, `Cover`, `RatingStep`, `ClaimRule`, `Lifecycle`, `Enrichment`, `Table`, etc.). Filled by parser, read by engine. No logic. |
| `engine.py` | Applies a `Product` to a risk: eligibility, cover states, rating (with per-item `for each` loops), lifecycle (bind/cancel/adjust/renew), claims settlement. All arithmetic is `Decimal`, never float. |
| `expr.py` | Expression sub-language: comparisons, boolean logic, arithmetic, functions (`exp`, `ln`, `sqrt`, `min`, `max`, `round`), `N% of x`, `rate from "Table"`. Returns plain tuples as AST nodes; `evaluate()` walks them. |
| `tables.py` | Lookup tables in long CSV format. Cells are exact values, inclusive bands (`17-20`, `65+`), or `*` wildcard. Most-specific-row wins. Supports linear and geometric interpolation on one key. |
| `versions.py` | A product's published versions (`History`): which is live on a date, moving answers between versions. Built by the CLI from the `.idl` files beside the product with the same name; a lone file is a history of one. |
| `scenarios.py` | Runs `scenario` blocks: feeds events (`bound`, `cancelled`, `adjusted`, `claim`, `renewed`) into the engine in order, then checks `expect` lines against the resulting state. |
| `cli.py` | Two commands: `check` (run scenarios) and `quote` (price one risk). |

### Key flow: how a scenario runs

`scenarios.py` → creates a `Run` → processes `when` events (each calls into `engine.py` to bind, cancel, adjust, claim, or renew) → processes `expect` lines by comparing engine state to expected values → returns `Result` with pass/fail.

### Expression AST

Expressions are tuples: `("num", Decimal("3.5"))`, `("<", ("name", "rider_age"), ("num", Decimal("25")))`, `("lookup", "rate", "Van rates")`. `expr.parse_expr()` produces them; `expr.evaluate()` walks them against a context dict.

## Design decisions that matter

- **`pays` clause order is semantic**: `up to limit, less excess` (cap then deduct) differs from `less excess, up to limit` (deduct then cap). The order written is the order applied.
- **Tax is on the rounded net**, not pre-round.
- **Fees never refund** (except during cooling off).
- **Waiting periods and `within N months of inception`** run from the original inception, not the latest renewal.
- **Only paid claims that `count`** go towards `claims in term`, but every paid claim erodes an aggregate limit.
- **All arithmetic is `Decimal`**, so products price identically on every machine. Never introduce `float`.
- **Enrichment** is shape-only (what keys, what fields); scenarios stub it by giving the provided fields directly.

## Extending the language

Pattern: write an example `.idl` product that needs the new feature → run its scenarios to find the gap → add parser support → add engine support → tests. One feature per commit. The language reference is `docs/reference.md`; keep it in sync.

`docs/reference.md` § "Not yet supported" lists known gaps.
