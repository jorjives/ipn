---
title: Design
nav_order: 8
---

# Design

Why the language is the shape it is, and the semantic decisions that a reader used to
other systems may find surprising. Each was made for a reason; where the reason was a real
product's wording, the example that proved it is linked.

## Principles

**The file is the product.** Everything a product is, from the questions asked to the
settlement of a claim, sits in one text file that an underwriter can read top to bottom.
There is no separate rating engine configuration, no rules table in a database, no
document that describes what the code does. The language reads like a policy wording on
purpose: `excess 10% of claim, minimum 50` and `decline when reported after 30 days
because "..."` are the sentences the wording already uses.

**The proof is in the same file.** A `scenario` gives the answers, plays the events in
order and says what must be true after each. Scenarios are written in the same language
by the same person, and `check` runs them in well under a second. A product with passing
scenarios is a product that does what its author said it does, and a rate change that
breaks one is caught before it is sold. This is also how a pricing team checks a reissued
table: the scenarios are the acceptance test for the spreadsheet.

**Nothing is silent.** A word the product does not know, a row that no cell matches, a
renewal that needs an answer, a dated line that reaches a version without the words to
read it: every one of these is an error with a line number, or a scenario failure that
says what the engine produced. There are no defaults that would let a risk price
wrongly rather than not at all.

**Deterministic to the penny.** Every figure is a `Decimal`, rounded half up to the
smallest unit of the risk's currency. Floating point is never used, so a premium is the
same on every machine and a scenario's `expect premium 93.97` is exact, not approximate.

**Extend by need, one construct at a time.** The language grew by writing real products
against it and adding a construct only where a line's wording could not be expressed:
the aggregate limit came from professional indemnity, the waiting period from pet, the
benefit paid month by month from income protection, `in force from` from travel. Each
addition is one feature, proven by one scenario, in one commit.

## Semantics that matter

These are the decisions most likely to differ from what another system does. They are all
deliberate.

| Decision | Why |
|---|---|
| **The order of `pays` clauses is the order applied.** `up to limit, less excess` caps then deducts; `less excess, up to limit` deducts then caps. | A sum insured caps the loss before the excess comes off; a liability or aggregate limit caps what the insurer pays after it. Both wordings exist, and writing the clauses in the wording's order keeps the file honest. See [professional indemnity](examples/pi.md). |
| **Rating steps run in the order written.** | The premium calculation is a procedure the pricing team owns; the file shows it as one. A `minimum` before a `discount` floors before discounting; after it, the other way round. |
| **Tax is charged on the rounded net.** | That is how the amount on the schedule is reached: the net is a figure the customer sees, and the tax is a percentage of that figure. |
| **Fees never refund**, except in cooling off. | An administration fee is earned on day one. Cooling off returns everything because the contract is treated as never made. |
| **A percentage excess is of the amount claimed, before depreciation.** | The wording says "10% of the claim"; the claim is what was claimed. |
| **A claim that comes to nothing after the excess is declined, not paid 0.** | Paying nothing would still count as a claim and could step back a no claims discount. It is declined as "nothing is payable after the excess" and does not count. |
| **Only paid claims that count go towards `claims in term`; every paid claim erodes an aggregate limit.** | Glass and non-fault motor claims should not load the renewal, but they still spend the limit. See [private motor](examples/motor.md). |
| **The claims loading applies to the renewal net, before tax; fees are not loaded.** | Insurers load the premium, not the fixed fee, and tax follows the loaded net. |
| **After a capped or loaded renewal, `premium` is what was charged, not the re-rated figure.** | Refunds and the next renewal's cap work from what the customer paid. An adjustment resets it to the new annual premium. |
| **Waiting periods and `within N months of inception` run from the first inception, not the latest renewal.** | Renewing does not restart a waiting period; a suicide clause counts from the day cover first began. See [pet](examples/pet.md) and [life](examples/life.md). |
| **Pro rata is by days**, over the term's actual days. | A leap year has 366; the refund says so. |
| **Instalments sum exactly.** The credit charge is rounded, the total is split to the penny, and the first instalment takes the rounding. | A schedule that is a penny out is a customer complaint. |
| **`territory` decides the currency; the product does not.** | A product sold in four countries is one file with a table keyed on territory, not four copies. See [gadget](examples/gadget.md). |
| **A missing table cell is an error, never a default.** | A typo in a hundred-thousand-row spreadsheet must not be a row that quietly never matches. Cells are also type-checked against their input when the file is read. |
| **Interpolation is between knots only; outside them is an error.** | A curve is not a licence to extrapolate. |

## Versions

A product changes. The decisions here were agreed in discussion and are recorded in
full in the [versions design spec](https://github.com/jorjives/open-idl/blob/main/docs/superpowers/specs/2026-09-07-product-versions-design.md).

- **No version numbers.** A version is the date it went on sale. Which version a policy is
  on is "the one live when it incepted or last renewed", which is how insurers already
  think. Any compatibility class is derived by the tool, never declared.
- **Upgrade mappings are language, in expressions.** How an old answer becomes a new one
  is underwriting knowledge, so it lives in the file and is proven like everything else.
- **`ask` is the signal that a policy cannot move by itself.** Whether a renewal can
  proceed unattended is decided per policy, when the upgrade runs, not per version. Most
  of a book rolls over; the few that need an answer are named.
- **Mid-term changes are dated amendments, not versions.** A `from DATE` line reaches every
  policy in force, whichever version it is on, because those customers are the ones it
  must reach. It is written once, in the latest version, and must read in the words of
  every version it reaches.
- **The history is a directory of files.** Where the files come from (git, a folder) is
  the managing engineer's concern, not the language's.

## What was considered and left out

- **YAML or JSON** as the surface syntax: quoting noise and `key: value` nesting defeat
  the goal of reading like a wording. The expression sub-language is needed either way.
- **A general-purpose scripting language** embedded for rating: it would let a product say
  anything, including things an underwriter cannot read. Every construct here is a sentence
  an underwriter would write.
- **Version numbers and semantic versioning**: a class of change is a property of two
  files, derivable by a tool; declaring it invites it to be wrong.
- **Multi-currency on one policy, more than one product per file, a named settlement basis
  (new-for-old versus indemnity)**: each is a small addition; none was needed by a real
  line yet. They are listed under [not yet supported](reference/not-yet-supported.md).

## The reference engine

The engine that runs the scenarios is a Python 3.12 package with no dependencies, so the
proof needs nothing installed beyond Python. It is a parser (text to a `Product` of plain
dataclasses), an evaluator for the expression language, an engine that applies a product
to a risk through eligibility, cover, rating, the lifecycle and claims, and a scenario
runner. It is deliberately small: around four thousand lines, read in an afternoon. The
[contributing](contributing.md) page describes how to extend it.
