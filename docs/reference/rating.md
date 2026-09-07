---
title: rating
parent: Language reference
nav_order: 7
---

# rating

```idl
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

```idl
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

`fee`, `commission` and `round` belong outside the block. A `tax` may sit inside it, worked
out on each item's net as it stands at that step (a fire levy on e-bikes only, say); the
items' amounts, each rounded, add up into one line of that name. The quote trail shows each
item's steps as `bike 1 base`, `bike 1 Bike age` and so on.

To rate items in a chosen order, add `ordered by` with one or more keys. Each key is a field
or an expression, ascending unless followed by `descending`; later keys break ties and items
that still tie keep the order they were given. Inside the block `position` is the item's
place in that order, starting at 1, so the first bike can take the full rate and the rest a
share of theirs:

```idl
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

```idl
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

```idl
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
| `tax Name N% [of <base>] [when ...]` | adds a tax line of N% of the rounded net, or of the base named after `of` |
| `fee "Label" <amount> [when ...]` | adds a flat fee line |
| `commission "Label" N% [of <base>] [when ...]` | reports N% of the rounded net (or of the base) as owed to that intermediary; never added to the premium |
| `round to 0.01` | rounding unit for every figure, half up; without it, the smallest unit of the currency (0.01 for GBP or EUR, 1 for JPY, 0.001 for KWD) |

A product with no tax simply has no `tax` line (life premiums, for example). A product
may carry several: each is its own line, in the order written.

Lines are steps like any other: a line is worked out where it stands, on the figures above
it, and a step written after a tax is not taxed. A line's amount or `when` may read `net`
(the running net so far, rounded as the customer sees it), `premium` (the net plus every
line above), and any tax above it that was named with a word rather than a quoted label
(`tax IPT 12%` makes `IPT` a word; `tax "Government levy" 3%` cannot be referred to). A bare
rate, `12%` or `ipt from "Territory"`, is that rate of `net`; with `of`, the expression is
the amount, so a levy charged on another tax, on the running total, on a deemed proportion,
only above a threshold or only when a cover is taken, reads as the law does:

```idl
  tax "Government levy" 3%
  tax "Fire brigade levy" 2% when Fire selected
  tax "Surcharge" 10% of IPT
  tax "QST" 9% of premium
  tax "Fire protection" 22% of 20% of net when ebike is yes
  fee "Stamp duty" 1 when net >= 20
```

A claims loading or an underwriter's load is applied just before the first line, so tax
follows a load and a fee does not.

The result is the net premium, one line per tax and fee, the total, and the commission
split of the net. The `quote` command prints the full trail of applied steps and
`batch` gives each commission its own column.
