# Production review: gaps in iDeclare for real lines at scale

Date: 2026-09-06. Autonomous run; Jorj was not available to answer questions, so each
decision below is recorded with its reasoning. The brief: review the language, its
structure and what it allows, against what a production environment modelling real
insurance across industries and lines would need, with complex use cases and large data
in mind; then design, build and prove a solution for every item that can be addressed.

## Method

Read every module and example, ran the suite (236 tests, 13 example products, all green),
then walked each block of the language asking two questions: what would an underwriter,
pricing actuary or claims handler on a real line be unable to say, and what would break or
mislead when the product or its data is large. Findings are grouped as *defects* (the
engine does something a real insurer would call wrong), *gaps* (a common need with no
way to write it) and *scale* (fine at 300 rows or 3 items, not at 100,000 or 5,000).

## Findings and decisions

### Defects (tidy first)

| # | Finding | Decision |
|---|---|---|
| D1 | An excess table with no `otherwise` row silently gives a zero excess when no row matches. A missing row on a money path must be loud. | Parse error: an excess table must end with `otherwise`. |
| D2 | A claim on a cover whose limit or excess uses item fields, made without `on <item> N`, fails with a Python type error reported as "do not understand". | Decline with the reason `<Cover> is per <item>; say which <item> the claim is on`. |
| D3 | Eligibility cannot see the selected covers, so `refer when "Winter Sports" selected and age > 70` is unwritable. | `check_eligibility` takes the selection; scenarios and the CLI pass it. |
| D4 | A claim that comes out at nothing after the excess is recorded as *paid* 0.00 and counts towards `claims in term`, so a 40 scratch on a 100 excess would step back a no claims discount. | Declined with the reason `nothing is payable after the excess`; it does not count. |
| D5 | `after N claims in term: renewal load x M` multiplies the whole renewal total, fees included. Insurers load the premium; a fixed fee is not loaded and tax follows the loaded net. | The loading is applied as a final `load` step on the net, so tax is on the loaded net and fees are unchanged. No example changes value (the cycle case is held by its cap; the others have no fee). |
| D6 | After a capped or loaded renewal is accepted, `expect premium` and a later cancellation refund use the re-rated price, not the price the customer actually paid. | The policy remembers the premium charged for the current term; `premium` and refunds work from that. |

### Gaps in the language

| # | Finding | Decision |
|---|---|---|
| G1 | **Short-rate cancellation.** Commercial lines and many personal lines refund by a short-rate scale, not pro rata, and often keep a minimum earned premium. | `cancellation by customer: refund <amount>` where the amount is an expression that may use `days in force` and `months in force`, so it can be a flat `refund 50%` or a lookup `refund retained from "Short rate"`. Table cells may be written as `80%`. |
| G2 | **Instalments.** Nearly every personal-lines product is sold monthly with a credit charge. | `instalments 12 monthly, charge 8%` in the lifecycle. The schedule is deterministic: the charge is a percentage of the total, each instalment is the rounded twelfth, the first absorbs the rounding. `expect instalment N AMOUNT` and `expect instalment charge AMOUNT`. |
| G3 | **Commission.** Brokers, MGAs and affinity schemes need the split of the net to be part of the product. | `commission "Broker" 15%` in rating: a reported line of the net, never added to the total. `expect commission "Broker" AMOUNT`. |
| G4 | **Aggregate limits per something.** Pet cover has a limit per condition per year; travel has a limit per traveller; liability has per claimant. Today an aggregate is per policy only. | `limit X per term per condition` (an asked fact) and `limit X per term per traveller` (an item). Each paid claim erodes the bucket it belongs to. `expect cover Name remaining AMOUNT for condition "x"` / `on traveller 2`. |
| G5 | **Conditions on imposed terms.** Protected no claims discount is an add-on that switches the step-back off, and some products load only when the claims were at fault. | `after N claims in term [unless <condition>]` and `after N claims in term: renewal load x M [unless <condition>]`, so `unless "Protected NCD" selected` reads as the wording does. |
| G6 | **Rolling claims history forward.** `previous_claims` is an input that never moves at renewal, so a renewed policy is rated as if the year were claim-free. | `index <input> by <expression>` where the expression may use `claims in term`: `index previous_claims by claims in term`. |
| G7 | **Excess ceiling and vocabulary.** A percentage excess is usually bounded on both sides, and outside the UK the word is deductible. | `excess 10% of claim, minimum 50, maximum 500`; `deductible` accepted wherever `excess` is, including `less deductible`. |
| G8 | **Fixed benefits still need `for 0`** in a claim event. | `when claim Death on DATE ...` with no `for` means a claim for nothing. |

### Scale

| # | Finding | Decision |
|---|---|---|
| S1 | `Table.lookup` scans every row on every evaluation. A postcode-sector by vehicle-group table of 100,000 cells makes a single quote a multi-second scan, and a policy does several evaluations per event. | Each key column is indexed on its exact-valued cells at load; rows whose cell is a band or `*` are the only ones scanned. Lookup cost follows the number of candidate rows, not the table. Proven on a 100,000-row table. |
| S2 | Table cells are never checked against the key's type, so a typo (`glod`, `Yes`, `17 -20`) in a big spreadsheet is a row that silently never matches. | At load, a cell in a `choice` column must be one of the choices or `*`; in a `yes/no` column `yes`, `no` or `*`; in a numeric column a number, band or `*`. |
| S3 | A group scheme of thousands of members cannot be written as `given member ...` lines, and the `quote` command cannot take items at all. | `given members from "members.csv"` in a scenario and `members=members.csv` on the command line, the CSV's columns being the fields. |
| S4 | There is no way to price a book. Impact analysis of a rate change over 100,000 policies is the everyday job of a pricing team. | `python3 -m ideclare batch product.idl risks.csv` reads one risk per row and writes one row per risk: eligibility, reasons, net, every tax, fee and commission line, total. Rows that are off the table are reported in place, never dropped. |

### Considered and deliberately not built

- **Multi-currency, more than one product per file, bundles.** Out of the language's stated scope; nothing in a single line's wording needs it.
- **Run-off cover after a claims-made policy ends.** A separate product (a run-off policy) in practice; the retroactive date mechanism already exists for the incoming side.
- **A benefit paid across policy years.** Needs a claim to have a life of its own beyond the term; a large change to the claim model for one line. Recorded as the next gap.
- **`is one of a, b, c`.** Commas are the stop token in most statements, so the list form fights the grammar; `or` says the same thing.
- **Input defaults.** Would let the `quote` command skip answers, but a product should ask what it needs; a default is a product decision that belongs in `calculated`.
- **Reinstatement of an eroded aggregate on payment of a premium**, **aggregate deductibles**, **underwriter terms on a referral**: each real, each a further branch on the mechanisms added here, none needed to prove the direction.

## Outcome

Filled in at the end of the run: what shipped, what each example proves, test counts.
