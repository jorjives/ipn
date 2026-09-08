---
title: claims
parent: Language reference
nav_order: 9
---

# claims

```ipn
claims
  claim Theft
    requires police_report, crime_reference
    pays claimed amount up to limit, less excess
    decline when reported after 30 days because "Theft must be reported within 30 days"
    decline when claimed > bike_value because "Claim exceeds the insured value"
    depreciation
      bike_age < 1: x 1.00
      bike_age < 3: x 0.85
      otherwise: x 0.70
  claim Death
    asks
      cause: choice of natural, accident, suicide
    requires death_certificate
    pays sum_assured
    decline when cause is suicide and within 12 months of inception because "Suicide in the first year"
  claim "Vet Fees"
    asks
      condition: text
    co-payment 20% when pet_age >= 9
    pays claimed amount, less excess, less co-payment, up to limit
  claim Windscreen
    pays claimed amount up to limit, less excess
    does not count towards claims in term
  after 2 claims in term: renewal load x 1.25
```

- `requires` lists evidence that must accompany the claim.
- `asks` declares facts only known when the claim is made, typed like inputs: the cause of
  death, who was driving, the true value of the contents. A claim without them is declined
  as "cause is required". They may be used in this claim's `decline when`, `co-payment`,
  `settlement` and in the cover's excess table.
- `pays claimed amount` followed by clauses **in the order they apply**: `up to limit`,
  `less excess`, `less co-payment`, and `up to <amount> [when <condition>]` for a
  sub-limit. A sum insured is usually capped then the excess deducted (`up to limit, less
  excess`); a liability or aggregate limit caps what the insurer pays after the excess
  (`less excess, up to limit`). A sub-limit caps only the
  claims its condition picks out, `up to 400 when kind is valuables`, and the claim still
  erodes the aggregate it sits within.
- `pays <amount>` is a fixed benefit instead of the amount claimed: `pays sum_assured`,
  `pays 50% of sum_assured`, `pays purchase_price`. It may use asked facts and take the same
  clauses.
- `pays <amount> per month for <months> months [after <period> days|weeks|months]` is a
  benefit paid over time: `pays monthly_benefit per month for ( weeks_off_work -
  deferred_weeks ) / 4 months after deferred_weeks weeks, up to limit`. The total is the
  monthly amount times the months, then the clauses apply; it goes out as a month's
  benefit at the end of each month after the deferred period, a part month last. The
  payments are dated from the loss and carry on past the term's expiry and through a
  renewal; the claim counts and erodes the limit in the term it arose in.
- `co-payment N% [when ...]` is a share the customer bears, applied where `less co-payment`
  sits in the `pays` line.
- `depreciation` (or `settlement`, the same table under a name that suits an average clause)
  scales the amount claimed first, before any `pays` clause: `x contents_sum / true_value`.
- `counts towards claims in term when fault is yes` and `does not count towards claims in
  term`: the claim is paid but does not add to the record that drives renewal loading,
  renewal decline rules and terms imposed after claims. Glass and non-fault motor claims
  are the usual case. Every paid claim still erodes an aggregate limit.

A cover whose `limit`, `excess` or `excludes` uses item fields is resolved per item, so
claims on it name the item: `when claim Theft on bike 2 for 900 on 2026-03-01`.

A claim on a cover is declined, with the reason, when the policy is not live on the loss
date, the cover is not included for that risk or item, the cover is not in force on that
date or is within its waiting period, a required item or asked fact is missing, an
aggregate limit is used up, or a `decline when` rule fires. Otherwise the amount (claimed,
or the fixed benefit) is first scaled by the `depreciation` or `settlement` table (same
shape as a rating factor: the first matching row applies), then the `pays` clauses apply in
the order written. A percentage excess is of the amount claimed, before depreciation. Only
paid claims that count go towards `claims in term`. A claim that comes to nothing after
the excess is declined as "nothing is payable after the excess" and does not count.
`after N claims in term: renewal load x M` multiplies the renewal net when the paid claim
count reaches N; the highest matching line wins.

A paid claim can also change the terms of the policy for the rest of the term. Write
`after N claims in term` (or `after 1 claim in term`) with lifecycle lines indented below;
they replace the product's own settings from the point the Nth claim is paid, and anything
not restated carries over. Either form takes `unless <condition>`, so a protected no
claims discount is `after 1 claim in term: renewal load x 1.30 unless "Protected NCD"
selected`. The `lifecycle` block must come first in the file:

```ipn
claims
  after 1 claim in term
    cancellation by customer: no refund
    adjustment: not allowed
```
