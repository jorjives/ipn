# Cover premiums and lines — Slice 2: Premium attributed to covers with classes

> **Status:** ✅ Complete — 2026-09-07 — `4a2801c`
> **For agentic workers:** REQUIRED SUB-SKILL: Use jorj-skills:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Slice:** 2 of `docs/superpowers/specs/2026-09-07-cover-premiums-and-lines-slices.md`
**Spec:** `docs/superpowers/specs/2026-09-07-cover-premiums-and-lines-design.md`

**Goal:** every figure a quote produces can be split by cover (and summed by class): `class` on a cover, `for Cover` on rating steps, `allocate` for the shared pool, lines attributed by their base, `Quote.shares`, shown by `quote`/`batch` and provable in scenarios.

**Architecture:** `run_steps` keeps the net as a dict of shares (`""` is the unattributed pool); the net is their sum. One helper `split(total, weights, quantum)` does every proportional split with the residue to the largest weight: rounding shares, applying `allocate`, attributing a line, and (slice 4) lifecycle amounts. A quoted cover or tax label in a line's expression is rewritten to a name at parse time, so `of "Accidental Damage"` works like `of Fire`.

**Tech Stack:** Python 3.12 stdlib, `Decimal`, `unittest`.

## Global Constraints

- Stdlib only; `Decimal` everywhere; a product using none of the new words prices and prints exactly as today.
- Buy-vs-build: reuse `parse_rating_steps`, `expression()`, `run_steps`, `known_words`; no new module.
- Operability: no new commands; suite, `check` on every product, grammar test, `scripts/site_pages.py`.

## Scaffolding Impact

- `docs/reference/cover.md` (`class`) → Task 6
- `docs/reference/rating.md` (`for`, `allocate`, cover bases, quoted labels now addressable: correct the slice-1 sentence) → Task 6
- `docs/reference/scenarios.md` (`expect ... for Cover`, `for class`) → Task 6
- `docs/reference/cli.md` (quote share blocks, batch columns) → Task 6
- `docs/reference/grammar.md` + `docs/assets/idl-grammar.json` → Task 6
- `examples/cycle.idl` gains classes and `allocate`; generated pages → Task 6

---

### Task 1: Parser: `class`, `for Cover`, `allocate`, quoted labels as bases
**Files:** `ideclare/model.py` (`Cover.class_`, `RatingStep.cover`, `Product.allocation`, `Product.attributed`), `ideclare/parser.py`, `tests/test_parser.py`.
- [ ] Tests: `class 8` parses to `cover.class_ == "8"`; `add "Fire" 45 for Fire when Fire selected` sets `step.cover == "Fire"` and the condition; `factor "Theft area" for Theft` table form and `factor "X" x 1.3 for Theft` single-row form; `minimum 10 for Theft` → error "'for' cannot be used on minimum"; `for Nowhere` → "unknown cover 'Nowhere'"; `allocate` rows sum to 100% else error "allocate rows sum to 90%, not 100%"; `allocate` with unknown cover → error; `tax "S" 10% of "Government levy"` after `tax "Government levy" 3%` parses to `("*", pct, ("name", "Government levy"))`; `tax "F" 22% of "Accidental Damage"` likewise; `product.attributed` true when any of class/for/allocate is used.
- [ ] Implement; commit.

### Task 2: Engine: shares through every step, `split`, allocation, `Quote.shares`
**Files:** `ideclare/engine.py`, `tests/test_engine.py`.
- [ ] Tests: `split(Decimal("10.00"), {"a": 1, "b": 1, "c": 1}, Decimal("0.01"))` → 3.34/3.33/3.33 with the extra cent on the first largest; base + `add 45 for Racing` + `allocate 60/40` + `minimum`/`maximum` → shares scale alike and sum to the rounded net; `factor x 1.3 for Theft` scales only Theft; `discount 10%` scales all; `for each` items' shares add up; classed product with a pool and no allocate → `ExprError` naming the amount; unattributed product → `shares == []`; `by_class()` sums.
- [ ] Implement; commit.

### Task 3: Lines attributed by their base
- [ ] Tests: `tax "Fire tax" 22% of Fire` wholly to Fire; `tax IPT 12% of net less Fire` split over the others in proportion; `tax IPT 12%` split in proportion to net; fee has no share; commission attributed; a tax on a tax follows the first tax's shares.
- [ ] Implement (per-cover evaluation with the cover's figures, then `split`); commit.

### Task 4: Scenario expectations
**Files:** `ideclare/scenarios.py`, `tests/test_scenarios.py`.
- [ ] Tests: `expect net for Theft 40.00`, `expect tax IPT for Theft 4.80`, `expect commission "Broker" for Theft 6.00`, `expect net for class 9 40.00`, `expect tax IPT for class 9 4.80`; unknown cover → failure text "no share for 'X'"; `expect net for bike 1` unchanged.
- [ ] Implement; commit.

### Task 5: CLI
**Files:** `ideclare/cli.py`, `tests/test_cli.py`.
- [ ] Tests: `quote` prints `Shares:` block lines `  Theft (class 9)  net 40.00  IPT 4.80` and `By class:`; a product without attribution prints nothing new; `batch` header gains `net:Theft`, `IPT:Theft`, … after `currency` and commission and before `error`.
- [ ] Implement; commit.

### Task 6: Docs, grammar, cycle example
- [ ] Update the pages listed under Scaffolding Impact; cycle gets `class 9`/`class 3`, `add "Racing cover" 45 for Racing when Racing selected`, `allocate`, and scenario lines `expect net for Theft`/`for class 3`; `python3 scripts/site_pages.py`; suite; commit.
