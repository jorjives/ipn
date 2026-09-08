# IPN - Insurance Product Notation

Insurance Product Notation: an open spec for declaring an insurance product end to end, from the
questions asked at quote through eligibility, cover, rating, the policy lifecycle (cooling
off, cancellation, mid-term adjustment, lapse, renewal, versions) and claims. Written for
insurance professionals, not developers, and proven by scenarios written in the same file.

**Site and full reference: <https://jorjives.github.io/ipn/>**

```
python3 -m ipngine check examples/cycle.ipn
python3 -m ipngine quote examples/cycle.ipn bike_value=2000 rider_age=22 security=gold racing=no previous_claims=0 bike_age=0
python3 -m ipngine batch examples/cycle.ipn risks.csv > priced.csv
```

The reference engine is the `ipngine` package: Python 3.12, standard library only.
`python3 -m unittest` runs its tests.

- `docs/reference/`: the language, block by block, with a formal grammar.
- `examples/`: sixteen complete products and one across three versions, each proven by its
  scenarios. Start with `cycle.ipn`, which uses every part of the language.
- `templates/`: starter products, one per shape, each proven likewise.
- `docs/`: the site, built by GitHub Pages; `docs/examples/` and `docs/templates/` are
  generated from the files above by `scripts/site_pages.py`.

Licence: Apache-2.0 for the language and the engine; the files in `examples/` and
`templates/` are CC0-1.0, so they can be copied into your own products without
attribution.
