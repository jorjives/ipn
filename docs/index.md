---
title: Home
nav_order: 1
---

<div class="oidl-hero" markdown="1">

# Declare an insurance product. Check it in the same file.
{: .no_toc }

<p class="lede">IPN (Insurance Product Notation) is an open proposal for declaring an insurance product end to end: the questions asked, who is eligible, what is covered, how it is priced, how the policy behaves from purchase to renewal, and how claims are paid. It reads like a policy wording. The scenarios that check it live in the same file. Try a product in the playground; nothing to install.</p>

<div class="actions">
<a class="btn btn-primary" href="{{ site.baseurl }}/playground/">Try it in your browser</a>
<a class="btn" href="{{ site.baseurl }}/getting-started/">Get started</a>
</div>

<div class="oidl-proof">
<pre class="file"><code class="ipn">product "Home Contents"
  territory UK
  term 12 months

inputs
  contents_sum: money
  property_type: choice of detached, semi, terrace, flat
  alarm: yes/no

cover Contents
  limit contents_sum
  excess 100

rating
  base 0.5% of contents_sum
  factor "Property type"
    property_type is detached: x 1.10
    otherwise: x 1.00
  discount 10% when alarm is yes
  tax IPT 12%

scenario "A terrace of 20,000"
  given contents_sum 20000, property_type terrace, alarm no
  expect net 100.00
  expect premium 112.00</code></pre>
<pre class="out"><span class="cmd">$ python3 -m ipngine check contents.ipn</span>
<span class="line typed" style="animation-delay:.4s"><span class="pass">PASS</span> A terrace of 20,000</span><span class="line typed sum" style="animation-delay:.7s">Home Contents: 1 passed, 0 failed</span></pre>
</div>

</div>

The file is an executable product specification. It brings underwriting, rating,
lifecycle and claims together. It does not replace contractual documents, legal
review, or the platform that runs it. Passing scenarios show the product behaves
as expected for the cases written; they are not exhaustive verification.

IPN is a proposal, with a reference engine, offered for evaluation. [Known
gaps]({{ site.baseurl }}/reference/not-yet-supported/) are listed. Feedback is
welcome.

## Examples across the industry

Every example is a complete product whose scenarios pass.

<div class="oidl-lines" markdown="1">

| Line | What it shows |
|---|---|
| [Home contents]({{ site.baseurl }}/examples/home/) | Specified items, an excess by cause of loss, the average clause |
| [Buildings and contents]({{ site.baseurl }}/examples/household/) | Two optional sections, a bundle discount, premium split by class |
| [Private motor]({{ site.baseurl }}/examples/motor/) | Named drivers, a no claims discount that steps back, an excess that depends on who was driving |
| [Single-trip travel]({{ site.baseurl }}/examples/travel/) | Insuring people; a term ending on the return date; sections in force on different days |
| [Lifetime pet]({{ site.baseurl }}/examples/pet/) | An annual limit per condition eroded by claims, a waiting period, a co-payment that arrives with age |
| [Level term life]({{ site.baseurl }}/examples/life/) | A fixed benefit over a term of years, BMI calculated, no renewal |
| [Professional indemnity]({{ site.baseurl }}/examples/pi/) | Commercial, turnover-rated, claims-made with a retroactive date, an aggregate limit |
| [Cycle]({{ site.baseurl }}/examples/cycle/) | Theft, racing, tax, and a cancellation refund, with the arithmetic in the comments |

</div>

And [more]({{ site.baseurl }}/examples/), including a product across three published
versions.

The [design]({{ site.baseurl }}/design/) page records the principles and the
decisions that surprise. The [reference engine]({{ site.baseurl }}/engineers/)
is for anyone running or embedding the checker.
