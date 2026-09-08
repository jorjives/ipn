---
title: Contributing
nav_order: 10
---

# Contributing

IPN (Insurance Product Notation) is an open spec with a small reference engine, `ipngine`.
Both grow by the same route: write a real product against them and add what its wording needs.

## Running the engine

Python 3.12 or later and nothing else. Clone the repository and run the tests and every
example:

```sh
git clone https://github.com/jorjives/open-idl.git
cd open-idl
python3 -m unittest
for f in examples/*.ipn examples/versioned/*.ipn templates/*.ipn templates/versioned/*.ipn; do python3 -m ipngine check "$f" | tail -1; done
```

## Layout

| Path | What it is |
|---|---|
| `ipngine/parser.py` | Turns `.ipn` text into a `Product`. Tokenises, builds an indent tree, then reads each block. |
| `ipngine/model.py` | The dataclasses a `Product` is made of. No logic. |
| `ipngine/expr.py` | The expression sub-language: parser and evaluator over tuples. |
| `ipngine/engine.py` | Applies a product to a risk: eligibility, cover state, rating, the lifecycle, claims. All arithmetic in `Decimal`. |
| `ipngine/tables.py` | Lookup tables: cells, bands, wildcards, most-specific-row-wins, interpolation. |
| `ipngine/versions.py` | A product's history of published versions and moving a policy between them. |
| `ipngine/scenarios.py` | Runs `scenario` blocks: events into the engine, expectations against its state. |
| `ipngine/cli.py` | `check`, `quote` and `batch`. |
| `examples/` | Sixteen products and a versioned one, each proven by its scenarios. |
| `templates/` | Starter products, one per shape, each proven likewise. |
| `docs/` | This site. `docs/reference/` is the language reference; `docs/examples/` and `docs/templates/` are generated. |
| `docs/superpowers/specs/` | The design records: why each part of the language is the way it is. |

## Extending the language

1. Write an example product that needs the construct, with a scenario that says what it
   should do. Run `check`; the failure is the gap.
2. Add parser support (`parser.py`, and `expr.py` if the expression language changes),
   then engine support (`engine.py`), each with a unit test in `tests/`.
3. Update the [reference](reference/index.md) page for the block, and the
   [grammar](reference/grammar.md).
4. One construct per commit, with the commit message saying why.

Keep every figure a `Decimal`. Prefer an error with a line number to a default. A construct that only one product would ever use is probably a `calculated`
input or a table, not a new keyword.

## Regenerating the site's generated files

The example and template pages on this site are generated from the `.ipn` files, and the
playground's completion table (`docs/assets/ipn-grammar.json`) is compiled from the
[grammar](reference/grammar.md) page; a test fails if either is stale, and
`tests.test_grammar` fails if the grammar page no longer covers every example:

```sh
python3 scripts/site_pages.py
python3 -m unittest tests.test_site
```

The rest of the site is Markdown under `docs/`, built by GitHub Pages with the
[Just the Docs](https://just-the-docs.com) theme; nothing needs installing to edit it.

## Reporting a disagreement

If the [grammar](reference/grammar.md) and the parser disagree, or a scenario you believe
is right fails, open an issue with the `.ipn` file and the scenario: it says what was expected and what
happened.

## Licence

The language, the reference engine and this site are licensed under the
[Apache License 2.0](https://github.com/jorjives/open-idl/blob/main/LICENSE). It is permissive,
carries an explicit patent grant, and gives no rights to the name, so anyone can implement
or embed IPN while "IPN" itself stays the name of the specification.

The [examples](examples/index.md) and [templates](templates/index.md) are meant to be copied
into your own products, so they are dedicated to the public domain under
[CC0 1.0](https://github.com/jorjives/open-idl/blob/main/templates/LICENSE): take them without
attribution.

By contributing you agree that your contribution is licensed the same way (Apache 2.0, or
CC0 for a file under `examples/` or `templates/`), as section 5 of the Apache licence says.
