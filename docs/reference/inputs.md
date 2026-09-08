---
title: inputs
parent: Language reference
nav_order: 2
---

# inputs

The questions asked at quote. Each line is `name: type`.

| Type | Values |
|---|---|
| `money`, `number` | a decimal amount |
| `integer` | a whole number |
| `yes/no` | `yes` or `no` |
| `choice of a, b, c` | exactly one of the listed values; a value that is not one word is quoted, `choice of construction, "Health & Social Care"` |
| `choice of <column> from "Table" [for key, ...]` | one of the values in that key column of a [table](table.md); see [choices from a table](#choices-from-a-table) |
| `text` | free text; compare it to a quoted value, `make is "Acme"`; scenarios may leave it out |
| `date` | a calendar date, `2026-07-10` |
| `collection of item[, 1 to 5]` | repeatable items, each with the fields indented below it |
| `calculated` | an input or item field worked out from the others by the steps indented below it |

Any of these but a collection may end `, default <value>`: `voluntary_excess: money,
default 0`, `cover_type: choice of comprehensive, third_party, default comprehensive`. An
input or item field left out of a scenario, a `quote` or a `batch` row takes its default;
one without a default must be given.

## Repeatable items

```ipn
inputs
  contents_sum: money
  specified_items: collection of item, 1 to 10
    description: text
    value: money
```

The plural (`specified_items`) names the collection, the singular (`item`) names one item. Bounds
are optional: `, 1 to 10`, `, at least 1` or `, at most 10`. A quote outside the bounds is
declined with the reason `specified_items: at least 1 required` or `specified_items: at most 10 allowed`. A
field may not share its name with an input.

A quote gives the items as a CSV whose columns are the fields. A book gives one
such CSV per collection, with a `risk` column joining its rows to the book's
rows, so a whole book of policies with items is priced in one run. See
[Command line](../cli.md).

Items appear in conditions and amounts like this:

| Write | Meaning |
|---|---|
| `count of specified_items` | how many items |
| `total value of specified_items`, `highest value of specified_items`, `lowest value of specified_items` | aggregate of one field |
| `any item where value > 5000` | true if one item matches |
| `every item where value <= 15000` | true if all items match |
| `value`, `description` on their own | the current item's field, inside `for each`, a cover, a claim or a `where` |

## Calculated fields

A `calculated` input or item field is worked out from the others by the same
steps a `for each` block uses (`base`, `add`, `factor`, `discount`, `load`,
`minimum`, `maximum`). It is never asked. Calculated fields are filled in
before anything else runs, so eligibility, covers and claims can use them too.

A top-level formula, such as BMI on a life product:

```ipn
inputs
  height_cm: number
  weight_kg: number
  bmi: calculated
    base weight_kg / ( height_cm / 100 * height_cm / 100 )
```

An item field used to rank a collection (see [rating](rating.md)):

```ipn
inputs
  specified_items: collection of item
    description: text
    value: money
    rank: calculated
      base value
```

[Level term life](../examples/life.md) calculates BMI this way.

## Choices from a table

A list too long to write inline, or one that depends on an earlier answer, lives in a
[table](table.md) and the choice names the key column it draws on:

```ipn
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

The table is declared after the inputs that draw on it, and before any other table keyed
on them. A claim's `asks` list their choices inline. Its other columns are looked up
as usual, so the same file carries the class or rate of every occupation:
`factor "Occupation" x rate from "Occupations"`. A value from the file is written in the
product as it appears there: a single word bare, `industry is Construction`, anything
else quoted, `industry is "Health & Social Care"`. A code such as `1234` is text, not a
number. [`examples/income.ipn`](../examples/income.md) rates on an occupation drawn this
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

Give a long formula a name as a `calculated` input rather than writing it in one line.
See [rating](rating.md) for how a calculated field is used in the premium.
