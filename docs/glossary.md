---
title: Glossary
nav_order: 9
---

# Glossary

The insurance words the language uses, for readers who write code, and the language's own
words, for readers who write products.

## Insurance terms

| Term | Meaning here |
|---|---|
| **Adjustment** | A mid-term change to the policy (an endorsement): new answers, a repriced premium, and the difference charged or returned pro rata. |
| **Aggregate limit** | The most the insurer pays on a cover across the whole term, eroded by each paid claim. Written `limit X per term`. |
| **Bind, bound** | The moment the contract is made. A bound policy goes live on its inception date. |
| **Claims-made** | Cover that responds to claims *made* during the term (for work done after the retroactive date), as opposed to losses *occurring* during it. Professional indemnity is claims-made. |
| **Co-payment** | A share of a claim the customer bears, usually a percentage. Common in pet cover for older animals. |
| **Collar** | A floor on how far a renewal premium may fall against the expiring one. |
| **Class** | The regulatory class a cover reports under (fire, damage to vehicles, other damage to property). Written `class 8` on the cover; the engine carries each class's share of every figure. |
| **Commission** | The intermediary's share of the net premium. Reported, never added to the price. |
| **Cooling off** | A period after inception in which the customer may cancel for a full refund. |
| **Deductible** | The commercial-lines word for an excess. The language accepts both. |
| **Depreciation** | Scaling a claim down for the age of the thing lost. Written as a table, like a rating factor. |
| **Earning premium** | The part of the premium that is earned over the term: the net plus taxes. Fees are earned at once and are not part of it. |
| **Eligibility** | Whether the insurer will quote at all: *eligible*, *referred* to an underwriter, or *declined*. |
| **Enrichment** | Data the product needs but does not ask the customer for: a postcode's risk, a vehicle's group. The language declares its shape only. |
| **Excess** | The first part of every claim, borne by the customer. Flat, a percentage with a floor and cap, a table by circumstance, or `per term` as an aggregate. |
| **Fixed benefit** | A claim that pays a stated sum on an event (a death, an accident) rather than making a loss good. Written `pays sum_assured`. |
| **Inception** | The date cover starts. |
| **Indemnity** | Making a loss good, no more: the claimed amount, capped and less the excess. |
| **Index** | Moving an answer on at renewal: a sum insured up by inflation, an age up by a year. |
| **Instalments** | Paying the premium monthly, with a credit charge. |
| **IPT** | Insurance premium tax, a percentage of the net premium, in the UK. Other territories have their own; the language calls any of them `tax`. |
| **Lapse** | A bound policy that was never paid for, after the grace period. |
| **Limit** | The most the insurer pays on a claim (or, `per term`, across the term). |
| **Load, loading** | A percentage increase to the premium: for a smoker, for claims, for an underwriter's view of the risk. |
| **Net premium** | The price of the risk before tax and fees. What the rating steps produce; in a product with classes, the sum of the covers' shares. |
| **No claims discount (NCD)** | Years without a claim, earning a discount that steps back after a fault claim unless protected. |
| **Pro rata** | In proportion to the days left in the term. |
| **Referral** | A risk the product cannot decide by itself; an underwriter accepts it (perhaps on terms: a load, an excess, a cover withdrawn) or declines it. |
| **Reinstatement** | Buying back an eroded aggregate limit for the rest of the term. |
| **Retroactive date** | On a claims-made policy, the earliest date of work that is covered. |
| **Run-off** | Claims-made cover bought when a practice closes, for claims that arrive later about work already done. |
| **Short-rate** | A cancellation refund on a scale that returns less than pro rata, by months in force. |
| **Sum insured, sum assured** | The amount the customer is covered for (general insurance) or will be paid (life). |
| **Term** | One policy period. Twelve months for most products; years for life; until the return date for travel. |
| **Share** | One cover's part of the net, of a tax or of a refund. Built up by `for Cover` on a step, a cover's own `premium`, and `allocate` for the rest; rounded with the odd cent to the largest. |
| **Territory** | Where the product is sold. Decides the currency and, in a table, the tax and loadings. |
| **Waiting period** | Days after first inception during which a loss is not covered. Pet illness cover has one. |

## The language's own words

| Word | Meaning |
|---|---|
| **Block** | A keyword on a line of its own with lines indented beneath it: `product`, `inputs`, `cover`, `rating` and so on. |
| **Allocate** | The key in `rating` that shares the premium no step credited to a cover, by percentages summing to 100. |
| **Calculated** | An input or item field worked out from the others by steps, never asked. |
| **Collection, item** | A repeatable input (`bikes`) and one of its members (`bike`), each with fields. |
| **Dated line** | A cover or claim line beginning `from DATE` or `until DATE`: a mid-term amendment reaching every policy in force. |
| **Fact** | Something a claim `asks` for that is only known when the claim is made: the cause, who was driving. |
| **Cover premium** | A price written on the cover itself (`premium 0.5% of value`), joined to the net where `rating` says `add cover premiums`. |
| **Factor** | A rating step with rows of `condition: x N`; the first matching row applies. |
| **Line** | A `tax`, `fee` or `commission` step: an amount on top of, or reported against, the net as it stands where the line is written. |
| **History** | A product's versions: the `.idl` files in one directory that declare the same product name. |
| **Published** | The date a version went on sale, and its only identity. |
| **Scenario** | A proof: `given` answers, `select`ed covers, `when` events in order, and `expect`ations after each. |
| **Trail** | The list of rating steps applied to a risk and the running net after each, as `quote` prints it. |
| **Upgrading** | The block that says how the previous version's answers become this version's, including `ask`. |
| **Version** | One `.idl` file of a product with a `published` date. A policy stays on its version until it renews. |
