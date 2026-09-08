---
title: European Gadget Cover
parent: Examples
nav_order: 4
---

# European Gadget Cover

Gadget Cover sold across continental Europe: one product, several territories. The territory is chosen at quote. Everything that differs by country (tax, the loading on the EUR base rate, the currency it is quoted in) lives in a table keyed on territory, not in copies of the product.

{: .proof }
> 7 scenarios, all passing. Run them yourself:
> ```sh
> python3 -m ipngine check examples/gadget.ipn
> ```

The file: [`examples/gadget.ipn`](https://github.com/jorjives/ipn/blob/main/examples/gadget.ipn).

```ipn
# Gadget Cover sold across continental Europe: one product, several territories.
# The territory is chosen at quote. Everything that differs by country (tax, the
# loading on the EUR base rate, the currency it is quoted in) lives in a table
# keyed on territory, not in copies of the product.
# Run it with:  python3 -m ipngine check examples/gadget.ipn

product "European Gadget Cover"
  territory DE, FR, NL, CH
  term 12 months

inputs
  device_value: money
  device_age_months: integer
  refurbished: yes/no

# One row per territory: insurance premium tax and the loading that turns the
# EUR base rate into local pricing (CHF is not a 1:1 currency).
table "Territory" keyed on territory
  territory, ipt, load
  DE, 19%, 1.00
  FR, 9%, 1.05
  NL, 21%, 0.95
  CH, 5%, 1.10

eligibility
  decline when device_value > 3000 because "Devices over 3000 need specialist cover"
  decline when device_age_months > 36 because "Devices must be under 3 years old"
  refer when refurbished is yes and territory is CH because "Refurbished devices need proof of origin in Switzerland"

cover "Accidental Damage"
  limit device_value
  excess 50

cover Theft
  limit device_value
  excess 75
  excludes when territory is FR and device_value > 2000 because "Theft cover in France is capped at 2000"

rating
  base 6% of device_value
  factor "Age"
    device_age_months <= 12: x 1.00
    device_age_months <= 24: x 1.20
    otherwise: x 1.50
  factor "Territory" x load from "Territory"
  minimum 30
  tax IPT ipt from "Territory"

lifecycle
  cooling off 14 days, full refund
  cancellation by customer: refund pro rata
  cancellation by insurer: refund pro rata
  adjustment: not allowed
  renewal: none

claims
  claim "Accidental Damage"
    pays claimed amount up to limit, less excess
  claim Theft
    requires police_report
    pays claimed amount up to limit, less excess

# --- Same device, four territories ---------------------------------------

scenario "Germany: 19% IPT, no loading, quoted in EUR"
  given device_value 1000, device_age_months 6, refurbished no, territory DE
  when bound on 2026-03-01
  expect eligible
  expect net 60.00
  expect tax IPT 11.40
  expect premium 71.40
  expect currency EUR

scenario "France: 9% IPT, 5% loading"
  given device_value 1000, device_age_months 6, refurbished no, territory FR
  when bound on 2026-03-01
  expect net 63.00
  expect tax IPT 5.67
  expect premium 68.67
  expect currency EUR

scenario "Netherlands: 21% IPT, 5% discount"
  given device_value 1000, device_age_months 6, refurbished no, territory NL
  when bound on 2026-03-01
  expect net 57.00
  expect tax IPT 11.97
  expect premium 68.97
  expect currency EUR

scenario "Switzerland: 5% stamp duty, 10% loading, quoted in CHF"
  given device_value 1000, device_age_months 6, refurbished no, territory CH
  when bound on 2026-03-01
  expect net 66.00
  expect tax IPT 3.30
  expect premium 69.30
  expect currency CHF

# --- Territory in rules ---------------------------------------------------

scenario "Refurbished device is referred in Switzerland only"
  given device_value 1000, device_age_months 6, refurbished yes, territory CH
  expect referred "Refurbished devices need proof of origin in Switzerland"

scenario "Refurbished device is fine in Germany"
  given device_value 1000, device_age_months 6, refurbished yes, territory DE
  expect eligible

scenario "Theft cover excluded for expensive devices in France"
  given device_value 2500, device_age_months 6, refurbished no, territory FR
  expect eligible
  expect cover Theft excluded "Theft cover in France is capped at 2000"
  expect cover "Accidental Damage" included
```
