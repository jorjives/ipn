---
title: eligibility
parent: Language reference
nav_order: 5
---

# eligibility

```ipn
eligibility
  decline when rider_age < 16 because "Rider must be at least 16"
  refer when previous_claims >= 3 because "Claims history needs an underwriter"
```

Every rule is checked. If any `decline` fires the outcome is *declined*; otherwise if any
`refer` fires it is *referred*; otherwise *eligible*. All reasons that fired are reported.
Rules may look at the chosen covers, `refer when Racing selected and rider_age > 60`;
write the eligibility block after the covers it names. A bundle of sections sold as one
policy (buildings and contents, say) is optional covers with a rule that at least one is
taken, `decline when not Buildings selected and not Contents selected because "..."`, and
a `discount N% when Buildings selected and Contents selected` in the rating.

A declined risk cannot be bound. A referred risk is bound only once an underwriter has
accepted it, on terms if they choose: a load or discount on the net (a final step in the
rating trail, "Underwriter load"), an excess imposed on a cover in place of the product's,
or a cover withdrawn (reported as excluded, "underwriter terms"). The terms hold for the
life of the policy, renewals included. The underwriter may instead decline the risk.
