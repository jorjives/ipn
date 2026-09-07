---
title: Scenarios
parent: Language reference
nav_order: 10
---

# Scenarios

```idl
scenario "Customer cancels mid term"
  given bike_value 2000, rider_age 22, security gold, racing no, previous_claims 0
  select Racing
  when bound on 2026-01-01
  when cancelled by customer on 2026-04-11
  expect refund 35.96
  expect status cancelled
```

`given` supplies every input except calculated ones; `select` chooses optional covers.
Repeatable items are given one per line using the singular name, with every field: `given
bike value 2000, age 0, security gold`, or all at once from a CSV beside the product with
the field names as its header: `given members from "members.csv"`. Dates are given as
`given departure_date 2026-07-10`.
Then `when` lines happen in order and `expect` lines check the state at that point.

Events:

| Event | Meaning |
|---|---|
| `when bound on DATE [unpaid]` | inception date; add `unpaid` to test lapse |
| `when paid on DATE` | payment received |
| `when accepted by underwriter on DATE [with load N%, discount N%, excess AMOUNT on Cover, excluding Cover, ...]` | the underwriter accepts a referred risk, on these terms |
| `when declined by underwriter on DATE` | the underwriter declines it; binding is then refused |
| `when reinstated Cover on DATE` | buys back an eroded aggregate limit; the charge is available to `expect additional premium` |
| `when cancelled by customer\|insurer on DATE` | cancellation; the refund is available to `expect refund` |
| `when adjusted on DATE with input value, input value` | mid-term change; in the words of the version it is priced on |
| `when adjusted on DATE adding bike value 500, age 1, security gold` | add an item |
| `when adjusted on DATE removing bike 2` | remove the second item |
| `when claim Cover [on bike N] [for AMOUNT] on DATE [reported DATE] [with item, fact value, ...]` | a loss on DATE, to item N if the cover is per item, notified on the reported date, with the listed evidence words and asked facts (`with death_certificate, cause suicide`); a fixed benefit claims no amount, so `for` may be left out |
| `when renewed on DATE [with input value, ...]` | accept the renewal offer (fails if it is declined); the new term is on the version live that day, and `with` answers what its `upgrading` asked for |

Expectations:

| Expectation | Checks |
|---|---|
| `expect eligible` / `expect referred ["reason"]` / `expect declined ["reason"]` | eligibility outcome |
| `expect cover Name [on bike N] included\|excluded\|"not selected"\|"not available" ["reason"]` | cover state, for item N if per item |
| `expect cover Name [on bike N] limit AMOUNT` | the resolved limit |
| `expect cover Name remaining AMOUNT`, `... remaining AMOUNT for condition "x"`, `expect cover Name on traveller 2 remaining AMOUNT` | what is left of an aggregate limit this term, for that condition or item |
| `expect cover Name excess remaining AMOUNT` | what the insured still bears of an aggregate excess this term |
| `expect net AMOUNT`, `expect premium AMOUNT` | net and total premium; once bound, the premium is what was charged for the term (capped or loaded at renewal, repriced by an adjustment) |
| `expect net for bike 2 AMOUNT` | one item's share of the net, before the steps after `for each` |
| `expect net for Theft AMOUNT`, `expect net for class 3 AMOUNT` | one cover's share of the net, or the total for the covers of that class (see [rating](rating.md#shares-by-cover)) |
| `expect tax Name AMOUNT`, `expect fee "Label" AMOUNT` | one line of the premium |
| `expect tax Name for Theft AMOUNT`, `expect tax Name for class 3 AMOUNT` | one cover's, or one class's, share of a tax line |
| `expect currency CODE` | the currency the risk is quoted in, from its territory |
| `expect commission "Label" AMOUNT` | that intermediary's share of the net |
| `expect commission "Label" for Theft AMOUNT`, `... for class 3 AMOUNT` | how much of that commission one cover, or one class, carries |
| `expect factor "Label" x 1.40` | what a factor applied |
| `expect status STATUS [on DATE]` | policy status, at the last event's date by default |
| `expect expiry DATE` | end of the current term |
| `expect refund AMOUNT` | refund from the last cancellation |
| `expect instalment charge AMOUNT`, `expect instalment N AMOUNT` | the credit charge and the Nth instalment on the premium as it stands |
| `expect refused ["reason"]` | the event just before was rightly refused (binding a declined or unaccepted referred risk, an adjustment when `adjustment: not allowed`, cancellation by a party with no terms) |
| `expect additional premium AMOUNT`, `expect return premium AMOUNT` | result of the last adjustment or reinstatement |
| `expect claim paid`, `expect claim declined ["reason"]`, `expect payout AMOUNT` | the last claim |
| `expect claims in term N` | paid claims this policy year |
| `expect benefit paid AMOUNT by DATE` | everything paid out on or before that date, whichever term the claims arose in |
| `expect renewal premium AMOUNT`, `expect renewal invite DATE`, `expect renewal offered`, `expect renewal declined ["reason"]` | the renewal offer as things stand |
| `expect renewal needs input[, input]` | the answers the new version's `upgrading` asks for before the renewal can be priced; `premium`, `offered` and `declined` fail while any are needed |
| `expect version DATE` | the `published` date of the version the policy is on |
| `expect <input> <value>` | an answer as the policy now holds it, after indexing at renewal, an upgrade or an adjustment: `expect bike_value 2100` |
