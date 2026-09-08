---
title: Several items on one policy
parent: Templates
nav_order: 2
---

# Several items on one policy

Several items on one policy: a collection of items, each rated on its own fields with `for each`, a cover resolved per item, and claims that name the item. Copy this file, rename the product and the item, and give the item the fields your product asks about.

{: .proof }
> 5 scenarios, all passing, so the template is a working product before you change a line.

Copy [`templates/multi-item-product.ipn`](https://github.com/jorjives/ipn/blob/main/templates/multi-item-product.ipn), rename the product, and replace each
block as the comments direct. Keep `check` passing as you go.

```ipn
# Several items on one policy: a collection of items, each rated on its own fields with
# `for each`, a cover resolved per item, and claims that name the item. Copy this file,
# rename the product and the item, and give the item the fields your product asks about.
# Run it with:  python3 -m ipngine check templates/multi-item-product.ipn

product "Multi Item Product"
  territory UK
  term 12 months

inputs
  owner_age: integer
  items: collection of item, 1 to 5     # the plural names the collection, the singular one item
    description: text                   # free text is optional in scenarios
    value: money
    kept_at_home: yes/no

eligibility
  decline when owner_age < 18 because "Owners must be 18 or over"
  decline when any item where value > 10000 because "Items over 10,000 need a specialist policy"

cover "Loss or Damage"        # uses an item field, so it is resolved per item and a claim names the item
  limit value
  excess 50
  excludes when kept_at_home is no and value > 3000 because "Items over 3,000 must be kept at home"

rating
  for each item               # each item is rated on its own running net, then the results are added
    base 3% of value
    factor "Kept at home"
      kept_at_home is yes: x 0.90
      otherwise: x 1.00
  factor "Several items"      # steps after the block continue on the total
    count of items >= 3: x 0.95
    otherwise: x 1.00
  minimum 40
  tax IPT 12%
  round to 0.01

lifecycle
  cooling off 14 days, full refund
  cancellation by customer: refund pro rata
  cancellation by insurer: refund pro rata
  adjustment: reprice, charge pro rata difference
  renewal
    invite 21 days before expiry
    increase capped at 20%
    index item value by 3%    # moves a field on every item

claims
  claim "Loss or Damage"
    pays claimed amount up to limit, less excess

# --- Scenarios ---------------------------------------------------------------

scenario "Two items are rated one by one"
  given owner_age 40
  given item description "Watch", value 2000, kept_at_home yes
  given item description "Camera", value 1000, kept_at_home no
  # item 1: 60 x 0.90 = 54; item 2: 30 x 1.00 = 30; total 84
  expect net for item 1 54.00
  expect net for item 2 30.00
  expect net 84.00
  expect premium 94.08

scenario "Three items earn the discount"
  given owner_age 40
  given item description "Watch", value 2000, kept_at_home yes
  given item description "Camera", value 1000, kept_at_home no
  given item description "Ring", value 500, kept_at_home yes
  # 54 + 30 + 13.50 = 97.50, x 0.95 = 92.625, rounded to 92.63
  expect net 92.63
  expect premium 103.75

scenario "An expensive item kept away from home is excluded"
  given owner_age 40
  given item description "Bike", value 4000, kept_at_home no
  expect cover "Loss or Damage" on item 1 excluded "Items over 3,000 must be kept at home"

scenario "A claim names the item"
  given owner_age 40
  given item description "Watch", value 2000, kept_at_home yes
  given item description "Camera", value 1000, kept_at_home no
  when bound on 2026-01-01
  when claim "Loss or Damage" on item 2 for 800 on 2026-05-01
  expect payout 750.00

scenario "Adding an item mid term charges the pro rata difference"
  given owner_age 40
  given item description "Watch", value 2000, kept_at_home yes
  given item description "Camera", value 1000, kept_at_home no
  when bound on 2026-01-01
  when adjusted on 2026-07-02 adding item description "Ring", value 1000, kept_at_home yes
  # new net (54 + 30 + 27) x 0.95 = 105.45, IPT 12.65: 118.10 earning against 94.08; 24.02 x 183/365
  expect additional premium 12.04
```
