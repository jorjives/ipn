# iDeclare beyond bikes: proving the language on other lines

## Purpose

The first build proved iDeclare on a property line (bike cover). This piece of work asks
whether the same language can describe products across the industry without bending, and
adds the smallest features that the other lines genuinely need. Each line gets a worked
example in `examples/` whose scenarios pass under `python3 -m ideclare check`.

Autonomous run on 2026-09-05; Jorj not available. Conventions for each line were taken
from public UK policy wordings and guides (see Research).

## Lines and what each one stresses

| Line | Example | What is new about it |
|---|---|---|
| Single-trip travel | `travel.idl` | People not things; term set by trip dates; sections of cover that start and stop at different dates (cancellation from purchase, medical from departure); trip length and destination rating; per-person sub-limits |
| Pet (lifetime) | `pet.idl` | Annual aggregate vet-fee limit eroded by claims; 14-day waiting period; co-payment for older pets; renewal loading on age |
| Private motor | `motor.idl` | Named-driver collection; no-claims discount that steps back at renewal after a fault claim but not for glass; excess that depends on who was driving (a fact known only at claim time); voluntary excess |
| Term life | `life.idl` | Term chosen in years by the customer; fixed benefit (pays the sum assured, not the amount claimed); BMI as a calculated input from height and weight; 12-month suicide exclusion; no renewal |
| Professional indemnity | `pi.idl` | Commercial; turnover-rated; claims-made basis with a retroactive date; limit any one claim versus in the aggregate; costs inclusive |
| Home contents | `home.idl` | Average clause (proportional settlement when underinsured, using the true value found at claim time); peril-specific excess (escape of water); specified high-value items |

## Language additions

Each addition is used by at least one example, and none is speculative.

- `term N days|months|years`, `term <input> years` and `term until <date input>`: the term
  is not always twelve months. Travel ends on the return date; life runs for the number of
  years chosen.
- `date` input type, with `<`, `>` comparisons and `a - b` giving the days between.
- Top-level `calculated` inputs (`bmi: calculated` with steps), not just item fields.
- `cover X` may say `in force from <date input>` and/or `in force until <date input>`; a
  claim outside that window is declined "not in force".
- `cover X` may say `waiting period N days`: losses in the first N days after the policy
  first started are declined. Measured from the original inception, not the latest renewal.
- `limit N per term`: an aggregate limit; each paid claim on the cover erodes what is left in
  the term. Reset on renewal. `limit N` alone stays "any one claim".
- `claim X` may declare `asks name: type` lines: facts asked when the claim is made (cause of
  death, who was driving, the true value of contents). Scenarios give them as `with cause
  suicide, driver_age 19` alongside evidence words.
- `within N days|months of inception` in claim conditions.
- `pays <amount>` (for example `pays sum_assured`) as a fixed benefit alternative to
  `pays claimed amount up to limit`.
- `co-payment N% [when ...]` in a claim: taken off after the excess, before the limit.
- `settlement` as an alias for `depreciation` (an average clause is not depreciation).
- `excess` as a table of rows (`condition: amount`, `otherwise: amount`), like a factor, so
  the excess can depend on claim facts.
- `index X by -N` (negative) and `index X by N, at least A` / `, at most B` bounds. Inside
  `after N claims in term`, restating an index for the same input replaces it instead of
  adding a second one; this is how a no-claims discount steps back.

Found necessary while building, not foreseen above:

- `renewal: none` for products that simply end (travel, life); the offer is declined.
- `expect refused ["reason"]` so a scenario can prove an adjustment or cancellation was
  rightly refused rather than have the runner treat the refusal as a broken step.
- `counts towards claims in term when <cond>` and `does not count towards claims in term`
  on a claim: glass and non-fault motor claims are paid but leave the no-claims record alone.
- The `pays` clauses apply in the order written (see below); the fixed "limit then excess"
  order of the first build was one line's convention, not the industry's.
- Eligibility rules on a field an enrichment could not provide are skipped; the lookup's
  own refer or decline speaks for them (engine bug found by the motor example).
- `after 1 claim in term: renewal load x M` accepts the singular.

## Settlement order in a claim

claimed (or the fixed benefit) → settlement/depreciation table → the `pays` clauses in the
order written: `up to limit`, `less excess`, `less co-payment`. A sum insured is usually
capped then the excess deducted; a liability or aggregate limit caps what the insurer pays
after the excess. Pet wordings read excess, then co-payment, then the annual limit.

## Outcome

| Example | Scenarios |
|---|---|
| travel.idl | 17 |
| pet.idl | 18 |
| motor.idl | 18 |
| life.idl | 19 |
| pi.idl | 16 |
| home.idl | 17 |

All pass alongside the three bike examples; the engine's own tests grew from 129 to 177.
Every example was written against the engine as it stood and the language was extended
only where a scenario could not be expressed; each extension is one commit with its own
tests.

## Research

- Pet: 14-day waiting period and 20% co-payment over age 8 or 9 are common (Animal Friends,
  ManyPets, British Pet Insurance guides).
- Travel: cancellation cover starts on purchase for single-trip policies (GoCompare,
  MoneySuperMarket, Age UK guides).
- Motor: step-back of two years per fault claim, windscreen claims exempt (Selectra,
  Financial Ombudsman, wecovr guides).
- Professional indemnity: claims-made with a retroactive date; any one claim versus in the
  aggregate; costs inclusive erodes the limit; rate applied to turnover (Hiscox, Markel,
  PolicyBee, Riskbox).
- Life: 12-month suicide exclusion is the norm (Aviva, MoneySuperMarket).
- Home: average clause reduces the claim in proportion to underinsurance (Financial
  Ombudsman case studies, Howden, Lansdown).
