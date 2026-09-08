---
title: Level Term Life
parent: Examples
nav_order: 13
---

# Level Term Life

Level Term Life: a fixed benefit rather than an indemnity. The customer chooses how many years the cover runs, the premium is guaranteed for that term (no adjustment, no renewal), BMI is worked out from height and weight, and the cause of death matters in the first year.

{: .proof }
> 19 scenarios, all passing. Run them yourself:
> ```sh
> python3 -m ipngine check examples/life.ipn
> ```

The file: [`examples/life.ipn`](https://github.com/jorjives/ipn/blob/main/examples/life.ipn).

```ipn
# Level Term Life: a fixed benefit rather than an indemnity. The customer chooses
# how many years the cover runs, the premium is guaranteed for that term (no
# adjustment, no renewal), BMI is worked out from height and weight, and the
# cause of death matters in the first year.
# Run it with:  python3 -m ipngine check examples/life.ipn

product "Level Term Life"
  territory UK
  term term_years years

inputs
  age: integer
  sum_assured: money
  term_years: integer
  smoker: yes/no
  height_cm: number
  weight_kg: number
  bmi: calculated
    base weight_kg / ( height_cm / 100 * height_cm / 100 )
  occupation: choice of office, manual, hazardous

eligibility
  decline when age < 18 because "Applicants must be 18 or over"
  decline when age + term_years > 80 because "Cover must end before age 80"
  decline when term_years < 5 because "The minimum term is 5 years"
  decline when bmi >= 45 because "BMI is outside the range we can insure"
  refer when bmi >= 35 because "Medical underwriting required"
  refer when sum_assured > 1000000 because "Sums over 1,000,000 need an underwriter"

cover Death
  limit sum_assured

cover "Terminal Illness"
  limit sum_assured

cover "Critical Illness" optional
  limit 50% of sum_assured

rating
  # An annual premium: a rate per 1,000 of sum assured, then the risk factors.
  base sum_assured / 1000 * 1.20
  factor "Age"
    age < 30: x 0.80
    age < 40: x 1.00
    age < 50: x 1.60
    age < 60: x 2.80
    otherwise: x 5.00
  factor "Smoker"
    smoker is yes: x 1.90
    otherwise: x 1.00
  factor "BMI"
    bmi < 18.5: x 1.20
    bmi < 25: x 1.00
    bmi < 30: x 1.10
    otherwise: x 1.40
  factor "Occupation"
    occupation is hazardous: x 1.50
    occupation is manual: x 1.15
    otherwise: x 1.00
  factor "Term"
    term_years > 20: x 1.15
    otherwise: x 1.00
  load 80% when "Critical Illness" selected
  minimum 60

lifecycle
  cooling off 30 days, full refund
  cancellation by customer: no refund
  adjustment: not allowed
  lapse when unpaid after 60 days
  renewal: none

claims
  claim Death
    asks
      cause: choice of natural, accident, suicide
    requires death_certificate
    pays sum_assured
    decline when cause is suicide and within 12 months of inception because "Suicide is not covered in the first year"
  claim "Terminal Illness"
    requires consultant_report
    pays sum_assured
  claim "Critical Illness"
    asks
      condition: choice of cancer, heart_attack, stroke, other
    requires consultant_report
    pays 50% of sum_assured
    decline when condition is other because "Not one of the listed conditions"
    decline when within 90 days of inception because "Critical illness is not covered in the first 90 days"

# --- Eligibility ---------------------------------------------------------

scenario "A healthy thirty five year old, twenty year term"
  given age 35, sum_assured 250000, term_years 20, smoker no, height_cm 180, weight_kg 78, occupation office
  expect eligible

scenario "Cover may not run past eighty"
  given age 62, sum_assured 100000, term_years 20, smoker no, height_cm 180, weight_kg 78, occupation office
  expect declined "Cover must end before age 80"

scenario "BMI is calculated and can refer or decline"
  given age 35, sum_assured 250000, term_years 20, smoker no, height_cm 170, weight_kg 105, occupation office
  # 105 / 1.7 squared = 36.3
  expect referred "Medical underwriting required"

scenario "A very high BMI is declined"
  given age 35, sum_assured 250000, term_years 20, smoker no, height_cm 160, weight_kg 120, occupation office
  expect declined "BMI is outside the range we can insure"

# --- Rating --------------------------------------------------------------

scenario "Annual premium for the healthy thirty five year old"
  given age 35, sum_assured 250000, term_years 20, smoker no, height_cm 180, weight_kg 78, occupation office
  # 250 x 1.20 = 300, all factors 1.00 (BMI 24.1)
  expect factor "BMI" x 1.00
  expect net 300.00
  expect premium 300.00

scenario "A smoker in their forties pays for both"
  given age 45, sum_assured 250000, term_years 20, smoker yes, height_cm 180, weight_kg 78, occupation office
  # 300 x 1.60 x 1.90
  expect net 912.00

scenario "A long term on a manual occupation"
  given age 28, sum_assured 150000, term_years 25, smoker no, height_cm 175, weight_kg 85, occupation manual
  # 180 x 0.80 x 1.10 (BMI 27.8) x 1.15 x 1.15
  expect factor "Term" x 1.15
  expect net 209.48

scenario "Critical illness cover loads the premium"
  given age 35, sum_assured 250000, term_years 20, smoker no, height_cm 180, weight_kg 78, occupation office
  select "Critical Illness"
  expect cover "Critical Illness" limit 125000
  expect net 540.00

scenario "A small sum assured pays the minimum"
  given age 25, sum_assured 20000, term_years 10, smoker no, height_cm 180, weight_kg 78, occupation office
  # 24 x 0.80 = 19.20, floored to 60
  expect net 60.00

# --- Lifecycle: the term is what the customer chose ----------------------

scenario "A twenty year term runs to the day"
  given age 35, sum_assured 250000, term_years 20, smoker no, height_cm 180, weight_kg 78, occupation office
  when bound on 2026-04-01
  expect expiry 2046-04-01
  expect status live on 2046-03-31
  expect status expired on 2046-04-01
  expect renewal declined "The policy is not renewable"

scenario "Premiums are guaranteed: no mid term change"
  given age 35, sum_assured 250000, term_years 20, smoker no, height_cm 180, weight_kg 78, occupation office
  when bound on 2026-04-01
  when adjusted on 2027-04-01 with sum_assured 300000
  expect refused "adjustment is not allowed"
  expect premium 300.00

scenario "Thirty days to change your mind"
  given age 35, sum_assured 250000, term_years 20, smoker no, height_cm 180, weight_kg 78, occupation office
  when bound on 2026-04-01
  when cancelled by customer on 2026-04-28
  expect refund 300.00

scenario "No refund after cooling off"
  given age 35, sum_assured 250000, term_years 20, smoker no, height_cm 180, weight_kg 78, occupation office
  when bound on 2026-04-01
  when cancelled by customer on 2026-06-01
  expect refund 0

scenario "An unpaid policy lapses after sixty days"
  given age 35, sum_assured 250000, term_years 20, smoker no, height_cm 180, weight_kg 78, occupation office
  when bound on 2026-04-01 unpaid
  expect status live on 2026-05-31
  expect status lapsed on 2026-06-01

# --- Claims: fixed benefits ----------------------------------------------

scenario "Death pays the sum assured whatever the claim says"
  given age 35, sum_assured 250000, term_years 20, smoker no, height_cm 180, weight_kg 78, occupation office
  when bound on 2026-04-01
  when claim Death on 2030-06-15 with death_certificate, cause natural
  expect payout 250000.00

scenario "Suicide in the first year is not covered; after that it is"
  given age 35, sum_assured 250000, term_years 20, smoker no, height_cm 180, weight_kg 78, occupation office
  when bound on 2026-04-01
  when claim Death on 2027-03-31 with death_certificate, cause suicide
  expect claim declined "Suicide is not covered in the first year"
  when claim Death on 2027-04-01 with death_certificate, cause suicide
  expect payout 250000.00

scenario "The cause of death must be given"
  given age 35, sum_assured 250000, term_years 20, smoker no, height_cm 180, weight_kg 78, occupation office
  when bound on 2026-04-01
  when claim Death on 2030-06-15 with death_certificate
  expect claim declined "cause is required"

scenario "Critical illness pays half the sum assured for a listed condition"
  given age 35, sum_assured 250000, term_years 20, smoker no, height_cm 180, weight_kg 78, occupation office
  select "Critical Illness"
  when bound on 2026-04-01
  when claim "Critical Illness" on 2026-06-01 with consultant_report, condition cancer
  expect claim declined "Critical illness is not covered in the first 90 days"
  when claim "Critical Illness" on 2031-06-01 with consultant_report, condition other
  expect claim declined "Not one of the listed conditions"
  when claim "Critical Illness" on 2031-06-01 with consultant_report, condition heart_attack
  expect payout 125000.00

scenario "Nothing is paid once the term has ended"
  given age 35, sum_assured 250000, term_years 20, smoker no, height_cm 180, weight_kg 78, occupation office
  when bound on 2026-04-01
  when claim Death on 2046-04-02 with death_certificate, cause natural
  expect claim declined "policy was expired on 2046-04-02"
```
