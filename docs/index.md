---
title: Home
nav_order: 1
---

<div class="oidl-hero" markdown="1">

# Declare an insurance product. Prove it in the same file.
{: .no_toc }

<p class="lede">Open IDL is a declarative language for defining an insurance product end to end: the questions asked, who is eligible, what is covered, how it is priced, how the policy behaves from purchase to renewal, and how claims are paid. It reads like a policy wording, and the scenarios that prove it live in the same file.</p>

<div class="actions">
<a class="btn btn-primary" href="{{ site.baseurl }}/getting-started/">Get started</a>
<a class="btn" href="{{ site.baseurl }}/reference/">Read the reference</a>
<a class="btn" href="{{ site.baseurl }}/playground/">Try it in your browser</a>
</div>

<div class="oidl-proof">
<pre class="file"><code class="idl">product "Bike Cover"
  territory UK
  term 12 months

inputs
  bike_value: money
  rider_age: integer
  lock: choice of bronze, silver, gold

eligibility
  decline when rider_age < 16 because "Riders must be 16 or over"

cover Theft
  limit bike_value
  excess 10% of claim, minimum 50
  excludes when lock is bronze and bike_value > 2000 because "Needs a silver or gold lock"

rating
  base 3% of bike_value
  factor "Rider age"
    rider_age < 25: x 1.40
    otherwise: x 1.00
  discount 10% when lock is gold
  tax IPT 12%

lifecycle
  cooling off 14 days, full refund
  cancellation by customer: refund pro rata, fee 25
  renewal
    invite 21 days before expiry
    increase capped at 20%

claims
  claim Theft
    requires crime_reference
    pays claimed amount up to limit, less excess
    decline when reported after 30 days because "Theft must be reported within 30 days"

scenario "A young rider with a gold lock"
  given bike_value 2000, rider_age 22, lock gold
  expect net 75.60
  expect premium 84.67

scenario "Theft is paid less the excess"
  given bike_value 2000, rider_age 22, lock gold
  when bound on 2026-03-01
  when claim Theft for 1500 on 2026-06-10 with crime_reference
  expect payout 1350.00

scenario "Cancelling mid term refunds pro rata, less the fee"
  given bike_value 2000, rider_age 22, lock gold
  when bound on 2026-03-01
  when cancelled by customer on 2026-09-01
  expect refund 16.99</code></pre>
<pre class="out"><span class="cmd">$ python3 -m ideclare check bike.idl</span>
<span class="line typed" style="animation-delay:.4s"><span class="pass">PASS</span> A young rider with a gold lock</span><span class="line typed" style="animation-delay:.7s"><span class="pass">PASS</span> Theft is paid less the excess</span><span class="line typed" style="animation-delay:1s"><span class="pass">PASS</span> Cancelling mid term refunds pro rata, less the fee</span><span class="line typed sum" style="animation-delay:1.3s">Bike Cover: 3 passed, 0 failed</span></pre>
</div>

</div>

## What a file says

A product is a sequence of blocks, read top to bottom the way a wording is. Each block is
a few lines an underwriter, a product manager or a pricing actuary would write themselves.

<div class="oidl-walk" markdown="1">

<div class="step" markdown="1">
<div markdown="1">
### inputs
The questions asked at quote, each with a type. Repeatable items (several bikes, named drivers) are a `collection`; a value worked out from the others is `calculated`.
</div>
```idl
inputs
  bike_value: money
  rider_age: integer
  lock: choice of bronze, silver, gold
  bikes: collection of bike, 1 to 4
    value: money
    age: integer
```
</div>

<div class="step" markdown="1">
<div markdown="1">
### eligibility
Who is declined and who is referred to an underwriter, each with the reason the customer will be given. A decline outranks a refer.
</div>
```idl
eligibility
  decline when rider_age < 16 because "Riders must be 16 or over"
  refer when previous_claims >= 3 because "Claims history needs an underwriter"
```
</div>

<div class="step" markdown="1">
<div markdown="1">
### cover
One block per section: the limit, the excess, when it is excluded, whether it is optional. Aggregates, waiting periods, dates in force and per-item cover are the same few words.
</div>
```idl
cover Theft
  limit bike_value
  excess 10% of claim, minimum 50
  excludes when lock is bronze and bike_value > 2000 because "Needs a silver or gold lock"

cover Racing optional
  limit 5000
  available when racing is yes
```
</div>

<div class="step" markdown="1">
<div markdown="1">
### rating
The premium, step by step, in the order written. Factors, flat additions, discounts and loads, floors and caps, then tax on the rounded net and any fees. Big tables come from the pricing team's spreadsheet.
</div>
```idl
rating
  base 3% of bike_value
  factor "Rider age"
    rider_age < 25: x 1.40
    otherwise: x 1.00
  factor "Area" x rate from "Postcode rates"
  discount 10% when lock is gold
  minimum 60
  tax IPT 12%
  fee "Admin fee" 10
```
</div>

<div class="step" markdown="1">
<div markdown="1">
### lifecycle
How the policy behaves after it is bought: cooling off, cancellation by either party, mid-term changes, lapse, instalments, and renewal with indexing, a cap and a collar.
</div>
```idl
lifecycle
  cooling off 14 days, full refund
  cancellation by customer: refund pro rata, fee 25
  adjustment: reprice, charge pro rata difference
  instalments 12 monthly, charge 8%
  renewal
    invite 21 days before expiry
    increase capped at 20%
    index bike_value by 5%
```
</div>

<div class="step" markdown="1">
<div markdown="1">
### claims
What each claim needs, how it is settled, and what a paid claim changes. The `pays` clauses apply in the order written, because a sum insured and a liability limit are worded differently.
</div>
```idl
claims
  claim Theft
    requires crime_reference
    pays claimed amount up to limit, less excess
    decline when reported after 30 days because "Theft must be reported within 30 days"
  after 2 claims in term: renewal load x 1.25
```
</div>

<div class="step" markdown="1">
<div markdown="1">
### scenario
The proof. Answers, then events in the order they happen, then what must be true after each. `check` runs every scenario and names the line that disagrees.
</div>
```idl
scenario "Two claims load the renewal, within the cap"
  given bike_value 2000, rider_age 22, lock gold
  when bound on 2026-01-01
  when claim Theft for 600 on 2026-05-01 with crime_reference
  when claim Theft for 900 on 2026-08-01 with crime_reference
  expect claims in term 2
  expect renewal premium 101.60
```
</div>

</div>

When the product changes, the new version sits beside the old with a `published` date. A
customer stays on the version they bought until renewal, and the file says how their old
answers become new ones. See [Versions]({{ site.baseurl }}/reference/versions/).

## Proven across the industry

Every example is a complete product whose scenarios pass. The language grew by writing
these; each construct exists because one of them needed it.

<div class="oidl-lines" markdown="1">

| Line | What it proved |
|---|---|
| [Cycle]({{ site.baseurl }}/examples/cycle/) | Every part of the language in one product, with the arithmetic in the comments |
| [Private motor]({{ site.baseurl }}/examples/motor/) | Named drivers, a no claims discount that steps back after a fault claim unless protected, an excess that depends on who was driving, instalments |
| [Home contents]({{ site.baseurl }}/examples/home/) | Specified items, an excess by cause of loss, the average clause |
| [Single-trip travel]({{ site.baseurl }}/examples/travel/) | People not things; a term ending on the return date; sections in force on different days |
| [Lifetime pet]({{ site.baseurl }}/examples/pet/) | An annual limit per condition eroded by claims, a waiting period, a co-payment that arrives with age |
| [Level term life]({{ site.baseurl }}/examples/life/) | A fixed benefit over a term of years, BMI calculated, no renewal |
| [Term life from a curve]({{ site.baseurl }}/examples/mortality/) | A mortality curve interpolated geometrically, power laws and exponentials |
| [Income protection]({{ site.baseurl }}/examples/income/) | A benefit paid month by month that carries on past the term |
| [Professional indemnity]({{ site.baseurl }}/examples/pi/) | Commercial, turnover-rated, claims-made with a retroactive date, an aggregate limit, short-rate cancellation, commission |
| [Light commercial vehicle]({{ site.baseurl }}/examples/van/) | A three-dimensional rating table owned as a spreadsheet |
| [Gadget in four countries]({{ site.baseurl }}/examples/gadget/) | One product, several territories, each with its own tax and currency |
| [Cycle leasing scheme]({{ site.baseurl }}/examples/leasing/) | A group policy whose members join and leave all year |

</div>

And [five more]({{ site.baseurl }}/examples/), including a product across three published
versions.

## Three commands

```sh
python3 -m ideclare check product.idl                 # run the scenarios: PASS or FAIL, line by line
python3 -m ideclare quote product.idl bike_value=2000 rider_age=22 lock=gold
python3 -m ideclare batch product.idl risks.csv > priced.csv
```

The reference engine is Python with no dependencies. Every figure is a decimal, never a
float, so a premium is the same on every machine and a scenario's `expect premium 84.67`
is exact. The [design]({{ site.baseurl }}/design/) page records the principles and the
decisions that surprise; the [grammar]({{ site.baseurl }}/reference/grammar/) gives the
language formally for anyone building another engine.
