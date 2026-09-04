# iDeclare: a declarative insurance product language

## Purpose

Let an insurance professional (product manager, underwriter, pricing actuary) define a
complete policy product in one readable text file: what is asked, who is eligible, what
is covered, how it is priced, how the policy behaves from quote to renewal, and how claims
are settled. A minimal sidecar engine reads the file and proves every part behaves as
declared by running scenarios written in the same language.

## Assumptions (autonomous run, no user available)

- Target user writes the product file; they never touch the engine.
- One product per file. Personal-lines, single-term (annual or N-month) products.
- UK-flavoured defaults (IPT as a tax line, cooling-off) but nothing UK-specific in the grammar.
- Money is decimal, rounded once at the end of rating. Dates are ISO `YYYY-MM-DD`. Pro rata is by days.
- Custom DSL over YAML: quoting noise and `key: value` nesting defeat the "reads like a wording" goal.
  The expression sub-language (`rider_age < 25 and security is gold`) is unavoidable either way.
- Engine in Python 3.12, stdlib only. Determinism and zero setup beat everything else for a proof.

## The language (`.idl`)

Indentation-based blocks. One statement per line. `#` comments. Strings in double quotes.
Identifiers are `snake_case`. Cover names may be quoted.

```
product "Cycle Cover"
  territory UK
  currency GBP
  term 12 months

inputs
  bike_value: money
  rider_age: integer
  security: choice of bronze, silver, gold
  racing: yes/no
  previous_claims: integer

eligibility
  decline when rider_age < 16 because "Rider must be at least 16"
  refer when previous_claims >= 3 because "Claims history needs an underwriter"

cover Theft
  limit bike_value
  excess 10% of claim, minimum 50
  excludes when security is bronze and bike_value > 2000 because "Gold or silver lock required"

cover Racing optional
  limit 5000
  excess 250
  available when racing is yes

rating
  base 3.5% of bike_value
  factor "Rider age"
    rider_age < 25: x 1.40
    otherwise: x 1.00
  add 45 when Racing selected
  minimum 60
  tax IPT 12%
  fee "Admin fee" 10
  round to 0.01

lifecycle
  cooling off 14 days, full refund
  cancellation by customer: refund pro rata, fee 25
  cancellation by insurer: refund pro rata
  adjustment: reprice, charge pro rata difference
  lapse when unpaid after 30 days
  renewal
    invite 21 days before expiry
    premium change capped at 20%
    decline when claims in term >= 2

claims
  claim Theft
    requires police_report
    pays claimed amount up to limit, less excess
    decline when reported after 30 days
  after 2 claims in term: renewal load x 1.25

scenario "Young rider"
  given bike_value 2000, rider_age 22, security gold, previous_claims 0, racing no
  expect premium 88.40

scenario "Cancel mid term"
  given bike_value 2000, rider_age 30, security gold, previous_claims 0, racing no
  when bound on 2026-01-01
  when cancelled by customer on 2026-04-11
  expect refund 24.87
  expect status cancelled
```

### Expressions

Comparisons `< <= > >= is "is not"`, boolean `and or not`, arithmetic `+ - * /`,
`N% of X`, literals (numbers, quoted strings, choice names, `yes`/`no`), input names,
`<Cover> selected`. Evaluated with `Decimal`.

### Rating semantics

Steps run in the order written. `base` sets net premium. `factor` picks the first matching
row (`x` multiplies, `+`/`-` adds) and applies it. `add` adds a flat amount, optionally
conditional. `minimum` floors net premium. `tax` adds a percentage line on net premium.
`fee` adds a flat non-refundable line. `round to` rounds every money figure at the end.
Result: net, each tax and fee line, and total.

### Lifecycle semantics

States: `quoted → bound → live → (cancelled | lapsed | expired | renewed)`. Term runs from
inception for `term` months. Refund on cancellation = pro rata of (net + tax) by days
remaining over term days, full within cooling-off, less any cancellation fee; fees are
never refunded. Adjustment reprices with new inputs and charges the pro rata difference.
Renewal reprices with current inputs plus any claims loading, caps the change, and applies
renewal decline rules.

### Claims semantics

A claim names a cover. It is declined if the cover is excluded for this risk, not selected,
a `requires` field is missing, or a `decline when` rule fires. Payout = min(claimed, limit) -
excess (percentage excess is of the claimed amount, floored at its minimum). Claims count
against the term and feed renewal loading.

## Engine

```
ideclare/            stdlib-only Python package
  parser.py          text -> Product (dataclasses); reports line-numbered errors
  expr.py            expression parser and evaluator
  engine.py          eligibility, rating, lifecycle, claims
  scenarios.py       runs scenario blocks, reports pass/fail
  cli.py             `python -m ideclare check FILE` and `quote FILE k=v ...`
examples/cycle.idl   full worked product with scenarios covering every part
tests/               unittest, one file per module
docs/reference.md    language reference for insurance professionals
```

Proof of each language part = a scenario in `examples/cycle.idl` that exercises it and
passes under `python -m ideclare check`.

## Out of scope

Multi-product bundles, instalment schedules, commission, multi-currency, document
generation, persistence, any UI.
