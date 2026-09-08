---
title: Versions
parent: Language reference
nav_order: 11
---

# Versions

A customer stays on the version of a product they bought until it renews. A version is
identified by the date it went on sale, `published 2026-07-01` in the `product` block; there
are no version numbers. The other versions of a product are the `.ipn` files in the same
directory that declare the same product name. `check` finds them itself, and a file sees
only the versions published on or before its own date, so a proof written in an old version
stays true when new ones are published. See [`examples/versioned/`](../examples/bike-versioned.md).

- The version **live** on a date is the one with the latest `published` on or before it.
  `when bound on DATE` binds under that version; binding before the first version is
  refused with "no version of X was on sale on DATE".
- A scenario that binds before the file's own `published` date is on an earlier version,
  so its `given` is written in that version's words and checked when it runs.
- **Renewal** moves the policy to the version live on the first day of the new term. The
  expiring version's `index` lines move the answers on, then the answers are carried to the
  new version, then the new version prices them, with the claims loading, cap and collar
  as usual. The cap and collar hold against the premium charged for the expiring term,
  whichever version charged it.
- An answer is **carried** when the new version has an input of the same name and
  compatible type: the same kind, a choice that still lists every old value, a collection
  whose fields carry likewise. A new input takes its `default`. A new input with neither is
  an error when the history loads: "x is new in the version published DATE; add it to
  upgrading, or give it a default". Inputs the new version dropped are left behind.
  Calculated and enrichment-provided values are recomputed, `territory` is carried, and
  free text is optional as everywhere.

## upgrading

When carrying is not enough, the `upgrading` block says how this version's answers are
derived from the previous version's. Every word on the right-hand side is an input, item
field or choice value of the **previous** version (the one published immediately before
this file), or a choice value of the input being set. There is no `previous` keyword: the
right-hand side always reads the old answers, even when the name is kept.

```ipn
upgrading
  lock_rating
    security is gold: gold
    security is silver: silver
    otherwise: ask
  total_value: bike_value + accessories_value
  racing: no
  bikes: for each bike
    lock: high when security is gold, otherwise low
```

- `input: <expression>` gives one value; `input: <value> when <condition>, <value> when
  <condition>, otherwise <value>` gives cases on one line; the block form is rows of
  `condition: value` ending in `otherwise: value`, the same shape as a `factor`. A
  conditional value must end in `otherwise`, so no policy is left without an answer.
- `ask` as a value means the customer must answer: the renewal **needs** that input before
  it can be priced (see [`expect renewal needs`](scenarios.md)). `otherwise: ask` asks only the policies
  that reach that row, so most of a book rolls over unattended and a few are asked.
- `collection: for each <old item>` upgrades every item; the lines below use the old
  item's fields and the old answers, fields not mentioned carry by name, and the
  collection may be renamed. An asked item field is reported as `bike.lock`.
- A word the previous version does not know, a row block without `otherwise`, or a bare
  word that is neither an old input nor a choice of the target is an error when the
  history loads, with the line. A value the target cannot hold (`lock_rating` given
  `gold` when its choices are `low, high`) fails the renewal with "lock_rating cannot be
  'gold'; it is a choice of low, high".
- Across several versions the blocks chain in publication order. An `ask` at one step
  leaves that answer unknown, and any later expression that reads it is unknown too; what
  the renewal needs is whatever is still unknown at the end.

## Dated lines: mid-term amendments

A change that must reach policies already in force is an amendment with an effective
date, written inside the current version rather than as a new one. Any line inside a `cover` block or a `claim` block may
begin with `from DATE`, `until DATE`, or both:

```ipn
cover Theft
  limit bike_value
  from 2027-03-01 limit 2 * bike_value
  until 2027-03-01 excludes when racing is yes because "Racing was excluded until March 2027"

claims
  claim Theft
    pays claimed amount up to limit, less excess
    requires crime_reference
    from 2027-03-01 requires crime_reference, lock_photo
```

- A dated line is in effect for an event on or after its `from` date and before its
  `until` date. A claim is settled on the wording in force at the loss; `expect cover` reads
  the wording at the last event's date, and with no event yet, or from the `quote` command,
  only undated lines apply.
- A setting with one value (`limit`, `excess`, `pays`, `available when`, `waiting period`,
  `requires`, `depreciation`, `counts`) is **replaced** by the dated line in effect; the
  undated line covers the other dates. A setting that is a list (`excludes`, `decline`,
  `co-payment`) **accumulates**: every line in effect applies. Two dated lines for one
  setting whose windows overlap are an error: "limit is given twice for DATE".
- Dated lines are checked like any other, in every window they create. `asks` cannot be
  dated, and `rating`, `eligibility` and `lifecycle` lines cannot be dated at all: the
  premium charged for the term already stands and eligibility is settled at purchase.
- The words a dated line may use are the words its block may use: a cover line reads the
  answers, a claim line also reads the facts the claim asks for.
- **An amendment reaches every version in force.** A dated line written in one version also
  amends the same cover or claim in every earlier version (a policy bought on the January
  version is settled with a `from` line written in July), because the customers on the old
  version are the ones it must reach. Write it once, in the latest version. It must
  therefore read in the words of every version it reaches: a dated line naming an input or
  fact an earlier version never asked for is refused at load with "'word' is not known to
  the version published DATE, which this amendment reaches". A version's own undated lines
  are its own; only dated lines travel.
