---
title: Light Commercial Vehicle
parent: Examples
nav_order: 12
---

# Light Commercial Vehicle

Light Commercial Vehicle: rated from a three-dimensional table the pricing team owns as a spreadsheet. Driver age band by postcode area by vehicle group, 300 cells, exported as one row per cell to van_rates.csv beside this file. A small two-dimensional table (theft excess by area and use) is written inline instead.

Reads [`van_rates.csv`](https://github.com/jorjives/open-idl/blob/main/examples/van_rates.csv) from beside the file.

{: .proof }
> 14 scenarios, all passing. Run them yourself:
> ```sh
> python3 -m ipngine check examples/van.ipn
> ```

The file: [`examples/van.ipn`](https://github.com/jorjives/open-idl/blob/main/examples/van.ipn).

```ipn
# Light Commercial Vehicle: rated from a three-dimensional table the pricing team
# owns as a spreadsheet. Driver age band by postcode area by vehicle group, 300
# cells, exported as one row per cell to van_rates.csv beside this file. A small
# two-dimensional table (theft excess by area and use) is written inline instead.
# Run it with:  python3 -m ipngine check examples/van.ipn

product "Light Commercial Vehicle"
  territory UK
  term 12 months

inputs
  postcode: text
  vehicle_value: money
  vehicle_group: integer
  driver_age: integer
  ncd_years: integer
  use: choice of own_goods, haulage, courier

enrichment "Postcode area" from postcode
  provides
    area: integer
  when unavailable: refer because "Postcode not recognised"

# One row per cell: driver_age, area, vehicle_group, rate. Age bands are inclusive
# (17-20, 21-24, ... 65+); the engine finds the one row whose cells all match.
table "Van rates" from "van_rates.csv" keyed on driver_age, area, vehicle_group

# Rows with * are the fallback: a more specific row beats them.
table "Theft excess" keyed on area, use
  area, use, excess
  1-3, *, 250
  4-5, courier, 750
  4-5, *, 500

eligibility
  decline when driver_age < 17 because "Drivers must be 17 or over"
  decline when driver_age < 21 and use is courier because "Courier use needs a driver of 21 or over"
  decline when vehicle_value > 60000 because "Vehicles over 60,000 need a fleet policy"
  refer when vehicle_group >= 9 and driver_age < 25 because "High group with a young driver needs an underwriter"

cover "Accidental Damage"
  limit vehicle_value
  # A commercial aggregate deductible: the insured bears the first 350 of damage across the year, not on every claim
  excess 350 per term

cover Theft
  limit vehicle_value
  excess excess from "Theft excess"

cover "Third Party Liability"
  limit 5000000

rating
  base 6% of vehicle_value
  factor "Driver, area and group" x rate from "Van rates"
  factor "Use"
    use is courier: x 1.30
    use is haulage: x 1.15
    otherwise: x 1.00
  factor "No claims discount"
    ncd_years >= 3: x 0.60
    ncd_years is 2: x 0.70
    ncd_years is 1: x 0.80
    otherwise: x 1.00
  minimum 250
  tax IPT 12%
  fee "Arrangement fee" 30

lifecycle
  cooling off 14 days, full refund
  cancellation by customer: refund pro rata, fee 40
  cancellation by insurer: refund pro rata
  adjustment: reprice, charge pro rata difference, fee 20
  renewal
    invite 21 days before expiry
    index driver_age by 1
    index ncd_years by 1, at most 5

claims
  claim "Accidental Damage"
    pays claimed amount up to limit, less excess
  claim Theft
    requires crime_reference
    pays claimed amount up to limit, less excess
  claim "Third Party Liability"
    pays claimed amount up to limit

# --- Rating from the table ----------------------------------------------------
# The cell for a 30-49 driver in area 3 with a group 5 van is 1.10.

scenario "A mid-life driver in an average area"
  given postcode "LS1 1AA", area 3, vehicle_value 10000, vehicle_group 5, driver_age 35, ncd_years 0, use own_goods
  expect eligible
  expect factor "Driver, area and group" x 1.10
  expect net 660.00
  expect tax IPT 79.20
  expect premium 769.20

scenario "The far corner of the table: youngest band, highest area, top group"
  given postcode "L1 1AA", area 5, vehicle_value 10000, vehicle_group 10, driver_age 19, ncd_years 0, use own_goods
  expect referred "High group with a young driver needs an underwriter"
  expect factor "Driver, area and group" x 5.62
  expect premium 3806.64

scenario "Age bands are inclusive: 24 is the last year of 21-24"
  given postcode "LS1 1AA", area 3, vehicle_value 10000, vehicle_group 5, driver_age 24, ncd_years 2, use own_goods
  expect factor "Driver, area and group" x 2.09
  expect net 877.80
  expect premium 1013.14

scenario "A year older moves to the next band"
  given postcode "LS1 1AA", area 3, vehicle_value 10000, vehicle_group 5, driver_age 25, ncd_years 2, use own_goods
  expect factor "Driver, area and group" x 1.49
  expect net 625.80
  expect premium 730.90

scenario "The open band: 65+ takes any age from 65"
  given postcode "YO1 1AA", area 2, vehicle_value 5000, vehicle_group 4, driver_age 70, ncd_years 3, use own_goods
  expect factor "Driver, area and group" x 1.09
  expect net 250.00
  expect premium 310.00

scenario "Use and no claims discount apply after the table"
  given postcode "LS1 1AA", area 3, vehicle_value 10000, vehicle_group 5, driver_age 35, ncd_years 1, use haulage
  expect factor "Use" x 1.15
  expect factor "No claims discount" x 0.80
  expect net 607.20
  expect premium 710.06

# --- The table is keyed on an enrichment ---------------------------------------

scenario "No postcode area, no rate: the risk is referred"
  given postcode "ZZ99 9ZZ", vehicle_value 10000, vehicle_group 5, driver_age 35, ncd_years 0, use own_goods
  expect referred "Postcode not recognised"

scenario "A courier under 21 is declined"
  given postcode "LS1 1AA", area 3, vehicle_value 10000, vehicle_group 5, driver_age 20, ncd_years 0, use courier
  expect declined "Courier use needs a driver of 21 or over"

# --- Lifecycle: the table is looked up again whenever the policy is repriced ---
# Area 4 group 7 for a 30-49 driver is 1.50; area 5 is 1.76. Net 576.00 (earning 645.12)
# becomes 675.84 (earning 756.94); 111.82 over the 184 remaining days of 365 is 56.37,
# plus the 20 fee.

scenario "Moving to a higher area mid term is charged pro rata"
  given postcode "S1 1AA", area 4, vehicle_value 8000, vehicle_group 7, driver_age 40, ncd_years 1, use own_goods
  expect net 576.00
  when bound on 2026-01-01
  when adjusted on 2026-07-01 with postcode "L1 1AA", area 5
  expect net 675.84
  expect additional premium 76.37

scenario "Renewal indexes the age across a band edge and grows the discount"
  given postcode "LS1 1AA", area 3, vehicle_value 10000, vehicle_group 5, driver_age 24, ncd_years 2, use own_goods
  when bound on 2026-03-01
  expect premium 1013.14
  expect renewal premium 630.77
  expect renewal invite 2027-02-08
  when renewed on 2027-03-01
  expect premium 630.77
  expect factor "Driver, area and group" x 1.49

# --- Claims: an aggregate deductible on damage --------------------------------

scenario "The insured bears the first 350 of damage across the year"
  given postcode "YO1 1AA", area 2, vehicle_value 10000, vehicle_group 5, driver_age 35, ncd_years 0, use own_goods
  when bound on 2026-01-01
  expect cover "Accidental Damage" excess remaining 350
  when claim "Accidental Damage" for 200 on 2026-02-01
  expect claim declined "nothing is payable after the excess"
  expect cover "Accidental Damage" excess remaining 150
  when claim "Accidental Damage" for 1000 on 2026-05-01
  expect payout 850.00
  expect cover "Accidental Damage" excess remaining 0
  when claim "Accidental Damage" for 600 on 2026-08-01
  expect payout 600.00
  expect claims in term 2

# --- Claims: the excess comes from the inline table ----------------------------

scenario "Theft in a low area takes the 250 excess"
  given postcode "YO1 1AA", area 2, vehicle_value 10000, vehicle_group 5, driver_age 35, ncd_years 0, use own_goods
  when bound on 2026-01-01
  when claim Theft for 3000 on 2026-05-01 with crime_reference
  expect payout 2750.00

scenario "Theft of a courier van in a high area takes the specific 750 row"
  given postcode "L1 1AA", area 5, vehicle_value 10000, vehicle_group 5, driver_age 30, ncd_years 0, use courier
  when bound on 2026-01-01
  when claim Theft for 3000 on 2026-05-01 with crime_reference
  expect payout 2250.00

scenario "Theft of any other van in a high area falls back to the * row"
  given postcode "S1 1AA", area 4, vehicle_value 10000, vehicle_group 5, driver_age 30, ncd_years 0, use haulage
  when bound on 2026-01-01
  when claim Theft for 3000 on 2026-05-01 with crime_reference
  expect payout 2500.00
```
