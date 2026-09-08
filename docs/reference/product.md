---
title: product
parent: Language reference
nav_order: 1
---

# product

```ipn
product "Cycle Cover"
  territory UK
  term 12 months
```

`territory` is where the product is sold. A product sold in several countries lists them,
`territory DE, FR, NL, CH`, and `territory` is then an answer given at quote, so a table
keyed on it carries the country's tax and loading and a condition can say `territory is
CH`. With one territory it is assumed. The currency follows the territory (GBP for UK,
EUR for DE, CHF for CH, and so on); a product priced in another currency, or sold
somewhere the engine does not know, says `currency EUR`. See [`examples/gadget.ipn`](../examples/gadget.md).

`published 2026-07-01` says when this version of the product went on sale; see
[Versions](versions.md). A product without it is a single version.

`term` is the length of one policy period: `term 12 months`, `term 10 days`, `term 25
years`. A policy bound on 31 January with a 1 month term expires on 28 February. The
number may be an input the customer chooses, `term term_years years`, and a product that
ends on a date the customer gives says `term until return_date`.
