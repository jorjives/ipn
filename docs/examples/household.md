---
title: Household
parent: Examples
nav_order: 2
---

# Household

Household: buildings and contents sold as one policy. Each section is optional, priced on its own sum insured with its own excess and claims, and taking both earns a bundle discount. A customer must take at least one section. Each section carries its class, so the premium and tax are split between them.

{: .proof }
> 8 scenarios, all passing. Run them yourself:
> ```sh
> python3 -m ipngine check examples/household.ipn
> ```

The file: [`examples/household.ipn`](https://github.com/jorjives/ipn/blob/main/examples/household.ipn).

```ipn
# Household: buildings and contents sold as one policy. Each section is optional,
# priced on its own sum insured with its own excess and claims, and taking both
# earns a bundle discount. A customer must take at least one section. Each
# section carries its class, so the premium and tax are split between them.
# Run it with:  python3 -m ipngine check examples/household.ipn

product "Household"
  territory UK
  term 12 months

inputs
  rebuild_cost: money, default 0
  contents_sum: money, default 0
  property_type: choice of detached, semi, terrace, flat
  year_built: integer
  previous_claims: integer

cover Buildings optional
  class 8
  premium 0.15% of rebuild_cost
  limit rebuild_cost
  excess
    cause is subsidence: 1000
    otherwise: 250

cover Contents optional
  class 9
  premium 0.5% of contents_sum
  limit contents_sum
  excess 100

# Eligibility reads the chosen sections, so it comes after the covers it names.
eligibility
  decline when not Buildings selected and not Contents selected because "Take buildings cover, contents cover or both"
  decline when Buildings selected and rebuild_cost < 50000 because "The minimum rebuild cost is 50,000"
  decline when Contents selected and contents_sum < 5000 because "The minimum contents sum insured is 5,000"
  decline when rebuild_cost > 1000000 because "Rebuild costs over 1,000,000 need a high net worth policy"
  refer when year_built < 1850 because "Listed and very old buildings need an underwriter"

rating
  add cover premiums
  factor "Property type"
    property_type is flat: x 0.90
    property_type is detached: x 1.10
    otherwise: x 1.00
  factor "Age of building"
    year_built < 1920: x 1.25
    year_built < 1980: x 1.05
    otherwise: x 1.00
  factor "Claims history"
    previous_claims >= 2: x 1.40
    previous_claims is 1: x 1.15
    otherwise: x 1.00
  discount 10% when Buildings selected and Contents selected
  minimum 60
  tax IPT 12%

lifecycle
  cooling off 14 days, full refund
  cancellation by customer: refund pro rata, fee 25
  cancellation by insurer: refund pro rata
  adjustment: reprice, charge pro rata difference
  renewal
    invite 21 days before expiry
    index rebuild_cost by 4%
    index contents_sum by 3%
    index previous_claims by claims in term

claims
  claim Buildings
    asks
      cause: choice of fire, storm, flood, subsidence, escape_of_water, other
    pays claimed amount up to limit, less excess
  claim Contents
    asks
      cause: choice of fire, theft, escape_of_water, other
    pays claimed amount up to limit, less excess
  after 2 claims in term: renewal load x 1.20

# --- One section, the other, or both --------------------------------------

scenario "Buildings only"
  given rebuild_cost 300000, property_type semi, year_built 1995, previous_claims 0
  select Buildings
  expect eligible
  expect cover Buildings included
  expect cover Contents "not selected"
  # 0.15% of 300,000 = 450
  expect net 450.00
  expect net for Buildings 450.00
  expect premium 504.00

scenario "Contents only, in a flat"
  given contents_sum 40000, property_type flat, year_built 2005, previous_claims 0
  select Contents
  expect eligible
  # 0.5% of 40,000 = 200, x 0.90
  expect net 180.00

scenario "Both sections earn the bundle discount"
  given rebuild_cost 300000, contents_sum 40000, property_type semi, year_built 1995, previous_claims 0
  select Buildings, Contents
  expect eligible
  # 450 + 200 = 650, less 10%; each section keeps its share of the discount and of IPT
  expect net 585.00
  expect net for Buildings 405.00
  expect net for Contents 180.00
  expect tax IPT for Buildings 48.60
  expect tax IPT for class 9 21.60
  expect premium 655.20

scenario "Neither section is not a policy"
  given property_type semi, year_built 1995, previous_claims 0
  expect declined "Take buildings cover, contents cover or both"

scenario "A section that is not taken is not checked"
  given rebuild_cost 300000, contents_sum 1000, property_type semi, year_built 1995, previous_claims 0
  select Buildings
  expect eligible

# --- Each section settles on its own terms ---------------------------------

scenario "Subsidence carries the higher buildings excess"
  given rebuild_cost 300000, contents_sum 40000, property_type semi, year_built 1995, previous_claims 0
  select Buildings, Contents
  when bound on 2026-01-01
  when claim Buildings for 12000 on 2026-05-01 with cause subsidence
  expect payout 11000.00
  when claim Contents for 3000 on 2026-06-01 with cause theft
  expect payout 2900.00
  when claim Contents for 500 on 2026-07-01 with cause fire
  expect payout 400.00

scenario "A section not taken cannot be claimed on"
  given rebuild_cost 300000, property_type semi, year_built 1995, previous_claims 0
  select Buildings
  when bound on 2026-01-01
  when claim Contents for 3000 on 2026-06-01 with cause theft
  expect claim declined "Contents is not selected"

scenario "Renewal indexes both sums and rolls the claims forward"
  given rebuild_cost 300000, contents_sum 40000, property_type semi, year_built 1995, previous_claims 0
  select Buildings, Contents
  when bound on 2026-01-01
  when claim Buildings for 12000 on 2026-05-01 with cause storm
  # 312,000 x 0.15% = 468, 41,200 x 0.5% = 206, 674 x 1.15 = 775.10, less 10% = 697.59
  expect renewal premium 781.30
```
