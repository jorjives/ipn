---
title: Single Trip Travel
parent: Examples
nav_order: 7
---

# Single Trip Travel

Single Trip Travel: people rather than things. The term runs until the return date, cancellation cover starts the day the policy is bought and stops at departure, and the other sections only start once the trip does.

{: .proof }
> 19 scenarios, all passing. Run them yourself:
> ```sh
> python3 -m ideclare check examples/travel.idl
> ```

The file: [`examples/travel.idl`](https://github.com/jorjives/open-idl/blob/main/examples/travel.idl).

```idl
# Single Trip Travel: people rather than things. The term runs until the return
# date, cancellation cover starts the day the policy is bought and stops at
# departure, and the other sections only start once the trip does.
# Run it with:  python3 -m ideclare check examples/travel.idl

product "Single Trip Travel"
  territory UK
  term until return_date

inputs
  departure_date: date
  return_date: date
  destination: choice of uk, europe, worldwide
  trip_days: calculated
    base return_date - departure_date
  travellers: collection of traveller, 1 to 8
    age: integer
    medical_conditions: yes/no

eligibility
  decline when trip_days < 1 because "Return must be after departure"
  decline when trip_days > 90 because "Trips over 90 days need long stay cover"
  decline when any traveller where age > 85 because "Travellers must be 85 or under"
  refer when any traveller where medical_conditions is yes because "Medical screening required"

cover Cancellation
  limit 3000
  excess 75
  in force until departure_date

cover "Medical Expenses"
  limit 5000000
  excess 75
  in force from departure_date
  excludes when destination is uk because "Medical expenses are not covered in the UK"

cover Baggage
  # Each traveller has their own baggage limit for the trip
  limit 1500 per term per traveller
  excess 75
  in force from departure_date

cover "Winter Sports" optional
  limit 500
  excess 75
  in force from departure_date

rating
  for each traveller
    base 12
    factor "Age"
      age < 18: x 0.50
      age < 65: x 1.00
      age < 75: x 1.80
      otherwise: x 3.00
    factor "Medical"
      medical_conditions is yes: x 1.50
      otherwise: x 1.00
  factor "Destination"
    destination is uk: x 0.60
    destination is europe: x 1.00
    otherwise: x 2.20
  factor "Duration"
    trip_days <= 7: x 1.00
    trip_days <= 14: x 1.40
    trip_days <= 31: x 2.20
    otherwise: x 3.50
  add "Winter sports" 25 * count of travellers when "Winter Sports" selected
  minimum 15
  tax IPT 20%

lifecycle
  cooling off 14 days, full refund
  cancellation by customer: no refund
  cancellation by insurer: refund pro rata
  adjustment: not allowed
  renewal: none

claims
  claim Cancellation
    requires cancellation_invoice
    pays claimed amount up to limit, less excess
  claim "Medical Expenses"
    pays claimed amount up to limit, less excess
  claim Baggage
    asks
      kind: choice of valuables, cash, other
    requires property_irregularity_report
    # Sub-limits for valuables and cash sit inside the traveller's baggage limit
    pays claimed amount up to 400 when kind is valuables, up to 250 when kind is cash, up to limit, less excess
    decline when reported after 31 days because "Baggage losses must be reported within 31 days"
  claim "Winter Sports"
    pays claimed amount up to limit, less excess

# --- Eligibility ---------------------------------------------------------

scenario "A week in Europe for two adults"
  given departure_date 2026-07-10, return_date 2026-07-17, destination europe
  given traveller age 40, medical_conditions no
  given traveller age 38, medical_conditions no
  expect eligible

scenario "Return before departure is declined"
  given departure_date 2026-07-10, return_date 2026-07-09, destination europe
  given traveller age 40, medical_conditions no
  expect declined "Return must be after departure"

scenario "Long stays are declined"
  given departure_date 2026-01-01, return_date 2026-04-15, destination worldwide
  given traveller age 40, medical_conditions no
  expect declined "Trips over 90 days need long stay cover"

scenario "A medical condition is referred for screening"
  given departure_date 2026-07-10, return_date 2026-07-17, destination europe
  given traveller age 70, medical_conditions yes
  expect referred "Medical screening required"

# --- Rating --------------------------------------------------------------

scenario "Two adults, a week in Europe"
  given departure_date 2026-07-10, return_date 2026-07-17, destination europe
  given traveller age 40, medical_conditions no
  given traveller age 38, medical_conditions no
  # 12 + 12 = 24, x 1.00 destination, x 1.00 duration (7 days)
  expect factor "Duration" x 1.00
  expect net 24.00
  expect tax IPT 4.80
  expect premium 28.80

scenario "A family for a fortnight worldwide"
  given departure_date 2026-08-01, return_date 2026-08-15, destination worldwide
  given traveller age 42, medical_conditions no
  given traveller age 41, medical_conditions no
  given traveller age 12, medical_conditions no
  given traveller age 9, medical_conditions no
  # 12 + 12 + 6 + 6 = 36, x 2.20 worldwide, x 1.40 for 14 days = 110.88
  expect factor "traveller 3 Age" x 0.50
  expect factor "Destination" x 2.20
  expect factor "Duration" x 1.40
  expect net 110.88
  expect premium 133.06

scenario "An older traveller with a screened condition"
  given departure_date 2026-09-01, return_date 2026-09-22, destination europe
  given traveller age 72, medical_conditions yes
  # 12 x 1.80 x 1.50 = 32.40, x 2.20 for 21 days = 71.28
  expect net 71.28

scenario "Winter sports adds a flat amount per traveller"
  given departure_date 2026-12-20, return_date 2026-12-27, destination europe
  given traveller age 30, medical_conditions no
  given traveller age 30, medical_conditions no
  select "Winter Sports"
  expect cover "Winter Sports" included
  # 24 + 50
  expect net 74.00

scenario "A short UK break hits the minimum premium"
  given departure_date 2026-05-01, return_date 2026-05-03, destination uk
  given traveller age 30, medical_conditions no
  # 12 x 0.60 = 7.20, floored to 15
  expect net 15.00
  expect cover "Medical Expenses" excluded "Medical expenses are not covered in the UK"

# --- Lifecycle -----------------------------------------------------------

scenario "The policy runs from purchase to the return date"
  given departure_date 2026-07-10, return_date 2026-07-17, destination europe
  given traveller age 40, medical_conditions no
  when bound on 2026-03-01
  expect status live on 2026-03-01
  expect expiry 2026-07-17
  expect status live on 2026-07-16
  expect status expired on 2026-07-17
  expect renewal declined "The policy is not renewable"

scenario "Cancelling within cooling off refunds in full"
  given departure_date 2026-07-10, return_date 2026-07-17, destination europe
  given traveller age 40, medical_conditions no
  when bound on 2026-03-01
  when cancelled by customer on 2026-03-10
  # one traveller: 12 floored to the 15 minimum, plus 20% IPT
  expect refund 18.00

scenario "No refund once cooling off has passed"
  given departure_date 2026-07-10, return_date 2026-07-17, destination europe
  given traveller age 40, medical_conditions no
  when bound on 2026-03-01
  when cancelled by customer on 2026-04-01
  expect refund 0

# --- Claims: each section has its own dates ------------------------------

scenario "Cancellation cover responds before departure"
  given departure_date 2026-07-10, return_date 2026-07-17, destination europe
  given traveller age 40, medical_conditions no
  when bound on 2026-03-01
  when claim Cancellation for 1200 on 2026-06-20 with cancellation_invoice
  expect payout 1125.00

scenario "Cancellation cover has stopped once the trip has begun"
  given departure_date 2026-07-10, return_date 2026-07-17, destination europe
  given traveller age 40, medical_conditions no
  when bound on 2026-03-01
  when claim Cancellation for 1200 on 2026-07-12 with cancellation_invoice
  expect claim declined "Cancellation is not in force on 2026-07-12"

scenario "Medical expenses only start at departure"
  given departure_date 2026-07-10, return_date 2026-07-17, destination europe
  given traveller age 40, medical_conditions no
  when bound on 2026-03-01
  when claim "Medical Expenses" for 800 on 2026-07-01
  expect claim declined "Medical Expenses is not in force on 2026-07-01"
  when claim "Medical Expenses" for 800 on 2026-07-12
  expect payout 725.00

scenario "Nothing is covered after the return date"
  given departure_date 2026-07-10, return_date 2026-07-17, destination europe
  given traveller age 40, medical_conditions no
  when bound on 2026-03-01
  when claim Baggage on traveller 1 for 400 on 2026-07-18 with property_irregularity_report, kind other
  expect claim declined "policy was expired on 2026-07-18"

scenario "Baggage claims need the airline's report and prompt notice"
  given departure_date 2026-07-10, return_date 2026-07-17, destination europe
  given traveller age 40, medical_conditions no
  when bound on 2026-03-01
  when claim Baggage on traveller 1 for 400 on 2026-07-12 with kind other
  expect claim declined "property_irregularity_report is required"
  when claim Baggage on traveller 1 for 400 on 2026-07-12 reported 2026-09-01 with property_irregularity_report, kind other
  expect claim declined "Baggage losses must be reported within 31 days"
  when claim Baggage on traveller 1 for 2000 on 2026-07-12 with property_irregularity_report, kind other
  expect payout 1425.00

scenario "Each traveller has their own baggage limit"
  given departure_date 2026-07-10, return_date 2026-07-17, destination europe
  given traveller age 40, medical_conditions no
  given traveller age 38, medical_conditions no
  when bound on 2026-03-01
  when claim Baggage on traveller 1 for 2000 on 2026-07-12 with property_irregularity_report, kind other
  expect payout 1425.00
  expect cover Baggage on traveller 1 remaining 75
  expect cover Baggage on traveller 2 remaining 1500
  when claim Baggage on traveller 2 for 600 on 2026-07-14 with property_irregularity_report, kind other
  expect payout 525.00
  when claim Baggage on traveller 1 for 300 on 2026-07-15 with property_irregularity_report, kind other
  # 75 is left for traveller 1, and the 75 excess takes all of it
  expect claim declined "nothing is payable after the excess"

scenario "Valuables and cash have sub-limits inside the baggage limit"
  given departure_date 2026-07-10, return_date 2026-07-17, destination europe
  given traveller age 40, medical_conditions no
  when bound on 2026-03-01
  when claim Baggage on traveller 1 for 900 on 2026-07-12 with property_irregularity_report, kind valuables
  # capped at 400 for valuables, less the 75 excess
  expect payout 325.00
  when claim Baggage on traveller 1 for 300 on 2026-07-13 with property_irregularity_report, kind cash
  expect payout 175.00
  # both came out of the traveller's 1,500
  expect cover Baggage on traveller 1 remaining 1000
  when claim Baggage on traveller 1 for 1200 on 2026-07-14 with property_irregularity_report, kind other
  expect payout 925.00
```
