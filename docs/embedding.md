---
title: Embedding the engine
parent: For engineers
nav_order: 2
---

# Embedding the engine

The supported interface is the [command line](cli.md): `check`, `quote` and
`batch`. Text in, text or CSV out, a non-zero exit on failure, errors as
`line N: …`. There is no HTTP or JSON quote API.

The Python package is the reference implementation, not a versioned SDK.
`ipngine/__init__.py` exports nothing. An integrator who imports modules does
so against the source.

## Call chain

`parser.parse` turns `.ipn` text into a `Product`. Table files named in the
product are read relative to the `base` directory passed in.

```python
from ipngine.parser import parse, ParseError

product = parse(open("contents.ipn", encoding="utf-8").read(), ".")
```

`check` does not parse that file alone. It builds a `History` from sibling
`.ipn` files of the same product name, then runs every `scenario`:

```python
from ipngine.versions import History
from ipngine.scenarios import run_all

history = History.for_file("contents.ipn")
product = history.versions[-1]
for result in run_all(product, history):
    print(("PASS " if result.passed else "FAIL ") + result.scenario.name)
    for failure in result.failures:
        print("     " + failure)
```

`quote` parses the given file only. It uses `engine.check_inputs`,
`engine.check_eligibility`, `engine.cover_state` and `engine.rate`. Arithmetic
is `Decimal`, never float.

Failures are `ParseError`, `ExprError`, `TableError`, or scenario failure
strings. Each parse error names a line.

## What the engine does not do

Persistence, idempotency, replay, concurrency and the policy store are the
host platform. The engine evaluates a product against a risk. It makes no
network calls. Product text is untrusted input: it is evaluated, not executed
as Python, but a large table or a deep expression still costs time and memory.

Enrichment is shape only. Scenarios stub provided fields on `given`. `quote`
has no lookup service, so `when unavailable` fires for a real postcode.

## Language versus engine

Another implementation should take the [grammar](reference/grammar.md) and the
examples' scenarios as the conformance set. The parser is one implementation,
not the spec. A parser change may be a bug fix or a language change; say which
in the commit.
