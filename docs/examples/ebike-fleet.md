---
title: E-bike Fleet
parent: Examples
nav_order: 8
---

# E-bike Fleet

E-bike Fleet: pedal and electric bikes on one policy. Every bike carries theft and accidental damage. Fire cover prices itself on each e-bike (the battery is the fire risk) and is excluded on pedal bikes, so its premium is exactly the e-bikes' share. Each cover carries the class it reports under, a fire levy is charged on the fire premium alone, and the tax on the rest is split by cover.

{: .proof }
> 5 scenarios, all passing. Run them yourself:
> ```sh
> python3 -m ipngine check examples/ebike-fleet.ipn
> ```

The file: [`examples/ebike-fleet.ipn`](https://github.com/jorjives/ipn/blob/main/examples/ebike-fleet.ipn).

```ipn
# E-bike Fleet: pedal and electric bikes on one policy. Every bike carries theft
# and accidental damage. Fire cover prices itself on each e-bike (the battery is
# the fire risk) and is excluded on pedal bikes, so its premium is exactly the
# e-bikes' share. Each cover carries the class it reports under, a fire levy is
# charged on the fire premium alone, and the tax on the rest is split by cover.
# Run it with:  python3 -m ipngine check examples/ebike-fleet.ipn

product "E-bike Fleet"
  territory UK
  term 12 months

inputs
  rider_age: integer
  bikes: collection of bike, 1 to 6
    value: money
    ebike: yes/no
    security: choice of bronze, silver, gold

eligibility
  decline when rider_age < 18 because "Policyholder must be an adult"
  decline when any bike where value > 10000 because "Bikes over 10,000 need a specialist policy"

cover Theft
  class 9
  limit value
  excess 10% of claim, minimum 50
  excludes when security is bronze and value > 2000 because "Gold or silver rated lock required"

cover "Accidental Damage"
  class 3
  limit value
  excess 50

cover Fire
  class 8
  premium 0.5% of value
  limit value
  excess 50
  excludes when ebike is no because "Fire cover is for e-bikes"

rating
  for each bike
    base 3% of value for Theft
    add "Damage" 1.5% of value for "Accidental Damage"
    # The lock discount is for theft and damage; fire joins after it.
    factor "Security"
      security is gold: x 0.85
      security is silver: x 0.95
      otherwise: x 1.00
    add cover premiums
  factor "Fleet"
    count of bikes >= 3: x 0.90
    otherwise: x 1.00
  minimum 60
  tax "Fire levy" 20% of Fire
  tax IPT 12% of net less Fire
  fee "Admin fee" 5

lifecycle
  cooling off 14 days, full refund
  cancellation by customer: refund pro rata, fee 10
  cancellation by insurer: refund pro rata
  adjustment: reprice, charge pro rata difference
  renewal
    invite 21 days before expiry

claims
  claim Theft
    pays claimed amount up to limit, less excess
  claim "Accidental Damage"
    pays claimed amount up to limit, less excess
  claim Fire
    pays claimed amount up to limit, less excess

# --- Rating ---------------------------------------------------------------

scenario "Fire is priced on the e-bikes only, and the levy on fire alone"
  given rider_age 30
  given bike value 2000, ebike yes, security gold
  given bike value 1000, ebike no, security gold
  given bike value 3000, ebike yes, security silver
  expect eligible
  expect cover Fire on bike 2 excluded "Fire cover is for e-bikes"
  # bike 1: theft 60 + damage 30, x 0.85 = 76.50, + fire 10 = 86.50
  # bike 2: theft 30 + damage 15, x 0.85 = 38.25, no fire
  # bike 3: theft 90 + damage 45, x 0.95 = 128.25, + fire 15 = 143.25
  # 268 less the 10% fleet discount = 241.20
  expect net for bike 1 86.50
  expect net for bike 2 38.25
  expect net 241.20
  expect net for Theft 145.80
  expect net for "Accidental Damage" 72.90
  expect net for Fire 22.50
  # the levy is 20% of the fire premium; IPT is 12% of the other 218.70, split between them
  expect tax "Fire levy" 4.50
  expect tax "Fire levy" for Fire 4.50
  expect tax IPT 26.24
  expect tax IPT for Fire 0.00
  expect tax IPT for Theft 17.49
  expect net for class 8 22.50
  expect net for class 9 145.80
  expect net for class 3 72.90
  expect premium 276.94

scenario "A pedal-only fleet carries no fire premium and no levy"
  given rider_age 30
  given bike value 1500, ebike no, security gold
  # theft 45 + damage 22.50, x 0.85 = 57.375, raised to the minimum: theft and damage keep their 2:1 split
  expect net 60.00
  expect net for Theft 40.00
  expect net for "Accidental Damage" 20.00
  expect tax "Fire levy" 0.00
  expect tax IPT 7.20

scenario "Bikes over 10,000 need a specialist policy"
  given rider_age 30
  given bike value 12000, ebike yes, security gold
  expect declined "Bikes over 10,000 need a specialist policy"

# --- Claims ---------------------------------------------------------------

scenario "A fire claim pays on an e-bike and is excluded on a pedal bike"
  given rider_age 30
  given bike value 2000, ebike yes, security gold
  given bike value 1000, ebike no, security gold
  when bound on 2026-01-01
  when claim Fire on bike 1 for 800 on 2026-03-01
  expect payout 750.00
  when claim Fire on bike 2 for 500 on 2026-04-01
  expect claim declined "Fire is excluded: Fire cover is for e-bikes"

# --- Lifecycle ------------------------------------------------------------

scenario "A refund is split between the covers as the premium was"
  given rider_age 30
  given bike value 2000, ebike yes, security gold
  given bike value 1000, ebike no, security gold
  given bike value 3000, ebike yes, security silver
  when bound on 2026-01-01
  when cancelled by customer on 2026-07-01
  # net and taxes 271.94 earn over the term; 184 of 365 days are left, less the 10 fee: 127.09
  # each cover takes the share of it that its net plus taxes had: fire 27.00 of 271.94
  expect refund 127.09
  expect refund for Fire 12.62
  expect refund for Theft 76.31
  expect refund for "Accidental Damage" 38.16
  expect refund for class 3 38.16
```
