---
title: rating
parent: Language reference
nav_order: 7
---

# rating

The premium, in the order you write it. A factor, a discount, a minimum, then
tax. Move a step and the price changes.

```ipn
rating
  base 0.5% of contents_sum
  factor "Property type"
    property_type is flat: x 0.90
    property_type is detached: x 1.10
    otherwise: x 1.00
  add "Accidental Damage" 45 when "Accidental Damage" selected
  discount 10% when alarm is yes
  load 25% when previous_claims >= 2
  minimum 60
  maximum 800
  tax IPT 12%
  fee "Admin fee" 10
```

Steps run top to bottom.

To rate repeatable items, put the per-item steps under `for each item`. Each
item is rated on its own running net using its fields, the results are added
together, and the steps after the block continue on that total:

```ipn
rating
  base 0.5% of contents_sum
  for each item
    base 1.5% of value
  factor "Multi-item discount"
    count of specified_items >= 3: x 0.85
    otherwise: x 1.00
  tax IPT 12%
```

`fee`, `commission` and `round` belong outside the block. A `tax` may sit inside it, worked
out on each item's net as it stands at that step; the
items' amounts, each rounded, add up into one line of that name. The quote trail shows each
item's steps as `item 1 base`, `item 1 value` and so on.

To rate items in a chosen order, add `ordered by` with one or more keys. Each key is a field
or an expression, ascending unless followed by `descending`; later keys break ties and items
that still tie keep the order they were given. Inside the block `position` is the item's
place in that order, starting at 1, so the first item can take the full rate and the rest a
share of theirs. The [ranked bikes](../examples/multibike.md) example orders a collection
this way:

```ipn
rating
  for each bike, ordered by ebike descending, value descending
    base 4% of value
    factor "Position"
      position is 1: x 1.00
      otherwise: x 0.50
```

The ordering only decides the position. Items keep their given numbers in the trail and in
claims, so `item 2` always means the second item declared.

When the order depends on several things at once, give each item a [calculated
field](inputs.md#calculated-fields) and order on that. A calculated field is
never given in a scenario.

| Step | Effect on the net premium |
|---|---|
| `base <amount>` | sets it |
| `factor "Label"` with rows `condition: x N`, `: + N` or `: - N` | first row whose condition holds is applied; `otherwise` must be last |
| `factor "Label" x <amount> [when ...]` (or `+`, `-`) | a single-row factor, usually `x rate from "Table"` |
| `add ["Label"] <amount> [when ...]` | adds a flat amount |
| `discount N% [when ...]`, `load N% [when ...]` | multiplies by (1 - N%) or (1 + N%) |
| `minimum <amount>` | raises it to at least this |
| `maximum <amount>` | lowers it to at most this |
| `tax Name N% [of <base>] [when ...]` | adds a tax of N% of the rounded net, or of the base named after `of` |
| `fee "Label" <amount> [when ...]` | adds a flat fee |
| `commission "Label" N% [of <base>] [when ...]` | reports N% of the rounded net (or of the base) as owed to that intermediary; never added to the premium |
| `round to 0.01` | rounding unit for every figure, half up; without it, the smallest unit of the currency (0.01 for GBP or EUR, 1 for JPY, 0.001 for KWD) |

A product with no tax simply has no `tax` step (life premiums, for example). A product
may carry several: each is its own amount, in the order written.

Tax, fee and commission are steps like any other: each is worked out where it stands, on the figures above
it, and a step written after a tax is not taxed. The amount or `when` may read `net`
(the running net so far, rounded as the customer sees it), `premium` (the net plus every
tax, fee or commission above), and any tax above it that was named with a word rather than a quoted label
(`tax IPT 12%` makes `IPT` a word; a quoted label is read as `of "Government levy"`), and
any cover's name (its share of the net, see below). A bare rate, `12%` or `ipt from "Territory"`, is that rate of `net`; with `of`, the expression is
the amount, so a levy charged on another tax, on the running total, on a deemed proportion,
only above a threshold or only when a cover is taken, reads as the law does:

```ipn
  tax "Government levy" 3%
  tax "Fire brigade levy" 2% when Fire selected
  tax "Surcharge" 10% of IPT
  tax "QST" 9% of premium
  fee "Stamp duty" 1 when net >= 20
```

[Cycle in Ireland](../examples/irish-cycle.md) states several levies this way. The
[e-bike fleet](../examples/ebike-fleet.md) example charges a fire levy on the
e-bikes only, `tax "Fire protection" 22% of 20% of net when ebike is yes`,
inside `for each`.

A claims loading or an underwriter's load is applied just before the first tax, fee or
commission, so the load is taxed and a fee is not.

The result is the net premium, one amount per tax and fee, the total, and the commission
split of the net. The `quote` command prints the full trail of applied steps and
`batch` gives each commission its own column.

## Shares by cover

A regulator, a reinsurer or a bordereau may want each policy's premium split by
cover, or by the class each cover reports under. The product says which steps
belong to which cover, and the engine keeps every cover's share of the net
through each step.

```ipn
cover Buildings optional
  class 8
cover Contents optional
  class 9

rating
  add cover premiums
  factor "Property type" x 1.10 for Buildings when property_type is detached
  allocate
    Buildings 60%
    Contents 40%
  minimum 60
  tax IPT 12%
```

- `add cover premiums` credits each cover that has a `premium` with its own price; see
  below.
- `for <Cover>` after the amount of a `base`, `add`, `factor`, `discount` or `load` credits
  that amount to the cover, or scales that cover's share only. It goes before `when`. It
  cannot be written on `minimum`, `maximum`, tax, fee or commission.
- Steps without `for` work on the whole: a `base` or `add` goes into a shared pool; a
  `factor`, `discount`, `load`, `minimum` or `maximum` scales every share alike.
- `allocate` divides the pool between covers by the percentages given, which must sum to
  100%. Where it sits in the block makes no difference.
- The shares are rounded to the same unit as the net, and any odd cent goes to the largest
  share, so the shares always add up to the net.
- A tax or commission is attributed in proportion to its base worked out per cover: a
  plain `12%` follows the net shares, `5% of Buildings` belongs wholly to Buildings, and
  `12% of net less Buildings` is split over the others. A fee is a policy charge and has no
  share.

Once any cover has a `class` or a `premium`, any step has `for` or the block has
`allocate`, every pound of the net must belong to a cover: a pool left over with no
`allocate` is a rating error naming the amount. A product that uses none of these has no
shares and prices as it always has.

The `quote` command prints each cover's share and the class subtotals; `batch` gives each
cover a column per figure; scenarios check them with `expect net for Contents 81.00` and
`expect tax IPT for class 8 36.45`.

## Covers that price themselves

A section of cover may carry its own price (see [cover](cover.md#cover-premium-one-line-price)), and `add cover
premiums` is the step where those prices join the running net, each credited to its
cover. Buildings and contents sold together, each priced on its own sum insured:

```ipn
cover Buildings optional
  class 8
  premium 0.15% of rebuild_cost

cover Contents optional
  class 9
  premium 0.5% of contents_sum

rating
  add cover premiums
  discount 10% when Buildings selected and Contents selected
  minimum 60
  tax IPT 12%
```

- A product where any cover has a `premium` must write `add cover premiums` exactly once;
  one where no cover has a premium may not write it. Each cover's premium joins the net
  once.
- A cover that is not selected, not available or excluded contributes nothing. The steps
  after `add cover premiums` treat the covers' prices like any other share: a `discount`
  or `minimum` scales every cover alike, `for <Cover>` scales one.
- Inside `for each item`, `add cover premiums` adds the current item's premiums, so the
  steps that follow in the loop apply to them too; every priced cover must then be priced
  on an item's fields, or the parse fails naming the one that is not. Outside the loop it
  adds every cover's premium, a per-item one summed over its items. The quote trail shows each price as it joins (`Buildings + 450.00`,
  `item 1 Fire + 10.00`); a `premium` block also shows its own steps (`Buildings base`).
- A cover may have a `premium` and a row in `allocate` too: it takes its own price and its
  share of the pool.

The [e-bike fleet](../examples/ebike-fleet.md) example prices fire cover on the e-bikes of
a mixed fleet this way.
