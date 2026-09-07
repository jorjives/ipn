---
title: inputs
parent: Language reference
nav_order: 2
---

# inputs

What you ask at quote. Each line is `name: type`.

| Type | Values |
|---|---|
| `money`, `number` | a decimal amount |
| `integer` | a whole number |
| `yes/no` | `yes` or `no` |
| `choice of a, b, c` | exactly one of the listed values; a value that is not one word is quoted, `choice of construction, "Health & Social Care"` |
| `choice of <column> from "Table" [for key, ...]` | one of the values in that key column of a [table](table.md); see [choices from a table](#choices-from-a-table) |
| `text` | free text; compare it to a quoted value, `make is "Brompton"`; scenarios may leave it out |
| `date` | a calendar date, `2026-07-10` |
| `collection of bike[, 1 to 5]` | repeatable items, each with the fields indented below it |
| `calculated` | an input or item field worked out from the others by the steps indented below it |

Any of these but a collection may end `, default <value>`: `voluntary_excess: money,
default 0`, `cover_type: choice of comprehensive, third_party, default comprehensive`. An
input or item field left out of a scenario, a `quote` or a `batch` row takes its default;
one without a default must be given.

## Repeatable items

```idl
inputs
  rider_age: integer
  bikes: collection of bike, 1 to 4
    value: money
    age: integer
    security: choice of bronze, silver, gold
```

The plural (`bikes`) names the collection, the singular (`bike`) names one item. Bounds
are optional: `, 1 to 4`, `, at least 1` or `, at most 4`. A quote outside the bounds is
declined with the reason `bikes: at least 1 required` or `bikes: at most 4 allowed`. A
field may not share its name with an input.

Items appear in conditions and amounts like this:

| Write | Meaning |
|---|---|
| `count of bikes` | how many items |
| `total value of bikes`, `highest value of bikes`, `lowest value of bikes` | aggregate of one field |
| `any bike where value > 5000` | true if one item matches |
| `every bike where security is gold` | true if all items match |
| `value`, `age` on their own | the current item's field, inside `for each`, a cover, a claim or a `where` |

## Choices from a table

A list too long to write inline, or one that depends on an earlier answer, lives in a
[table](table.md) and the choice names the key column it draws on:

```idl
inputs
  industry: choice of industry from "Occupations"
  occupation: choice of occupation from "Occupations" for industry

table "Occupations" from "occupations.csv" keyed on industry, occupation
```

`industry` offers the distinct values of that column. `for industry` narrows
`occupation` to the rows whose industry matches the one given, so a platform shows the
occupations of the chosen industry and a quote giving a pair the table does not list is
refused: `occupation "Nurse" is not an occupation for industry "Construction"`. Several
keys narrow on all of them: `for industry, sector`. The same lines work as the fields of
a collection item, keyed on the item's other fields (each person's industry and
occupation), and the keyed check runs per item.

The table is declared after the inputs that draw on it. Its other columns are looked up
as usual, so the same file carries the class or rate of every occupation:
`factor "Occupation" x rate from "Occupations"`. A value from the file is written in the
product as it appears there: a single word bare, `industry is Construction`, anything
else quoted, `industry is "Health & Social Care"`. A code such as `1234` is text, not a
number. [`examples/income.idl`](../examples/income.md) rates on an occupation drawn this
way.

## Formulas

Amounts and conditions are expressions: `+ - * /`, `N% of x`, `a ^ b` (power, so
`( bmi / 25 ) ^ 2` is a power law and `x ^ 0.5` a square root), parentheses, comparisons,
`and`, `or`, `not`, and these functions:

| Function | Gives |
|---|---|
| `exp ( x )`, `ln ( x )`, `sqrt ( x )` | the exponential, natural log and square root, so a GLM term is `exp ( 0.021 * annual_mileage / 1000 )` |
| `min ( a, b, ... )`, `max ( a, b, ... )` | the smallest or largest |
| `round ( x, 0.0001 )` | x to that unit, half up; use it so a curve's value reads sensibly in the trail and can be expected in a scenario |

All arithmetic is in decimal, not floating point, so a curve prices the same on every
machine. A long formula is better given a name as a `calculated` input (see [repeatable
items](#repeatable-items)) than written in one line.
