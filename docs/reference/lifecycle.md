---
title: lifecycle
parent: Language reference
nav_order: 8
---

# lifecycle

How the policy behaves after it is bought: cooling off, cancellation,
adjustment, lapse, instalments and renewal.

```ipn
lifecycle
  cooling off 14 days, full refund
  cancellation by customer: refund pro rata, fee 25
  cancellation by insurer: refund pro rata
  adjustment: reprice, charge pro rata difference, fee 10
  lapse when unpaid after 30 days
  instalments 12 monthly, charge 10%
  renewal
    invite 21 days before expiry
    increase capped at 20%
    decrease collared at 10%
    index contents_sum by 5%
    index previous_claims by claims in term
    decline when claims in term >= 3 because "Three or more claims in the year"
```

A product that simply ends, such as single-trip travel or term life, says
`renewal: none` instead of a `renewal` block. No invitation is made.

Policy status on any date is one of *quoted*, *bound* (before inception), *live*,
*lapsed*, *cancelled*, *expired* or *renewed* (a past policy year).

- **Cooling off**: cancelling within this many days of inception refunds the whole
  amount paid, fees included. The days are an expression, so a product sold in several
  territories takes them from a table: `cooling off days from "Territory" days, full refund`.
- **Cancellation** terms per party: `refund pro rata`, `full refund`, `no refund` or
  `refund <share>`, optionally `, fee N`. Pro rata refunds the earning premium (net plus
  taxes, never fees) for the unused days of the term, less the fee, never below zero. A
  party without a cancellation line cannot cancel. `refund <share>` returns that share of
  the earning premium, where the share is an expression that may use `days in force` and
  `months in force` (whole months since inception): a flat `refund 50%`, a formula such
  as `refund 100% - days in force / 365 * 100%`, or a short-rate table looked up by
  `refund refunded from "Short rate"` with the table `keyed on months in force`.
- **Adjustment** (mid-term change): the policy is repriced with the new answers and the
  difference in earning premium is charged pro rata for the remaining days, plus the fee.
  A negative result is a return premium. Write `adjustment: not allowed` to forbid it.
  After an adjustment the customer's annual premium is the new one. By default the
  repricing is on the version the policy is on: a mid-term change is an endorsement to the
  contract the customer holds. `adjustment: reprice on the current version, charge pro
  rata difference` instead moves the policy to the version live that day first (see
  [Versions](versions.md)); the changes are then written in that version's words and answer
  anything its `upgrading` asked for, and an unanswered `ask` refuses the adjustment with
  "adjustment needs x".
- **Lapse**: a policy bound but unpaid lapses after this many days until it is paid.
- **Instalments**: `instalments N monthly`, optionally `, charge P%`. The credit charge is
  that percentage of the premium, rounded; premium plus charge is split into N equal
  instalments to the penny, with the first taking any rounding so the schedule sums
  exactly. The `quote` command shows the schedule.
- **Renewal**: `index` lines first move the answers on: `by N%` for inflation of a sum
  insured, `by N` to add a fixed amount, such as a year of age, `by -N` to take one away.
  `, at least 0` and `, at most 9` keep the result within bounds, so a no claims discount
  grows to nine years and never falls below zero. The amount may be any expression over
  the expiring answers and `claims in term`, so `index previous_claims by claims in term`
  rolls the year's claims into the record the rating reads. `index item value by 5%`
  moves a field on every item. The offer is the product repriced on those answers, with
  any claims loading (see [claims](claims.md)) applied to the net before tax, then held within the
  cap and collar: no more than the premium charged for the current term plus the cap
  percentage, no less than it minus the collar percentage. `decline when` rules use the indexed answers and
  `claims in term`. Accepting a renewal starts a new term at expiry with the indexed
  answers and resets the claims count.
