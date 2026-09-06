# iDeclare language reference

iDeclare lets you describe an insurance product in one plain text file: what you ask the
customer, who you will and will not insure, what is covered, how it is priced, how the
policy behaves from purchase to renewal, and how claims are paid. You then prove the
product does what you meant by writing *scenarios* in the same file and running:

```
python3 -m ideclare check my-product.idl
```

Every scenario prints `PASS` or `FAIL`, and every failure says which line disagreed and
what the engine actually produced. You can also price a single risk from the terminal:

```
python3 -m ideclare quote my-product.idl bike_value=2000 rider_age=22 security=gold racing=yes previous_claims=0 select=Racing
```

A repeatable item (see `inputs`) is given as a CSV of items, one row each, with the field
names as the header: `bikes=bikes.csv`. Per-item covers are reported per item. To price a
whole book, `batch` takes a CSV with one column per input (a `select` column lists chosen
covers separated by `;`) and writes one row per risk with eligibility, the reasons, the
net, each tax and fee, the total and each commission; a row the product cannot price says
why in its `error` column instead of stopping the run:

```
python3 -m ideclare batch my-product.idl risks.csv > priced.csv
```

See `examples/cycle.idl` for a complete single-bike product, `examples/family.idl` for a
policy covering several bikes and `examples/multibike.idl` for a fleet where the first bike
takes the full rate. The other examples take the same language across the industry:
`travel.idl` (people, trip dates, sections that start on different days), `pet.idl` (an
annual limit eroded by claims, waiting period, co-payment), `motor.idl` (named drivers, no
claims discount, an excess that depends on who was driving), `life.idl` (a fixed benefit
over a term of years), `pi.idl` (claims-made commercial cover, aggregate limit) and
`home.idl` (specified items, the average clause), `income.idl` (a benefit paid over time) and `leasing.idl` (a group scheme whose members join and leave).

## Writing conventions

- Indent with two spaces to put a line inside the block above it.
- One statement per line. Anything after `#` is a comment.
- Names of inputs are single words joined with underscores: `bike_value`, `rider_age`.
- Cover names, labels and reasons that contain spaces go in double quotes: `"Accidental Damage"`.
- Money and numbers are written plainly: `2000`, `3.5`, `12%`. Dates are `2026-01-31`.
- Words that stand for the same thing may be singular or plural where English wants it:
  `after 1 claim in term`, `after 2 claims in term`.
- The file starts with the `product` block. The other blocks can come in any order.

## Conditions

Many lines take a condition after `when`. A condition compares inputs and other known
values and can be combined:

| Write | Meaning |
|---|---|
| `rider_age < 25`, `<=`, `>`, `>=` | numeric comparison |
| `security is gold`, `security is not gold` | equal / not equal, also `racing is yes` |
| `a and b`, `a or b`, `not a` | combine conditions; `and` binds tighter than `or` |
| `( ... )` | group |
| `Racing selected` | the customer chose the optional cover Racing |
| `10% of bike_value`, `bike_value * 2`, `+ - /` | arithmetic, used in amounts |
| `return_date - departure_date` | the days between two dates |
| `work_date < retroactive_date`, `start is 2026-01-01` | dates compare like numbers |

Words available inside conditions: every input you declared, every choice value, every
cover name, and in claim rules `claimed` (the amount claimed) and any facts the claim asks
for. In renewal and claim rules `claims in term` is the number of paid claims this policy
year that count (see `claims`). In claim rules `within N days of inception` and `within N
months of inception` are true when the loss is that soon after the policy first started.

## Blocks

### product

```
product "Cycle Cover"
  territory UK
  currency GBP
  term 12 months
```

`term` is the length of one policy period: `term 12 months`, `term 10 days`, `term 25
years`. A policy bound on 31 January with a 1 month term expires on 28 February. The
number may be an input the customer chooses, `term term_years years`, and a product that
ends on a date the customer gives says `term until return_date`.

### inputs

What you ask at quote. Each line is `name: type`.

| Type | Values |
|---|---|
| `money`, `number` | a decimal amount |
| `integer` | a whole number |
| `yes/no` | `yes` or `no` |
| `choice of a, b, c` | exactly one of the listed words |
| `text` | free text; compare it to a quoted value, `make is "Brompton"`; scenarios may leave it out |
| `date` | a calendar date, `2026-07-10` |
| `collection of bike[, 1 to 5]` | repeatable items, each with the fields indented below it |
| `calculated` | an input or item field worked out from the others by the steps indented below it |

Any of these but a collection may end `, default <value>`: `voluntary_excess: money,
default 0`, `cover_type: choice of comprehensive, third_party, default comprehensive`. An
input or item field left out of a scenario, a `quote` or a `batch` row takes its default;
one without a default must be given.

#### Repeatable items

```
inputs
  rider_age: integer
  bikes: collection of bike, 1 to 4
    value: money
    age: integer
    security: choice of bronze, silver, gold
```

The plural (`bikes`) names the collection, the singular (`bike`) names one item. Bounds
are optional: `, 1 to 4`, `, at least 1` or `, at most 4`. A quote outside the bounds is
declined with the reason `bikes: at least 1 required` or `bikes: at most 4 allowed`. A
field may not share its name with an input.

Items appear in conditions and amounts like this:

| Write | Meaning |
|---|---|
| `count of bikes` | how many items |
| `total value of bikes`, `highest value of bikes`, `lowest value of bikes` | aggregate of one field |
| `any bike where value > 5000` | true if one item matches |
| `every bike where security is gold` | true if all items match |
| `value`, `age` on their own | the current item's field, inside `for each`, a cover, a claim or a `where` |

#### Formulas

Amounts and conditions are expressions: `+ - * /`, `N% of x`, `a ^ b` (power, so
`( bmi / 25 ) ^ 2` is a power law and `x ^ 0.5` a square root), parentheses, comparisons,
`and`, `or`, `not`, and these functions:

| Function | Gives |
|---|---|
| `exp ( x )`, `ln ( x )`, `sqrt ( x )` | the exponential, natural log and square root, so a GLM term is `exp ( 0.021 * annual_mileage / 1000 )` |
| `min ( a, b, ... )`, `max ( a, b, ... )` | the smallest or largest |
| `round ( x, 0.0001 )` | x to that unit, half up; use it so a curve's value reads sensibly in the trail and can be expected in a scenario |

All arithmetic is in decimal, not floating point, so a curve prices the same on every
machine. A long formula is better given a name as a `calculated` input (see repeatable
items above) than written in one line.

### enrichment

Products depend on lookups they do not perform themselves: postcode risk, a bike or
vehicle catalogue, claims history. An `enrichment` block declares the shape of such a lookup
and nothing about how it is done:

```
enrichment "Postcode risk" from postcode
  provides
    theft_area: choice of low, medium, high
  when unavailable: refer because "Postcode not recognised"
  held for the term

enrichment "Bike catalogue" for each bike from make, model
  provides
    category: choice of road, mountain, folding, other
  when unavailable: category is other
```

- `from` names the inputs the lookup is keyed on. `for each bike` makes it a lookup per
  item, keyed on that item's fields.
- `provides` lists the fields it returns, typed like inputs. They are used exactly like
  inputs everywhere else, but the customer is never asked for them.
- `when unavailable` is the underwriting decision for a lookup that cannot answer: either
  defaults for every provided field, or `refer because "..."` or `decline because "..."`.
- `held for the term` fixes the values at inception; an adjustment that changes them is
  refused. Without it the lookup is taken to run again on adjustment and at renewal.

Scenarios stand in for the lookup by giving the provided fields directly, for example
`given postcode "M1 1AA", theft_area high`. Leaving them out is how a scenario says the
lookup could not answer.

### table

Rating tables with several dimensions (driver age band by area by vehicle group, say) are
owned by the pricing team as a spreadsheet, not written as factor rows. A `table` block
reads one in its *long* form: one row per cell, one column per key, then the value
columns. That is what a spreadsheet grid becomes with one unpivot, and it carries any
number of dimensions:

```
table "Van rates" from "van_rates.csv" keyed on driver_age, area, vehicle_group

table "Theft excess" keyed on area, use
  area, use, excess
  1-3, *, 250
  4-5, courier, 750
  4-5, *, 500
```

- `from "file.csv"` reads the rows from a file beside the `.idl`; without it the rows are
  written below, as plain CSV with the header first. The same text works in either place.
- `keyed on` names the columns matched against the product's inputs, item fields,
  calculated inputs or enrichment-provided fields. The column headers are the input names.
  Every other column is a value column.
- A cell is matched by its form, so a column may mix them:

  | Cell | Matches |
  |---|---|
  | `gold`, `12`, `yes` | that value exactly |
  | `80%` | the number 0.80, in a value column |
  | `17-20` | a number from 17 to 20, both inclusive |
  | `65+` | a number of 65 or more |
  | `*` | anything; a row with fewer `*` cells beats one with more, so `*` rows are the fallback |

  Key cells are checked against the input they match when the product is read: a choice
  that is not one of the input's choices, or a band on a yes/no input, is an error with
  the row number rather than a row that never fires. Rows are indexed on their exact
  cells, so a table of a hundred thousand rows looks up in microseconds.

A stepped table becomes a curve with `interpolated [linearly | geometrically] on <key>`
(linearly is the default). The named key's cells are then single numbers, the knots; the
other keys match as in a plain lookup. On a knot the value is the knot's, between two knots
it is interpolated, and outside the knots it is an error, never a clamp:

```
table "Mortality" keyed on age, smoker
  age, smoker, rate
  40, no, 1.30
  45, no, 2.05

rating
  base sum_assured / 1000 * rate from "Mortality" interpolated geometrically on age
```

| Method | Between knots (x0, y0) and (x1, y1), t = (x - x0) / (x1 - x0) | Right for |
|---|---|---|
| `linearly` | y0 + (y1 - y0) * t | additive quantities: an expense, a sum-insured loading |
| `geometrically` | y0 * (y1 / y0) ^ t | rates that grow by a ratio: mortality, claims frequency. Knot values must be positive |

At 42 the curve above gives 1.5598 geometrically and 1.60 linearly. A cubic spline
(`smoothly`) and interpolation across two keys are not provided; each is one more branch
in the same place. `examples/mortality.idl` prices a term life product from such a curve.

A value is taken with `<column> from "<table>"` anywhere an amount can go: a factor, a
`base`, an `add`, a `limit`, an `excess`, a benefit. Inside `for each` the lookup uses the
current item's fields.

```
rating
  base 6% of vehicle_value
  factor "Driver, area and group" x rate from "Van rates"

cover Theft
  excess excess from "Theft excess"
```

The parser checks that the file exists, every key is an input the product knows and a
column of the table, at least one value column exists, every cell reads, and no two rows
repeat the same keys. When a risk is priced, exactly one row must match: none is reported
as `no row in Van rates for driver_age 16, area 3, vehicle_group 5`, and two equally
specific rows (overlapping bands) as ambiguous. A value between bands is an error, never a
silent default, so the scenarios that prove the product are how the pricing team checks a
reissued table. `examples/van.idl` rates from a three-dimensional table of 300 cells.

### eligibility

```
eligibility
  decline when rider_age < 16 because "Rider must be at least 16"
  refer when previous_claims >= 3 because "Claims history needs an underwriter"
```

Every rule is checked. If any `decline` fires the outcome is *declined*; otherwise if any
`refer` fires it is *referred*; otherwise *eligible*. All reasons that fired are reported.
Rules may look at the chosen covers, `refer when Racing selected and rider_age > 60`.

### cover

One block per section of cover.

```
cover Theft
  limit bike_value
  excess 10% of claim, minimum 50
  excludes when security is bronze and bike_value > 2000 because "Gold or silver rated lock required"

cover Racing optional
  limit 5000
  excess 250
  available when racing is yes
```

- `optional` covers are only included when the customer selects them.
- `available when` says when an optional cover may be offered at all.
- `excludes when` removes the cover for this risk and records the reason.
- `limit` and `excess` are amounts; `claim` inside an excess means the amount claimed.
  `, minimum 100` floors a percentage excess and `, maximum 1000` caps it:
  `excess 10% of claim, minimum 100, maximum 1000`. Commercial wordings may write
  `deductible` for `excess`; the two are the same.
- `excess 350 per term` (or `deductible 350 per term`) is an aggregate excess: the insured
  bears the first 350 across the term's claims on the cover rather than on each one. A
  claim inside it is declined as nothing payable but still uses it up; it is restored at
  renewal.
- `limit 7000 per term` is an aggregate limit: the most the insurer pays on this cover in
  the whole term. Each paid claim eats into it and it is restored at renewal. A plain
  `limit` applies to any one claim.
- `limit 4000 per term per condition` keeps one such limit for each value of a fact the
  claim asks for (`condition` here), and `limit 1500 per term per traveller` one for each
  item, which makes the cover per item so claims say `on traveller 2`. A claim erodes only
  the limit it belongs to.
- An excess may be a table instead of one amount, in the shape of a rating factor without
  the `x`, ending with an `otherwise` row so every claim has an excess. Its rows may use
  facts the claim asks for (see `claims`), so the excess can depend on who was driving or
  what caused the loss:

  ```
  excess
    driver_age < 25: 550 + voluntary_excess
    otherwise: 250 + voluntary_excess
  ```
- `in force from departure_date` and `in force until departure_date` make a section of
  cover start or stop on a date of its own rather than with the policy. A loss outside the
  window is declined as "not in force". Travel cancellation cover runs from purchase until
  departure; medical cover from departure.
- `waiting period 14 days`: losses this soon after the policy *first* started are declined.
  Renewing does not restart it.

The engine reports each cover as *included*, *excluded*, *not selected* or *not available*.

### rating

```
rating
  base 3.5% of bike_value
  factor "Rider age"
    rider_age < 25: x 1.40
    rider_age < 40: x 1.00
    otherwise: x 0.90
  add "Racing cover" 45 when Racing selected
  discount 10% when security is gold
  load 25% when rider_age < 21
  minimum 60
  maximum 800
  tax IPT 12%
  fee "Admin fee" 10
  round to 0.01
```

Steps run top to bottom, so the order you write is the order of calculation.

To rate repeatable items, put the per-item steps under `for each bike`. Each item is
rated on its own running net using its fields, the results are added together, and the
steps after the block continue on that total:

```
rating
  for each bike
    base 3% of value
    factor "Bike age"
      age < 1: x 1.00
      otherwise: x 0.90
  factor "Multi-bike discount"
    count of bikes >= 3: x 0.85
    otherwise: x 1.00
  tax IPT 12%
```

`tax`, `fee` and `round` belong outside the block. The quote trail shows each item's steps
as `bike 1 base`, `bike 1 Bike age` and so on.

To rate items in a chosen order, add `ordered by` with one or more keys. Each key is a field
or an expression, ascending unless followed by `descending`; later keys break ties and items
that still tie keep the order they were given. Inside the block `position` is the item's
place in that order, starting at 1, so the first bike can take the full rate and the rest a
share of theirs:

```
rating
  for each bike, ordered by ebike descending, value descending
    base 4% of value
    factor "Position"
      position is 1: x 1.00
      otherwise: x 0.50
```

The ordering only decides the position. Items keep their given numbers in the trail and in
claims, so `bike 2` always means the second bike declared.

When the order depends on several things at once, give each item a calculated field and
order on that. A calculated field is declared with the other fields and worked out by the
same steps a `for each` block uses (`base`, `add`, `factor`, `discount`, `load`, `minimum`,
`maximum`), with the item's other fields in scope. It is never given in a scenario:

```
inputs
  bikes: collection of bike
    make: text
    value: money
    ebike: yes/no
    rank: calculated
      base value
      add 0.01 when ebike is yes
      add 0.001 when make is "Brompton"

rating
  for each bike, ordered by rank descending
```

Calculated fields are filled in before anything else runs, so eligibility, covers and
claims can use them too. A top-level input can be calculated in the same way; the customer
is never asked for it:

```
inputs
  height_cm: number
  weight_kg: number
  bmi: calculated
    base weight_kg / ( height_cm / 100 * height_cm / 100 )
```

| Step | Effect on the net premium |
|---|---|
| `base <amount>` | sets it |
| `factor "Label"` with rows `condition: x N`, `: + N` or `: - N` | first row whose condition holds is applied; `otherwise` must be last |
| `factor "Label" x <amount> [when ...]` (or `+`, `-`) | a single-row factor, usually `x rate from "Table"` |
| `add ["Label"] <amount> [when ...]` | adds a flat amount |
| `discount N% [when ...]`, `load N% [when ...]` | multiplies by (1 - N%) or (1 + N%) |
| `minimum <amount>` | raises it to at least this |
| `maximum <amount>` | lowers it to at most this |
| `tax Name N%` | adds a tax line of N% of the rounded net |
| `fee "Label" <amount>` | adds a flat fee line |
| `commission "Label" N%` | reports N% of the rounded net as owed to that intermediary; never added to the premium |
| `round to 0.01` | rounding unit for every figure, half up (default 0.01) |

A product with no tax simply has no `tax` line (life premiums, for example).

The result is the net premium, one line per tax and fee, the total, and the commission
split of the net. The `quote` command prints the full trail of applied steps and
`batch` gives each commission its own column.

### lifecycle

```
lifecycle
  cooling off 14 days, full refund
  cancellation by customer: refund pro rata, fee 25
  cancellation by insurer: refund pro rata
  adjustment: reprice, charge pro rata difference, fee 10
  lapse when unpaid after 30 days
  instalments 12 monthly, charge 10%
  renewal
    invite 21 days before expiry
    increase capped at 20%
    decrease collared at 10%
    index bike_value by 5%
    index rider_age by 1
    decline when claims in term >= 3 because "Three or more claims in the year"
```

A product that simply ends, such as single-trip travel or term life, says `renewal: none`
instead of a `renewal` block; the offer is then declined with "The policy is not renewable".

Policy status on any date is one of *quoted*, *bound* (before inception), *live*,
*lapsed*, *cancelled*, *expired* or *renewed* (a past policy year).

- **Cooling off**: cancelling within this many days of inception refunds the whole
  amount paid, fees included.
- **Cancellation** terms per party: `refund pro rata`, `full refund`, `no refund` or
  `refund <share>`, optionally `, fee N`. Pro rata refunds the earning premium (net plus
  taxes, never fees) for the unused days of the term, less the fee, never below zero. A
  party without a cancellation line cannot cancel. `refund <share>` returns that share of
  the earning premium, where the share is an expression that may use `days in force` and
  `months in force` (whole months since inception): a flat `refund 50%`, a formula such
  as `refund 100% - days in force / 365 * 100%`, or a short-rate table looked up by
  `refund refunded from "Short rate"` with the table `keyed on months in force`.
- **Adjustment** (mid-term change): the policy is repriced with the new answers and the
  difference in earning premium is charged pro rata for the remaining days, plus the fee.
  A negative result is a return premium. Write `adjustment: not allowed` to forbid it.
  After an adjustment the customer's annual premium is the new one.
- **Lapse**: a policy bound but unpaid lapses after this many days until it is paid.
- **Instalments**: `instalments N monthly`, optionally `, charge P%`. The credit charge is
  that percentage of the premium, rounded; premium plus charge is split into N equal
  instalments to the penny, with the first taking any rounding so the schedule sums
  exactly. The `quote` command shows the schedule.
- **Renewal**: `index` lines first move the answers on: `by N%` for inflation of a sum
  insured, `by N` to add a fixed amount, such as a year of age, `by -N` to take one away.
  `, at least 0` and `, at most 9` keep the result within bounds, so a no claims discount
  grows to nine years and never falls below none. The amount may be any expression over
  the expiring answers and `claims in term`, so `index previous_claims by claims in term`
  rolls the year's claims into the record the rating reads. `index bike value by 5%`
  moves a field on every item. The offer is the product repriced on those answers, with
  any claims loading (see `claims`) applied to the net before tax, then held within the
  cap and collar: no more than the premium charged for the current term plus the cap
  percentage, no less than it minus the collar percentage. `decline when` rules use the indexed answers and
  `claims in term`. Accepting a renewal starts a new term at expiry with the indexed
  answers and resets the claims count.

### claims

```
claims
  claim Theft
    requires police_report, crime_reference
    pays claimed amount up to limit, less excess
    decline when reported after 30 days because "Theft must be reported within 30 days"
    decline when claimed > bike_value because "Claim exceeds the insured value"
    depreciation
      bike_age < 1: x 1.00
      bike_age < 3: x 0.85
      otherwise: x 0.70
  claim Death
    asks
      cause: choice of natural, accident, suicide
    requires death_certificate
    pays sum_assured
    decline when cause is suicide and within 12 months of inception because "Suicide in the first year"
  claim "Vet Fees"
    asks
      condition: text
    co-payment 20% when pet_age >= 9
    pays claimed amount, less excess, less co-payment, up to limit
  claim Windscreen
    pays claimed amount up to limit, less excess
    does not count towards claims in term
  after 2 claims in term: renewal load x 1.25
```

- `requires` lists evidence that must accompany the claim.
- `asks` declares facts only known when the claim is made, typed like inputs: the cause of
  death, who was driving, the true value of the contents. A claim without them is declined
  as "cause is required". They may be used in this claim's `decline when`, `co-payment`,
  `settlement` and in the cover's excess table.
- `pays claimed amount` followed by clauses **in the order they apply**: `up to limit`,
  `less excess`, `less co-payment`. A sum insured is usually capped then the excess
  deducted (`up to limit, less excess`); a liability or aggregate limit caps what the
  insurer pays after the excess (`less excess, up to limit`). Write what the wording says.
- `pays <amount>` is a fixed benefit instead of the amount claimed: `pays sum_assured`,
  `pays 50% of sum_assured`, `pays purchase_price`. It may use asked facts and take the same
  clauses: `pays monthly_benefit * ( weeks_off_work - deferred_weeks ) / 4, up to limit`.
- `co-payment N% [when ...]` is a share the customer bears, applied where `less co-payment`
  sits in the `pays` line.
- `depreciation` (or `settlement`, the same table under a name that suits an average clause)
  scales the amount claimed first, before any `pays` clause: `x contents_sum / true_value`.
- `counts towards claims in term when fault is yes` and `does not count towards claims in
  term`: the claim is paid but does not add to the record that drives renewal loading,
  renewal decline rules and terms imposed after claims. Glass and non-fault motor claims
  are the usual case. Every paid claim still erodes an aggregate limit.

A cover whose `limit`, `excess` or `excludes` uses item fields is resolved per item, so
claims on it name the item: `when claim Theft on bike 2 for 900 on 2026-03-01`.

A claim on a cover is declined, with the reason, when the policy is not live on the loss
date, the cover is not included for that risk or item, the cover is not in force on that
date or is within its waiting period, a required item or asked fact is missing, an
aggregate limit is used up, or a `decline when` rule fires. Otherwise the amount (claimed,
or the fixed benefit) is first scaled by the `depreciation` or `settlement` table (same
shape as a rating factor: the first matching row applies), then the `pays` clauses apply in
the order written. A percentage excess is of the amount claimed, before depreciation. Only
paid claims that count go towards `claims in term`. A claim that comes to nothing after
the excess is declined as "nothing is payable after the excess" and does not count.
`after N claims in term: renewal load x M` multiplies the renewal net when the paid claim
count reaches N; the highest matching line wins.

A paid claim can also change the terms of the policy for the rest of the term. Write
`after N claims in term` (or `after 1 claim in term`) with lifecycle lines indented below;
they replace the product's own settings from the point the Nth claim is paid, and anything
not restated carries over. Either form takes `unless <condition>`, so a protected no
claims discount is `after 1 claim in term: renewal load x 1.30 unless "Protected NCD"
selected`. The `lifecycle` block must come first in the file:

```
claims
  after 1 claim in term
    cancellation by customer: no refund
    adjustment: not allowed
```

## Scenarios

```
scenario "Customer cancels mid term"
  given bike_value 2000, rider_age 22, security gold, racing no, previous_claims 0
  select Racing
  when bound on 2026-01-01
  when cancelled by customer on 2026-04-11
  expect refund 35.96
  expect status cancelled
```

`given` supplies every input except calculated ones; `select` chooses optional covers.
Repeatable items are given one per line using the singular name, with every field: `given
bike value 2000, age 0, security gold`, or all at once from a CSV beside the product with
the field names as its header: `given members from "members.csv"`. Dates are given as
`given departure_date 2026-07-10`.
Then `when` lines happen in order and `expect` lines check the state at that point.

Events:

| Event | Meaning |
|---|---|
| `when bound on DATE [unpaid]` | inception date; add `unpaid` to test lapse |
| `when paid on DATE` | payment received |
| `when cancelled by customer\|insurer on DATE` | cancellation; the refund is available to `expect refund` |
| `when adjusted on DATE with input value, input value` | mid-term change |
| `when adjusted on DATE adding bike value 500, age 1, security gold` | add an item |
| `when adjusted on DATE removing bike 2` | remove the second item |
| `when claim Cover [on bike N] [for AMOUNT] on DATE [reported DATE] [with item, fact value, ...]` | a loss on DATE, to item N if the cover is per item, notified on the reported date, with the listed evidence words and asked facts (`with death_certificate, cause suicide`); a fixed benefit claims no amount, so `for` may be left out |
| `when renewed on DATE` | accept the renewal offer (fails if it is declined) |

Expectations:

| Expectation | Checks |
|---|---|
| `expect eligible` / `expect referred ["reason"]` / `expect declined ["reason"]` | eligibility outcome |
| `expect cover Name [on bike N] included\|excluded\|"not selected"\|"not available" ["reason"]` | cover state, for item N if per item |
| `expect cover Name [on bike N] limit AMOUNT` | the resolved limit |
| `expect cover Name remaining AMOUNT`, `... remaining AMOUNT for condition "x"`, `expect cover Name on traveller 2 remaining AMOUNT` | what is left of an aggregate limit this term, for that condition or item |
| `expect cover Name excess remaining AMOUNT` | what the insured still bears of an aggregate excess this term |
| `expect net AMOUNT`, `expect premium AMOUNT` | net and total premium; once bound, the premium is what was charged for the term (capped or loaded at renewal, repriced by an adjustment) |
| `expect net for bike 2 AMOUNT` | one item's share of the net, before the steps after `for each` |
| `expect tax Name AMOUNT`, `expect fee "Label" AMOUNT` | one line of the premium |
| `expect commission "Label" AMOUNT` | that intermediary's share of the net |
| `expect factor "Label" x 1.40` | what a factor applied |
| `expect status STATUS [on DATE]` | policy status, at the last event's date by default |
| `expect expiry DATE` | end of the current term |
| `expect refund AMOUNT` | refund from the last cancellation |
| `expect instalment charge AMOUNT`, `expect instalment N AMOUNT` | the credit charge and the Nth instalment on the premium as it stands |
| `expect refused ["reason"]` | the event just before was rightly refused (an adjustment when `adjustment: not allowed`, cancellation by a party with no terms) |
| `expect additional premium AMOUNT`, `expect return premium AMOUNT` | result of the last adjustment |
| `expect claim paid`, `expect claim declined ["reason"]`, `expect payout AMOUNT` | the last claim |
| `expect claims in term N` | paid claims this policy year |
| `expect renewal premium AMOUNT`, `expect renewal invite DATE`, `expect renewal offered`, `expect renewal declined ["reason"]` | the renewal offer as things stand |

## Not yet supported

Multi-currency, more than one product per file, new-for-old versus indemnity as a named
settlement basis (use a depreciation table), run-off cover after a claims-made policy
ends, a benefit that continues to be paid across policy years. Each is a small addition
to the engine; say which you need.
