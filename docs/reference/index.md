---
title: Language reference
nav_order: 6
has_children: true
has_toc: false
---

# Language reference

Each block is one kind of sentence an underwriter writes. The `product` block
comes first; the others may follow in any order, except that a block which
names something must come after the block that declares it (an `eligibility`
rule that says `Contents selected` comes after `cover Contents`).

| Block | What it declares |
|---|---|
| [`product`](product.md) | the name, where it is sold, the term, and when this version was published |
| [`inputs`](inputs.md) | the questions asked at quote, their types, repeatable items and calculated values |
| [`enrichment`](enrichment.md) | the shape of external lookups (postcode risk, a vehicle catalogue) the product depends on |
| [`table`](table.md) | rating tables in long CSV form, inline or from a file, with bands, wildcards and interpolation |
| [`eligibility`](eligibility.md) | who is declined and who is referred to an underwriter |
| [`cover`](cover.md) | each section of cover: limit, excess, exclusions, optionality, aggregates, dates in force, its class and its own premium |
| [`rating`](rating.md) | the premium calculation, step by step, in the order written; tax, fee and commission on any base; the net split by cover |
| [`lifecycle`](lifecycle.md) | cooling off, cancellation, mid-term adjustment, lapse, instalments and renewal |
| [`claims`](claims.md) | what a claim needs, how it is settled, and what a paid claim changes |
| [`scenario`](scenarios.md) | answers, events in order, and what must be true after each |
| [`upgrading`](versions.md) | how a previous version's answers become this version's |

The [grammar](grammar.md) is the syntax for another engine.
[Not yet supported](not-yet-supported.md) lists the known gaps. Every construct
on these pages is exercised by at least one [example product](../examples/index.md)
whose scenarios pass.

## Writing conventions

- Indent with two spaces to put a line inside the block above it.
- One statement per line. Anything after `#` is a comment.
- Names of inputs are single words joined with underscores: `contents_sum`, `property_type`.
- Cover names, labels and reasons that contain spaces go in double quotes: `"Accidental Damage"`.
- Money and numbers are written plainly: `20000`, `0.5`, `12%`. Dates are `2026-01-31`.
- Words that stand for the same thing may be singular or plural where English wants it:
  `after 1 claim in term`, `after 2 claims in term`.

## Conditions

Many lines take a condition after `when`. A condition compares inputs and other known
values and can be combined:

| Write | Meaning |
|---|---|
| `contents_sum < 5000`, `<=`, `>`, `>=` | numeric comparison |
| `alarm is yes`, `property_type is not flat` | equal / not equal |
| `a and b`, `a or b`, `not a` | combine conditions; `and` binds tighter than `or` |
| `( ... )` | group |
| `Contents selected` | the customer chose the optional cover Contents |
| `10% of contents_sum`, `contents_sum * 2`, `+ - /` | arithmetic, used in amounts |
| `return_date - departure_date` | the days between two dates |
| `work_date < retroactive_date`, `start is 2026-01-01` | dates compare like numbers |

Words available inside conditions: every input you declared, every choice value, every
cover name, and in claim rules `claimed` (the amount claimed) and any facts the claim asks
for. In renewal and claim rules `claims in term` is the number of paid claims this policy
year that count (see [claims](claims.md)). In claim rules `within N days of inception` and `within N
months of inception` are true when the loss is that soon after the policy first started.
