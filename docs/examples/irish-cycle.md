---
title: Irish Cycle
parent: Examples
nav_order: 5
---

# Irish Cycle

Irish Cycle: the three Irish charges on a non-life premium. The Government levy (3%) and the Insurance Compensation Fund contribution (2%) are taxes on the premium, refunded with it; the stamp duty is a fixed EUR 1 on each policy with EUR 20 or more of annual premium, charged when the policy is issued and never refunded, so it is a fee with a threshold.

{: .proof }
> 4 scenarios, all passing. Run them yourself:
> ```sh
> python3 -m ideclare check examples/irish-cycle.idl
> ```

The file: [`examples/irish-cycle.idl`](https://github.com/jorjives/open-idl/blob/main/examples/irish-cycle.idl).

```idl
# Irish Cycle: the three Irish charges on a non-life premium. The Government levy
# (3%) and the Insurance Compensation Fund contribution (2%) are taxes on the
# premium, refunded with it; the stamp duty is a fixed EUR 1 on each policy with
# EUR 20 or more of annual premium, charged when the policy is issued and never
# refunded, so it is a fee with a threshold.
# Run it with:  python3 -m ideclare check examples/irish-cycle.idl

product "Irish Cycle"
  territory IE
  term 12 months

inputs
  bike_value: money
  rider_age: integer
  kept_indoors: yes/no

eligibility
  decline when rider_age < 18 because "Rider must be 18 or over"
  refer when bike_value > 8000 because "Underwriter review"

cover Theft
  limit bike_value
  excess 10% of claim, minimum 25
  excludes when kept_indoors is no and bike_value > 2000 because "Bikes over EUR 2,000 must be kept indoors"

cover "Accidental Damage"
  limit bike_value
  excess 50

rating
  base 1.2% of bike_value
  minimum 10
  tax "Government levy" 3%
  tax "ICF levy" 2%
  fee "Stamp duty" 1 when net >= 20

lifecycle
  cooling off 14 days, full refund
  cancellation by customer: refund pro rata
  cancellation by insurer: refund pro rata
  adjustment: reprice, charge pro rata difference

claims
  claim Theft
    requires crime_reference
    pays claimed amount up to limit, less excess
  claim "Accidental Damage"
    pays claimed amount up to limit, less excess

scenario "Under the stamp duty threshold"
  given bike_value 1000, rider_age 30, kept_indoors yes
  expect eligible
  expect net 12.00
  expect tax "Government levy" 0.36
  expect tax "ICF levy" 0.24
  expect premium 12.60
  expect currency EUR

scenario "On the threshold: the duty is charged on the rounded net"
  given bike_value 1666.50, rider_age 30, kept_indoors yes
  # 1.2% of 1,666.50 is 19.998, which the customer sees as 20.00
  expect net 20.00
  expect fee "Stamp duty" 1.00
  expect premium 22.00

scenario "Over the threshold, cancelled half way: the levies refund, the duty does not"
  given bike_value 2500, rider_age 30, kept_indoors yes
  when bound on 2026-01-01
  expect net 30.00
  expect tax "Government levy" 0.90
  expect tax "ICF levy" 0.60
  expect fee "Stamp duty" 1.00
  expect premium 32.50
  when cancelled by customer on 2026-07-02
  # 183 of 365 days unused on 31.50 of earning premium
  expect refund 15.79

scenario "Theft claim"
  given bike_value 2500, rider_age 30, kept_indoors yes
  when bound on 2026-01-01
  when claim Theft for 2500 on 2026-03-01 with crime_reference
  expect payout 2250.00
```
