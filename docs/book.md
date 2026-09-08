---
title: Price a book
nav_order: 2.5
---

# Price a book

A scenario pins a case you wrote. A book is a set of risks you already have.
Change a rate and see who moves.

This page prices twelve contents risks against a product, then against the same
product with the terrace factor raised from 1.00 to 1.15. Flats, semis and
detached houses are unchanged. Edit the after file and run again to see that
the table follows the product.

Checks and this comparison run in the browser. The page does not submit your
product text to a server. On first load it fetches
[Pyodide](https://pyodide.org) (CPython, about 10 MB, once) and the engine. A
real book of thousands of rows is `python3 -m ipngine batch` on your machine;
see [Command line](cli.md).

<div class="oidl-play oidl-book">
<div class="pair">
<div>
<p class="pane">Before</p>
<div id="bk-before" class="editor" aria-label="Product before the change"></div>
</div>
<div>
<p class="pane">After</p>
<div id="bk-after" class="editor" aria-label="Product after the change"></div>
</div>
</div>
<p class="pane">The book</p>
<p class="hint">Twelve risks. Every terrace should move; the other property types should not.</p>
<div id="bk-risks" class="table-wrap"></div>
<div class="bar">
<button id="bk-run" class="btn btn-primary" disabled>Price the book</button>
<button id="bk-reset" class="btn" disabled>Reset after</button>
<span id="bk-status" class="status" aria-live="polite">Loading the engine...</span>
</div>
<div id="bk-out" class="table-wrap" aria-label="Comparison" aria-live="polite"></div>
</div>

The [playground](playground.md) is where you write a product and check its
scenarios. [Getting started](getting-started.md) builds a small contents product
that way.

## Risks with items

A book whose risks carry specified items, named drivers or scheme members is
two CSVs, joined on `risk`.

```
# examples/home-risks.csv
risk,postcode,contents_sum,property_type,alarm,occupied_during_day,previous_claims,flood_risk,theft_area
A,SW1A 1AA,20000,terrace,no,yes,0,low,low
B,E1 6AN,20000,terrace,no,yes,0,low,low
C,M1 1AE,80000,detached,yes,no,1,low,high
```

```
# examples/home-specified-items.csv
risk,description,value
A,watch,2000
C,necklace,4000
C,painting,8000
```

```sh
python3 -m ipngine batch examples/home.ipn examples/home-risks.csv specified_items=examples/home-specified-items.csv
```

A has one item, C has two, and B has none: a risk with no matching row has an
empty collection, and a product that requires items declines those rows and
prices them anyway. See [Command line](cli.md).

<script src="https://cdn.jsdelivr.net/pyodide/v0.28.3/full/pyodide.js"></script>
<script type="importmap">
{"imports": {
  "@codemirror/state": "https://esm.sh/*@codemirror/state@6.7.4",
  "@codemirror/view": "https://esm.sh/*@codemirror/view@6.43.11",
  "@codemirror/language": "https://esm.sh/*@codemirror/language@6.12.4",
  "@codemirror/autocomplete": "https://esm.sh/*@codemirror/autocomplete@6.20.3",
  "@codemirror/commands": "https://esm.sh/*@codemirror/commands@6.11.0",
  "@lezer/common": "https://esm.sh/*@lezer/common@1.5.2",
  "@lezer/highlight": "https://esm.sh/*@lezer/highlight@1.2.3",
  "@lezer/lr": "https://esm.sh/*@lezer/lr@1.4.10",
  "style-mod": "https://esm.sh/*style-mod@4.1.3",
  "w3c-keyname": "https://esm.sh/*w3c-keyname@2.2.8",
  "crelt": "https://esm.sh/*crelt@1.0.7",
  "@marijn/find-cluster-break": "https://esm.sh/*@marijn/find-cluster-break@1.0.4"
}}
</script>
<script type="module" src="{{ site.baseurl }}/assets/js/book.js"></script>
