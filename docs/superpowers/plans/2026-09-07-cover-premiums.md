# Cover premiums and lines — Slice 3: Covers that price themselves

> **Status:** ✅ Complete — 2026-09-07 — `4bb9050`
> **For agentic workers:** REQUIRED SUB-SKILL: Use jorj-skills:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Slice:** 3 of `docs/superpowers/specs/2026-09-07-cover-premiums-and-lines-slices.md`
**Spec:** `docs/superpowers/specs/2026-09-07-cover-premiums-and-lines-design.md`

**Goal:** a cover may carry `premium <expr> [when ...]` or a `premium` block of rating steps; `add cover premiums` places them in the net (once, outside or inside `for each`); unselected or excluded covers contribute nothing; household moves its section prices onto its covers; a new e-bike fleet example.

**Architecture:** `Cover.premium` is a list of `RatingStep` (the expression form is one `base` step with the `when` as its condition), parsed by `parse_rating_steps` with the per-item kinds, exactly as a `calculated` input is. `Cover.premium_item` names the collection singular when the steps read item fields. `add cover premiums` is a `RatingStep("premiums", label=<loop singular or "">)`; the engine runs each included cover's steps with `run_steps` and credits the total to that cover's share, per item inside a loop and summed outside. Cover inclusion is the same check `cover_state` makes, factored out so both use it.

**Tech Stack:** Python 3.12 stdlib, `Decimal`, `unittest`.

## Global Constraints

- Stdlib only; `Decimal` everywhere; a product with no cover `premium` prices and prints exactly as today.
- Buy-vs-build: reuse `parse_rating_steps`, `expression()`, `run_steps`, `cover_state`'s checks; no new module.
- Operability: no new commands; suite, `check` on every product, grammar test, `scripts/site_pages.py`.

## Scaffolding Impact

- `docs/reference/cover.md` (`premium`) → Task 4
- `docs/reference/rating.md` (`add cover premiums`, per item) → Task 4
- `docs/reference/grammar.md` + `docs/assets/idl-grammar.json` → Task 4
- `examples/household.idl` rewritten; `examples/ebike-fleet.idl` new; `scripts/site_pages.py` and `docs/playground.md` lists; generated pages → Task 4

---

### Task 1: Parser and model
**Files:** `ideclare/model.py`, `ideclare/parser.py`, `tests/test_parser.py`.
- [ ] Tests: `premium 0.15% of rebuild_cost when Buildings selected` → one `base` step with condition; `premium` block with `base`/`factor`/`minimum` → steps; `tax` or `for each` inside the block → error naming the line "'tax' cannot be used in a cover premium"; `premium 0.5% of value when ebike is yes` → `premium_item == "bike"`; fields of two collections → error; `premium 10% of net` → "unknown word 'net'"; `premium 10% of Theft` → "'Theft' is a cover, not an input"; `add cover premiums` → `RatingStep("premiums")`, inside `for each bike` → label "bike"; missing → "cover premiums never join the net; add 'add cover premiums' to rating"; twice → "cover premiums join twice"; present with no cover premium → "no cover has a premium"; `product.attributed` true.
- [ ] Implement; commit.

### Task 2: Engine
**Files:** `ideclare/engine.py`, `tests/test_engine.py`.
- [ ] Tests: household-shaped product prices as its `add` form did and shares are per section; a `premium` block prices as the same steps in `calculated` would; an unselected optional cover and an excluded cover contribute nothing; per-item premium summed at an outer `add cover premiums` and placed per bike at an inner one (trail order); a cover with both `premium` and an `allocate` row takes both.
- [ ] Implement (`included(cover, ctx)` factored from `cover_state`; `cover_premiums()`); commit.

### Task 3: Household on cover premiums; e-bike fleet example
- [ ] `examples/household.idl`: classes 8/9, `premium` on each section, `add cover premiums`, share expectations; scenarios unchanged otherwise. New `examples/ebike-fleet.idl` with classes 3/8/9, fire on e-bikes only, `tax "Fire levy" 20% of Fire`, `tax IPT 12% of net less Fire`; `check` passes; commit.

### Task 4: Docs, grammar, site lists
- [ ] cover.md, rating.md, grammar.md; `scripts/site_pages.py` EXAMPLES and `docs/playground.md` gain ebike-fleet; `python3 scripts/site_pages.py`; suite; commit.
