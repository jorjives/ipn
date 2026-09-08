---
title: Rated from a table
parent: Templates
nav_order: 5
---

# Rated from a table

Rated from a table: the pricing team keeps the rates as a spreadsheet, exported in its long form (one row per cell) to rates.csv beside this file, and the product reads a factor from it. A small table is written inline instead. Copy this file and rates.csv, rename the keys to your own questions, and reissue the CSV whenever the rates change: the scenarios are how you check a reissued table.

{: .proof }
> 5 scenarios, all passing, so the template is a working product before you change a line.

Copy [`templates/rated-from-a-table.ipn`](https://github.com/jorjives/ipn/blob/main/templates/rated-from-a-table.ipn), rename the product, and replace each
block as the comments direct. Keep `check` passing as you go.

```ipn
# Rated from a table: the pricing team keeps the rates as a spreadsheet, exported in its
# long form (one row per cell) to rates.csv beside this file, and the product reads a
# factor from it. A small table is written inline instead. Copy this file and rates.csv,
# rename the keys to your own questions, and reissue the CSV whenever the rates change:
# the scenarios are how you check a reissued table.
# Run it with:  python3 -m ipngine check templates/rated-from-a-table.ipn

product "Rated From A Table"
  territory UK
  term 12 months

inputs
  driver_age: integer
  area: choice of urban, suburban, rural
  vehicle_value: money

table "Rates" from "rates.csv" keyed on driver_age, area    # driver age band by area

table "Excess" keyed on area      # a small table, written inline
  area, amount
  urban, 500
  *, 250

eligibility
  decline when driver_age < 17 because "Drivers must be 17 or over"
  decline when driver_age > 85 because "Drivers over 85 need a specialist policy"

cover Damage
  limit vehicle_value
  excess amount from "Excess"

rating
  base 4% of vehicle_value
  factor "Age and area" x rate from "Rates"
  minimum 200
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
    index driver_age by 1

claims
  claim Damage
    pays claimed amount up to limit, less excess

# --- Scenarios ---------------------------------------------------------------

scenario "A driver of 40 in a rural area takes the rural rate"
  given driver_age 40, area rural, vehicle_value 10000
  # 4% of 10,000 = 400, x 0.90 from the table
  expect factor "Age and area" x 0.90
  expect net 360.00
  expect premium 403.20

scenario "A young urban driver takes the top rate"
  given driver_age 19, area urban, vehicle_value 10000
  expect factor "Age and area" x 1.80
  expect net 720.00

scenario "The excess comes from the inline table"
  given driver_age 40, area urban, vehicle_value 10000
  when bound on 2026-01-01
  when claim Damage for 2000 on 2026-04-01
  expect payout 1500.00

scenario "The wildcard row is the fallback"
  given driver_age 40, area rural, vehicle_value 10000
  when bound on 2026-01-01
  when claim Damage for 2000 on 2026-04-01
  expect payout 1750.00

scenario "Renewal moves the driver into the next band"
  given driver_age 24, area suburban, vehicle_value 10000
  when bound on 2026-01-01
  expect net 640.00
  # at 25 the rate falls from 1.60 to 1.00: 400 net, 448 with IPT; uncollared
  expect renewal premium 448.00
```
