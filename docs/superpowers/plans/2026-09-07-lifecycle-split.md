# Cover premiums and lines — Slice 4: Lifecycle amounts split by cover

> **Status:** ✅ Complete — 2026-09-07 — `bb86bc8`
> **For agentic workers:** REQUIRED SUB-SKILL: Use jorj-skills:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Slice:** 4 of `docs/superpowers/specs/2026-09-07-cover-premiums-and-lines-slices.md`
**Spec:** `docs/superpowers/specs/2026-09-07-cover-premiums-and-lines-design.md`

**Goal:** any amount a policy produces over its life (refund, adjustment difference, renewal premium) can be split across covers in proportion to each cover's earning share (net plus taxes) of the quote it came from; scenarios prove it with `expect refund for Fire`, `expect additional premium for Fire`, `expect return premium for Fire`, `expect renewal premium for Fire`.

**Architecture:** `Quote.split(amount)` shares an amount by each cover's earning (`net` plus its tax lines) using the existing `split()` helper, residue to the largest; a quote with no shares returns `{"": amount}`. `Policy.split(amount)` is the current quote's split; `RenewalOffer` keeps the quote it was priced on so a renewal premium splits by the renewal quote. No lifecycle arithmetic changes.

**Tech Stack:** Python 3.12 stdlib, `Decimal`, `unittest`.

## Global Constraints

- Stdlib only; `Decimal` everywhere; a product with no shares is unchanged.
- Buy-vs-build: reuse `split()`, `Quote.shares`, the scenarios' `share()` lookup.
- Operability: no new commands; suite, `check` on every product, grammar test, `scripts/site_pages.py`.

## Scaffolding Impact

- `docs/reference/scenarios.md` (lifecycle `for Cover` forms) → Task 3
- `docs/reference/grammar.md` + `docs/assets/idl-grammar.json` → Task 3
- `examples/ebike-fleet.idl` gains a cancellation scenario with the refund per cover; generated page → Task 3

---

### Task 1: `Quote.split`, `Policy.split`, renewal offer keeps its quote
**Files:** `ideclare/engine.py`, `tests/test_engine.py`.
- [ ] Tests: on the e-bike fixture bound and cancelled, `policy.split(refund)` sums to the refund and follows net + tax per cover (Fire's share carries its levy); a plain product gives `{"": amount}`; `offer.quote.shares` present on a renewal offer.
- [ ] Implement; commit.

### Task 2: Scenario expectations
**Files:** `ideclare/scenarios.py`, `tests/test_scenarios.py`.
- [ ] Tests: `expect refund for Fire X`, `expect additional premium for Fire X` (adding an e-bike grows Fire's share), `expect return premium for Fire X`, `expect renewal premium for Fire X`, `for class 8`; unknown cover → "no share for 'X'"; a plain product → "no share for 'X'".
- [ ] Implement; commit.

### Task 3: Example, docs, grammar
- [ ] `examples/ebike-fleet.idl`: customer cancels 2026-07-01 the three-bike fleet bound 2026-01-01: refund (271.94 x 184/365) - 10 = 127.09; Fire 12.62, Theft 76.31, Accidental Damage 38.16. scenarios.md rows; grammar `expectation` lines; `python3 scripts/site_pages.py`; suite; commit.
