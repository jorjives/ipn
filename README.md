# Open IDL

An open, declarative language for defining an insurance product end to end, from the
questions asked at quote through eligibility, cover, rating, the policy lifecycle (cooling
off, cancellation, mid-term adjustment, lapse, renewal, versions) and claims. Written for
insurance professionals, not developers, and proven by scenarios written in the same file.

**Site and full reference: <https://jorjives.github.io/open-idl/>**

```
python3 -m ideclare check examples/cycle.idl
python3 -m ideclare quote examples/cycle.idl bike_value=2000 rider_age=22 security=gold racing=no previous_claims=0 bike_age=0
python3 -m ideclare batch examples/cycle.idl risks.csv > priced.csv
```

The reference engine is the `ideclare` package (the project's working name): Python 3.12,
standard library only. `python3 -m unittest` runs its tests.

- `docs/reference/`: the language, block by block, with a formal grammar.
- `examples/`: sixteen complete products and one across three versions, each proven by its
  scenarios. Start with `cycle.idl`, which uses every part of the language.
- `templates/`: starter products, one per shape, each proven likewise.
- `docs/`: the site, built by GitHub Pages; `docs/examples/` and `docs/templates/` are
  generated from the files above by `scripts/site_pages.py`.

The licence is still to be chosen before the first tagged release.
