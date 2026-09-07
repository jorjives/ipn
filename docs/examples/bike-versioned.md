---
title: Bike Cover across three versions
parent: Examples
nav_order: 17
---

# Bike Cover across three versions

Published versions, upgrading answers at renewal, a dated amendment. The files sit together in [`examples/versioned/`](https://github.com/jorjives/open-idl/tree/main/examples/versioned); each
declares the same product name and says when it was published, and `check` finds the others by itself.

{: .proof }
> 16 scenarios across the versions, all passing.

## bike-2026-01-01

Bike Cover as first sold. Later versions of this product sit beside it in this directory; each says when it was published, and a policy stays on the version live when it was bound until it renews. Run:  python3 -m ideclare check examples/versioned/bike-2026-01-01.idl

2 scenarios: `python3 -m ideclare check examples/versioned/bike-2026-01-01.idl`

```idl
# Bike Cover as first sold. Later versions of this product sit beside it in this directory;
# each says when it was published, and a policy stays on the version live when it was bound
# until it renews. Run:  python3 -m ideclare check examples/versioned/bike-2026-01-01.idl

product "Bike Cover"
  published 2026-01-01
  territory UK
  term 12 months

inputs
  bike_value: money
  rider_age: integer
  security: choice of bronze, silver, gold

eligibility
  decline when rider_age < 16 because "Rider must be at least 16"

cover Theft
  limit bike_value
  excess 50
  excludes when security is bronze and bike_value > 2000 because "Gold or silver rated lock required"

cover "Accidental Damage"
  limit bike_value
  excess 100

rating
  base 60
  add "Value" 3% of bike_value
  discount "Gold lock" 10% when security is gold
  round to 0.01
  tax IPT 12%

lifecycle
  cooling off 14 days, full refund
  cancellation by customer: refund pro rata, fee 25
  adjustment: reprice, charge pro rata difference
  renewal
    invite 21 days before expiry
    increase capped at 20%
    index bike_value by 5%

claims
  claim Theft
    requires crime_reference
    pays claimed amount up to limit, less excess

scenario "A gold lock earns the discount"
  given bike_value 2000, rider_age 30, security gold
  expect eligible
  expect net 108.00
  expect premium 120.96

scenario "Theft is paid less the excess"
  given bike_value 2000, rider_age 30, security gold
  when bound on 2026-02-01
  when claim Theft for 1500 on 2026-06-01 with crime_reference
  expect payout 1450.00
```

## bike-2026-07-01

Bike Cover, second version: the base rate rises and racing cover is offered. Customers on the first version keep it until renewal, when they move here. The renewal cap holds against the premium they were charged, whichever version charged it. It also carries a mid-term amendment: from 1 March 2027 a theft claim needs a photo of the lock as well as a crime reference. A dated line is not a new version; it reaches every policy in force on that date, on this version or the first, so it is written once, here, and never copied into later versions. It must read in the words of every version it reaches.

7 scenarios: `python3 -m ideclare check examples/versioned/bike-2026-07-01.idl`

```idl
# Bike Cover, second version: the base rate rises and racing cover is offered. Customers on
# the first version keep it until renewal, when they move here. The renewal cap holds
# against the premium they were charged, whichever version charged it.
#
# It also carries a mid-term amendment: from 1 March 2027 a theft claim needs a photo of the
# lock as well as a crime reference. A dated line is not a new version; it reaches every policy
# in force on that date, on this version or the first, so it is written once, here, and never
# copied into later versions. It must read in the words of every version it reaches.
# Run:  python3 -m ideclare check examples/versioned/bike-2026-07-01.idl

product "Bike Cover"
  published 2026-07-01
  territory UK
  term 12 months

inputs
  bike_value: money
  rider_age: integer
  security: choice of bronze, silver, gold
  racing: yes/no, default no

eligibility
  decline when rider_age < 16 because "Rider must be at least 16"

cover Theft
  limit bike_value
  excess 50
  excludes when security is bronze and bike_value > 2000 because "Gold or silver rated lock required"

cover "Accidental Damage"
  limit bike_value
  excess 100

cover Racing optional
  limit bike_value
  excess 250
  available when racing is yes

rating
  base 80
  add "Value" 3% of bike_value
  add "Racing" 40 when Racing selected
  discount "Gold lock" 10% when security is gold
  round to 0.01
  tax IPT 12%

lifecycle
  cooling off 14 days, full refund
  cancellation by customer: refund pro rata, fee 25
  adjustment: reprice on the current version, charge pro rata difference
  renewal
    invite 21 days before expiry
    increase capped at 20%
    index bike_value by 5%

claims
  claim Theft
    requires crime_reference
    from 2027-03-01 requires crime_reference, lock_photo
    pays claimed amount up to limit, less excess

scenario "A new customer pays the new base rate"
  given bike_value 2000, rider_age 30, security gold
  when bound on 2026-08-01
  expect version 2026-07-01
  expect net 126.00
  expect premium 141.12

scenario "A customer from the first version stays on it until renewal"
  given bike_value 2000, rider_age 30, security gold
  when bound on 2026-03-01
  expect version 2026-01-01
  expect premium 120.96
  when claim Theft for 500 on 2026-09-01 with crime_reference
  expect payout 450.00
  expect status live on 2026-09-01
  expect version 2026-01-01

scenario "At renewal the customer moves to this version, within the cap"
  given bike_value 2000, rider_age 30, security gold
  when bound on 2026-03-01
  expect renewal premium 144.14
  when renewed on 2027-03-01
  expect version 2026-07-01
  expect bike_value 2100
  expect racing no
  expect premium 144.14

scenario "Nobody could buy the product before it existed"
  given bike_value 2000, rider_age 30, security gold
  when bound on 2025-12-01
  expect refused "no version of Bike Cover was on sale on 2025-12-01"

scenario "Before the amendment a crime reference was enough"
  given bike_value 2000, rider_age 30, security gold
  when bound on 2026-08-01
  when claim Theft for 1000 on 2027-02-01 with crime_reference
  expect payout 950.00

scenario "From the amendment date a theft claim also needs a photo of the lock"
  given bike_value 2000, rider_age 30, security gold
  when bound on 2026-08-01
  when claim Theft for 1000 on 2027-03-01 with crime_reference
  expect claim declined "lock_photo is required"
  when claim Theft for 1000 on 2027-03-01 with crime_reference, lock_photo
  expect payout 950.00

scenario "The amendment reaches a customer still on the first version"
  given bike_value 2000, rider_age 30, security gold
  when bound on 2026-06-01
  expect version 2026-01-01
  when claim Theft for 1000 on 2027-02-01 with crime_reference
  expect payout 950.00
  when claim Theft for 1000 on 2027-04-01 with crime_reference
  expect claim declined "lock_photo is required"
  expect version 2026-01-01
```

## bike-2027-01-01

Bike Cover, third version: the lock question changes shape. `security` becomes `lock_rating`, with a new top tier, and a customer's answer moves across with the `upgrading` block. A bronze lock may be no lock worth the name, so those customers are asked rather than guessed at: their renewal needs an answer before it can be priced.

7 scenarios: `python3 -m ideclare check examples/versioned/bike-2027-01-01.idl`

```idl
# Bike Cover, third version: the lock question changes shape. `security` becomes
# `lock_rating`, with a new top tier, and a customer's answer moves across with the
# `upgrading` block. A bronze lock may be no lock worth the name, so those customers are
# asked rather than guessed at: their renewal needs an answer before it can be priced.
# Run:  python3 -m ideclare check examples/versioned/bike-2027-01-01.idl

product "Bike Cover"
  published 2027-01-01
  territory UK
  term 12 months

inputs
  bike_value: money
  rider_age: integer
  lock_rating: choice of bronze, silver, gold, diamond
  racing: yes/no, default no
  usage: choice of leisure, commuting, default leisure

upgrading
  lock_rating
    security is gold: gold
    security is silver: silver
    otherwise: ask

eligibility
  decline when rider_age < 16 because "Rider must be at least 16"

cover Theft
  limit bike_value
  excess 50
  excludes when lock_rating is bronze and bike_value > 1000 because "Silver rated lock or better required"

cover "Accidental Damage"
  limit bike_value
  excess 100

cover Racing optional
  limit bike_value
  excess 250
  available when racing is yes

rating
  base 80
  add "Value" 3% of bike_value
  add "Racing" 40 when Racing selected
  load "Commuting" 15% when usage is commuting
  discount "Gold lock" 10% when lock_rating is gold
  discount "Diamond lock" 20% when lock_rating is diamond
  round to 0.01
  tax IPT 12%

lifecycle
  cooling off 14 days, full refund
  cancellation by customer: refund pro rata, fee 25
  adjustment: reprice on the current version, charge pro rata difference
  renewal
    invite 21 days before expiry
    increase capped at 20%
    index bike_value by 5%

claims
  claim Theft
    requires crime_reference
    pays claimed amount up to limit, less excess

scenario "A new customer answers the new question"
  given bike_value 2000, rider_age 30, lock_rating diamond, usage commuting
  when bound on 2027-02-01
  expect version 2027-01-01
  expect net 128.80
  expect premium 144.26

scenario "A gold lock from the first version carries across two upgrades"
  given bike_value 2000, rider_age 30, security gold
  when bound on 2026-03-01
  expect version 2026-01-01
  when renewed on 2027-03-01
  expect version 2027-01-01
  expect lock_rating gold
  expect racing no
  expect usage leisure
  expect bike_value 2100
  expect premium 144.14

scenario "A bronze lock must be asked about before the renewal can be priced"
  given bike_value 900, rider_age 30, security bronze
  when bound on 2026-03-01
  expect renewal needs lock_rating
  when renewed on 2027-03-01
  expect refused "renewal needs lock_rating"
  when renewed on 2027-03-01 with lock_rating silver
  expect version 2027-01-01
  expect lock_rating silver
  expect cover Theft included

scenario "A customer from the second version moves straight here"
  given bike_value 2000, rider_age 30, security silver, racing yes
  select Racing
  when bound on 2026-09-01
  expect version 2026-07-01
  when renewed on 2027-09-01
  expect version 2027-01-01
  expect lock_rating silver
  expect racing yes

scenario "A first-version customer's mid-term change stays on the first version"
  given bike_value 2000, rider_age 30, security gold
  when bound on 2026-03-01
  when adjusted on 2027-02-01 with bike_value 3000
  expect version 2026-01-01
  expect premium 151.20
  expect additional premium 2.32

scenario "A second-version customer's mid-term change moves them here"
  given bike_value 2000, rider_age 30, security gold
  when bound on 2026-09-01
  expect version 2026-07-01
  when adjusted on 2027-02-01 with bike_value 3000
  expect version 2027-01-01
  expect lock_rating gold
  expect premium 171.36

scenario "A bronze lock cannot move mid term without answering"
  given bike_value 900, rider_age 30, security bronze
  when bound on 2026-09-01
  when adjusted on 2027-02-01 with bike_value 950
  expect refused "adjustment needs lock_rating"
  expect version 2026-07-01
  when adjusted on 2027-02-01 with bike_value 950, lock_rating silver
  expect version 2027-01-01
  expect bike_value 950
```
