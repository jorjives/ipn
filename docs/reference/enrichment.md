---
title: enrichment
parent: Language reference
nav_order: 3
---

# enrichment

Products depend on lookups they do not perform themselves: postcode risk, a bike or
vehicle catalogue, claims history. An `enrichment` block declares the shape of such a lookup
and nothing about how it is done:

```idl
enrichment "Postcode risk" from postcode
  provides
    theft_area: choice of low, medium, high
  when unavailable: refer because "Postcode not recognised"
  held for the term

enrichment "Bike catalogue" for each bike from make, model
  provides
    category: choice of road, mountain, folding, other
  when unavailable: category is other
```

- `from` names the inputs the lookup is keyed on. `for each bike` makes it a lookup per
  item, keyed on that item's fields.
- `provides` lists the fields it returns, typed like inputs. They are used exactly like
  inputs everywhere else, but the customer is never asked for them.
- `when unavailable` is the underwriting decision for a lookup that cannot answer: either
  defaults for every provided field, or `refer because "..."` or `decline because "..."`.
- `held for the term` fixes the values at inception; an adjustment that changes them is
  refused. Without it the lookup is taken to run again on adjustment and at renewal.

Scenarios stand in for the lookup by giving the provided fields directly, for example
`given postcode "M1 1AA", theft_area high`. Leaving them out is how a scenario says the
lookup could not answer.
