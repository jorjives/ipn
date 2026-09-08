---
title: Getting started
nav_order: 2
---

# Getting started

Twenty minutes: install nothing, run the examples, then write a small product of your own
and prove it.

## Install

You need Python 3.12 or later and nothing else. Clone the repository and run the tests:

```sh
git clone https://github.com/jorjives/open-idl.git
cd open-idl
python3 -m unittest
```

The reference engine is the `ipngine` package in the repository. Every command below is
`python3 -m ipngine ...` run from that directory.

## Run an example

```sh
python3 -m ipngine check examples/cycle.ipn
```

```check
PASS Standard rider is eligible
PASS Under 16 is declined
PASS Heavy claims history is referred
...
PASS Depreciation: an older bike is settled at 85% before the excess
Cycle Cover: 35 passed, 0 failed
```

Open [`examples/cycle.ipn`](examples/cycle.md) beside the output. Each `scenario` at the
bottom of the file is one of those lines, and the scenarios above the lifecycle ones are
commented with the arithmetic. Every example on this site runs the same way.

## Write your first product

Make a file called `camera.ipn` with a product, its questions, one cover, a price, and a
scenario that says what the price should be:

```ipn
product "Camera Cover"
  territory UK
  term 12 months

inputs
  camera_value: money
  owner_age: integer

cover Theft
  limit camera_value
  excess 75

rating
  base 5% of camera_value
  tax IPT 12%

scenario "A camera worth 1,000"
  given camera_value 1000, owner_age 30
  expect net 50.00
  expect premium 56.00
```

```sh
python3 -m ipngine check camera.ipn
```

```check
PASS A camera worth 1,000
Camera Cover: 1 passed, 0 failed
```

That is a complete, proven product: a question, a cover, a price with tax, and a scenario
that holds it to the number you meant.

### Add eligibility and a rating factor

Add an `eligibility` block, a `factor` on the owner's age, and two scenarios for them.
The factor's rows are tried in order and the first that holds applies.

```ipn
eligibility
  decline when owner_age < 18 because "Owners must be 18 or over"
  refer when camera_value > 10000 because "Cameras over 10,000 need an underwriter"

rating
  base 5% of camera_value
  factor "Owner age"
    owner_age < 25: x 1.30
    otherwise: x 1.00
  tax IPT 12%

scenario "A young owner pays more"
  given camera_value 1000, owner_age 22
  expect factor "Owner age" x 1.30
  expect premium 72.80

scenario "Under 18 is declined"
  given camera_value 1000, owner_age 17
  expect declined "Owners must be 18 or over"
```

```check
PASS A camera worth 1,000
PASS A young owner pays more
PASS Under 18 is declined
Camera Cover: 3 passed, 0 failed
```

### See a failure

Change the young owner's expected premium to `65.00` and run `check` again:

```check
PASS A camera worth 1,000
FAIL A young owner pays more
     line 33: expected premium 65.00, got 72.80
PASS Under 18 is declined
Camera Cover: 2 passed, 1 failed
```

A failure names the line and says what the engine produced. The exit status is 1, so a
failing product cannot get through a pipeline. Put the number back before going on.

### Add the lifecycle and claims

The `lifecycle` block says how the policy behaves after it is bought; the `claims` block
says what a claim needs and how it is paid. Scenarios can now play events in order with
`when`, and check the state after each.

```ipn
lifecycle
  cooling off 14 days, full refund
  cancellation by customer: refund pro rata, fee 10
  cancellation by insurer: refund pro rata
  adjustment: reprice, charge pro rata difference
  renewal
    invite 21 days before expiry
    increase capped at 20%
    index owner_age by 1

claims
  claim Theft
    requires police_report
    pays claimed amount up to limit, less excess
    decline when reported after 30 days because "Theft must be reported within 30 days"

scenario "Cancelling half way through refunds half, less the fee"
  given camera_value 1000, owner_age 30
  when bound on 2026-01-01
  when cancelled by customer on 2026-07-02
  # 183 of 365 days unused: 56.00 x 183/365 = 28.08, less the 10 fee
  expect refund 18.08
  expect status cancelled

scenario "A young owner's renewal at 25 loses the loading"
  given camera_value 1000, owner_age 24
  when bound on 2026-01-01
  expect premium 72.80
  expect renewal premium 56.00

scenario "Theft pays the claim less the excess"
  given camera_value 1000, owner_age 30
  when bound on 2026-01-01
  when claim Theft for 800 on 2026-05-01 with police_report
  expect claim paid
  expect payout 725.00

scenario "A theft reported late is declined"
  given camera_value 1000, owner_age 30
  when bound on 2026-01-01
  when claim Theft for 800 on 2026-05-01 reported 2026-06-15 with police_report
  expect claim declined "Theft must be reported within 30 days"
```

```check
PASS A camera worth 1,000
PASS A young owner pays more
PASS Under 18 is declined
PASS Cancelling half way through refunds half, less the fee
PASS A young owner's renewal at 25 loses the loading
PASS Theft pays the claim less the excess
PASS A theft reported late is declined
Camera Cover: 7 passed, 0 failed
```

Notice what the renewal scenario proves: `index owner_age by 1` moves the owner to 25, the
factor's first row no longer holds, and the loading falls away by itself.

## Price a risk

`quote` prices one risk and prints the trail, step by step:

```sh
python3 -m ipngine quote camera.ipn camera_value=1000 owner_age=22
```

```
Eligibility: eligible
  Theft: included, limit 1000.00
Premium:
  base                      50.00  = 50.00
  Owner age                x 1.30  = 65.00
  net                              = 65.00
  IPT                              + 7.80
  total                            = 72.80 GBP
```

`batch` does the same for a CSV of risks, one row each. See the
[command line](cli.md) page.

## Where next

- No install at all: the [playground](playground.md) runs `check` in your browser on any of the
  examples, or on what you type.
- Start a real product from a [template](templates/index.md): each is a working file with
  comments that say what to change.
- Read the [reference](reference/index.md) block by block, or find the construct you need
  in a product like yours among the [examples](examples/index.md).
- When the product changes, put the new version beside the old with a `published` date;
  see [Versions](reference/versions.md).
