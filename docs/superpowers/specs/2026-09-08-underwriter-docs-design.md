# Underwriter-first documentation site

Date: 2026-09-08. Agreed with Jorj: the public site is for underwriters who would
adopt IPN as a standard. Engineering is one nav section they can open when they
need it. UK home contents is the teaching product. Every hand-written page is
rewritten. The engine and the language do not change in this work.

This spec supersedes the audience, information architecture, landing-page walk,
teaching product, and “proof” framing in
[`2026-09-07-website-design.md`](2026-09-07-website-design.md). It keeps that
spec’s buy-vs-build (Jekyll, Just the Docs, generated example and template
pages), visual system (palette, Literata, IBM Plex Mono, code as the memorable
thing), and GitHub Pages operability.

## Purpose

An underwriter landing on the site should believe, in thirty seconds, that they
could declare a familiar product in IPN and check it in the browser. They should
not meet Git, Python, or `unittest` before they have typed a line. An engineer
embedding or extending the reference engine should find a walled section that
tells the truth about what is stable, not infer a contract from contributing
notes.

## Decisions

- **Primary audience.** Underwriters, product managers, and pricing actuaries
  who would write and adopt products. Engineers are a secondary audience with
  their own section, not a parallel homepage.
- **Split the path, not the voice.** No “who this is for” callout on every page.
  The sidebar is the split.
- **Teaching product is UK home contents.** Homepage hero, Getting started, and
  syntax snippets in the hand-written reference use contents (sum insured,
  specified items, property type, alarm), not bikes, riders, or locks. Cycle,
  Irish cycle, e-bike fleet, and bike-versioned remain in the generated examples
  catalogue as products. Design and reference may still *point at* those files
  where they are the product that forced a construct (Irish levies, fire class
  split, versioned bike). They are not how a new reader learns the language.
- **Playground default is `examples/home.ipn`.** That is the real home-contents
  example, not the short teaching excerpt on Home and Getting started.
- **Scenarios are executable examples, not proof.** Passing scenarios show the
  product behaves as expected for the cases written. They are not exhaustive
  verification. The word “proof” leaves running prose. The generator’s green
  callout on example and template pages is labelled from the scenario count, not
  “Proof”.
- **The file is an executable product specification.** It brings questions,
  eligibility, cover, rating, lifecycle, and claims together. It does not
  replace contractual documents, schedules, certificates, notices, legal
  review, or the controls of the platform that runs it. External tables and
  sibling version files are part of what runs.
- **IPN is a proposal.** Home states this once: intended for evaluation, a
  reference engine exists, known gaps are listed, feedback is welcome. That
  status is not repeated as a banner on every page.
- **Document the engine as it is.** Do not change claims outcomes, version
  loading, or any other language or engine behaviour in this work. Where the
  current docs disagree with the code, the docs follow the code. Where a word
  in the engine is operationally blunt (every unpaid claim is “declined”), say
  so.
- **Buy-vs-build.** Keep Jekyll on GitHub Pages with the Just the Docs remote
  theme, source in `docs/` on `main`. Keep `scripts/site_pages.py` as the only
  writer of example and template pages. Do not hand-edit those pages. Do not
  introduce MkDocs, Docusaurus, or a second site. A custom theme would re-build
  navigation and search the current theme already supplies.
- **Operability / DX.** GitHub Pages still builds from `main:/docs`. Local
  preview remains `scripts/site_build.sh`. `tests.test_site` still asserts
  generated pages equal the script, playground assets exist, and the playground
  example menu matches the `EXAMPLES` / `TEMPLATES` lists. `tests.test_grammar`
  still requires the grammar page to cover every example. Editing the site is
  still Markdown; nothing new to install.

## Information architecture

The sidebar, in this order:

| Nav entry | Role |
|---|---|
| Home | What IPN is, a short contents product that checks, playground as the primary action |
| Playground | Write and check in the browser |
| Getting started | Build a small contents product in the playground, then templates and the reference |
| Examples | Generated catalogue; Home contents first |
| Templates | Generated starters, named by product kind |
| Language reference | One page per block; insurance meaning first, then syntax |
| Glossary | Insurance terms, then the language’s own words |
| Design | Principles and surprising semantics; the voice to copy |
| For engineers | Parent: CLI, embedding, grammar, contributing |

Child pages of Language reference stay the block pages plus Not yet supported.
Grammar moves out of that parent and under For engineers. The reference index
may link to it as the page for someone building another engine.

Child pages of For engineers, with `parent: For engineers`:

| Page | File | `nav_order` |
|---|---|---|
| Command line | `docs/cli.md` | 1 |
| Embedding the engine | `docs/embedding.md` | 2 |
| Grammar | `docs/reference/grammar.md` | 3 |
| Contributing | `docs/contributing.md` | 4 |

Pages keep their current paths. Grammar is not moved into a new directory.
The parent page is `docs/engineers.md`.

`nav_order` on the public site:

| Page | `nav_order` |
|---|---|
| Home | 1 |
| Playground | 2 |
| Getting started | 3 |
| Examples (generated index) | 4 |
| Templates (generated index) | 5 |
| Language reference | 6 |
| Glossary | 7 |
| Design | 8 |
| For engineers | 9 |

The generator already emits 4 and 5 for those indexes; those values stay.

## Voice

Copy the Design page’s register: a short principle, then a concrete refusal.
Keep “Nothing is silent”, the `pays`-order row, and the other falsifiable
semantics. Do not flatten the site into a friendly blog.

Change the packing, not the spine:

- One sentence, one job. A sentence that states the rule, the exception, and
  the consequence is three sentences.
- Active verbs. “Defines the questions asked at quote and their types,” not
  “The questions asked at quote, each with a type.”
- Lead with the insurance meaning, then the syntax. Shares-by-cover opens with
  why a regulator cares, then the algorithm.
- A fact has one home. Python and no dependencies live on For engineers.
  Exact pennies live on Design, with one line on the CLI page. Scenarios in
  the same file are pitched on Home once and shown on Getting started. The
  reference index does not re-open like a second homepage: one sentence, then
  the table of blocks.
- In running prose, say tax, fee, or commission, not “line”, except when
  naming a source location (`line 8: unknown word`). Glossary “Line” stays,
  with that distinction.
- Dated amendments lead with the January/July example, then the rule.
- Keep related words together. A claims loading is applied just before the
  first tax, fee, or commission, so the load is taxed and a fee is not.
- Positive form. `renewal: none` means no invitation is made.
- Do not restate `ipngine`, `Decimal`, or “sixteen products, each proven” on
  pages that are not their home.

Replace these claims with the sentences below, or with equivalents that keep
the same meaning:

| Leave behind | Write |
|---|---|
| “The file is the product.” | The file is an executable product specification. It does not replace contractual documents, legal review, or the platform that runs it. |
| “A product with passing scenarios is a product that does what its author said it does.” | Passing scenarios show the product behaves as expected for the cases written. They are executable examples, not exhaustive verification. |
| “There are no defaults.” | Invalid words, unmatched table rows, and incomplete version mappings stop evaluation. Defaults apply only where the product declares them. |
| “Nothing you type leaves your machine.” | Checks run in the browser. The playground does not submit product text to a server. On first load it fetches Pyodide, editor modules, the engine, and the selected example. |
| “The parser is the specification.” | The grammar page is the syntax for another engine. The reference engine is one implementation. A parser change may be a bug fix or a language change; say which in the commit. |

## Home

The hero is still the language: a short real excerpt and `check` output with
PASS lines printing in (disabled under `prefers-reduced-motion`). The excerpt
is a UK Home Contents teaching product, complete enough to show questions, one
cover, a price with IPT, and one pricing scenario. It is not a block-by-block
tour of the language, and it is not the full `examples/home.ipn` (no postcode
enrichment, no specified-items loop, no average clause). One pricing scenario
in the hero is enough; claims and lifecycle wait for Getting started.

The lede names IPN, says it is an open proposal for declaring product behaviour
end to end, and points at the playground. Primary button: Try it in your
browser. Secondary: Get started. No third button to the reference from the
hero. No “three commands” block.

After the hero: a short examples table that leads with Home contents, Household,
and other recognisable lines. Cycle appears in that table as cycle insurance,
not as “every part of the language”. A single sentence points at Design for
principles and at For engineers for the reference engine.

Site footer (`docs/_config.yml`) drops the Python-engine sentence. Licence and
CC0 for examples stay.

## Playground

Unchanged as a tool: Pyodide, CodeMirror, `check` in the browser, example
menu driven by the generated lists. Changes:

- First option, and the file loaded on arrival, is Home contents
  (`examples/home.ipn`).
- Intro qualifies network behaviour as in the table above.
- The page stays in the underwriter nav (order 2), not under For engineers.

`tests.test_site.Playground.test_example_menu_matches_the_generated_pages`
continues to require the menu order to match `EXAMPLES` then `TEMPLATES`.
Reordering `EXAMPLES` in `scripts/site_pages.py` so `home` is first updates
the generated examples index, the playground menu, and the test together.

## Getting started

This page is the underwriter’s adoption workflow. It does not open with Git or
Python.

1. Open the playground. Load Home contents, change an `expect`, press Check.
2. Write a small contents product from scratch in the playground: questions,
   one cover, a price with IPT, a scenario that holds the premium. Same
   teaching product family as Home, smaller than `examples/home.ipn`. Not
   camera, not bike.
3. Add eligibility and a rating factor, with scenarios for a decline and a
   loaded price. Show a failure: the engine names the line and the figure it
   produced.
4. Add lifecycle and claims, with a cancellation refund and a paid theft.
5. Point at Templates for a real starting file, Examples for a product like
   theirs, the reference for a construct, Versions when the product changes.
6. Close with a short “On your machine” that links to For engineers. Clone,
   `unittest`, and `python3 -m ipngine` live there, not here.

Do not bow after the first PASS (“that is a complete, proven product”). The
output already said PASS.

## Language reference

Each block page opens with the insurance meaning in one short paragraph, then
the syntax. Example, already the pattern on waiting periods: “An aggregate
limit is the most you will pay on this section in the term. Write
`limit 7000 per term`.”

Teaching snippets on these pages use contents vocabulary (`contents_sum`,
`specified_items` / `item`, `property_type`, `alarm`). Collection examples are
specified items, not bikes. Per-item rating uses `for each item`. Where a
construct only exists in a non-contents example (Irish levies, e-bike class
split, ranked bikes, versioned bike), link that example after a contents-shaped
snippet, or keep a minimal snippet in the product’s own words and label it as
that product.

Specific unpacks:

- **`cover` `premium`.** Five headings, not one bullet: (1) one-line price,
  (2) when it does not apply (not selected, excluded), (3) per-item: priced
  once per item, one collection only, (4) where it joins the net (`add cover
  premiums`) as a link, (5) the indented-steps form as a second construct.
- **`claims`.** Keep the settlement bullets. Replace the closing walls with a
  short ordered list: declined if / otherwise scale / then `pays` in order /
  then what counts. State current engine behaviour: missing evidence, a covered
  claim below the excess, and a loss the wording does not cover are all
  reported as declined. Do not invent pending or “covered with no payment”
  outcomes. Fix the false rule “the `lifecycle` block must come first in the
  file”: `product` comes first; if `after N claims` restates cancellation or
  adjustment, a `lifecycle` block must already exist above that restatement.
- **`inputs`.** Calculated fields live entirely here, including the BMI
  example currently on rating. Rating says a calculated field is an input and
  links here.
- **`rating` shares.** Why first (regulator, class, bordereau), then the
  syntax and the odd-cent rule.
- **`versions` dated lines.** January policy, July `from` line, then: write
  it once in the latest file; every affected version must already have the
  names it uses.
- **Index.** One sentence, then the table of blocks. Grammar is linked as
  “for another engine”, not listed as a child.
- **Not yet supported.** Classify each gap as language-supported,
  reference-engine-supported, delegated to the host platform, or unsupported.
  Do not call unbuilt features “small additions”. Do not turn the page into a
  roadmap. Add the adoption questions the three-line stub does not answer,
  only where the honest answer is short: documents, referrals as a human
  process, billing, audit evidence, reinsurance, and conformance sit with the
  host platform unless a construct already exists.

## Design

Same page, same job. Qualify “the file is the product” and “the proof is in
the same file” as in the voice table. Keep “Nothing is silent”, with declared
defaults distinguished from silent fallbacks. Label the semantics table as
deliberate current-engine choices that a product owner must confirm against
wording and jurisdiction (tax base, fee refunds, cooling-off, percentage
excess). Links to Irish cycle and e-bike fleet stay where those products
forced the row.

## Glossary

Audience sentence flips: written for people who write products; the language’s
own words are second. Collection example is specified items. Scenario is an
executable example, not a proof. Add **word** (an identifier the product
must recognise). Keep **line** but split source location from tax/fee/commission.

## For engineers

A short parent page: IPN is the language; `ipngine` is a Python 3.12 reference
engine with no dependencies; these pages are how to run it, embed it, and
extend it.

**Command line.** Three commands, with version history told as the code does
it: `check` builds a `History` from sibling files of the same product name;
`quote` and `batch` parse the given file only. Examples use `examples/home.ipn`,
not cycle. Decimal and exact pennies get one sentence. The `batch` paragraph
is the rule plus one example, not a second essay.

**Embedding the engine.** A new page. The supported interface is the CLI
(`check`, `quote`, `batch`): text in, text or CSV out, non-zero exit on
failure, errors as `line N: …`. There is no HTTP or JSON quote API. The Python
package is the reference implementation; `ipngine/__init__.py` exports nothing.
An integrator who imports modules does so against the source, not a versioned
SDK. Document the actual call chain an embedder needs: `parser.parse` gives a
`Product`; `versions.History.for_file` is what `check` uses; `scenarios.run_all`
runs scenarios; `engine.rate`, `check_eligibility`, and `cover_state` are what
`quote` uses; arithmetic is `Decimal`; failures are `ParseError`, `ExprError`,
`TableError`, or scenario failure strings. Persistence, idempotency, replay,
concurrency, and the policy store are the host platform. Untrusted product
text is evaluated; the engine makes no network calls. Language versus engine:
another implementation should take the grammar page and the examples’ scenarios
as the conformance set; the parser is not itself the spec.

**Grammar.** The same syntax page, now parented under For engineers. Its
intro still says it is the formal language for another engine. Contributing
points here for that job.

**Contributing.** Engine contributors: clone, tests, layout, extend-by-need,
regenerate site pages. Licence paragraphs stay as they are (Apache 2.0, patent
grant, name reserved, CC0 for examples). No embedding tutorial here; that is
the Embedding page.

## Generated pages

Hand-written example and template Markdown remains forbidden. In-scope changes
to the generator:

- `EXAMPLES` lists Home contents first. Cycle stays in the list, later.
- Examples index intro does not say “Start with Cycle” or that Cycle exercises
  the whole language. It says the files are complete products whose scenarios
  pass, and points at Home contents as a familiar place to begin.
- Templates index names the product kinds (annual personal lines, several
  items, a fixed-term benefit, claims-made, a table, a second version) instead
  of “one per shape”.
- The green callout class may stay `proof` in CSS; the visible title in
  `_config.yml` is “Scenarios”, and the generated sentence says N scenarios,
  all passing.

Leading comments inside `examples/*.ipn` and `templates/*.ipn` are out of
scope. Cycle’s own comment may still say it exercises the language; that file
is not rewritten here.

## GitHub README

The repository front door is not the site, but it must not re-teach the
engineer-first, bike-first path. The README keeps the site URL as the place to
learn. Its command examples use `examples/home.ipn`. It does not tell the
reader to start with `cycle.ipn`. Package name, Python, and unittest stay,
because a README clone is an engineer arriving at the source.

`CLAUDE.md` is out of scope.

## Visual system

Unchanged: paper white, ink, marine, sepia, teal, pass green, decline red,
rule grey; Literata and IBM Plex Mono; body under 80 characters; no card grid,
no numbered markers, no eyebrows. The landing page no longer uses the
block-by-block `.oidl-walk`. The hero (`.oidl-hero` / `.oidl-proof`) stays.
No new visual identity.

## Out of scope

- Any change to parser, engine, CLI behaviour, or `.ipn` example and template
  files.
- A production policy state machine, embedding SDK, JSON API, or conformance
  suite beyond pointing at examples’ scenarios.
- Renaming CSS class `proof` or colour scheme `openidl` (internal identifiers).
- Expanding Not yet supported into a feature roadmap.
- A global “remove AI tells” pass that would sand off “Nothing is silent”.

## Testing

Existing tests remain the harness:

- `tests.test_site.GeneratedPages` — generated Markdown matches the script
  after generator copy and `EXAMPLES` order change.
- `tests.test_site.Links` — every relative Markdown link on the public site
  resolves, including new For engineers pages and moved grammar parent.
- `tests.test_site.Playground` — engine file list, assets, example menu order.
- `tests.test_grammar` — grammar page still covers every example.

No new engine tests. A page whose relative links break, or a playground menu
that disagrees with `EXAMPLES`, is a failing test, not a visual QA-only check.
