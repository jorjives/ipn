---
title: Language reference
nav_order: 3
has_children: true
has_toc: false
---

# Language reference

Open IDL describes an insurance product in one plain text file: what you ask the
customer, who you will and will not insure, what is covered, how it is priced, how the
policy behaves from purchase to renewal, and how claims are paid. You then prove the
product does what you meant by writing *scenarios* in the same file and running:

```sh
python3 -m ideclare check my-product.idl
```

Every scenario prints `PASS` or `FAIL`, and every failure says which line disagreed and
what the engine actually produced. The [command line](../cli.md) page covers `check`,
`quote` (price one risk) and `batch` (price a book).

## The shape of a file

A file is a sequence of blocks. Each block is a keyword on its own line with its lines
indented beneath it. The `product` block comes first; the others may follow in any order,
except that a block which names something must come after the block that declares it
(an `eligibility` rule that says `Racing selected` comes after `cover Racing`).

| Block | What it declares |
|---|---|
| [`product`](product.md) | the name, where it is sold, the term, and when this version was published |
| [`inputs`](inputs.md) | the questions asked at quote, their types, repeatable items and calculated values |
| [`enrichment`](enrichment.md) | the shape of external lookups (postcode risk, a vehicle catalogue) the product depends on |
| [`table`](table.md) | rating tables in long CSV form, inline or from a file, with bands, wildcards and interpolation |
| [`eligibility`](eligibility.md) | who is declined and who is referred to an underwriter |
| [`cover`](cover.md) | each section of cover: limit, excess, exclusions, optionality, aggregates, dates in force, its class and its own premium |
| [`rating`](rating.md) | the premium calculation, step by step, in the order written; tax, fee and commission lines on any base; the net split by cover |
| [`lifecycle`](lifecycle.md) | cooling off, cancellation, mid-term adjustment, lapse, instalments and renewal |
| [`claims`](claims.md) | what a claim needs, how it is settled, and what a paid claim changes |
| [`scenario`](scenarios.md) | a proof: answers, events in order, and what must be true after each |
| [`upgrading`](versions.md) | how a previous version's answers become this version's |

The [grammar](grammar.md) page gives the same language formally, and
[not yet supported](not-yet-supported.md) lists the known gaps. Every construct on these
pages is exercised by at least one [example product](../examples/index.md) whose scenarios
pass.

## Writing conventions

- Indent with two spaces to put a line inside the block above it.
- One statement per line. Anything after `#` is a comment.
- Names of inputs are single words joined with underscores: `bike_value`, `rider_age`.
- Cover names, labels and reasons that contain spaces go in double quotes: `"Accidental Damage"`.
- Money and numbers are written plainly: `2000`, `3.5`, `12%`. Dates are `2026-01-31`.
- Words that stand for the same thing may be singular or plural where English wants it:
  `after 1 claim in term`, `after 2 claims in term`.
- The file starts with the `product` block. The other blocks can come in any order.

## Conditions

Many lines take a condition after `when`. A condition compares inputs and other known
values and can be combined:

| Write | Meaning |
|---|---|
| `rider_age < 25`, `<=`, `>`, `>=` | numeric comparison |
| `security is gold`, `security is not gold` | equal / not equal, also `racing is yes` |
| `a and b`, `a or b`, `not a` | combine conditions; `and` binds tighter than `or` |
| `( ... )` | group |
| `Racing selected` | the customer chose the optional cover Racing |
| `10% of bike_value`, `bike_value * 2`, `+ - /` | arithmetic, used in amounts |
| `return_date - departure_date` | the days between two dates |
| `work_date < retroactive_date`, `start is 2026-01-01` | dates compare like numbers |

Words available inside conditions: every input you declared, every choice value, every
cover name, and in claim rules `claimed` (the amount claimed) and any facts the claim asks
for. In renewal and claim rules `claims in term` is the number of paid claims this policy
year that count (see [claims](claims.md)). In claim rules `within N days of inception` and `within N
months of inception` are true when the loss is that soon after the policy first started.
