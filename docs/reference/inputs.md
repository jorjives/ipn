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
| `choice of a, b, c` | exactly one of the listed words |
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
