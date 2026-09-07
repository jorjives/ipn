# Cover premiums, ordered premium lines and cover classes

Date: 2026-09-07. From a brainstorm with Jorj that began with "how would IDL apply two taxes"
and arrived at premium attribution. Three requirements drive it:

1. A tax may be charged on a base other than the whole net: a deemed fire proportion, a
   cover's share, another tax, or the running total (Austria, Germany, Italy, Canada).
2. Regulators report per cover class. The Austrian FMA wants each policy's premium split by
   class under VAG 2016 Anlage A (3 Landfahrzeug-Kasko, 8 Feuer, 9 sonstige Sachschäden), with
   each class carrying its share of net and of each tax, on every amount the policy produces
   over its life (premium, refund, adjustment, renewal).
3. Reporting itself is not a language feature. The engine exposes the split; the platform the
   product lives on does the reporting. There is no `report` command.

The design is the hybrid chosen in the brainstorm: a cover may carry a `class` and price
itself with `premium`; a rating step may be credited to a cover with `for`; whatever is left
unattributed is split by an `allocate` key; and tax, fee and commission lines become ordinary
steps evaluated where they stand, so a base is just an expression.

## Decisions

- **Attribution is a partition of the net, not a snapshot.** Every rating step keeps a vector
  of shares (one per cover, plus the unattributed pool) in step with the running net.
  Multiplicative steps and bounds scale every share alike, so a discount or a minimum written
  after `allocate` does not need re-allocating. This is what makes `allocate` a key rather
  than a step: its position carries no meaning, like `round to`.
- **Buy-vs-build.** Nothing to buy: the arithmetic is `Decimal` in the standard library, as
  everywhere in the engine. Prior art in this estate is reused throughout: cover `premium`
  blocks are parsed by `parse_rating_steps` exactly as `calculated` inputs are; cover names are
  already known words in expressions (`Racing selected`), so `of Fire` needs no new syntax;
  the trail already records per-item shares.
- **Operability/DX.** No new commands. `quote` prints shares under the premium; `batch` gains
  one column per cover per line. Scenarios prove shares with `expect ... for Cover`. `check`
  on every example and template, `python3 -m unittest`, and `tests/test_grammar.py` against the
  grammar page remain the whole verification story. The playground needs nothing beyond the
  regenerated grammar table.
- **Fees are never attributed.** A fee is a policy-level charge earned on day one; the report
  carries it at policy level. Taxes and commission are attributed.
- **Lines are attributed in proportion to their base evaluated per cover.** One rule covers
  `of net`, `of Fire`, `of net less Fire`, `of IPT` and `of premium` without special cases.
- **The cent goes to the largest share.** Every split that must sum to a rounded total gives
  any residue to the largest share; ties go to the first declared cover. Deterministic on every
  machine, as the rest of the engine.
- **Backwards compatible.** A product that uses none of `class`, `premium`, `for`, `allocate`
  or `add cover premiums` prices exactly as today and has no shares. The only visible change
  to such products is that a tax line's position now matters; no shipped example or template
  has a net-changing step after a line, so nothing reprices.

## Language

### cover

```
cover Fire optional
  class 8
  premium 0.05% of rebuild_cost when construction is timber
  limit rebuild_cost
```

- `class <word>`: the regulatory class the cover reports under. A word, not a number, so
  `class 8`, `class 9a` and `class Kasko` all work; the engine does not interpret it. Several
  covers may share a class; the quote's class subtotals sum them.
- `premium <expression> [when <condition>]` prices the cover on its own. The expression is the
  full expression language (arithmetic, `N% of x`, functions, `rate from "Table"`, `count of`,
  `any ... where`, calculated inputs). With `when`, an unmet condition gives no premium.
- `premium` on its own line followed by indented rating steps (`base`, `factor`, `add`,
  `discount`, `load`, `minimum`, `maximum`, each with its usual `when`) prices the cover as a
  `calculated` input is computed. Lines (`tax`, `fee`, `commission`, `round`) and `for each`
  are rejected inside it with a parse error naming the line.
- An optional cover that is not selected, or a cover excluded for the risk, has no premium.
- **Per item.** A premium expression that names an item field (a field of exactly one
  collection) is priced once per item of that collection, with that item's fields in scope,
  and the cover's contributions are one share summed over items. Naming fields of two
  collections is a parse error. A cover premium cannot read `net`, `premium`, a tax name or
  another cover's name: those are rating words, and the parse error says so.

### rating

```
rating
  base 3.5% of bike_value
  factor "Rider age" ...
  add cover premiums
  add "Battery loading" 0.5% of value for Fire when ebike is yes
  factor "Theft area" x 1.30 for Theft when theft_area is high
  allocate
    "Accidental Damage" 60%
    Theft 40%
  minimum 60
  tax "Fire protection tax" 22% of Fire
  tax "Insurance tax" 19% of net less Fire
  fee "Policy fee" 10 when net >= 20
  commission "Broker" 15% of net
```

- `add cover premiums` marks where cover-priced premiums join the running net. Required
  exactly once in a product where any cover has `premium`; a parse error otherwise ("cover
  premiums never join the net" / "cover premiums join twice"). Written inside `for each item`,
  it adds the current item's per-item cover premiums; per-item cover premiums whose loop has
  no `add cover premiums` join, summed, at the outer one. Each cover's premium joins exactly
  once.
- `for <Cover>` on `base`, `add`, `factor` (single-row and table forms), `discount` and `load`
  credits or scales that cover's share only. `for` goes after the amount and before `when`:
  `add "Fire" 45 for Fire when Fire selected`. On `minimum`, `maximum` or a line it is a parse
  error. Naming an unknown cover is a parse error.
- `allocate` splits the unattributed pool by proportion. Its rows are `<Cover> N%`; they must
  sum to 100% or the parse fails with the actual sum. A cover that has `premium` may still
  appear (it takes a share of the pool as well as its own premium). Its position in `rating`
  does not matter.
- If any cover has `class` or `premium`, or any step has `for`, and there is no `allocate`,
  the unattributed pool must be zero at the end of rating; otherwise rating raises an error
  naming the amount left unattributed. A product with none of these has one unattributed
  pool and no shares.
- **Lines in order.** `tax`, `fee` and `commission` are evaluated where they stand. Their
  expressions may read `net` (the running net so far, rounded to the currency unit as the
  customer sees it), `premium` (net plus every line above), a word-named tax declared above
  (`tax IPT 12%` makes `IPT` a name holding 12% of net; quoted labels are not addressable), and
  any cover name (its share of the net so far). `N%` on its own, or any expression without an
  `of`-base, means that rate of `net`, as today (`tax IPT ipt from "Territory"` still works).
  The `when` from the earlier commit stays.
- `tax` is allowed inside `for each`, evaluated on the item's rounded net; lines with the
  same label across items and across the product sum into one line, each item's amount
  rounded first. `fee` and `commission` stay outside the loop.
- `round to` keeps its meaning and its position-independence: it is read before any step runs.
- Claims loading and the underwriter's load, which the engine appends after the product's
  steps, are inserted before the first line instead, so "tax follows a load, fees do not"
  stays true.

### scenarios

- `expect net for Fire 12.00`, `expect tax "Insurance tax" for Fire 2.28`,
  `expect commission "Broker" for Fire 1.80`: one cover's share of a figure.
- `expect net for class 8 12.00`, `expect tax IPT for class 8 1.44`: a class subtotal.
- `expect refund for Fire 6.00`, `expect additional premium for Fire 3.00`,
  `expect return premium for Fire 3.00`, `expect renewal premium for Fire 12.50`: a cover's
  share of a lifecycle amount.
- The existing `expect net for bike 2 X` is unchanged; the word after `for` decides (an item
  singular, a cover name, or `class`).

## Engine

### Shares during rating

`run_steps` carries `shares: dict[str, Decimal]` alongside `net`, keyed by cover name with
`""` for the unattributed pool; the invariant `sum(shares.values()) == net` holds after every
step, unrounded.

| Step | No `for` | `for Cover` |
|---|---|---|
| `base`, `add` | joins the pool | credited to the cover |
| cover `premium` (via `add cover premiums`) | credited to its cover | |
| `factor`, `discount`, `load` | every share scaled by the same ratio | that cover's share scaled; net moves by the difference |
| `minimum`, `maximum` | every share scaled so the sum meets the bound | not allowed |
| `allocate` | after the last step: pool split by the key, then the pool is empty | |
| `for each` | the item's shares are added to the outer shares | |

A `base` with no `for` replaces the pool (the net is reset, as today) and clears cover shares
built so far; the reference says `base` starts the net.

### Rounded shares

After rating, the net is rounded as today. Shares are rounded to the same unit with the
residue to the largest share, so rounded shares sum to the rounded net.

### Lines

Each line's amount is evaluated where it stands with the words above in scope and is rounded.
It is then attributed by evaluating the same expression once per cover with that cover's
figures in place of the totals (`net` = the cover's net share, a cover name = its share if
this is that cover else 0, a tax name = the cover's share of that tax, `premium` = the cover's
net plus its line shares so far); the amounts are scaled so they sum to the line's rounded
amount, residue to the largest. A linear base (every base in this spec) attributes exactly;
the scaling only guards a non-linear one. A fee is not attributed. A commission is attributed
like a tax but reported apart, as today.

### Quote

`Quote` gains `shares: list[Share]` where `Share(cover: str, class_: str, net: Decimal,
lines: list[tuple[str, Decimal]], commission: list[tuple[str, Decimal]])`, one per cover with a
non-zero share, in declaration order. `Quote.earning` is unchanged. A helper
`Quote.by_class()` sums shares with the same class; a cover with no `class` reports under
`""`. A product with no attribution has `shares == []`.

### Lifecycle

Every amount the policy produces over its life that earns (a refund, an adjustment's
difference, a renewal's premium) is a scalar today and stays so. `Policy.split(amount)`
returns the amount divided across the covers in proportion to each cover's earning share of
the current quote (net share plus its tax shares), rounded with the residue to the largest.
Scenarios' `expect ... for Cover` on a lifecycle figure call it; the platform can call it on
whatever it settles. No lifecycle arithmetic changes.

### CLI

- `quote` prints, after the total, one block per cover with a share: the cover, its class,
  its net and each attributed line, then a class subtotal block when any cover has a class.
- `batch` adds columns `net:<Cover>` and `<Line>:<Cover>` for every cover that can carry a
  share and every attributed line, after the existing columns and before `error`, so today's
  columns keep their positions.

## Errors

Parse errors, each naming the line: `for` on a bound or a line; unknown cover after `for` or
in `allocate`; `allocate` rows not summing to 100%; a line or `for each` inside a cover
`premium` block; a cover premium reading rating words or fields of two collections;
`add cover premiums` missing or repeated when covers have premiums; `add cover premiums` in a
product where no cover has one. Rating errors, raised as `ExprError` so `quote` and `batch`
report them as they report a table miss: unattributed premium left with no `allocate`.

## Testing

- `tests/test_engine.py`: shares after each step kind (the table above, one test per row),
  rounding residue, per-item cover premiums, `add cover premiums` inside and outside a loop,
  lines in order (`net`, `premium`, named tax, cover base, `net less Fire`), per-item `tax`,
  the loads inserted before the first line, `Policy.split`.
- `tests/test_parser.py`: every error above; `allocate` position independence; `class` as a
  word.
- the test file that covers `expect` lines: each new `expect` form.
- `tests/test_cli.py`: `quote` share block, `batch` columns and their order.
- Examples: `examples/household.idl` moves its section prices onto the covers and gains
  classes; a new `examples/ebike-fleet.idl` (mixed pedal and e-bikes, fire on e-bikes only, a
  fire-only tax and a class 3/8/9 split, not attributed to any real country's rates); the
  `docs/reference` pages for `cover`, `rating`, `scenarios`, `cli` and `grammar.md` updated;
  `scripts/site_pages.py` regenerated; `tests/test_grammar.py` proves the corpus.

## Out of scope

Per-cover refund terms (a cover cancelled on its own), per-cover instalments, a report
command, a `share` keyword on covers (dropped in favour of `allocate`), and cover shares in
claims or bordereaux beyond commission.
