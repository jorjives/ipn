---
title: Family Cycle Cover
parent: Examples
nav_order: 14
---

# Family Cycle Cover

Family Cycle Cover: one policy, several bikes. Shows repeatable items.

{: .proof }
> 12 scenarios, all passing. Run them yourself:
> ```sh
> python3 -m ipngine check examples/family.ipn
> ```

The file: [`examples/family.ipn`](https://github.com/jorjives/ipn/blob/main/examples/family.ipn).

```ipn
# Family Cycle Cover: one policy, several bikes. Shows repeatable items.
# Run it with:  python3 -m ipngine check examples/family.ipn

product "Family Cycle Cover"
  territory UK
  term 12 months

inputs
  rider_age: integer
  bikes: collection of bike, 1 to 4
    value: money
    age: integer
    security: choice of bronze, silver, gold

eligibility
  decline when rider_age < 18 because "Policyholder must be an adult"
  decline when any bike where value > 10000 because "Bikes over 10,000 need a specialist policy"
  refer when total value of bikes > 15000 because "Fleet value needs an underwriter"

cover Theft
  limit value
  excess 10% of claim, minimum 50
  excludes when security is bronze and value > 2000 because "Gold or silver rated lock required"

cover "Accidental Damage"
  limit value
  excess 75

rating
  for each bike
    base 3% of value
    factor "Bike age"
      age < 1: x 1.00
      age < 4: x 0.90
      otherwise: x 0.80
    factor "Security"
      security is gold: x 0.85
      otherwise: x 1.00
  factor "Multi-bike discount"
    count of bikes >= 3: x 0.85
    count of bikes is 2: x 0.95
    otherwise: x 1.00
  minimum 45
  tax IPT 12%
  fee "Admin fee" 10

lifecycle
  cooling off 14 days, full refund
  cancellation by customer: refund pro rata, fee 20
  adjustment: reprice, charge pro rata difference
  renewal
    invite 21 days before expiry
    increase capped at 25%
    index bike value by 5%
    index bike age by 1

claims
  claim Theft
    requires police_report
    pays claimed amount up to limit, less excess
    depreciation
      age < 1: x 1.00
      otherwise: x 0.85
  claim "Accidental Damage"
    pays claimed amount up to limit, less excess
  after 2 claims in term: renewal load x 1.20

# --- Eligibility and bounds ------------------------------------------------

scenario "At least one bike is required"
  given rider_age 30
  expect declined "bikes: at least 1 required"

scenario "No more than four bikes"
  given rider_age 30
  given bike value 500, age 0, security gold
  given bike value 500, age 0, security gold
  given bike value 500, age 0, security gold
  given bike value 500, age 0, security gold
  given bike value 500, age 0, security gold
  expect declined "bikes: at most 4 allowed"

scenario "One bike over the limit declines the whole fleet"
  given rider_age 30
  given bike value 800, age 0, security gold
  given bike value 12000, age 0, security gold
  expect declined "Bikes over 10,000 need a specialist policy"

scenario "High total value is referred"
  given rider_age 30
  given bike value 8000, age 0, security gold
  given bike value 8000, age 0, security gold
  expect referred "Fleet value needs an underwriter"

# --- Covers per bike ---------------------------------------------------------

scenario "Cover is resolved bike by bike"
  given rider_age 30
  given bike value 2000, age 0, security gold
  given bike value 3000, age 2, security bronze
  expect cover Theft on bike 1 included
  expect cover Theft on bike 1 limit 2000
  expect cover Theft on bike 2 excluded "Gold or silver rated lock required"
  expect cover "Accidental Damage" on bike 2 included

# --- Rating ------------------------------------------------------------------

scenario "Each bike is rated on its own, then the fleet discount applies"
  given rider_age 30
  given bike value 2000, age 0, security gold
  given bike value 1000, age 2, security silver
  # bike 1: 60 x 1.00 x 0.85 = 51.00; bike 2: 30 x 0.90 x 1.00 = 27.00; fleet 78.00 x 0.95 = 74.10
  expect factor "Multi-bike discount" x 0.95
  expect net 74.10
  expect tax IPT 8.89
  expect premium 92.99

scenario "Three bikes earn the larger discount"
  given rider_age 30
  given bike value 1000, age 0, security gold
  given bike value 1000, age 0, security gold
  given bike value 1000, age 5, security gold
  # 25.50 + 25.50 + 20.40 = 71.40 x 0.85 = 60.69
  expect net 60.69

# --- Lifecycle with items ----------------------------------------------------

scenario "Adding a bike mid term charges the pro rata difference"
  given rider_age 30
  given bike value 2000, age 0, security gold
  when bound on 2026-01-01
  # single bike: net 51.00, IPT 6.12, earning 57.12
  expect premium 67.12
  when adjusted on 2026-07-02 adding bike value 1000, age 2, security silver
  # two bikes: earning 74.10 + 8.89 = 82.99; difference 25.87 x 183/365
  expect additional premium 12.97
  expect premium 92.99

scenario "Removing a bike returns premium"
  given rider_age 30
  given bike value 2000, age 0, security gold
  given bike value 1000, age 2, security silver
  when bound on 2026-01-01
  when adjusted on 2026-07-02 removing bike 2
  expect return premium 12.97
  expect premium 67.12

scenario "Renewal indexes every bike's value and age"
  given rider_age 30
  given bike value 2000, age 0, security gold
  when bound on 2026-01-01
  # at renewal the bike is worth 2100 and is 1 year old: 63 x 0.90 x 0.85 = 48.20, IPT 5.78, fee 10
  expect renewal premium 63.98

# --- Claims on a bike --------------------------------------------------------

scenario "Theft claim on a specific bike"
  given rider_age 30
  given bike value 2000, age 0, security gold
  given bike value 1000, age 2, security silver
  when bound on 2026-01-01
  when claim Theft on bike 2 for 900 on 2026-03-01 with police_report
  # 900 x 0.85 depreciation = 765, less 10% of 900
  expect payout 675.00
  when claim Theft on bike 1 for 1500 on 2026-04-01 with police_report
  expect payout 1350.00
  expect claims in term 2

scenario "Claim on an excluded bike is declined"
  given rider_age 30
  given bike value 3000, age 0, security bronze
  when bound on 2026-01-01
  when claim Theft on bike 1 for 1500 on 2026-03-01 with police_report
  expect claim declined "Theft is excluded: Gold or silver rated lock required"
  when claim "Accidental Damage" on bike 1 for 500 on 2026-03-01
  expect payout 425.00
```
