# Lookup tables: rating from a large, multi-dimensional table

## Purpose

Insurers rate from tables, not formulas. A motor book has a driver-age band by vehicle
group by area grid with hundreds or thousands of cells; it lives in a spreadsheet owned by
the pricing team and is reissued every few months. This piece of work asks how iDeclare
carries such a table, and adds the smallest language feature that makes it possible.

Autonomous run on 2026-09-05; Jorj not available, so the decisions are recorded here.

## What the language could do before

- A `factor` is a list of `condition: x N` rows, first match wins. A three-dimensional
  table can be written as one row per cell with a compound condition
  (`age < 25 and area is high and vehicle_group < 10: x 1.40`), but a 7 x 5 x 10 table is
  350 hand-written rows whose order matters, with no check that every cell is present and
  no way for the pricing team to reissue it without editing the product.
- An `enrichment` pushes the lookup outside the product. The product then no longer
  proves its own rating; every scenario has to give the answer by hand.

Neither is how an insurer would want to hold a rating table. So: a new feature.

## Design

### The table is a long-format CSV

A grid in a spreadsheet is two-dimensional per sheet. The form that carries any number of
dimensions is *long* (unpivoted): one row per cell, one column per key, then the value
columns. This is what pricing teams export, and what a three-dimensional grid becomes with
one unpivot. iDeclare reads exactly that, from a file beside the product or written inline
for small tables:

```
table "Motor rates" from "van_rates.csv" keyed on driver_age, area, vehicle_group

table "Theft excess" keyed on area
  area, excess
  1-2, 150
  3-4, 250
  5, 400
```

- `keyed on` names the columns that are matched against the product's inputs (or item
  fields, calculated inputs and enrichment-provided fields). Column headers must be the
  input names. Every other column is a value column.
- A file path is relative to the `.idl` file. Inline rows are plain CSV lines, header
  first, so the same text works in either place.

### How a cell matches

The cell decides, so a column may mix forms:

| Cell | Matches |
|---|---|
| `gold`, `12`, `yes` | that value exactly |
| `17-20` | a number from 17 to 20 inclusive |
| `65+` | a number of 65 or more |
| `*` | anything |

Bands are inclusive at both ends because that is how tables are written (`0-999`,
`1000-1999`). A value that falls between bands has no row, and that is an error the
scenario reports, not a silent default.

### Using a value from the table

A value column is an expression, `<column> from "<table>"`, usable anywhere an amount
is: a factor, a base, an add, a limit, an excess. Inside `for each` it looks up on the
current item's fields. So:

```
rating
  base 400
  factor "Age, area and group" x rate from "Motor rates"

cover Theft
  excess excess from "Theft excess"
```

`factor "Label" x <amount>` is a new, single-row form of factor (also `+` and `-`, with an
optional `when`). Its trail line reads exactly like a row factor's, so `expect factor
"Age, area and group" x 1.40` proves which cell was used.

### What is checked, and when

At parse time: the file exists, every key names an input the product knows, every key is a
column of the table, at least one value column exists, every cell parses, and no two rows
have identical keys. At lookup time: exactly one row matches; none is "no row in Motor
rates for driver_age 22, area 3, vehicle_group 12", more than one is "ambiguous" (two
overlapping bands). Overlap is not searched for at parse time; that is quadratic in the
row count and the scenarios that prove the product exercise the cells that matter.

### Not done

- Wide (grid) CSVs with one key down the side and one across the top. Unpivot in the
  spreadsheet; every tool does it. Add a `rows X, columns Y` form if that proves tiresome.
- Interpolation between bands. Rating tables step; they do not interpolate.
- A table keyed on an expression (`bike_value / 100`). Use a calculated input.
- Indexing the rows. Lookups scan every row; a few thousand rows and a few dozen lookups
  per scenario is well inside what a check run tolerates.

## Worked example

`examples/van.idl`: light commercial vehicle cover rated from `examples/van_rates.csv`, a
three-dimensional table (six driver age bands by five areas by ten vehicle groups, 300
rows), plus an inline two-dimensional theft excess table.
