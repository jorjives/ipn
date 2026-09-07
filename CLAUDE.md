# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Open IDL (codename iDeclare; the Python package is still `ideclare`) is a declarative language (`.idl` files) for defining insurance products end to end, plus a Python 3.12 sidecar engine that parses, evaluates and proves them. Standard library only; no dependencies. Public site: https://jorjives.github.io/open-idl/ (repo `jorjives/open-idl`).

The audience is insurance professionals, not developers. The DSL reads like English on purpose.

## Commands

```bash
# Run all engine tests (GitHub Actions runs the same on pull requests and on main)
python3 -m unittest

# Run a single test file or test
python3 -m unittest tests.test_engine
python3 -m unittest tests.test_engine.TestRate.test_base_only

# Check all example products and templates pass their scenarios
for f in examples/*.idl examples/versioned/*.idl templates/*.idl templates/versioned/*.idl; do python3 -m ideclare check "$f" | tail -1; done

# Regenerate the site's example and template pages and the playground's completion table (tests.test_site fails if they are stale)
python3 scripts/site_pages.py

# Build the site locally with GitHub's own Pages image (Docker + gh); output in /tmp/oidl-out
scripts/site_build.sh

# Check one product
python3 -m ideclare check examples/cycle.idl

# Quote a single risk (scalar inputs only; use scenarios for items)
python3 -m ideclare quote examples/cycle.idl bike_value=2000 rider_age=22 security=gold racing=no previous_claims=0
```

## Architecture

The pipeline is: **parser → model → engine**, with scenarios driving the engine through lifecycle events.

| Module | Role |
|---|---|
| `parser.py` (~1200 lines) | Line-oriented, indentation-based parser. Turns `.idl` text into a `Product`. Tokenises, builds an indent tree, then walks each block type. |
| `model.py` | Pure dataclasses (`Product`, `Input`, `Cover`, `RatingStep`, `ClaimRule`, `Lifecycle`, `Enrichment`, `Table`, etc.). Filled by parser, read by engine. No logic. |
| `engine.py` | Applies a `Product` to a risk: eligibility, cover states, rating (with per-item `for each` loops), lifecycle (bind/cancel/adjust/renew), claims settlement. All arithmetic is `Decimal`, never float. |
| `expr.py` | Expression sub-language: comparisons, boolean logic, arithmetic, functions (`exp`, `ln`, `sqrt`, `min`, `max`, `round`), `N% of x`, `rate from "Table"`. Returns plain tuples as AST nodes; `evaluate()` walks them. |
| `tables.py` | Lookup tables in long CSV format. Cells are exact values, inclusive bands (`17-20`, `65+`), or `*` wildcard. Most-specific-row wins. Supports linear and geometric interpolation on one key. A key column can also be the list a `choice of <column> from "Table" [for key]` input draws on (`Table.values_for`); `engine.check_inputs` validates keyed choices. |
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
- **Lines are steps in order**: `tax`, `fee` and `commission` are evaluated where they stand, so a step written after a tax is not taxed. A line's base may be `net`, `premium`, an earlier tax or a cover (`12% of net less Fire`). Claims and underwriter loads are inserted before the first line.
- **The net is a partition across covers** (`engine.run_steps` carries `shares`, `""` = unattributed pool): `for Cover` on a step, `allocate` for the pool, `class` on a cover, `premium` on a cover joined by `add cover premiums`. Rounded splits give the residue to the largest share (`engine.split`). Fees are never attributed. Reporting is the platform's job: no report command.
- **Fees never refund** (except during cooling off).
- **Waiting periods and `within N months of inception`** run from the original inception, not the latest renewal.
- **Only paid claims that `count`** go towards `claims in term`, but every paid claim erodes an aggregate limit.
- **All arithmetic is `Decimal`**, so products price identically on every machine. Never introduce `float`.
- **Enrichment** is shape-only (what keys, what fields); scenarios stub it by giving the provided fields directly.

## Extending the language

Pattern: write an example `.idl` product that needs the new feature → run its scenarios to find the gap → add parser support → add engine support → tests. One feature per commit. The language reference is `docs/reference/` (one page per block, plus `grammar.md`); keep it in sync.

`docs/reference/not-yet-supported.md` lists known gaps.

## The website

`docs/` is a Jekyll site published by GitHub Pages from `main` (Just the Docs remote theme, no build tooling in the repo). Hand-written pages: `index.md`, `getting-started.md`, `reference/*.md`, `cli.md`, `design.md`, `glossary.md`, `contributing.md`. Generated pages: `docs/examples/*.md` and `docs/templates/*.md`, written by `scripts/site_pages.py` from the `.idl` files; never edit them by hand. The same script compiles `docs/reference/grammar.md` into `docs/assets/idl-grammar.json` (`scripts/grammar_table.py`), the automaton table the playground's completion walks; `tests/test_grammar.py` proves every example and template parses under the grammar page, so the page must be kept exact. Fenced ```` ```idl ```` blocks are highlighted client-side by `docs/assets/js/idl.js`. `docs/playground.md` runs `check` in the browser through Pyodide, fetching the engine and the products from the repository at `main` (`docs/assets/js/playground.js`); `tests/test_site.py` keeps its file and example lists in step with the package and the generator. Design decisions are in `docs/superpowers/specs/2026-09-07-website-design.md`.
