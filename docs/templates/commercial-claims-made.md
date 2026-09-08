---
title: Commercial claims-made
parent: Templates
nav_order: 4
---

# Commercial claims-made

Commercial claims-made: a business rated on its turnover and profession, a limit that applies in the aggregate for the term, a retroactive date that decides which work is covered, a short-rate cancellation scale and broker commission. Professional indemnity is the usual case; directors' and officers' or cyber take the same shape. Copy this file and replace the professions, the rates and the scale.

{: .proof }
> 6 scenarios, all passing, so the template is a working product before you change a line.

Copy [`templates/commercial-claims-made.ipn`](https://github.com/jorjives/open-idl/blob/main/templates/commercial-claims-made.ipn), rename the product, and replace each
block as the comments direct. Keep `check` passing as you go.

```ipn
# Commercial claims-made: a business rated on its turnover and profession, a limit that
# applies in the aggregate for the term, a retroactive date that decides which work is
# covered, a short-rate cancellation scale and broker commission. Professional indemnity
# is the usual case; directors' and officers' or cyber take the same shape. Copy this file
# and replace the professions, the rates and the scale.
# Run it with:  python3 -m ipngine check templates/commercial-claims-made.ipn

product "Commercial Claims-Made"
  territory UK
  term 12 months

inputs
  profession: choice of consultant, architect, accountant
  turnover: money
  years_trading: integer
  limit_of_indemnity: money
  retroactive_date: date      # work before this date is not covered

table "Rates" keyed on profession   # the rate on turnover, one row per profession
  profession, rate
  consultant, 0.008
  architect, 0.015
  accountant, 0.010

table "Short rate" keyed on months in force    # what is refunded, by whole months in force
  months_in_force, refunded
  0-2, 75%
  3-5, 50%
  6-8, 25%
  9+, 0%

eligibility
  decline when years_trading < 1 because "At least one year's trading is required"
  refer when turnover > 2000000 because "Turnover over 2,000,000 needs an underwriter"

cover "Professional Indemnity"
  limit limit_of_indemnity per term     # an aggregate: every paid claim erodes it
  excess 1000

rating
  base turnover * rate from "Rates"
  factor "Limit"
    limit_of_indemnity >= 1000000: x 1.50
    limit_of_indemnity >= 500000: x 1.25
    otherwise: x 1.00
  minimum 250
  commission "Broker" 15%     # reported as a share of the net, never added to the premium
  tax IPT 12%
  round to 0.01

lifecycle
  cooling off 14 days, full refund
  cancellation by customer: refund refunded from "Short rate"
  cancellation by insurer: refund pro rata
  adjustment: reprice, charge pro rata difference
  renewal
    invite 30 days before expiry
    increase capped at 30%
    decline when claims in term >= 2 because "Two or more claims in the year"

claims
  claim "Professional Indemnity"
    asks
      work_date: date         # when the work complained of was done
    requires claim_letter
    pays claimed amount less excess, up to limit    # the limit caps what the insurer pays after the excess
    decline when work_date < retroactive_date because "Work before the retroactive date is not covered"

# --- Scenarios ---------------------------------------------------------------

scenario "A consultant is rated on turnover with the limit loading"
  given profession consultant, turnover 250000, years_trading 5, limit_of_indemnity 500000, retroactive_date 2021-01-01
  expect eligible
  # 250,000 x 0.008 = 2,000, x 1.25 for the limit
  expect net 2500.00
  expect commission "Broker" 375.00
  expect tax IPT 300.00
  expect premium 2800.00

scenario "A new business is declined"
  given profession consultant, turnover 50000, years_trading 0, limit_of_indemnity 250000, retroactive_date 2026-01-01
  expect declined "At least one year's trading is required"

scenario "Short-rate cancellation after four months returns half"
  given profession consultant, turnover 250000, years_trading 5, limit_of_indemnity 500000, retroactive_date 2021-01-01
  when bound on 2026-01-01
  when cancelled by customer on 2026-05-15
  # four whole months in force: 50% of the 2,800 earning premium
  expect refund 1400.00

scenario "A claim for work after the retroactive date is paid after the excess"
  given profession consultant, turnover 250000, years_trading 5, limit_of_indemnity 500000, retroactive_date 2021-01-01
  when bound on 2026-01-01
  when claim "Professional Indemnity" for 40000 on 2026-06-01 with claim_letter, work_date 2024-03-01
  expect payout 39000.00
  expect cover "Professional Indemnity" remaining 461000.00

scenario "Work before the retroactive date is not covered"
  given profession consultant, turnover 250000, years_trading 5, limit_of_indemnity 500000, retroactive_date 2021-01-01
  when bound on 2026-01-01
  when claim "Professional Indemnity" for 40000 on 2026-06-01 with claim_letter, work_date 2019-03-01
  expect claim declined "Work before the retroactive date is not covered"

scenario "The aggregate limit caps the term's claims"
  given profession consultant, turnover 250000, years_trading 5, limit_of_indemnity 500000, retroactive_date 2021-01-01
  when bound on 2026-01-01
  when claim "Professional Indemnity" for 450000 on 2026-03-01 with claim_letter, work_date 2024-03-01
  expect payout 449000.00
  when claim "Professional Indemnity" for 100000 on 2026-09-01 with claim_letter, work_date 2024-06-01
  # 51,000 is left of the aggregate after the first claim
  expect payout 51000.00
  expect renewal declined "Two or more claims in the year"
```
