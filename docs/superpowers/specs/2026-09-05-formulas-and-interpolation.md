# Formulas and interpolation: curves, power laws and continuous terms

## Purpose

Lookup tables (see `2026-09-05-lookup-tables.md`) step. Some pricing does not: a
mortality rate rises smoothly with age, a BMI loading follows a power law, a GLM term is
`exp` of a linear predictor. This piece of work adds the smallest set of mathematical forms
that let a product say those things, and proves them on a mortality-rated term life
product.

Autonomous run on 2026-09-05; Jorj asked for it, including non-linear interpolation to show
how those options are shaped.

## Design

### An operator and a fixed set of functions

- `a ^ b`: power, right-associative, binding tighter than `*` and than unary minus, so
  `- 2 ^ 2` is `-4` and `2 ^ 3 ^ 2` is `2 ^ 9`.
- Functions, written `name ( args )`: `exp`, `ln`, `sqrt`, `min`, `max`, `round`.
  `round ( x, 0.0001 )` quantises to the unit, half up, so a curve's value can be shown in
  the trail and expected in a scenario at a sensible precision.

Everything stays in `Decimal`. Python's `Decimal` implements `exp`, `ln`, `sqrt` and
non-integral powers itself, so the proof does not depend on the platform's floating point
and two machines give the same premium to the penny.

Not added: user-defined functions, loops, and trigonometry. A fitted model with hundreds of
coefficients belongs in an `enrichment`; the product declares the shape of the lookup and
consumes it. A formula belongs in the product when an underwriter would read it.

### Interpolation is a modifier on a table lookup

```
table "Mortality" keyed on age, smoker
  age, smoker, rate
  25, no, 0.60
  30, no, 0.70
  ...

rating
  base sum_assured / 1000 * rate from "Mortality" interpolated geometrically on age
```

- `interpolated [linearly | geometrically] on <key>`; linearly is the default.
- The named key's cells must be single numbers: the knots. The other keys are matched
  as in a plain lookup (exact, band or `*`, most specific row wins). At least two knots
  must survive that match.
- On a knot the value is the knot's; between two knots it is interpolated; outside the
  knots it is an error (`age 90 is outside Mortality, whose knots run from 25 to 65`),
  never a clamp. The scenarios that prove the product decide what the edges do.

Two methods, chosen by the shape of the underlying quantity:

| Method | Between knots (x0, y0) and (x1, y1) | Right for |
|---|---|---|
| `linearly` | y0 + (y1 - y0) * t | an expense or a sum-insured loading: additive quantities |
| `geometrically` | y0 * (y1 / y0) ^ t | a mortality or claims-frequency rate: quantities that grow by a ratio, so a straight line between knots would overstate the rate in the first half of each gap and understate it in the second |

where t = (x - x0) / (x1 - x0). Geometric interpolation needs positive knot values.

Shapes deliberately not added yet, and where they would go: a cubic spline (`smoothly`)
needs every knot, not just the bracketing pair, and a tridiagonal solve; bilinear
interpolation across two keys (`on age and term_years`). Both are one more branch in
`Table.interpolate` once a product needs them.

## Worked example

`examples/mortality.idl`: term life rated from a mortality curve with knots every five years,
interpolated geometrically, a BMI loading as a power law, an `exp` decay discount for large
sums assured and an expense loading interpolated linearly on sum assured.
