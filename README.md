# iDeclare

A declarative language for defining an insurance product end to end, from the questions
asked at quote through eligibility, cover, rating, the policy lifecycle (cooling off,
cancellation, mid-term adjustment, lapse, renewal) and claims. Written for insurance
professionals, not developers, and proven by scenarios written in the same file.

```
python3 -m ideclare check examples/cycle.idl
python3 -m ideclare quote examples/cycle.idl bike_value=2000 rider_age=22 security=gold racing=no previous_claims=0
```

- `docs/reference.md`: the language, block by block.
- `examples/cycle.idl`: a complete product with scenarios covering every language feature.
- `examples/family.idl`: several bikes on one policy, showing repeatable items.
- `examples/multibike.idl`: bikes ranked and rated in order, the first at full rate and the rest at half, with postcode and catalogue enrichment.
- `examples/travel.idl`: single-trip travel; people not things, a term ending on the return date, cover sections that start and stop on different days.
- `examples/pet.idl`: lifetime pet cover; an annual limit eroded by claims, a waiting period, a co-payment that arrives with age.
- `examples/motor.idl`: private motor; named drivers, a no claims discount that steps back after fault claims, an excess that depends on who was driving.
- `examples/life.idl`: level term life; a fixed benefit over a term of years chosen by the customer, BMI calculated, no renewal.
- `examples/pi.idl`: professional indemnity; commercial, turnover-rated, claims-made with a retroactive date and an aggregate limit.
- `examples/home.idl`: home contents; specified items on top of a sum insured, a cause-based excess, the average clause.
- `examples/leasing.idl`: a cycle leasing scheme; a group policy held by the supplier, members who join and leave mid term, each covered for their own lease dates.
- `examples/income.idl`: short-term income protection; a monthly benefit paid for the months off work after a deferred period, up to a year's worth.
- `examples/van.idl`: light commercial vehicle; rated from a three-dimensional table of 300 cells held as a CSV beside the product (`van_rates.csv`), with a small excess table written inline.
- `examples/mortality.idl`: term life rated from a mortality curve interpolated geometrically between five-year knots, with a power-law BMI loading, an exponential large-sum discount and a linearly interpolated expense loading.
- `ideclare/`: the sidecar engine. Python 3.12, standard library only.
- `python3 -m unittest`: the engine's own tests.
