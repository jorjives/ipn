# IPN - Insurance Product Notation

Insurance Product Notation: an open proposal for declaring an insurance product
end to end, from the questions asked at quote through eligibility, cover,
rating, the policy lifecycle and claims. Written for insurance professionals.
The site is the place to learn it.

**Site and full reference: <https://jorjives.github.io/ipn/>**

The reference engine is the `ipngine` package: Python 3.12, standard library
only. `python3 -m unittest` runs its tests.

```
python3 -m ipngine check examples/home.ipn
python3 -m ipngine quote examples/household.ipn rebuild_cost=250000 contents_sum=20000 property_type=flat year_built=1990 previous_claims=0 'select=Buildings;Contents'
python3 -m ipngine batch examples/household.ipn risks.csv > priced.csv
```

- `docs/`: the site, built by GitHub Pages. Start at the playground; engineers
  have their own section.
- `docs/reference/`: the language, block by block.
- `examples/`: sixteen complete products and one across three versions, each
  with scenarios that pass. `home.ipn` is a familiar place to begin.
- `templates/`: starter products, one per kind, each with scenarios that pass.
- `docs/examples/` and `docs/templates/` are generated from the files above by
  `scripts/site_pages.py`.

Licence: Apache-2.0 for the language and the engine; the files in `examples/`
and `templates/` are CC0-1.0, so they can be copied into your own products
without attribution.
