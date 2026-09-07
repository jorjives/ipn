# Cover premiums, ordered lines and cover classes: slice scope

**Spec:** `docs/superpowers/specs/2026-09-07-cover-premiums-and-lines-design.md`

Each slice is a working end-to-end increment proven by scenarios in `examples/` and by the
`quote` command. A product that uses none of the new words must price exactly as before after
every slice (full existing suite green, every example and template still passing `check`).

**Build note (every slice):** reuse the engine's own machinery: `Decimal` arithmetic, the
existing rating-step parser for cover premium blocks (as `calculated` inputs already do), the
expression language's known words for cover names, the trail for per-item figures. Nothing is
bought and nothing is hand-rolled that the engine already does.

**Operational note (every slice):** no new commands. Verification stays `python3 -m unittest`,
`check` on every example and template, and the grammar test against the reference page; the
reference pages and the generated grammar table are updated in the same slice as the behaviour.

## Slice 1: Premium lines evaluated in order, with any base

**Status:** ✅ Complete — 2026-09-07 — `4a2801c`

**Scope:** `tax`, `fee` and `commission` become steps evaluated where they stand; `net`,
`premium`, word-named taxes and cover names (whole net for now, as no shares exist yet) in
scope for a line's expression; `N%` alone stays "of net"; claims and underwriter loads
inserted before the first line; `tax` inside `for each` with same-label lines summed;
`round to` read before any step runs; reference and grammar pages updated.

**Prerequisites:** the `when` clause on lines (already shipped).

**Acceptance criteria**
- `tax "Surcharge" 10% of IPT` after `tax IPT 12%` gives 10% of the IPT amount; `expect tax
  "Surcharge"` proves it. A quoted tax label used as a base is a parse error naming the line.
- `tax "QST" 9% of premium` is 9% of the net plus every line above it.
- `tax "Fire protection" 22% of 20% of net when ebike is yes` inside `for each bike` charges
  each e-bike's rounded net and the quote shows one "Fire protection" line.
- A product with a claims loading or an underwriter's load prices as today: the loads apply
  before the first tax line whatever its position.
- Every shipped example and template prices identically.
- `fee` or `commission` inside `for each` is a parse error.

**Human UAT:** `python3 -m ideclare check examples/irish-cycle.idl` still passes, and a new
scenario in a template shows a surcharge on a tax on the quote.

## Slice 2: Premium attributed to covers with classes

**Status:** ✅ Complete — 2026-09-07 — `4a2801c`

**Scope:** `class` on a cover; `for <Cover>` on `base`, `add`, `factor`, `discount`, `load`;
`allocate` key; shares carried through every step and rounded with the residue to the largest;
unattributed premium with no `allocate` is a rating error; lines attributed in proportion to
their base evaluated per cover (`of Fire`, `of net less Fire`), fees never; `Quote.shares` and
`by_class()`; `quote` prints per-cover and per-class blocks; `batch` gains per-cover columns;
`expect net for Cover`, `expect tax Name for Cover`, `expect commission Name for Cover`,
`expect net for class X`, `expect tax Name for class X`; reference pages updated.

**Prerequisites:** lines evaluated in order with cover names accepted in their expressions.

**Acceptance criteria**
- Cycle with classes 9 and 3, `add "Racing cover" 45 for Racing`, and `allocate 60/40` shows
  three shares summing to the net after the minimum and maximum; `expect net for Theft`
  passes; a 1-cent residue lands on the largest share.
- `tax "Fire tax" 22% of Fire` is attributed wholly to Fire; `tax IPT 12% of net less Fire`
  is split across the other covers in proportion; the fee has no share.
- `expect net for class 3` sums the covers with that class.
- `for` on `minimum`, on a line, or naming an unknown cover; `allocate` rows not summing to
  100%: parse errors at the right line. A `class`ed product with unattributed premium and no
  `allocate` fails to price with the amount named.
- `quote` on such a product prints the shares and class subtotals; `batch` writes a column
  per cover per attributed figure after the existing columns.
- A product with no `class`, `for` or `allocate` has no shares and prints as today.

**Human UAT:** `python3 -m ideclare quote examples/cycle.idl ...` shows Theft, Accidental
Damage and Racing each with their net and IPT, and class subtotals 3 and 9.

## Slice 3: Covers that price themselves

**Scope:** `premium <expression> [when ...]` and a `premium` block on a cover; `add cover
premiums` (once, outside or inside `for each`); per-item cover premiums from item fields;
unselected or excluded covers have no premium; parse errors for lines or loops inside a
premium block, rating words in a cover premium, fields of two collections, missing or
repeated `add cover premiums`; household moved to cover-side prices with classes; the
e-bike fleet example; reference pages updated.

**Prerequisites:** shares carried through rating and shown by `quote`; lines attributed.

**Acceptance criteria**
- Household with `premium 0.15% of rebuild_cost` on Buildings and `premium 0.5% of
  contents_sum` on Contents prices exactly as before the move (its scenarios unchanged), and
  each section shows its share after the bundle discount and the minimum.
- A cover with a `premium` block (base, factor table, minimum) prices as the same steps
  would in a `calculated` input.
- `premium 0.5% of value when ebike is yes` on Fire in a fleet of pedal and e-bikes gives Fire
  the sum over e-bikes; `add cover premiums` inside the loop places it per bike, outside the
  loop places the sum.
- An unselected optional cover contributes nothing; an excluded cover contributes nothing.
- Each parse error above lands on the offending line.

**Human UAT:** `python3 -m ideclare check examples/ebike-fleet.idl` shows fire tax only on
the e-bikes' share and classes 3, 8 and 9 on the quote.

## Slice 4: Lifecycle amounts split by cover

**Scope:** `Policy.split(amount)` in proportion to each cover's earning share of the current
quote; `expect refund for Cover`, `expect additional premium for Cover`, `expect return
premium for Cover`, `expect renewal premium for Cover`; reference page for scenarios updated.

**Prerequisites:** quotes carry rounded per-cover shares of net and taxes.

**Acceptance criteria**
- A pro rata cancellation on the e-bike fleet refunds, and `expect refund for Fire` is Fire's
  share of the refund (fees excluded, residue to the largest share).
- An adjustment that adds an e-bike shows the additional premium split with Fire's share
  grown; a downward adjustment splits the return premium.
- A renewal offer's premium splits by the renewal quote's shares.
- A product with no shares: the split is the whole amount under one unnamed share, and the
  `for Cover` expectations are a scenario error naming the cover.

**Human UAT:** `python3 -m ideclare check examples/ebike-fleet.idl` shows a mid-term
cancellation with the refund per cover.
