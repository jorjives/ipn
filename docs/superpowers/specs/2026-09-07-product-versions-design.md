# Product versions: upgrading, dated amendments and renewal across versions

## Purpose

A customer stays on the version of a product they bought until the contract renews. A
new version may change the price, the wording or the questions asked. Today iDeclare
treats one file as the whole product for ever: renewal is "the same product repriced on
indexed answers", which silently assumes the file never changes. This spec adds what the
language needs to describe how one version becomes the next, and what the engine needs to
carry a policy from the version it was sold on to the version live when it renews, with
every step proven by scenarios in the usual way.

Agreed with Jorj in discussion on 2026-09-07. The decisions below are his where marked.

## Decisions

- **No version numbers.** A version is identified by its publication date (Jorj). Which
  version a policy is on is "the one live when it incepted or last renewed", which is how
  insurers already think. Any compatibility class (the semver-style patch/minor/major) is
  derived by the tool from the file, never declared.
- **Upgrade mappings are language, in expressions** (Jorj). How an old answer becomes a new
  one is underwriting knowledge and must be readable and provable, so it lives in the
  `.idl` and uses the existing expression language, not just key-to-key renames.
- **`ask` is the signal that a policy cannot move automatically** (Jorj). Whether a
  renewal can proceed unattended is decided per policy, when the upgrade runs, not per
  version.
- **Mid-term changes are dated amendments, not a version step.** A `from DATE` line is in
  effect for events on or after that date, on every policy in force whichever version it
  is on. They are permitted on cover and claims lines only: eligibility is moot once
  bound, and the premium charged for the term already stands (the engine enforces this).
- **The history is a collection of files** (Jorj). Where the history comes from (git or a
  directory) is a matter for the managing engineer, not the language. The engine takes a
  `History` object; the CLI builds one from the directory the file is in. No other source
  is built.
- **Buy-vs-build:** nothing bought; standard library only, as for the rest of the engine.
  The version chain is a fold over the files, not a migration framework.
- **Operability / DX:** `python3 -m ideclare check FILE` behaves exactly as before for a
  lone file. When other files in the same directory declare the same product name they
  are the history, found automatically. Every check the tool makes about versions is a
  parse-time or load-time error with a line number, or a scenario failure; nothing is
  silent.

## The language

### `published`

One new line in the product header:

```
product "Cycle Cover"
  published 2027-01-01
  territory UK
  term 12 months
```

The date the version goes on sale. A file without `published` is a single version, live
on every date, and behaves exactly as today. A file with `published` is one version of
the product; the others are the files in the same directory whose `product` name is the
same. Two versions with the same `published` date are an error.

**Which version is live on a date:** the one with the latest `published` on or before it.
Before the first version was published, nothing is live: binding then is refused.

**Which history a file sees:** only versions published on or before its own `published`
date. A proof written in an old version stays true after new versions are published; the
newest file is where migrations from every earlier version are proven.

### `upgrading`

A block describing how the answers held on the previous version become answers on this
one. The previous version is the one published immediately before this file, in the
history.

```
upgrading
  lock_rating
    security is gold: diamond
    security is silver: silver
    otherwise: bronze
  racing: no
  annual_mileage: ask
  total_value: bike_value + accessories_value
  bikes: for each bike
    lock_rating: security
```

- Each line names an input of **this** version and gives its value as an expression over
  the **previous** version's answers. Every bare word on the right-hand side is an input,
  item field or choice value of the previous version, or a choice value of the target.
  There is no `previous` keyword: the right-hand side always reads the old answers, so
  `security: diamond when ...` reads the old `security` even when the name is kept.
- The one-line form `name: <expression>` is for a value that needs no cases. The block form
  is rows of `condition: value` ending in `otherwise: value`, the same shape as a `factor`
  or an excess table; `otherwise` is required, as it is there.
- A value may be `ask`, on a line or in a row: this policy cannot be moved without the
  customer answering. `ask` in a row (`otherwise: ask`) means only policies that reach that
  row need asking.
- `name: for each <old item>` upgrades a collection item by item; the lines below use the
  old item's fields and the old top-level answers. Fields not mentioned are carried by
  name. The collection may be renamed (`cycles: for each bike`).
- An input **not mentioned** is carried from the previous version when an input of the
  same name and compatible type exists there (same kind; for a choice, the new choices
  include all the old ones; for a collection, its fields likewise). Otherwise it takes its
  `default`. An input that is neither carried, defaulted nor mentioned is an error when
  the history is loaded, naming the input: the author must say how it is derived, or
  `ask`. Inputs dropped by this version need no line. Calculated, enrichment-provided
  and `territory` inputs are not upgraded: calculated and provided values are recomputed,
  territory is carried.
- The value an expression produces is checked against the target input when the upgrade
  runs: a word that is not one of the target's choices, a number for a yes/no, are errors
  that fail the renewal loudly. A literal that can be checked when the file is read is
  checked then.
- A version with no `upgrading` block upgrades entirely by carrying and defaults.

**Upgrading across several versions** is the chain of each version's block in publication
order, each step turning answers in one version's shape into the next. An `ask` at any
step leaves that input unknown; an expression that reads an unknown input makes its own
target unknown. What is reported is the set of target inputs still unknown at the end.

### `from DATE` and `until DATE` on cover and claims lines

Any line inside a `cover` block or a `claim` block may begin with `from DATE`,
`until DATE`, or both:

```
cover Theft
  limit bike_value
  excludes when security is bronze and bike_value > 2000 because "Gold or silver rated lock required"
  from 2027-03-01 excludes when left_unattended_overnight because "Bikes must be secured overnight"
  until 2027-03-01 excludes when racing because "Racing was excluded until March 2027"

claims
  claim Theft
    pays claimed amount up to limit, less excess
    from 2027-03-01 pays claimed amount up to limit, less excess, less co-payment
```

- A dated line is in effect for an event on or after its `from` date and before its
  `until` date. An undated line is in effect on every date not covered by a dated line
  for the same setting.
- For a setting that has one value (`limit`, `excess`, `pays`, `available when`,
  `waiting period`, `requires`, `depreciation`, `counts`) the dated line in effect
  replaces the undated one. For a setting that is a list (`excludes`, `decline`,
  `co-payment`, `up to <amount> when` caps) every line in effect applies. Two dated
  lines in one version whose windows overlap on a one-valued setting are an error.
- `from` and `until` are not accepted anywhere else. `rating`, `eligibility` and
  `lifecycle` lines cannot be dated.
- An amendment applies to **every policy in force**, whichever version it is on: a policy
  on the version published 2026-01-01 whose claim falls on 2027-04-01 is settled on its own
  version's wording plus every dated line in effect that day from that version and every
  version published after it, later versions overriding earlier ones setting by setting.
  So an amendment is written once, in the version current when it was decided, and never
  copied. This is why a dated line must be written in words every version it reaches can
  evaluate: a dated line that uses a word some earlier version in the history does not
  know is an error when the history is loaded, naming the line and the version. The
  author's choices are to write it in shared words or to remove the version from the
  collection once no policy remains on it, which is the managing engineer's call.
- Where there is no event date (`quote` from the command line, `expect cover` before any
  event) only undated lines apply. In scenarios `expect cover` is evaluated at the last
  event's date, and a claim at its loss date.

### `adjustment: reprice on the current version`

```
lifecycle
  adjustment: reprice on the current version, charge pro rata difference, fee 10
```

By default an adjustment reprices on the version the policy is on: a mid-term change is
an endorsement to the existing contract. With `on the current version` the policy is
first upgraded to the version live on the adjustment date, then the changes are applied,
then it is repriced. The changes are given in the new version's words and satisfy any
`ask` the upgrade raised; an `ask` still unanswered refuses the adjustment, naming the
input. `held for the term` enrichments are checked as today.

### Renewal

Renewal moves the policy to the version live on the first day of the new term. The
expiring answers are indexed by the **expiring** version's `index` lines, then upgraded
along the chain to the new version, then repriced by the new version with the claims
loading and cap and collar as today (the cap and collar hold against the premium charged
for the expiring term, whichever version priced it). The new version's `decline when`
rules apply, on the upgraded answers. The lifecycle imposed by claims in the expiring
term (`after N claims in term` blocks) is the expiring version's, as now.

An offer whose upgrade left inputs unknown is neither offered nor declined: it **needs**
those answers. `when renewed on DATE with input value, input value` supplies them;
renewing without them is refused with "renewal needs annual_mileage". Asked item fields
are reported the same way (`bike.make`) but cannot be supplied in a scenario; that is the
one place where the engine's API is ahead of the scenario language.

### Scenarios

Nothing new is needed to prove a policy sold on an earlier version: `when bound on DATE`
binds under the version live on that date, and `given` is written in that version's words.
A scenario that binds before this file's `published` date is checked against the version
it binds under when it runs, not when the file is parsed; a scenario that binds on or
after it, or never binds, is checked against this file as today.

New:

| Line | Meaning |
|---|---|
| `when renewed on DATE with input value, ...` | accept the renewal, answering what the upgrade asked |
| `expect renewal needs input[, input]` | the renewal cannot proceed without these answers |
| `expect version DATE` | the `published` date of the version the policy is on |
| `expect <input> <value>` | an answer as the policy now holds it (after an upgrade, an index, an adjustment) |

`expect renewal premium`, `offered` and `declined` fail with "renewal needs ..." when the
upgrade asked. `expect refused` after `when renewed` and `when adjusted` works as for the
other events.

Example, in the version published 2027-01-01 whose predecessor asked `security`:

```
scenario "A 2026 customer renews onto the lock rating wording"
  given bike_value 2000, rider_age 30, security gold, racing no, previous_claims 0
  when bound on 2026-06-01
  expect version 2026-01-01
  when renewed on 2027-06-01
  expect version 2027-01-01
  expect lock_rating diamond
  expect premium 214.30

scenario "A 2026 customer with a bronze lock must be asked"
  given bike_value 2000, rider_age 30, security bronze, racing no, previous_claims 0
  when bound on 2026-06-01
  expect renewal needs lock_rating
  when renewed on 2027-06-01
  expect refused "renewal needs lock_rating"
  when renewed on 2027-06-01 with lock_rating bronze
  expect version 2027-01-01
```

## The engine

### `versions.py`: `History`

A new module owning everything about more than one version. Nothing else in the engine
knows how a history is found.

- `History(products)`: the versions, each a parsed `Product` with `published` set, sorted
  by date. Construction runs the load-time checks: distinct dates; for each consecutive
  pair, every input of the later version is mentioned, carried or defaulted, and every
  `upgrading` expression's words are known; every dated cover and claims line evaluates
  in the words of every earlier version. Errors are `ParseError` with the offending
  file's name and line.
- `History.for_file(path)`: the CLI's constructor. Parses the file; if it has
  `published`, reads the header of every other `.idl` in the same directory, parses those
  with the same product name and an earlier or equal `published`, and returns the
  history visible to this file. A file without `published` gives a history of one.
- `live_on(date) -> Product`: the version live on that date, or an error before the first.
- `upgrade(answers, from_version, to_version) -> (answers, needs)`: the chain fold.
  `needs` is the list of unknown target inputs, in declaration order.
- `cover(version, name, on) -> Cover` and `claim(version, name, on) -> ClaimRule`: the
  wording in effect for a policy on `version` on that date, dated amendments from later
  versions included. Materialised by parsing the applicable lines, memoised per window
  between consecutive dates.
- A `History` of one version, or `None`, reduces every method to today's behaviour, so the
  engine's existing tests hold without change.

### Parser

- `published DATE` in the header → `Product.published`.
- `upgrading` block → `Product.upgrading: list[Upgrade]`, where `Upgrade(target, rows,
  item)` holds rows of `(condition, value)` with `None` for `otherwise` and a value of
  `("ask",)` for `ask`. Expressions are parsed without the unknown-word check (the words
  belong to the previous version, which the parser does not have); `History` does that
  check. The block form's `otherwise` rule and the `for each` item check use the existing
  code paths for excess tables and rating `for each`.
- `from DATE` / `until DATE` prefixes on cover and claim child lines: the parser records
  each child line with its window on the `Cover` and `ClaimRule` (`dated: list[(from,
  until, Line)]`) and materialises the undated wording as today. It also materialises
  every window to validate the dated lines' syntax. `parse_cover` and `parse_claim` are
  split so that their body can be re-run over a chosen subset of lines; `History` reuses
  that to build cross-version wording.
- `adjustment: reprice on the current version, ...` → `Lifecycle.adjustment_upgrades`.
- `scenario` `given` lines are kept as tokens and resolved against the product at the end
  of `parse()` as today, except for a scenario whose first `when bound` date precedes
  `published`, whose `given` is left for the run to resolve.

### Engine

- `Policy(product, inputs, selected, history=None)`. `self.product` is the version the
  policy is on and changes at renewal, or at adjustment when the lifecycle upgrades.
- Every place the engine reads a cover or a claim rule for an event goes through
  `self.wording(name, on)`, which asks the history; with no history it is
  `product.cover(name)` as today. Places: `cover_state` (for a claim, at the loss date;
  for `expect cover`, at the date given), `claim`, `remaining`, `excess_remaining`,
  `reinstate`.
- `renew()`: target version from `history.live_on(self.expiry)`; index with the expiring
  version's lines; `history.upgrade`; `RenewalOffer` gains `version` and `needs`. Cap,
  collar and decline as now, on the target version.
- `accept_renewal(answers=None)`: refuses while `needs` remain after `answers`; otherwise
  switches `self.product`, sets the inputs, starts the term as now.
- `adjust(on, changes)`: with `adjustment_upgrades` and a newer live version, upgrades
  first; `changes` fill `needs`; refuses on anything still unknown.
- `version` property: `self.product.published`.

### Scenarios

- `Run` takes the history; the bound version is resolved on the first `when bound`; the
  `given` for an early-binding scenario is resolved then, in that version's words, and
  its failures are scenario failures on the `given` line.
- `when renewed ... with` and the three new expectations as in the table above.
  `expect <input> <value>` is the fallback when no `expect_` handler matches and the word
  is an input of the policy's version.

### CLI

`check` builds the history with `History.for_file` and passes it to the runs. Load-time
errors print as parse errors do and return 1. `quote` and `batch` are unchanged: a single
undated risk on the file given.

## Errors, in one place

| When | Error |
|---|---|
| Two versions share a `published` date | `cycle-2.idl: published 2027-01-01 is also the date of cycle-1.idl` |
| A new input has no line, no carry, no default | `line N: annual_mileage is new in this version; add it to upgrading, or give it a default` |
| An `upgrading` line names an input this version does not have | `line N: unknown input 'foo'` |
| An `upgrading` expression uses a word the previous version does not know | `line N: unknown word 'lock_rating' in the version published 2026-01-01` |
| A block form lacks `otherwise` | as excess tables: `an upgrading table must end with an 'otherwise' row` |
| An upgrade yields a value the target cannot hold | scenario failure: `lock_rating cannot be 'platinum'; it is a choice of bronze, silver, gold, diamond` |
| A dated line uses a word an earlier version lacks | `line N: 'lock_rating' is not known to the version published 2026-01-01, which this amendment reaches` |
| `from`/`until` outside cover or claims | `line N: only cover and claims lines can be dated` |
| Renewing with `needs` unanswered | refused: `renewal needs annual_mileage` |
| Binding before the first version | refused: `no version of Cycle Cover was on sale on 2025-01-01` |

## Testing

- `tests/test_versions.py`: `History` in isolation, built from products parsed from
  strings: live-on resolution (before first, on a boundary, after last), carry and
  default rules, type compatibility, chain over three versions with an `ask` in the
  middle poisoning a dependent, exhaustiveness errors, dated-line cross-version
  materialisation and the shared-words check.
- `tests/test_parser.py`: `published`, both `upgrading` forms, `for each`, `ask`,
  `from`/`until` accepted on cover and claim lines and rejected elsewhere, the new
  adjustment line, deferred `given`.
- `tests/test_engine.py`: renewal onto a new version with and without `needs`; adjustment
  on the current version; a claim on an old-version policy settled with a later
  amendment; a `History` of one changing nothing.
- `tests/test_scenarios.py`: the new `when` and `expect` lines, `expect refused` for a
  needed answer.
- `examples/versioned/`: three versions of one small product (`bike-2026-01-01.idl`,
  `bike-2026-07-01.idl` changing the rating and adding a dated exclusion,
  `bike-2027-01-01.idl` replacing `security` with `lock_rating` and adding a new input
  that is asked for some policies), the newest carrying scenarios that bind under each
  earlier version and renew, adjust and claim across them. Checked by the same loop as
  the other examples.
- Every existing test and example passes unchanged: a lone file is a history of one.

## Not built, and why

- **Deriving a compatibility label** (`ideclare diff`). The information is all present
  (a dated line, an `upgrading` block with `ask`, a rating change) but no one has asked
  for the label; the engine reports per policy instead, which is the more useful fact.
- **Flagging stale dated lines** (a `from` older than any policy could still predate).
  Cheap once `term` is a plain number; add when a real product accumulates them.
- **Supplying asked item fields at renewal in a scenario.** The engine reports them; the
  scenario syntax for per-item answers on renewal is deferred until a product needs it.
- **Git as a history source.** The `History` boundary is where it would plug in; the
  managing engineer's tool, not the language's.
- **Amendments that cannot be written in shared words.** Deliberately an error rather than
  a partial application; see the dated-lines section.
