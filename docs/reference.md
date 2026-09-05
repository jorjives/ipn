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

See `examples/cycle.idl` for a complete single-bike product, `examples/family.idl` for a
policy covering several bikes and `examples/multibike.idl` for a fleet where the first bike
takes the full rate.

## Writing conventions

- Indent with two spaces to put a line inside the block above it.
- One statement per line. Anything after `#` is a comment.
- Names of inputs are single words joined with underscores: `bike_value`, `rider_age`.
- Cover names, labels and reasons that contain spaces go in double quotes: `"Accidental Damage"`.
- Money and numbers are written plainly: `2000`, `3.5`, `12%`. Dates are `2026-01-31`.
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

Words available inside conditions: every input you declared, every choice value, every
cover name, and in claim rules `claimed` (the amount claimed). In renewal rules
`claims in term` is the number of paid claims this policy year.

## Blocks

### product

```
product "Cycle Cover"
  territory UK
  currency GBP
  term 12 months
```

`term` is the length of one policy period. A policy bound on 31 January with a 1 month
term expires on 28 February.

### inputs

What you ask at quote. Each line is `name: type`.

| Type | Values |
|---|---|
| `money`, `number` | a decimal amount |
| `integer` | a whole number |
| `yes/no` | `yes` or `no` |
| `choice of a, b, c` | exactly one of the listed words |
| `text` | free text; compare it to a quoted value, `make is "Brompton"`; scenarios may leave it out |
| `collection of bike[, 1 to 5]` | repeatable items, each with the fields indented below it |
| `calculated` | an item field worked out from the others by the steps indented below it |

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

### eligibility

```
eligibility
  decline when rider_age < 16 because "Rider must be at least 16"
  refer when previous_claims >= 3 because "Claims history needs an underwriter"
```

Every rule is checked. If any `decline` fires the outcome is *declined*; otherwise if any
`refer` fires it is *referred*; otherwise *eligible*. All reasons that fired are reported.

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
  `minimum` floors a percentage excess.

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
claims can use them too.

| Step | Effect on the net premium |
|---|---|
| `base <amount>` | sets it |
| `factor "Label"` with rows `condition: x N`, `: + N` or `: - N` | first row whose condition holds is applied; `otherwise` must be last |
| `add ["Label"] <amount> [when ...]` | adds a flat amount |
| `discount N% [when ...]`, `load N% [when ...]` | multiplies by (1 - N%) or (1 + N%) |
| `minimum <amount>` | raises it to at least this |
| `maximum <amount>` | lowers it to at most this |
| `tax Name N%` | adds a tax line of N% of the rounded net |
| `fee "Label" <amount>` | adds a flat fee line |
| `round to 0.01` | rounding unit for every figure, half up (default 0.01) |

The result is the net premium, one line per tax and fee, and the total. The `quote`
command prints the full trail of applied steps.

### lifecycle

```
lifecycle
  cooling off 14 days, full refund
  cancellation by customer: refund pro rata, fee 25
  cancellation by insurer: refund pro rata
  adjustment: reprice, charge pro rata difference, fee 10
  lapse when unpaid after 30 days
  renewal
    invite 21 days before expiry
    increase capped at 20%
    decrease collared at 10%
    index bike_value by 5%
    index rider_age by 1
    decline when claims in term >= 3 because "Three or more claims in the year"
```

Policy status on any date is one of *quoted*, *bound* (before inception), *live*,
*lapsed*, *cancelled*, *expired* or *renewed* (a past policy year).

- **Cooling off**: cancelling within this many days of inception refunds the whole
  amount paid, fees included.
- **Cancellation** terms per party: `refund pro rata`, `full refund` or `no refund`,
  optionally `, fee N`. Pro rata refunds the earning premium (net plus taxes, never fees)
  for the unused days of the term, less the fee, never below zero. A party without a
  cancellation line cannot cancel.
- **Adjustment** (mid-term change): the policy is repriced with the new answers and the
  difference in earning premium is charged pro rata for the remaining days, plus the fee.
  A negative result is a return premium. Write `adjustment: not allowed` to forbid it.
  After an adjustment the customer's annual premium is the new one.
- **Lapse**: a policy bound but unpaid lapses after this many days until it is paid.
- **Renewal**: `index` lines first move the answers on: `by N%` for inflation of a sum
  insured, `by N` to add a fixed amount, such as a year of age. `index bike value by 5%`
  moves a field on every item. The offer is the product
  repriced on those answers, times any claims loading (see `claims`), then held within the
  cap and collar: no more than the current annual premium plus the cap percentage, no less
  than it minus the collar percentage. `decline when` rules use the indexed answers and
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
  after 2 claims in term: renewal load x 1.25
```

A cover whose `limit`, `excess` or `excludes` uses item fields is resolved per item, so
claims on it name the item: `when claim Theft on bike 2 for 900 on 2026-03-01`.

A claim on a cover is declined, with the reason, when the policy is not live on the loss
date, the cover is not included for that risk or item, a required item is missing, or a `decline
when` rule fires. Otherwise the claimed amount is first written down by the `depreciation` table (same
shape as a rating factor: the first matching row applies), then capped at the cover's
limit, then reduced by the cover's excess if `less excess` is written. A percentage excess
is of the amount claimed, before depreciation. Only paid claims count towards
`claims in term`. `after N claims in term: renewal load x M` multiplies the renewal
premium when the paid claim count reaches N; the highest matching line wins.

A paid claim can also change the terms of the policy for the rest of the term. Write
`after N claims in term` (or `after 1 claim in term`) with lifecycle lines indented below;
they replace the product's own settings from the point the Nth claim is paid, and anything
not restated carries over. The `lifecycle` block must come first in the file:

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

`given` supplies every input; `select` chooses optional covers. Repeatable items are given
one per line using the singular name, with every field: `given bike value 2000, age 0,
security gold`. Then `when` lines happen
in order and `expect` lines check the state at that point.

Events:

| Event | Meaning |
|---|---|
| `when bound on DATE [unpaid]` | inception date; add `unpaid` to test lapse |
| `when paid on DATE` | payment received |
| `when cancelled by customer\|insurer on DATE` | cancellation; the refund is available to `expect refund` |
| `when adjusted on DATE with input value, input value` | mid-term change |
| `when adjusted on DATE adding bike value 500, age 1, security gold` | add an item |
| `when adjusted on DATE removing bike 2` | remove the second item |
| `when claim Cover [on bike N] for AMOUNT on DATE [reported DATE] [with item, item]` | a loss on DATE, to item N if the cover is per item, notified on the reported date, with the listed evidence |
| `when renewed on DATE` | accept the renewal offer (fails if it is declined) |

Expectations:

| Expectation | Checks |
|---|---|
| `expect eligible` / `expect referred ["reason"]` / `expect declined ["reason"]` | eligibility outcome |
| `expect cover Name [on bike N] included\|excluded\|"not selected"\|"not available" ["reason"]` | cover state, for item N if per item |
| `expect cover Name [on bike N] limit AMOUNT` | the resolved limit |
| `expect net AMOUNT`, `expect premium AMOUNT` | net and total premium |
| `expect tax Name AMOUNT`, `expect fee "Label" AMOUNT` | one line of the premium |
| `expect factor "Label" x 1.40` | what a factor applied |
| `expect status STATUS [on DATE]` | policy status, at the last event's date by default |
| `expect expiry DATE` | end of the current term |
| `expect refund AMOUNT` | refund from the last cancellation |
| `expect additional premium AMOUNT`, `expect return premium AMOUNT` | result of the last adjustment |
| `expect claim paid`, `expect claim declined ["reason"]`, `expect payout AMOUNT` | the last claim |
| `expect claims in term N` | paid claims this policy year |
| `expect renewal premium AMOUNT`, `expect renewal invite DATE`, `expect renewal offered`, `expect renewal declined ["reason"]` | the renewal offer as things stand |

## Not yet supported

Short-rate cancellation, instalments, commission, multi-currency, more than one product per
file, new-for-old versus indemnity as a named settlement basis (use a depreciation table).
The `quote` command takes scalar inputs only; price a policy with items through a scenario. Each is a small addition to the engine; say which you need.
