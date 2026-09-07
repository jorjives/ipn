---
title: Professional Indemnity
parent: Examples
nav_order: 15
---

# Professional Indemnity

Professional Indemnity: a commercial line, rated on turnover, written on a claims-made basis. The policy that responds is the one in force when the claim is made against the insured, provided the work was done after the retroactive date, and the limit of indemnity is in the aggregate, costs inclusive.

{: .proof }
> 19 scenarios, all passing. Run them yourself:
> ```sh
> python3 -m ideclare check examples/pi.idl
> ```

The file: [`examples/pi.idl`](https://github.com/jorjives/open-idl/blob/main/examples/pi.idl).

```idl
# Professional Indemnity: a commercial line, rated on turnover, written on a
# claims-made basis. The policy that responds is the one in force when the claim
# is made against the insured, provided the work was done after the retroactive
# date, and the limit of indemnity is in the aggregate, costs inclusive.
# Run it with:  python3 -m ideclare check examples/pi.idl

product "Professional Indemnity"
  territory UK
  term 12 months

inputs
  profession: choice of accountant, architect, consultant, it_contractor, solicitor
  turnover: money
  years_trading: integer
  limit_of_indemnity: money
  retroactive_date: date
  previous_claims: integer
  overseas_work: yes/no

eligibility
  decline when profession is solicitor because "Solicitors are written on the SRA minimum terms scheme"
  decline when previous_claims > 2 because "Claims history is outside appetite"
  decline when limit_of_indemnity > 5000000 because "Limits over 5,000,000 need a bespoke policy"
  refer when turnover > 2000000 because "Turnover over 2,000,000 needs an underwriter"
  refer when overseas_work is yes because "Overseas work needs an underwriter"

# Mid-term cancellation returns a short-rate share of the premium rather than a
# pro rata one: the insurer keeps more in the early months, when most of the
# exposure of a claims-made year has already been carried.
table "Short rate" keyed on months in force
  months_in_force, refunded
  0-2, 75%
  3-5, 50%
  6-8, 25%
  9+, 0%

cover "Professional Indemnity"
  limit limit_of_indemnity per term
  # Once the aggregate is eroded the insured may buy it back once, for the rest of the year
  reinstatement at 100% of premium pro rata
  excess 1000

cover "Court Attendance" 
  limit 5000 per term

rating
  # A rate on fee income, adjusted for the profession, the limit bought and experience.
  base 1.2% of turnover
  factor "Profession"
    profession is it_contractor: x 0.80
    profession is consultant: x 1.00
    profession is accountant: x 1.30
    otherwise: x 1.60
  factor "Limit of indemnity"
    limit_of_indemnity <= 250000: x 0.80
    limit_of_indemnity <= 1000000: x 1.00
    limit_of_indemnity <= 2000000: x 1.30
    otherwise: x 1.70
  factor "Experience"
    years_trading < 2: x 1.25
    years_trading < 5: x 1.00
    otherwise: x 0.90
  factor "Claims history"
    previous_claims is 0: x 1.00
    previous_claims is 1: x 1.30
    otherwise: x 1.75
  minimum 250
  tax IPT 12%
  fee "Policy fee" 35
  # The broker's share of the net, reported for the bordereau; the customer's premium is unchanged
  commission "Broker" 17.5%

lifecycle
  cooling off 14 days, full refund
  cancellation by customer: refund refunded from "Short rate", fee 50
  cancellation by insurer: refund pro rata
  adjustment: reprice, charge pro rata difference
  renewal
    invite 30 days before expiry
    increase capped at 25%
    decline when claims in term >= 2 because "Two or more claims in the period"

claims
  claim "Professional Indemnity"
    asks
      work_date: date
    requires written_demand
    pays claimed amount, less excess, up to limit
    decline when work_date < retroactive_date because "The work predates the retroactive date"
    decline when reported after 30 days because "Claims must be notified within 30 days of being made"
  claim "Court Attendance"
    pays claimed amount up to limit
  after 1 claim in term: renewal load x 1.30

# --- Eligibility ---------------------------------------------------------

scenario "An established consultancy"
  given profession consultant, turnover 400000, years_trading 8, limit_of_indemnity 1000000, retroactive_date 2018-04-01, previous_claims 0, overseas_work no
  expect eligible

scenario "Solicitors are declined"
  given profession solicitor, turnover 400000, years_trading 8, limit_of_indemnity 1000000, retroactive_date 2018-04-01, previous_claims 0, overseas_work no
  expect declined "Solicitors are written on the SRA minimum terms scheme"

scenario "Large turnover and overseas work both refer"
  given profession consultant, turnover 3000000, years_trading 8, limit_of_indemnity 1000000, retroactive_date 2018-04-01, previous_claims 0, overseas_work yes
  expect referred "Turnover over 2,000,000 needs an underwriter"
  expect referred "Overseas work needs an underwriter"

# --- Rating on turnover ---------------------------------------------------

scenario "Rate on fee income for the consultancy"
  given profession consultant, turnover 400000, years_trading 8, limit_of_indemnity 1000000, retroactive_date 2018-04-01, previous_claims 0, overseas_work no
  # 1.2% of 400,000 = 4,800, x 0.90 experience
  expect net 4320.00
  expect tax IPT 518.40
  expect premium 4873.40
  expect commission "Broker" 756.00

scenario "A new IT contractor buying a low limit"
  given profession it_contractor, turnover 60000, years_trading 1, limit_of_indemnity 250000, retroactive_date 2026-01-01, previous_claims 0, overseas_work no
  # 720 x 0.80 x 0.80 x 1.25 = 576
  expect net 576.00

scenario "A tiny turnover pays the minimum"
  given profession it_contractor, turnover 15000, years_trading 3, limit_of_indemnity 250000, retroactive_date 2026-01-01, previous_claims 0, overseas_work no
  # 180 x 0.80 x 0.80 = 115.20, floored to 250
  expect net 250.00

scenario "Architects buying a high limit with a claim behind them"
  given profession architect, turnover 900000, years_trading 12, limit_of_indemnity 3000000, retroactive_date 2010-01-01, previous_claims 1, overseas_work no
  # 10,800 x 1.60 x 1.70 x 0.90 x 1.30
  expect net 34369.92

# --- Short-rate cancellation ---------------------------------------------

scenario "Cancelling after four months returns half, less the fee"
  given profession consultant, turnover 400000, years_trading 8, limit_of_indemnity 1000000, retroactive_date 2018-04-01, previous_claims 0, overseas_work no
  when bound on 2026-01-01
  when cancelled by customer on 2026-05-15
  # four full months in force: 50% of the 4,838.40 earning premium (net plus IPT; the policy fee is kept), less the 50 fee
  expect refund 2369.20

scenario "Cancelling in the last quarter returns nothing"
  given profession consultant, turnover 400000, years_trading 8, limit_of_indemnity 1000000, retroactive_date 2018-04-01, previous_claims 0, overseas_work no
  when bound on 2026-01-01
  when cancelled by customer on 2026-10-20
  expect refund 0.00

# --- Claims made, retroactive date --------------------------------------

scenario "A claim made in the period for work after the retroactive date"
  given profession consultant, turnover 400000, years_trading 8, limit_of_indemnity 1000000, retroactive_date 2018-04-01, previous_claims 0, overseas_work no
  when bound on 2026-01-01
  when claim "Professional Indemnity" for 80000 on 2026-06-15 with written_demand, work_date 2023-09-01
  expect payout 79000.00

scenario "An eroded limit may be reinstated once, for a pro rata additional premium"
  given profession consultant, turnover 400000, years_trading 8, limit_of_indemnity 250000, retroactive_date 2018-04-01, previous_claims 0, overseas_work no
  when bound on 2026-01-01
  when claim "Professional Indemnity" for 200000 on 2026-03-01 with written_demand, work_date 2023-09-01
  expect payout 199000.00
  expect cover "Professional Indemnity" remaining 51000
  when reinstated "Professional Indemnity" on 2026-04-11
  # 100% of the earning premium (3,456 net plus 414.72 IPT) for the 265 days left
  expect additional premium 2810.25
  expect cover "Professional Indemnity" remaining 250000
  when reinstated "Professional Indemnity" on 2026-06-01
  expect refused "Professional Indemnity has already been reinstated this term"

scenario "Work done before the retroactive date is not covered"
  given profession consultant, turnover 400000, years_trading 8, limit_of_indemnity 1000000, retroactive_date 2018-04-01, previous_claims 0, overseas_work no
  when bound on 2026-01-01
  when claim "Professional Indemnity" for 80000 on 2026-06-15 with written_demand, work_date 2017-11-20
  expect claim declined "The work predates the retroactive date"

scenario "A claim made after expiry falls to the next policy, not this one"
  given profession consultant, turnover 400000, years_trading 8, limit_of_indemnity 1000000, retroactive_date 2018-04-01, previous_claims 0, overseas_work no
  when bound on 2026-01-01
  when claim "Professional Indemnity" for 80000 on 2027-02-01 with written_demand, work_date 2026-05-01
  expect claim declined "policy was expired on 2027-02-01"

scenario "Late notification is declined"
  given profession consultant, turnover 400000, years_trading 8, limit_of_indemnity 1000000, retroactive_date 2018-04-01, previous_claims 0, overseas_work no
  when bound on 2026-01-01
  when claim "Professional Indemnity" for 80000 on 2026-06-15 reported 2026-08-30 with written_demand, work_date 2023-09-01
  expect claim declined "Claims must be notified within 30 days of being made"

scenario "The written demand is required"
  given profession consultant, turnover 400000, years_trading 8, limit_of_indemnity 1000000, retroactive_date 2018-04-01, previous_claims 0, overseas_work no
  when bound on 2026-01-01
  when claim "Professional Indemnity" for 80000 on 2026-06-15 with work_date 2023-09-01
  expect claim declined "written_demand is required"

# --- The limit is in the aggregate ---------------------------------------

scenario "Every payment erodes the limit of indemnity for the period"
  given profession consultant, turnover 400000, years_trading 8, limit_of_indemnity 1000000, retroactive_date 2018-04-01, previous_claims 0, overseas_work no
  when bound on 2026-01-01
  when claim "Professional Indemnity" for 700000 on 2026-03-01 with written_demand, work_date 2024-01-01
  expect payout 699000.00
  expect cover "Professional Indemnity" remaining 301000
  when claim "Professional Indemnity" for 500000 on 2026-09-01 with written_demand, work_date 2024-06-01
  # 499,000 after the excess, but only 301,000 is left in the aggregate
  expect payout 301000.00
  expect cover "Professional Indemnity" remaining 0
  when claim "Professional Indemnity" for 20000 on 2026-11-01 with written_demand, work_date 2024-06-01
  expect claim declined "Professional Indemnity limit for the term is used up"

scenario "The limit is reinstated for the next period"
  given profession consultant, turnover 400000, years_trading 8, limit_of_indemnity 1000000, retroactive_date 2018-04-01, previous_claims 0, overseas_work no
  when bound on 2026-01-01
  when claim "Professional Indemnity" for 1200000 on 2026-03-01 with written_demand, work_date 2024-01-01
  expect payout 1000000.00
  # one claim loads the renewal 30%, held to the 25% cap: 4873.40 x 1.25
  expect renewal premium 6091.75
  when renewed on 2027-01-01
  expect cover "Professional Indemnity" remaining 1000000

scenario "Two claims in the period and the renewal is declined"
  given profession consultant, turnover 400000, years_trading 8, limit_of_indemnity 1000000, retroactive_date 2018-04-01, previous_claims 0, overseas_work no
  when bound on 2026-01-01
  when claim "Professional Indemnity" for 50000 on 2026-03-01 with written_demand, work_date 2024-01-01
  when claim "Professional Indemnity" for 50000 on 2026-07-01 with written_demand, work_date 2024-06-01
  expect renewal declined "Two or more claims in the period"

# --- Mid term turnover change ---------------------------------------------

scenario "Declaring higher turnover mid term charges the pro rata difference"
  given profession consultant, turnover 400000, years_trading 8, limit_of_indemnity 1000000, retroactive_date 2018-04-01, previous_claims 0, overseas_work no
  when bound on 2026-01-01
  when adjusted on 2026-07-02 with turnover 600000
  # earning goes from 4838.40 to 7257.60: 2419.20 x 183/365
  expect additional premium 1212.91
```
