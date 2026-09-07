---
title: Command line
nav_order: 7
---

# Command line

The reference engine is a Python package, `ideclare` (the project's working name), with no
dependencies. It has three commands. Every one reads a product file and, where the file
declares a `published` date, the other versions of the product beside it.

```sh
python3 -m ideclare check FILE.idl
python3 -m ideclare quote FILE.idl input=value ... [select=Cover] [items=file.csv]
python3 -m ideclare batch FILE.idl RISKS.csv
```

## check: run the scenarios

`check` runs every `scenario` in the file, in order, and prints one line per scenario.
A failure says which line disagreed and what the engine actually produced:

```check
PASS Racing cover selected and available
FAIL Young rider with a gold lock
     line 142: expected premium 90.00, got 93.97
PASS Minimum premium applies to a cheap bike
Cycle Cover: 34 passed, 1 failed
```

The exit status is 0 when every scenario passes and 1 otherwise, so `check` sits in a
pipeline or a pre-commit hook as it is. A file that cannot be read stops before any
scenario runs, with the line:

```
line 8: unknown word 'agee'
```

Errors of that kind are found when the file is read, not when a risk happens to hit the
line: an unknown word, a table cell that is not one of the input's choices, a factor whose
`otherwise` is not last, an excess table without `otherwise`, a dated line that names a
word an earlier version never asked for.

## quote: price one risk

`quote` takes the answers as `name=value` pairs, optional covers as `select=Name` (several
separated by `;`), and repeatable items as a CSV file whose columns are the item's fields.
It prints the eligibility outcome, the state of every cover, and the rating trail step by
step:

```sh
python3 -m ideclare quote examples/cycle.idl bike_value=2000 rider_age=22 security=gold racing=yes previous_claims=0 bike_age=0 select=Racing
```

```
Eligibility: eligible
  Theft: included, limit 2000.00
  Accidental Damage: included, limit 2000.00
  Racing: included, limit 5000.00
Premium:
  base                      70.00  = 70.00
  Rider age                x 1.40  = 98.00
  Security                 x 0.85  = 83.30
  Claims history           x 0.90  = 74.97
  Racing cover               + 45  = 119.97
  minimum                      60  = 119.97
  maximum                     800  = 119.97
  net                              = 119.97
  IPT                              + 14.40
  Admin fee                        + 10.00
  total                            = 144.37 GBP
```

A product with `instalments` also prints the schedule; one with `commission` prints each
intermediary's share. One that attributes its premium to covers (see
[rating](reference/rating.md#shares-by-cover)) prints each cover's share of the net and of
each tax under `Shares:`, and the totals per class under `By class:`. An input left out takes its `default`; one without a default is
reported as missing, with exit status 2, as is a keyed choice the table does not list under
the keys given (`occupation "Nurse" is not an occupation for industry "Construction"`). A quote reads only the undated lines of a cover:
dated amendments apply to events on a policy, not to a price.

## batch: price a book

`batch` reads one risk per row from a CSV whose columns are the input names (plus an
optional `select` column) and writes one row per risk to standard output: the eligibility
outcome and reasons, the net, every tax and fee line, the total, the currency, each
commission, and, when the product attributes its premium to covers, a column per cover
for the net and for each tax and commission (`net:Theft`, `IPT:Theft`, ...). A row the product cannot price says why in its own `error` column instead of
stopping the run, so an impact analysis over a hundred thousand policies reports the
rows that fell off a table instead of stopping at the first one:

```sh
python3 -m ideclare batch examples/cycle.idl risks.csv > priced.csv
```

```
risk,eligibility,reasons,net,IPT,Admin fee,total,currency,net:Theft,IPT:Theft,net:Accidental Damage,IPT:Accidental Damage,net:Racing,IPT:Racing,error
1,eligible,,74.97,9.00,10.00,93.97,GBP,29.99,3.60,44.98,5.40,0.00,0.00,
2,eligible,,191.30,22.96,10.00,224.26,GBP,58.52,7.02,87.78,10.54,45.00,5.40,
3,declined,Rider must be at least 16,60.00,7.20,10.00,77.20,GBP,24.00,2.88,36.00,4.32,0.00,0.00,
4,,,,,,,,,,,,,,"security is choice, cannot be 'platinum'"
```

A declined risk is still priced, so the book can be compared before and after a rule
change. A repeatable item cannot be given in a batch row; price such products with `quote`
and an items file, or in a scenario.

## Versions

When the file has a `published` date, all three commands find the other versions of the
product in the same directory (the `.idl` files declaring the same product name, published
on or before the file) and use them: a scenario that binds a policy before this version was
published runs it on the version live that day, and moves it here at renewal. See
[Versions](reference/versions.md).

## Determinism

Every figure is a decimal, and every rounding is half up to the smallest unit of the
risk's currency (or the product's `round to`), so the same file and answers give the same
premium wherever they run. See [design](design.md).
