---
title: Getting started
nav_order: 3
---

# Getting started

The fastest way to see a product check itself is the [playground](playground.md):
Home contents is already loaded. Change an `expect` line, press Check. Nothing
to install.

Then write a small contents product of your own, in the same playground.

## Write a product

Make a file called `contents.ipn` (or paste it into the playground) with a
product, its questions, one cover, a price, and a scenario that says what the
price should be:

```ipn
product "Home Contents"
  territory UK
  term 12 months

inputs
  contents_sum: money
  property_type: choice of detached, semi, terrace, flat

cover Contents
  limit contents_sum
  excess 100

rating
  base 0.5% of contents_sum
  tax IPT 12%

scenario "A terrace of 20,000"
  given contents_sum 20000, property_type terrace
  expect net 100.00
  expect premium 112.00
```

Press Check.

```check
PASS A terrace of 20,000
Home Contents: 1 passed, 0 failed
```

### Add eligibility and a rating factor

Add an `eligibility` block, a `factor` on the property type, and two scenarios
for them. The factor's rows are tried in order and the first that holds applies.

```ipn
eligibility
  decline when contents_sum < 5000 because "The minimum sum insured is 5,000"
  refer when contents_sum > 150000 because "Sums over 150,000 need a high net worth policy"

rating
  base 0.5% of contents_sum
  factor "Property type"
    property_type is detached: x 1.10
    otherwise: x 1.00
  tax IPT 12%

scenario "A detached house pays more"
  given contents_sum 20000, property_type detached
  expect factor "Property type" x 1.10
  expect premium 123.20

scenario "Under the minimum is declined"
  given contents_sum 4000, property_type terrace
  expect declined "The minimum sum insured is 5,000"
```

```check
PASS A terrace of 20,000
PASS A detached house pays more
PASS Under the minimum is declined
Home Contents: 3 passed, 0 failed
```

### See a failure

Change the detached house's expected premium to `100.00` and check again:

```check
PASS A terrace of 20,000
FAIL A detached house pays more
     line 33: expected premium 100.00, got 123.20
PASS Under the minimum is declined
Home Contents: 2 passed, 1 failed
```

A failure names the line and says what the engine produced. Put the number back
before going on.

### Add the lifecycle and claims

The `lifecycle` block says how the policy behaves after it is bought; the
`claims` block says what a claim needs and how it is paid. Scenarios can now
play events in order with `when`, and check the state after each.

```ipn
lifecycle
  cooling off 14 days, full refund
  cancellation by customer: refund pro rata, fee 20
  cancellation by insurer: refund pro rata
  adjustment: reprice, charge pro rata difference
  renewal
    invite 21 days before expiry
    increase capped at 20%
    index contents_sum by 5%

claims
  claim Contents
    requires police_report
    pays claimed amount up to limit, less excess
    decline when reported after 30 days because "Theft must be reported within 30 days"

scenario "Cancelling half way through refunds half, less the fee"
  given contents_sum 20000, property_type terrace
  when bound on 2026-01-01
  when cancelled by customer on 2026-07-02
  # 183 of 365 days unused: 112.00 x 183/365 = 56.15, less the 20 fee
  expect refund 36.15
  expect status cancelled

scenario "Renewal indexes the sum insured"
  given contents_sum 20000, property_type terrace
  when bound on 2026-01-01
  expect premium 112.00
  expect renewal premium 117.60

scenario "Theft pays the claim less the excess"
  given contents_sum 20000, property_type terrace
  when bound on 2026-01-01
  when claim Contents for 800 on 2026-05-01 with police_report
  expect claim paid
  expect payout 700.00

scenario "A theft reported late is declined"
  given contents_sum 20000, property_type terrace
  when bound on 2026-01-01
  when claim Contents for 800 on 2026-05-01 reported 2026-06-15 with police_report
  expect claim declined "Theft must be reported within 30 days"
```

```check
PASS A terrace of 20,000
PASS A detached house pays more
PASS Under the minimum is declined
PASS Cancelling half way through refunds half, less the fee
PASS Renewal indexes the sum insured
PASS Theft pays the claim less the excess
PASS A theft reported late is declined
Home Contents: 7 passed, 0 failed
```

The renewal scenario holds because `index contents_sum by 5%` moves the sum to
21,000, the base becomes 105, and IPT follows.

## Where next

- Price a sample book, change a rate, and see who moves, on
  [Price a book](book.md). A book whose risks carry specified items, drivers or
  members is a second CSV joined on `risk`, shown on the same page.
- Start a real product from a [template](templates/index.md): each is a working
  file with comments that say what to change.
- Read the [reference](reference/index.md) block by block, or find the construct
  you need in a product like yours among the [examples](examples/index.md).
- When the product changes, put the new version beside the old with a
  `published` date; see [Versions](reference/versions.md).

## On your machine

To run the same checks locally, clone the repository and use the reference
engine. That path, and how to embed the engine in a platform, is under
[For engineers](engineers.md).
