# Cover premiums and lines — Slice 1: Premium lines evaluated in order, with any base

> **Status:** ✅ Complete — 2026-09-07 — `4a2801c`
> **For agentic workers:** REQUIRED SUB-SKILL: Use jorj-skills:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Slice:** 1 of `docs/superpowers/specs/2026-09-07-cover-premiums-and-lines-slices.md`
**Spec:** `docs/superpowers/specs/2026-09-07-cover-premiums-and-lines-design.md`

**Goal:** `tax`, `fee` and `commission` become steps evaluated where they stand, so a tax's base can be `net`, `premium`, another word-named tax, or any expression; `tax` works inside `for each`.

**Architecture:** The parser wraps a line's expression as `rate × net` unless it already carries an `of`-base (`N% of …`), so `tax IPT 12%` keeps its meaning. `run_steps` evaluates a line when reached, with `net` (rounded), `premium` and earlier taxes in scope, and merges same-label lines. `rate()` inserts claims/underwriter loads before the first line rather than at the end. `round to` is read before the loop.

**Tech Stack:** Python 3.12 stdlib, `Decimal`, `unittest`.

## Global Constraints

- Standard library only; all money arithmetic in `Decimal`; never `float`.
- Buy-vs-build: reuse `parse_rating_steps`, `expression()` and `run_steps`; no new module.
- Operability: no new commands; `python3 -m unittest`, `check` on every example/template, `tests/test_grammar.py` against `docs/reference/grammar.md`; `scripts/site_pages.py` regenerates the grammar table.
- Every shipped example and template must price identically.

## Scaffolding Impact

- `docs/reference/rating.md` (line table, "belong outside the block" sentence, new words) → Task 4
- `docs/reference/grammar.md` (`each_block` allows `tax`; words `net`, `premium`, tax names) → Task 4
- `docs/assets/idl-grammar.json` regenerated → Task 4
- `docs/reference/cli.md` batch columns unchanged in shape; no update.

---

### Task 1: Parser: line bases, words in scope, `tax` inside `for each`

**Files:** Modify `ideclare/parser.py` (`parse_rating_steps`, `PER_ITEM_STEPS`, `calculated_steps`); Test `tests/test_parser.py`.

**Produces:** `RatingStep.amount` for `tax`/`commission` is always the absolute amount expression (`("*", rate, ("name","net"))` when no base was written); `fee` amount unchanged. `parse_rating_steps(lines, product, allowed=None, extra=frozenset())` where `allowed` is the step kinds permitted (None = all).

- [ ] Tests: `tax "S" 10% of IPT` after `tax IPT 12%` parses with amount `("*", ("pct", num 10), ("name","IPT"))`; `tax IPT 12%` parses to `("*", ("pct", num 12), ("name","net"))`; `tax "S" 10% of IPT` before any `tax IPT` → `unknown word 'IPT'`; `tax "X" 9% of premium` parses; `fee` inside `for each` → error `'fee' cannot be used inside 'for each'`; `tax` inside `for each` parses; `tax` under `calculated` → error.
- [ ] Implement; run `python3 -m unittest tests.test_parser`; commit.

### Task 2: Engine: lines evaluated in order, loads before the first line, `round` pre-read

**Files:** Modify `ideclare/engine.py` (`run_steps`, `rate`); Test `tests/test_engine.py`.

**Produces:** `run_steps(product, steps, ctx, net, trail, lines, prefix)` where `lines` is a list of `[kind, label, amount]` with rounded absolute amounts, same kind+label merged. `rate()` returns `Quote` as before.

- [ ] Tests: surcharge 10% of IPT on base 100 → lines `[("IPT", 12.00), ("S", 1.20)]`; `9% of premium` → 10.08; `add 10` after `tax IPT 12%` on base 100 → net 110, IPT 12.00 (order is semantic); claims loading 1.25 with tax → IPT on loaded net; `round to 1` after the tax still rounds the tax; per-item `tax "Fire" 22% of 20% of net when ebike is yes` over two bikes gives one line summing the e-bike's amount only; `net` in scope for a `when` unchanged.
- [ ] Implement; run full suite; run `check` on every example/template; commit.

### Task 3: CLI batch columns include per-item taxes

**Files:** Modify `ideclare/cli.py` (`batch` label discovery); Test `tests/test_cli.py`.

- [ ] Test: a product with `tax` inside `for each` shows that label as a batch column.
- [ ] Implement by walking `each` steps; commit.

### Task 4: Reference pages, grammar table, template scenario

**Files:** Modify `docs/reference/rating.md`, `docs/reference/grammar.md`, `templates/multi-item-product.idl` (a surcharge scenario), regenerate `docs/assets/idl-grammar.json` and `docs/templates/*.md`.

- [ ] Update: line table rows say "of the rounded net, or of the base after `of`"; add a "Lines in order" paragraph with `net`, `premium`, named taxes, per-item `tax`, order is semantic, loads before the first line; replace "`tax`, `fee` and `round` belong outside the block" with "`fee`, `commission` and `round` belong outside the block; `tax` may sit inside, on each item's net".
- [ ] Grammar: `each_block` steps include `tax`; words paragraph adds `net`, `premium` and word-named taxes inside a rating line.
- [ ] Run `python3 scripts/site_pages.py`, full suite; commit.
