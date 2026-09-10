---
title: table
parent: Language reference
nav_order: 4
---

# table

Rating tables with several dimensions (driver age band by area by vehicle group, say) are
owned by the pricing team as a spreadsheet, not written as factor rows. A `table` block
reads one in its *long* form: one row per cell, one column per key, then the value
columns. That is what a spreadsheet grid becomes with one unpivot, and it carries any
number of dimensions:

```ipn
table "Van rates" from "van_rates.csv" keyed on driver_age, area, vehicle_group

table "Theft excess" keyed on area, use
  area, use, excess
  1-3, *, 250
  4-5, courier, 750
  4-5, *, 500
```

- `from "file.csv"` reads the rows from a file beside the `.ipn`; without it the rows are
  written below, as plain CSV with the header first. The same text works in either place.
  The file must lie in the product's folder or below it: an absolute path, a `../` path or a
  link out of the folder cannot be read, and a product handed to the engine as text rather
  than as a file can read no files at all.
- `keyed on` names the columns matched against the product's inputs, item fields,
  calculated inputs or enrichment-provided fields. The column headers are the input names.
  Every other column is a value column.
- A cell is matched by its form, so a column may mix them:

  | Cell | Matches |
  |---|---|
  | `gold`, `12`, `yes` | that value exactly |
  | `80%` | the number 0.80, in a value column |
  | `17-20` | a number from 17 to 20, both inclusive |
  | `65+` | a number of 65 or more |
  | `*` | anything; a row with fewer `*` cells beats one with more, so `*` rows are the fallback |

  Key cells are checked against the input they match when the product is read: a choice
  that is not one of the input's choices, or a band on a yes/no input, is an error with
  the row number rather than a row that never fires. Rows are indexed on their exact
  cells, so a table of a hundred thousand rows looks up in microseconds.

A key column that a `choice of <column> from` [input](inputs.md#choices-from-a-table)
draws on is read as text: every cell is one of the values offered, so `*` or a band there
is an error, and `1234` is a code rather than a number. Such a table may be keys alone,
with no value column, when it is only a list.

A stepped table becomes a curve with `interpolated [linearly | geometrically] on <key>`
(linearly is the default). The named key's cells are then single numbers, the knots; the
other keys match as in a plain lookup. On a knot the value is the knot's, between two knots
it is interpolated, and outside the knots it is an error:

```ipn
table "Mortality" keyed on age, smoker
  age, smoker, rate
  40, no, 1.30
  45, no, 2.05

rating
  base sum_assured / 1000 * rate from "Mortality" interpolated geometrically on age
```

| Method | Between knots (x0, y0) and (x1, y1), t = (x - x0) / (x1 - x0) | Right for |
|---|---|---|
| `linearly` | y0 + (y1 - y0) * t | additive quantities: an expense, a sum-insured loading |
| `geometrically` | y0 * (y1 / y0) ^ t | rates that grow by a ratio: mortality, claims frequency. Knot values must be positive |

At 42 the curve above gives 1.5598 geometrically and 1.60 linearly. A cubic spline
(`smoothly`) and interpolation across two keys are not provided; each is one more branch
in the same place. [`examples/mortality.ipn`](../examples/mortality.md) prices a term life product from such a curve.

A value is taken with `<column> from "<table>"` anywhere an amount can go: a factor, a
`base`, an `add`, a `limit`, an `excess`, a benefit. Inside `for each` the lookup uses the
current item's fields.

```ipn
rating
  base 6% of vehicle_value
  factor "Driver, area and group" x rate from "Van rates"

cover Theft
  excess excess from "Theft excess"
```

The parser checks that the file exists, every key is an input the product knows and a
column of the table, at least one value column exists, every cell reads, and no two rows
repeat the same keys. When a risk is priced, exactly one row must match: none is reported
as `no row in Van rates for driver_age 16, area 3, vehicle_group 5`, and two equally
specific rows (overlapping bands) as ambiguous. A value between bands is an error, so the
scenarios that check the product are how the pricing team checks a reissued table. [`examples/van.ipn`](../examples/van.md) rates from a three-dimensional table of 300 cells.
