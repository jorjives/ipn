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
over a term of years), `pi.idl` (claims-made commercial cover, aggregate limit), `runoff.idl` (six years of
run-off cover after that practice closes) and
`home.idl` (specified items, the average clause), `household.idl` (buildings and
contents as sections of one policy), `income.idl` (a benefit paid over time), `leasing.idl` (a group scheme whose members join and leave)
and `gadget.idl` (one product sold across several territories, each with its own tax and currency).

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
  term 12 months
```

`territory` is where the product is sold. A product sold in several countries lists them,
`territory DE, FR, NL, CH`, and `territory` is then an answer given at quote, so a table
keyed on it carries the country's tax and loading and a condition can say `territory is
CH`. With one territory it is assumed. The currency follows the territory (GBP for UK,
EUR for DE, CHF for CH, and so on); a product priced in another currency, or sold
somewhere the engine does not know, says `currency EUR`. See `examples/gadget.idl`.

`published 2026-07-01` says when this version of the product went on sale; see
[Versions](#versions). A product without it is a single version.

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
Rules may look at the chosen covers, `refer when Racing selected and rider_age > 60`;
write the eligibility block after the covers it names. A bundle of sections sold as one
policy (buildings and contents, say) is optional covers with a rule that at least one is
taken, `decline when not Buildings selected and not Contents selected because "..."`, and
a `discount N% when Buildings selected and Contents selected` in the rating.

A declined risk cannot be bound. A referred risk is bound only once an underwriter has
accepted it, on terms if they choose: a load or discount on the net (a final step in the
rating trail, "Underwriter load"), an excess imposed on a cover in place of the product's,
or a cover withdrawn (reported as excluded, "underwriter terms"). The terms hold for the
life of the policy, renewals included. The underwriter may instead decline the risk.

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
- `reinstatement at 100% of premium pro rata` lets an eroded aggregate be bought back to
  its full amount once a term, for that share of the earning premium (net plus taxes) for
  the days left. The scenario event is `when reinstated Cover on DATE` and the charge is
  available to `expect additional premium`.
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
| `round to 0.01` | rounding unit for every figure, half up; without it, the smallest unit of the currency (0.01 for GBP or EUR, 1 for JPY, 0.001 for KWD) |

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
  amount paid, fees included. The days are an expression, so a product sold in several
  territories takes them from a table: `cooling off days from "Territory" days, full refund`.
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
  After an adjustment the customer's annual premium is the new one. By default the
  repricing is on the version the policy is on: a mid-term change is an endorsement to the
  contract the customer holds. `adjustment: reprice on the current version, charge pro
  rata difference` instead moves the policy to the version live that day first (see
  [Versions](#versions)); the changes are then written in that version's words and answer
  anything its `upgrading` asked for, and an unanswered `ask` refuses the adjustment with
  "adjustment needs x".
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
  `less excess`, `less co-payment`, and `up to <amount> [when <condition>]` for a
  sub-limit. A sum insured is usually capped then the excess deducted (`up to limit, less
  excess`); a liability or aggregate limit caps what the insurer pays after the excess
  (`less excess, up to limit`). Write what the wording says. A sub-limit caps only the
  claims its condition picks out, `up to 400 when kind is valuables`, and the claim still
  erodes the aggregate it sits within.
- `pays <amount>` is a fixed benefit instead of the amount claimed: `pays sum_assured`,
  `pays 50% of sum_assured`, `pays purchase_price`. It may use asked facts and take the same
  clauses.
- `pays <amount> per month for <months> months [after <period> days|weeks|months]` is a
  benefit paid over time: `pays monthly_benefit per month for ( weeks_off_work -
  deferred_weeks ) / 4 months after deferred_weeks weeks, up to limit`. The total is the
  monthly amount times the months, then the clauses apply; it goes out as a month's
  benefit at the end of each month after the deferred period, a part month last. The
  payments are dated from the loss and carry on past the term's expiry and through a
  renewal; the claim counts and erodes the limit in the term it arose in.
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
| `when accepted by underwriter on DATE [with load N%, discount N%, excess AMOUNT on Cover, excluding Cover, ...]` | the underwriter accepts a referred risk, on these terms |
| `when declined by underwriter on DATE` | the underwriter declines it; binding is then refused |
| `when reinstated Cover on DATE` | buys back an eroded aggregate limit; the charge is available to `expect additional premium` |
| `when cancelled by customer\|insurer on DATE` | cancellation; the refund is available to `expect refund` |
| `when adjusted on DATE with input value, input value` | mid-term change; in the words of the version it is priced on |
| `when adjusted on DATE adding bike value 500, age 1, security gold` | add an item |
| `when adjusted on DATE removing bike 2` | remove the second item |
| `when claim Cover [on bike N] [for AMOUNT] on DATE [reported DATE] [with item, fact value, ...]` | a loss on DATE, to item N if the cover is per item, notified on the reported date, with the listed evidence words and asked facts (`with death_certificate, cause suicide`); a fixed benefit claims no amount, so `for` may be left out |
| `when renewed on DATE [with input value, ...]` | accept the renewal offer (fails if it is declined); the new term is on the version live that day, and `with` answers what its `upgrading` asked for |

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
| `expect currency CODE` | the currency the risk is quoted in, from its territory |
| `expect commission "Label" AMOUNT` | that intermediary's share of the net |
| `expect factor "Label" x 1.40` | what a factor applied |
| `expect status STATUS [on DATE]` | policy status, at the last event's date by default |
| `expect expiry DATE` | end of the current term |
| `expect refund AMOUNT` | refund from the last cancellation |
| `expect instalment charge AMOUNT`, `expect instalment N AMOUNT` | the credit charge and the Nth instalment on the premium as it stands |
| `expect refused ["reason"]` | the event just before was rightly refused (binding a declined or unaccepted referred risk, an adjustment when `adjustment: not allowed`, cancellation by a party with no terms) |
| `expect additional premium AMOUNT`, `expect return premium AMOUNT` | result of the last adjustment or reinstatement |
| `expect claim paid`, `expect claim declined ["reason"]`, `expect payout AMOUNT` | the last claim |
| `expect claims in term N` | paid claims this policy year |
| `expect benefit paid AMOUNT by DATE` | everything paid out on or before that date, whichever term the claims arose in |
| `expect renewal premium AMOUNT`, `expect renewal invite DATE`, `expect renewal offered`, `expect renewal declined ["reason"]` | the renewal offer as things stand |
| `expect renewal needs input[, input]` | the answers the new version's `upgrading` asks for before the renewal can be priced; `premium`, `offered` and `declined` fail while any are needed |
| `expect version DATE` | the `published` date of the version the policy is on |
| `expect <input> <value>` | an answer as the policy now holds it, after indexing at renewal, an upgrade or an adjustment: `expect bike_value 2100` |

## Versions

A customer stays on the version of a product they bought until it renews. A version is
identified by the date it went on sale, `published 2026-07-01` in the `product` block; there
are no version numbers. The other versions of a product are the `.idl` files in the same
directory that declare the same product name. `check` finds them itself, and a file sees
only the versions published on or before its own date, so a proof written in an old version
stays true when new ones are published. See `examples/versioned/`.

- The version **live** on a date is the one with the latest `published` on or before it.
  `when bound on DATE` binds under that version; binding before the first version is
  refused with "no version of X was on sale on DATE".
- A scenario that binds before the file's own `published` date is on an earlier version,
  so its `given` is written in that version's words and checked when it runs.
- **Renewal** moves the policy to the version live on the first day of the new term. The
  expiring version's `index` lines move the answers on, then the answers are carried to the
  new version, then the new version prices them, with the claims loading, cap and collar
  as usual. The cap and collar hold against the premium charged for the expiring term,
  whichever version charged it.
- An answer is **carried** when the new version has an input of the same name and
  compatible type: the same kind, a choice that still lists every old value, a collection
  whose fields carry likewise. A new input takes its `default`. A new input with neither is
  an error when the history loads: "x is new in the version published DATE; add it to
  upgrading, or give it a default". Inputs the new version dropped are left behind.
  Calculated and enrichment-provided values are recomputed, `territory` is carried, and
  free text is optional as everywhere.

### upgrading

When carrying is not enough, the `upgrading` block says how this version's answers are
derived from the previous version's. Every word on the right-hand side is an input, item
field or choice value of the **previous** version (the one published immediately before
this file), or a choice value of the input being set. There is no `previous` keyword: the
right-hand side always reads the old answers, even when the name is kept.

```
upgrading
  lock_rating
    security is gold: gold
    security is silver: silver
    otherwise: ask
  total_value: bike_value + accessories_value
  racing: no
  bikes: for each bike
    lock: high when security is gold, otherwise low
```

- `input: <expression>` gives one value; `input: <value> when <condition>, <value> when
  <condition>, otherwise <value>` gives cases on one line; the block form is rows of
  `condition: value` ending in `otherwise: value`, the same shape as a `factor`. A
  conditional value must end in `otherwise`, so no policy is left without an answer.
- `ask` as a value means the customer must answer: the renewal **needs** that input before
  it can be priced (see `expect renewal needs`). `otherwise: ask` asks only the policies
  that reach that row, so most of a book rolls over unattended and a few are asked.
- `collection: for each <old item>` upgrades every item; the lines below use the old
  item's fields and the old answers, fields not mentioned carry by name, and the
  collection may be renamed. An asked item field is reported as `bike.lock`.
- A word the previous version does not know, a row block without `otherwise`, or a bare
  word that is neither an old input nor a choice of the target is an error when the
  history loads, with the line. A value the target cannot hold (`lock_rating` given
  `gold` when its choices are `low, high`) fails the renewal with "lock_rating cannot be
  'gold'; it is a choice of low, high".
- Across several versions the blocks chain in publication order. An `ask` at one step
  leaves that answer unknown, and any later expression that reads it is unknown too; what
  the renewal needs is whatever is still unknown at the end.

### Dated lines: mid-term amendments

A change that must reach policies already in force is not a new version; it is an
amendment with an effective date. Any line inside a `cover` block or a `claim` block may
begin with `from DATE`, `until DATE`, or both:

```
cover Theft
  limit bike_value
  from 2027-03-01 limit 2 * bike_value
  until 2027-03-01 excludes when racing is yes because "Racing was excluded until March 2027"

claims
  claim Theft
    pays claimed amount up to limit, less excess
    from 2027-03-01 decline when unlocked because "Bikes left unlocked are not covered from March 2027"
```

- A dated line is in effect for an event on or after its `from` date and before its
  `until` date. A claim is settled on the wording in force at the loss; `expect cover` reads
  the wording at the last event's date, and with no event yet, or from the `quote` command,
  only undated lines apply.
- A setting with one value (`limit`, `excess`, `pays`, `available when`, `waiting period`,
  `requires`, `depreciation`, `counts`) is **replaced** by the dated line in effect; the
  undated line covers the other dates. A setting that is a list (`excludes`, `decline`,
  `co-payment`) **accumulates**: every line in effect applies. Two dated lines for one
  setting whose windows overlap are an error: "limit is given twice for DATE".
- Dated lines are checked like any other, in every window they create. `asks` cannot be
  dated, and `rating`, `eligibility` and `lifecycle` lines cannot be dated at all: the
  premium charged for the term already stands and eligibility is settled at purchase.
- The words a dated line may use are the words its block may use: a cover line reads the
  answers, a claim line also reads the facts the claim asks for.

## Not yet supported

A policy carrying amounts in two currencies at once (a limit in USD on a premium in GBP),
more than one product per file, new-for-old versus indemnity as a named
settlement basis (use a depreciation table). Each is a small addition to the engine; say
which you need.
