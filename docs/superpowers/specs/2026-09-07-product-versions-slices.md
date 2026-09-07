# Product versions: slice scope

**Spec:** `docs/superpowers/specs/2026-09-07-product-versions-design.md`

Each slice is a working end-to-end increment proven by scenarios in `examples/versioned/`.
A lone file (no `published`) must behave exactly as before after every slice.

## Slice 1: A policy renews onto the version live at renewal

**Scope:** `published` header; `History` built from the directory; `live_on`; upgrading by
carry and default only (no `upgrading` block yet); renewal switches version; `expect version`;
`expect <input> <value>`; scenario `given` deferred for early-binding scenarios; CLI `check`
passes the history.

**Acceptance criteria**
- A file without `published` parses and runs exactly as today (full existing suite green).
- Two files in one directory with the same product name and `published` dates form a
  history; the earlier file sees only itself.
- `when bound on DATE` binds under the version live on DATE; binding before the first
  version is refused with `no version of X was on sale on DATE`.
- `when renewed on DATE` moves the policy to the version live at the start of the new term;
  the premium is the new version's, capped and collared against what was charged.
- An input carried by name keeps its value; a new input with a default takes it; a new
  input with neither is a load-time error naming it.
- `expect version DATE` and `expect <input> <value>` pass and fail correctly.
- Two versions with the same `published` date are a load-time error.

**Human UAT:** `python3 -m ideclare check examples/versioned/bike-2026-07-01.idl` shows a 2026-01
customer renewing onto the July rating at the capped premium.

## Slice 2: The `upgrading` block, `ask` and answering at renewal

**Scope:** `upgrading` block (one-line, block form with `otherwise`, `for each`, `ask`);
chain over several versions; unknown propagation; `RenewalOffer.needs`; `when renewed on
DATE with ...`; `expect renewal needs ...`; load-time checks (unknown words against the
previous version, exhaustiveness, `otherwise` required, literal choice check); run-time
value check against the target input.

**Acceptance criteria**
- A choice renamed and remapped by a block form produces the mapped value on renewal.
- A merged input (`total: a + b`) evaluates over the old answers.
- `for each` upgrades every item; unmentioned fields carry.
- `ask` on a line makes every renewal need the input; `otherwise: ask` only those reaching it.
- A renewal with needs is refused with `renewal needs X`; `with X value` satisfies it.
- `expect renewal premium` fails with `renewal needs X` when unanswered.
- A chain across three versions composes; an `ask` in the middle poisons a dependent.
- A block without `otherwise`, an unknown word, an unmentioned new input, a literal not in
  the target's choices: each is a load-time error at the right line.
- A value outside the target's choices at run time fails the renewal loudly.

**Human UAT:** `check examples/versioned/bike-2027-01-01.idl` shows a gold-lock 2026 customer
renewing to `lock_rating diamond` and a bronze-lock customer needing an answer.

## Slice 3: Adjustment on the current version

**Scope:** `adjustment: reprice on the current version, charge pro rata difference[, fee N]`;
`Policy.adjust` upgrades first when a newer version is live; changes satisfy needs; refusal
on unanswered needs.

**Acceptance criteria**
- Default lifecycle: an adjustment after a newer version is published stays on the policy's
  version (version unchanged, priced by the old version).
- With the new line: the policy moves to the current version, the changes apply in its
  words, and the pro rata difference is against the old version's earning premium.
- An unanswered `ask` refuses the adjustment naming the input; supplying it in `with`
  proceeds.

**Human UAT:** a scenario in `bike-2027-01-01.idl` adjusting a 2026 policy in February 2027
shows `expect version 2027-01-01` and the additional premium.

## Slice 4: Dated amendments within a version

**Scope:** `from DATE` / `until DATE` prefixes on cover and claim child lines; single-valued
settings replaced, list settings accumulated; overlap error; rejection elsewhere; engine
resolves wording at the event date; `expect cover` at the last event date; undated wording
when there is no date.

**Acceptance criteria**
- A claim before the `from` date settles on the undated wording; on or after it, on the
  dated line.
- An `until` exclusion stops applying on its date.
- `from` on a rating, eligibility or lifecycle line is a parse error: `only cover and claims
  lines can be dated`.
- Two overlapping dated `limit` lines are a parse error.
- `quote` from the CLI uses undated wording.

**Human UAT:** `bike-2026-07-01.idl` carries a dated exclusion and scenarios either side of it.

## Slice 5: Amendments reach earlier versions

**Scope:** `History.cover(version, name, on)` and `History.claim(...)` merge dated lines from
later versions; shared-words check at load.

**Acceptance criteria**
- A policy bound on the 2026-01 version, claiming after a `from` date written in the 2026-07
  version, is settled with that amendment.
- A dated line using a word an earlier version lacks is a load-time error naming both.
- The earlier file's own scenarios still pass (it sees no later versions).

**Human UAT:** a scenario in `bike-2026-07-01.idl` binding on 2026-02-01 and claiming after the
amendment date shows the amended settlement.
