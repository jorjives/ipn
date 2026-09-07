---
title: cover
parent: Language reference
nav_order: 6
---

# cover

One block per section of cover.

```idl
cover Theft
  limit bike_value
  excess 10% of claim, minimum 50
  excludes when security is bronze and bike_value > 2000 because "Gold or silver rated lock required"

cover Racing optional
  class 3
  limit 5000
  excess 250
  available when racing is yes
```

- `optional` covers are only included when the customer selects them.
- `class 3` names the class the cover reports under (a regulator's cover class, say). It is
  a word the engine does not interpret, so `class 8`, `class 9a` and `class Kasko` all
  work, and several covers may share one. A product whose covers have classes attributes
  its premium to them; see [rating](rating.md#shares-by-cover).
- `available when` says when an optional cover may be offered at all.
- `excludes when` removes the cover for this risk and records the reason.
- `limit` and `excess` are amounts; `claim` inside an excess means the amount claimed.
  `, minimum 100` floors a percentage excess and `, maximum 1000` caps it:
  `excess 10% of claim, minimum 100, maximum 1000`. Commercial wordings may write
  `deductible` for `excess`; the two are the same.
- `excess 350 per term` (or `deductible 350 per term`) is an aggregate excess: the insured
  bears the first 350 across the term's claims on the cover rather than on each one. A
  claim inside it is declined as nothing payable but still uses it up; it is restored at
  renewal.
- `limit 7000 per term` is an aggregate limit: the most the insurer pays on this cover in
  the whole term. Each paid claim eats into it and it is restored at renewal. A plain
  `limit` applies to any one claim.
- `reinstatement at 100% of premium pro rata` lets an eroded aggregate be bought back to
  its full amount once a term, for that share of the earning premium (net plus taxes) for
  the days left. The scenario event is `when reinstated Cover on DATE` and the charge is
  available to `expect additional premium`.
- `limit 4000 per term per condition` keeps one such limit for each value of a fact the
  claim asks for (`condition` here), and `limit 1500 per term per traveller` one for each
  item, which makes the cover per item so claims say `on traveller 2`. A claim erodes only
  the limit it belongs to.
- An excess may be a table instead of one amount, in the shape of a rating factor without
  the `x`, ending with an `otherwise` row so every claim has an excess. Its rows may use
  facts the claim asks for (see [claims](claims.md)), so the excess can depend on who was driving or
  what caused the loss:

  ```
  excess
    driver_age < 25: 550 + voluntary_excess
    otherwise: 250 + voluntary_excess
  ```
- `in force from departure_date` and `in force until departure_date` make a section of
  cover start or stop on a date of its own rather than with the policy. A loss outside the
  window is declined as "not in force". Travel cancellation cover runs from purchase until
  departure; medical cover from departure.
- `waiting period 14 days`: losses this soon after the policy *first* started are declined.
  Renewing does not restart it.

The engine reports each cover as *included*, *excluded*, *not selected* or *not available*.
