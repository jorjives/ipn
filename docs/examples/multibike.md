---
title: Multi Bike Cover
parent: Examples
nav_order: 3
---

# Multi Bike Cover

Multi Bike Cover: several bikes, each rated on its make and value. Every bike gets a calculated rank score, the fleet is ordered on it, and the first bike takes the full rate while the rest take half.

{: .proof }
> 11 scenarios, all passing. Run them yourself:
> ```sh
> python3 -m ipngine check examples/multibike.ipn
> ```

The file: [`examples/multibike.ipn`](https://github.com/jorjives/open-idl/blob/main/examples/multibike.ipn).

```ipn
# Multi Bike Cover: several bikes, each rated on its make and value. Every bike
# gets a calculated rank score, the fleet is ordered on it, and the first bike
# takes the full rate while the rest take half.
# Run it with:  python3 -m ipngine check examples/multibike.ipn

product "Multi Bike Cover"
  territory UK
  term 12 months

inputs
  rider_age: integer
  postcode: text
  bikes: collection of bike, 1 to 6
    make: text
    model: text
    value: money
    ebike: yes/no
    # The rank is the value plus small nudges: an e-bike beats a pedal bike of the
    # same value, and a Brompton beats another make. Bikes that still tie keep
    # the order they were given.
    rank: calculated
      base value
      add 0.01 when ebike is yes
      add 0.001 when make is "Brompton"

# Lookups the product relies on but does not perform. Each declares what it is
# keyed on, what it provides, and what to do when it cannot answer.
enrichment "Postcode risk" from postcode
  provides
    theft_area: choice of low, medium, high
  when unavailable: refer because "Postcode not recognised"
  held for the term

enrichment "Bike catalogue" for each bike from make, model
  provides
    category: choice of road, mountain, folding, other
  when unavailable: category is other

eligibility
  decline when rider_age < 18 because "Policyholder must be an adult"
  decline when any bike where value > 15000 because "Bikes over 15,000 need a specialist policy"

cover Theft
  limit value
  excess 10% of claim, minimum 50

cover "Accidental Damage"
  limit value
  excess 10% of claim, minimum 50

rating
  # The ordering decides which bike is "first"; it does not change any rate.
  for each bike, ordered by rank descending
    base 4% of value
    factor "Make"
      make is "Brompton": x 0.90
      make is "Canyon": x 1.10
      otherwise: x 1.00
    factor "Value band"
      value < 1000: x 1.00
      value < 3000: x 1.10
      otherwise: x 1.25
    factor "E-bike"
      ebike is yes: x 1.15
      otherwise: x 1.00
    factor "Category"
      category is folding: x 0.90
      otherwise: x 1.00
    factor "Position"
      position is 1: x 1.00
      otherwise: x 0.50
  factor "Theft area"
    theft_area is high: x 1.30
    theft_area is medium: x 1.10
    otherwise: x 1.00
  minimum 40
  tax IPT 12%

lifecycle
  cooling off 14 days, full refund
  cancellation by customer: refund pro rata
  cancellation by insurer: refund pro rata
  adjustment: reprice, charge pro rata difference
  renewal
    invite 21 days before expiry

claims
  claim Theft
    requires crime_reference
    pays claimed amount up to limit, less excess
  claim "Accidental Damage"
    pays claimed amount up to limit, less excess

# --- Rating ------------------------------------------------------------------

scenario "One bike takes the full rate"
  given rider_age 30, postcode "CH1 1AA", theft_area low
  given bike make "Trek", model "Domane", value 2000, ebike no
  expect factor "bike 1 Value band" x 1.10
  expect factor "bike 1 Position" x 1.00
  # 80 x 1.00 x 1.10 x 1.00 x 1.00 = 88.00
  expect net 88.00

scenario "The most valuable bike is first; the rest are half rate"
  given rider_age 30, postcode "CH1 1AA", theft_area low
  given bike make "Trek", model "FX", value 900, ebike no
  given bike make "Trek", model "Domane", value 2000, ebike no
  expect factor "bike 2 Position" x 1.00
  expect factor "bike 1 Position" x 0.50
  # bike 2: 80 x 1.10 = 88.00; bike 1: 36 x 1.00 x 0.5 = 18.00
  expect net 106.00
  expect premium 118.72

scenario "An e-bike outranks a pedal bike of the same value"
  given rider_age 30, postcode "CH1 1AA", theft_area low
  given bike make "Trek", model "Domane", value 2000, ebike no
  given bike make "Cube", model "Reaction Hybrid", value 2000, ebike yes
  expect factor "bike 2 Position" x 1.00
  expect factor "bike 1 Position" x 0.50
  # bike 2: 80 x 1.10 x 1.15 = 101.20; bike 1: 80 x 1.10 x 0.5 = 44.00
  expect net 145.20

scenario "A Brompton outranks another make of the same value"
  given rider_age 30, postcode "CH1 1AA", theft_area low
  given bike make "Canyon", model "Aeroad", value 1200, ebike no
  given bike make "Brompton", model "C Line", value 1200, ebike no
  expect factor "bike 1 Make" x 1.10
  expect factor "bike 2 Make" x 0.90
  # bike 2 first at 48 x 0.90 x 1.10 = 47.52; bike 1 second at 48 x 1.10 x 1.10 x 0.5 = 29.04
  expect net 76.56

scenario "Bikes that tie on rank keep the order they were given"
  given rider_age 30, postcode "CH1 1AA", theft_area low
  given bike make "Trek", model "FX", value 1200, ebike no
  given bike make "Trek", model "Domane", value 1200, ebike no
  expect factor "bike 1 Position" x 1.00
  expect factor "bike 2 Position" x 0.50

scenario "Adding a bike mid term re-orders the fleet"
  given rider_age 30, postcode "CH1 1AA", theft_area low
  given bike make "Trek", model "FX", value 900, ebike no
  when bound on 2026-01-01
  when adjusted on 2026-07-02 adding bike make "Trek", model "Domane", value 2000, ebike no
  # premium rises from 44.80 (36 net, held to the 40 minimum, plus IPT) to 118.72 (106 net):
  # 73.92 x 183/365 = 37.06, no fee
  expect additional premium 37.06

# --- Enrichment --------------------------------------------------------------

scenario "An unrecognised postcode is referred"
  given rider_age 30, postcode "ZZ9 9ZZ"
  given bike make "Trek", model "FX", value 900, ebike no
  expect referred "Postcode not recognised"

scenario "The theft area from the postcode lookup rates the fleet"
  given rider_age 30, postcode "M1 1AA", theft_area high
  given bike make "Trek", model "Domane", value 2000, ebike no
  expect factor "Theft area" x 1.30
  # 88.00 x 1.30
  expect net 114.40

scenario "A bike the catalogue knows uses its category"
  given rider_age 30, postcode "CH1 1AA", theft_area low
  given bike make "Brompton", model "C Line", value 1200, ebike no, category folding
  expect factor "bike 1 Category" x 0.90
  # 48 x 0.90 x 1.10 x 0.90
  expect net 42.77

scenario "A bike the catalogue does not know falls back to other"
  given rider_age 30, postcode "CH1 1AA", theft_area low
  given bike make "Homebuilt", model "One-off", value 1200, ebike no
  expect factor "bike 1 Category" x 1.00

# --- Claims ------------------------------------------------------------------

scenario "A claim settles on the named bike"
  given rider_age 30, postcode "CH1 1AA", theft_area low
  given bike make "Trek", model "FX", value 900, ebike no
  given bike make "Trek", model "Domane", value 2000, ebike no
  when bound on 2026-01-01
  when claim Theft on bike 2 for 2000 on 2026-03-01 with crime_reference
  # capped at the bike value, less 10% excess (200)
  expect payout 1800
```
