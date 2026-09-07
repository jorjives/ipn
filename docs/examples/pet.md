---
title: Lifetime Pet Cover
parent: Examples
nav_order: 10
---

# Lifetime Pet Cover

Lifetime Pet Cover: an annual vet fee limit that every paid claim eats into and that comes back at renewal, a waiting period before illness is covered, and a co-payment once the pet is older. The pet's age moves on each year, so the co-payment arrives by itself.

{: .proof }
> 18 scenarios, all passing. Run them yourself:
> ```sh
> python3 -m ideclare check examples/pet.idl
> ```

The file: [`examples/pet.idl`](https://github.com/jorjives/open-idl/blob/main/examples/pet.idl).

```idl
# Lifetime Pet Cover: an annual vet fee limit that every paid claim eats into and
# that comes back at renewal, a waiting period before illness is covered, and a
# co-payment once the pet is older. The pet's age moves on each year, so the
# co-payment arrives by itself.
# Run it with:  python3 -m ideclare check examples/pet.idl

product "Lifetime Pet Cover"
  territory UK
  term 12 months

inputs
  species: choice of dog, cat
  breed: text
  pet_age: integer
  purchase_price: money
  cover_level: choice of bronze, silver, gold
  # The annual vet fee limit follows the level chosen.
  vet_limit: calculated
    base 4000
    add 3000 when cover_level is silver
    add 8000 when cover_level is gold

enrichment "Breed catalogue" from species, breed
  provides
    breed_risk: choice of low, medium, high
  when unavailable: refer because "Breed not recognised"
  held for the term

eligibility
  decline when pet_age > 10 because "Pets must be under 11 when cover starts"
  decline when purchase_price > 5000 because "Pets worth over 5,000 need a specialist policy"

cover "Vet Fees"
  # The annual limit is per condition: a dog with a bad knee and an ear infection has a full limit for each
  limit vet_limit per term per condition
  excess 99
  waiting period 14 days

cover "Third Party Liability"
  limit 2000000
  excess 250
  excludes when species is cat because "Liability cover is for dogs only"

cover "Death from Illness"
  limit purchase_price
  excludes when pet_age >= 9 because "Death from illness is not covered from age 9"

rating
  factor "Species"
    species is dog: + 180
    otherwise: + 90
  factor "Age"
    pet_age < 1: x 1.00
    pet_age < 5: x 1.10
    pet_age < 9: x 1.50
    otherwise: x 2.20
  factor "Breed"
    breed_risk is high: x 1.40
    breed_risk is medium: x 1.15
    otherwise: x 1.00
  factor "Cover level"
    cover_level is gold: x 1.60
    cover_level is silver: x 1.25
    otherwise: x 1.00
  tax IPT 12%

lifecycle
  cooling off 14 days, full refund
  cancellation by customer: refund pro rata
  cancellation by insurer: refund pro rata
  adjustment: reprice, charge pro rata difference
  renewal
    invite 21 days before expiry
    increase capped at 40%
    index pet_age by 1

claims
  claim "Vet Fees"
    asks
      condition: text
    co-payment 20% when pet_age >= 9
    pays claimed amount, less excess, less co-payment, up to limit
  claim "Third Party Liability"
    pays claimed amount, less excess, up to limit
  claim "Death from Illness"
    requires vet_certificate
    pays purchase_price
  after 3 claims in term: renewal load x 1.15

# --- Eligibility and enrichment -------------------------------------------

scenario "A young labrador on silver cover"
  given species dog, breed "Labrador", pet_age 2, purchase_price 900, cover_level silver, breed_risk medium
  expect eligible
  expect cover "Vet Fees" limit 7000
  expect cover "Third Party Liability" included
  expect cover "Death from Illness" included

scenario "An unknown breed is referred"
  given species dog, breed "Mystery hound", pet_age 2, purchase_price 900, cover_level silver
  expect referred "Breed not recognised"

scenario "Too old to start cover"
  given species dog, breed "Labrador", pet_age 11, purchase_price 900, cover_level silver, breed_risk medium
  expect declined "Pets must be under 11 when cover starts"

scenario "Cats have no liability cover"
  given species cat, breed "Moggy", pet_age 3, purchase_price 100, cover_level bronze, breed_risk low
  expect cover "Third Party Liability" excluded "Liability cover is for dogs only"
  expect cover "Vet Fees" limit 4000

# --- Rating --------------------------------------------------------------

scenario "Rating a young labrador"
  given species dog, breed "Labrador", pet_age 2, purchase_price 900, cover_level silver, breed_risk medium
  # 180 x 1.10 x 1.15 x 1.25 = 284.63
  expect factor "Species" + 180
  expect net 284.63
  expect tax IPT 34.16
  expect premium 318.79

scenario "Rating an older cat on bronze"
  given species cat, breed "Moggy", pet_age 9, purchase_price 100, cover_level bronze, breed_risk low
  # 90 x 2.20
  expect net 198.00

scenario "Gold cover on a high risk breed"
  given species dog, breed "French Bulldog", pet_age 1, purchase_price 2500, cover_level gold, breed_risk high
  # 180 x 1.10 x 1.40 x 1.60
  expect net 443.52

# --- The annual limit ----------------------------------------------------

scenario "Every paid claim eats into the annual limit for its condition"
  given species dog, breed "Labrador", pet_age 2, purchase_price 900, cover_level bronze, breed_risk medium
  when bound on 2026-01-01
  expect cover "Vet Fees" remaining 4000 for condition "cruciate ligament"
  when claim "Vet Fees" for 2500 on 2026-03-01 with condition "cruciate ligament"
  expect payout 2401.00
  expect cover "Vet Fees" remaining 1599 for condition "cruciate ligament"
  when claim "Vet Fees" for 3000 on 2026-06-01 with condition "cruciate ligament"
  # 2901 after the excess, but only 1599 is left this year for the knee
  expect payout 1599.00
  expect cover "Vet Fees" remaining 0 for condition "cruciate ligament"
  when claim "Vet Fees" for 400 on 2026-08-01 with condition "cruciate ligament"
  expect claim declined "Vet Fees limit for the term is used up for condition cruciate ligament"
  # a different condition has its own untouched limit
  expect cover "Vet Fees" remaining 4000 for condition "ear infection"
  when claim "Vet Fees" for 400 on 2026-09-01 with condition "ear infection"
  expect payout 301.00
  expect claims in term 3

scenario "The limit is restored at renewal"
  given species dog, breed "Labrador", pet_age 2, purchase_price 900, cover_level bronze, breed_risk medium
  when bound on 2026-01-01
  when claim "Vet Fees" for 5000 on 2026-03-01 with condition "cruciate ligament"
  expect payout 4000.00
  when renewed on 2027-01-01
  expect cover "Vet Fees" remaining 4000 for condition "cruciate ligament"
  when claim "Vet Fees" for 500 on 2027-02-01 with condition "ear infection"
  expect payout 401.00

# --- Waiting period and co-payment ---------------------------------------

scenario "Illness in the first fourteen days is not covered"
  given species dog, breed "Labrador", pet_age 2, purchase_price 900, cover_level bronze, breed_risk medium
  when bound on 2026-01-01
  when claim "Vet Fees" for 300 on 2026-01-10 with condition "vomiting"
  expect claim declined "Vet Fees is within the 14 day waiting period"
  when claim "Vet Fees" for 300 on 2026-01-15 with condition "vomiting"
  expect payout 201.00

scenario "The waiting period does not start again at renewal"
  given species dog, breed "Labrador", pet_age 2, purchase_price 900, cover_level bronze, breed_risk medium
  when bound on 2026-01-01
  when renewed on 2027-01-01
  when claim "Vet Fees" for 300 on 2027-01-05 with condition "vomiting"
  expect payout 201.00

scenario "The co-payment arrives when the pet turns nine"
  given species dog, breed "Labrador", pet_age 8, purchase_price 900, cover_level bronze, breed_risk medium
  when bound on 2026-01-01
  when claim "Vet Fees" for 1099 on 2026-06-01 with condition "arthritis"
  expect payout 1000.00
  when renewed on 2027-01-01
  when claim "Vet Fees" for 1099 on 2027-06-01 with condition "arthritis"
  # 1000 after the excess, less 20%
  expect payout 800.00

scenario "A claim must name the condition"
  given species dog, breed "Labrador", pet_age 2, purchase_price 900, cover_level bronze, breed_risk medium
  when bound on 2026-01-01
  when claim "Vet Fees" for 300 on 2026-03-01
  expect claim declined "condition is required"

# --- Other sections ------------------------------------------------------

scenario "Death from illness pays the purchase price, not the bill"
  given species dog, breed "Labrador", pet_age 2, purchase_price 900, cover_level bronze, breed_risk medium
  when bound on 2026-01-01
  when claim "Death from Illness" on 2026-05-01 with vet_certificate
  expect payout 900.00

scenario "Death from illness stops at nine"
  given species dog, breed "Labrador", pet_age 8, purchase_price 900, cover_level bronze, breed_risk medium
  when bound on 2026-01-01
  expect cover "Death from Illness" included
  when renewed on 2027-01-01
  expect cover "Death from Illness" excluded "Death from illness is not covered from age 9"

scenario "Liability claims take the higher excess"
  given species dog, breed "Labrador", pet_age 2, purchase_price 900, cover_level bronze, breed_risk medium
  when bound on 2026-01-01
  when claim "Third Party Liability" for 12000 on 2026-05-01
  expect payout 11750.00

# --- Renewal -------------------------------------------------------------

scenario "Renewal moves the age band on, within the cap"
  given species dog, breed "Labrador", pet_age 4, purchase_price 900, cover_level bronze, breed_risk medium
  when bound on 2026-01-01
  # 180 x 1.10 x 1.15 = 227.70, IPT 27.32
  expect premium 255.02
  # at 5 the age factor is 1.50: 310.50 + 37.26 = 347.76, a 36% rise, inside the 40% cap
  expect renewal premium 347.76

scenario "Three claims in a year load the renewal"
  given species dog, breed "Labrador", pet_age 2, purchase_price 900, cover_level bronze, breed_risk medium
  when bound on 2026-01-01
  when claim "Vet Fees" for 300 on 2026-03-01 with condition "vomiting"
  when claim "Vet Fees" for 300 on 2026-05-01 with condition "limp"
  when claim "Vet Fees" for 300 on 2026-07-01 with condition "ear infection"
  expect claims in term 3
  # age 3 keeps the 1.10 factor; the net is loaded, 227.70 x 1.15 = 261.86, then IPT 31.42
  expect renewal premium 293.28
```
