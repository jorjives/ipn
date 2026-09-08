---
title: A second version
parent: Templates
nav_order: 6
---

# A second version

A product that changes its questions, with upgrading. The files sit together in [`templates/versioned/`](https://github.com/jorjives/open-idl/tree/main/templates/versioned); each
declares the same product name and says when it was published, and `check` finds the others by itself.

{: .proof }
> 4 scenarios across the versions, all passing.

## versioned-product-2026-01-01

A versioned product, first version. The `published` line says when it went on sale; the later version sits beside it in this directory, and a policy bound under this version stays on it until renewal. Copy both files, keep the product name the same in each, and put each version's own proof in its own file.

1 scenario: `python3 -m ipngine check templates/versioned/versioned-product-2026-01-01.ipn`

```ipn
# A versioned product, first version. The `published` line says when it went on sale; the
# later version sits beside it in this directory, and a policy bound under this version
# stays on it until renewal. Copy both files, keep the product name the same in each, and
# put each version's own proof in its own file.
# Run it with:  python3 -m ipngine check templates/versioned/versioned-product-2026-01-01.ipn

product "Versioned Product"
  published 2026-01-01
  territory UK
  term 12 months

inputs
  sum_insured: money
  cover_level: choice of basic, standard, full

cover Damage
  limit sum_insured
  excess 100

rating
  base 2% of sum_insured
  load 10% when cover_level is standard
  load 20% when cover_level is full
  tax IPT 12%
  round to 0.01

lifecycle
  cooling off 14 days, full refund
  cancellation by customer: refund pro rata
  adjustment: reprice, charge pro rata difference
  renewal
    invite 21 days before expiry
    increase capped at 20%

claims
  claim Damage
    pays claimed amount up to limit, less excess

scenario "Full cover carries the loading"
  given sum_insured 10000, cover_level full
  expect net 240.00
  expect premium 268.80
```

## versioned-product-2027-01-01

A versioned product, second version. The cover question changes shape: `cover_level` becomes `plan` with three tiers, and a new question arrives with a default. The `upgrading` block says how a customer's old answers become new ones at renewal; a row that says `ask` holds the renewal until the customer answers. Every scenario here that binds before this version was published is written in the first version's words.

3 scenarios: `python3 -m ipngine check templates/versioned/versioned-product-2027-01-01.ipn`

```ipn
# A versioned product, second version. The cover question changes shape: `cover_level`
# becomes `plan` with three tiers, and a new question arrives with a default. The
# `upgrading` block says how a customer's old answers become new ones at renewal; a row
# that says `ask` holds the renewal until the customer answers. Every scenario here that
# binds before this version was published is written in the first version's words.
# Run it with:  python3 -m ipngine check templates/versioned/versioned-product-2027-01-01.ipn

product "Versioned Product"
  published 2027-01-01
  territory UK
  term 12 months

inputs
  sum_insured: money
  plan: choice of bronze, silver, gold
  paperless: yes/no, default no     # new: a default means no upgrading line is needed

upgrading                           # right-hand sides read the previous version's answers
  plan
    cover_level is basic: bronze
    cover_level is full: gold
    otherwise: ask                  # a standard customer chooses silver or gold themselves

cover Damage
  limit sum_insured
  excess 100

rating
  base 2% of sum_insured
  load 10% when plan is silver
  load 25% when plan is gold
  discount 2% when paperless is yes
  tax IPT 12%
  round to 0.01

lifecycle
  cooling off 14 days, full refund
  cancellation by customer: refund pro rata
  adjustment: reprice, charge pro rata difference
  renewal
    invite 21 days before expiry
    increase capped at 20%

claims
  claim Damage
    pays claimed amount up to limit, less excess

scenario "A new customer answers the new questions"
  given sum_insured 10000, plan gold, paperless yes
  when bound on 2027-02-01
  expect version 2027-01-01
  # 200 x 1.25 = 250, less 2% = 245
  expect net 245.00

scenario "A customer on the first version stays there until renewal"
  given sum_insured 10000, cover_level full
  when bound on 2026-06-01
  expect version 2026-01-01
  expect premium 268.80
  expect renewal premium 280.00
  when renewed on 2027-06-01
  expect version 2027-01-01
  expect plan gold
  expect paperless no
  # 200 x 1.25 = 250, IPT 30; within the 20% cap on 268.80
  expect premium 280.00

scenario "A standard customer must choose before the renewal can be priced"
  given sum_insured 10000, cover_level standard
  when bound on 2026-06-01
  expect renewal needs plan
  when renewed on 2027-06-01
  expect refused "renewal needs plan"
  when renewed on 2027-06-01 with plan silver
  expect version 2027-01-01
  expect plan silver
  # 200 x 1.10 = 220, IPT 26.40
  expect premium 246.40
```
