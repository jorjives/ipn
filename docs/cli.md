---
title: Command line
parent: For engineers
nav_order: 1
---

# Command line

The reference engine is a Python package, `ipngine`, with no dependencies. It
has three commands.

```sh
python3 -m ipngine check FILE.ipn
python3 -m ipngine quote FILE.ipn input=value ... [select=Cover] [items=file.csv]
python3 -m ipngine batch FILE.ipn RISKS.csv [collection=file.csv ...]
```

`check` builds a `History` from sibling files of the same product name, where
the file declares a `published` date. `quote` and `batch` parse the given file
only. Every figure is a decimal, rounded half up to the smallest unit of the
risk's currency, so the same file and answers give the same premium wherever
they run. See [design](design.md).

## check: run the scenarios

`check` runs every `scenario` in the file, in order, and prints one line per
scenario. A failure says which line disagreed and what the engine actually
produced:

```check
PASS Standard contents, no specified items
FAIL Flood in a high-risk postcode is referred
     line 142: expected referred, got eligible
Home Contents: 12 passed, 1 failed
```

The exit status is 0 when every scenario passes and 1 otherwise, so `check`
sits in a pipeline or a pre-commit hook as it is. A file that cannot be read
stops before any scenario runs, with the line:

```
line 8: unknown word 'summ'
```

Errors of that kind are found when the file is read, not when a risk happens
to hit the line: an unknown word, a table cell that is not one of the input's
choices, a factor whose `otherwise` is not last, an excess table without
`otherwise`, a dated line that names a word an earlier version never asked
for.

```sh
python3 -m ipngine check examples/home.ipn
```

## quote: price one risk

`quote` takes the answers as `name=value` pairs, optional covers as
`select=Name` (several separated by `;`), and repeatable items as a CSV file
whose columns are the item's fields. It prints the eligibility outcome, the
state of every cover, and the rating trail step by step.

A product whose enrichment cannot answer follows `when unavailable`. The
[home contents](examples/home.md) example refers an unrecognised postcode;
[buildings and contents](examples/household.md) has no lookup, so a quote is
a clean trail:

```sh
python3 -m ipngine quote examples/household.ipn rebuild_cost=250000 contents_sum=20000 property_type=flat year_built=1990 previous_claims=0 select=Buildings\;Contents
```

```
Eligibility: eligible
  Buildings: included, limit 250000.00
  Contents: included, limit 20000.00
Premium:
  Buildings              + 375.00  = 375.00
  Contents               + 100.00  = 100.00
  Property type            x 0.90  = 427.50
  Age of building          x 1.00  = 427.50
  Claims history           x 1.00  = 427.50
  discount                  x 0.9  = 384.75
  minimum                      60  = 384.75
  net                              = 384.75
  IPT                              + 46.17
  total                            = 430.92 GBP
```

A product with `instalments` also prints the schedule; one with `commission`
prints each intermediary's share. One that attributes its premium to covers
(see [rating](reference/rating.md#shares-by-cover)) prints each cover's share
of the net and of each tax under `Shares:`, and the totals per class under
`By class:`. An input left out takes its `default`; one without a default is
reported as missing, with exit status 2, as is a keyed choice the table does
not list under the keys given (`occupation "Nurse" is not an occupation for
industry "Construction"`). A quote reads only the undated lines of a cover:
dated amendments apply to events on a policy, not to a price.

## batch: price a book

`batch` reads one risk per row from a CSV whose columns are the input names
(plus optional `select` and `risk` columns) and writes one row per risk: eligibility,
reasons, net, every tax and fee, the total, the currency, each commission,
and, when the product attributes its premium to covers, a column per cover
for the net and for each tax and commission. A row the product cannot price
says why in its own `error` column instead of stopping the run.

```sh
python3 -m ipngine batch examples/household.ipn examples/household-risks.csv > priced.csv
```

A declined risk is still priced, so the book can be compared before and after
a rule change.

`risk` names the row in the output; left out, the rows are numbered from 1. It
must be unique and non-blank, and it is matched as text, so `01` and `1` are
different rows.

Repeatable items come from one further CSV per collection, named as an extra
argument. Its header is `risk` and the item's fields, and each row attaches to
the book row with the same `risk`:

```sh
python3 -m ipngine batch examples/home.ipn examples/home-risks.csv specified_items=examples/home-specified-items.csv
```

That prices three risks: one with a watch, one with nothing specified, one
with a necklace and a painting. A risk with no matching row has an empty
collection, so a product that requires items declines it and prices it anyway.
An item row naming a risk the book does not have stops the run before any
premium is written. A collection may still be a column on the book whose cell
is the name of a file beside the product, which suits one risk rather than a
book.

The site's [Price a book](book.md) page runs the same comparison in the
browser on a prepared contents sample.

## Versions

When the file has a `published` date, `check` finds the other versions of the
product in the same directory (the `.ipn` files declaring the same product
name, published on or before the file) and uses them: a scenario that binds a
policy before this version was published runs it on the version live that day,
and moves it here at renewal. `quote` and `batch` parse the selected file
alone. See [Versions](reference/versions.md).
