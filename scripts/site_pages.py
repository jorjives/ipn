"""Writes the site's example and template pages from the .idl files, so the site cannot drift from the code.

    python3 scripts/site_pages.py          # write docs/examples/*.md and docs/templates/*.md
    python3 -m unittest tests.test_site    # fail if the committed pages differ from what this renders

Each page carries the file's leading comment block as its description, the number of scenarios
(which must all pass: a broken example cannot be published) and the full source.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ideclare.scenarios import run_all  # noqa: E402
from ideclare.versions import History  # noqa: E402

# Curated order and the line of business each example stands for. The description is the file's own.
EXAMPLES = [
    ("cycle", "Cycle", "Every part of the language in one personal-lines product"),
    ("family", "Cycle, several bikes", "Repeatable items on one policy"),
    ("multibike", "Cycle, ranked bikes", "Items rated in a chosen order; postcode and catalogue enrichment"),
    ("gadget", "Gadget, four countries", "One product, several territories, each with its own tax and currency"),
    ("home", "Home contents", "Specified items, an excess by cause of loss, the average clause"),
    ("household", "Buildings and contents", "Two optional sections sold as one policy with a bundle discount"),
    ("travel", "Single-trip travel", "People not things; a term ending on a date; sections in force on different days"),
    ("pet", "Lifetime pet", "An annual limit per condition eroded by claims, a waiting period, a co-payment with age"),
    ("motor", "Private motor", "Named drivers, a no claims discount that steps back, an excess by driver, instalments"),
    ("van", "Light commercial vehicle", "A three-dimensional rating table owned as a spreadsheet"),
    ("life", "Level term life", "A fixed benefit over a term of years, BMI calculated, no renewal"),
    ("mortality", "Term life from a curve", "Geometric and linear interpolation, power laws and exponentials"),
    ("income", "Income protection", "A benefit paid month by month that carries on past the term"),
    ("pi", "Professional indemnity", "Commercial, turnover-rated, claims-made with a retroactive date, an aggregate limit"),
    ("runoff", "Professional indemnity run-off", "Six years of claims-made cover bought with one premium"),
    ("leasing", "Cycle leasing scheme", "A group policy whose members join and leave all year"),
]
VERSIONED = ("bike-versioned", "Bike Cover across three versions", "Published versions, upgrading answers at renewal, a dated amendment")

TEMPLATES = [
    ("annual-product", "Annual product", "A single-term personal-lines product with every block in place"),
    ("multi-item-product", "Several items on one policy", "A collection of items rated with for each"),
    ("fixed-term-benefit", "Fixed-term benefit", "A benefit over a term of years, no renewal, no adjustment"),
    ("commercial-claims-made", "Commercial claims-made", "Turnover-rated, aggregate limit, retroactive date, short-rate cancellation, commission"),
    ("rated-from-a-table", "Rated from a table", "A multi-dimensional rating table kept as a spreadsheet"),
]
VERSIONED_TEMPLATE = ("versioned-product", "A second version", "A product that changes its questions, with upgrading")


def description(text: str) -> tuple[str, str]:
    """The leading comment block as prose, and the `Run it with` command if the block ends with one."""
    lines = []
    for line in text.split("\n"):
        if not line.startswith("#"):
            break
        lines.append(line[1:].strip())
    command = ""
    if lines and lines[-1].startswith("Run"):
        command = lines.pop().partition(":")[2].strip()
    return " ".join(l for l in lines if l), command


def check(path: Path) -> int:
    """How many scenarios the file has; every one must pass."""
    history = History.for_file(str(path))
    results = run_all(history.versions[-1], history)
    failed = [r for r in results if not r.passed]
    if failed:
        raise SystemExit(f"{path}: {len(failed)} scenario(s) fail; fix the file before publishing it")
    return len(results)


def sidecars(path: Path) -> list[str]:
    """Data files the product reads from beside it, found by their mention in the source."""
    text = path.read_text(encoding="utf-8")
    return sorted(f.name for f in path.parent.glob("*.csv") if f.name in text)


def source_block(path: Path, rel: str) -> str:
    text = path.read_text(encoding="utf-8").rstrip("\n")
    return f"```idl\n{text}\n```\n"


def example_page(stem: str, line: str, shows: str, order: int) -> str:
    path = ROOT / "examples" / f"{stem}.idl"
    text = path.read_text(encoding="utf-8")
    desc, command = description(text)
    n = check(path)
    history = History.for_file(str(path))
    name = history.versions[-1].name
    files = ", ".join(f"[`{f}`](https://github.com/jorjives/open-idl/blob/main/examples/{f})" for f in sidecars(path))
    beside = f"\n\nReads {files} from beside the file." if files else ""
    return f"""---
title: {name}
parent: Examples
nav_order: {order}
---

# {name}

{desc}{beside}

{{: .proof }}
> {n} scenarios, all passing. Run them yourself:
> ```sh
> {command or f'python3 -m ideclare check examples/{stem}.idl'}
> ```

The file: [`examples/{stem}.idl`](https://github.com/jorjives/open-idl/blob/main/examples/{stem}.idl).

{source_block(path, f'examples/{stem}.idl')}"""


def versioned_page(stems: list[Path], title: str, shows: str, order: int, parent: str, where: str) -> str:
    parts, total = [], 0
    for path in stems:
        text = path.read_text(encoding="utf-8")
        desc, command = description(text)
        n = check(path)
        total += n
        rel = path.relative_to(ROOT).as_posix()
        parts.append(f"""## {path.stem}

{desc}

{n} scenario{'s' if n != 1 else ''}: `{command or f'python3 -m ideclare check {rel}'}`

{source_block(path, rel)}""")
    return f"""---
title: {title}
parent: {parent}
nav_order: {order}
---

# {title}

{shows}. The files sit together in [`{where}/`](https://github.com/jorjives/open-idl/tree/main/{where}); each
declares the same product name and says when it was published, and `check` finds the others by itself.

{{: .proof }}
> {total} scenarios across the versions, all passing.

""" + "\n".join(parts)


def template_page(stem: str, title: str, shows: str, order: int) -> str:
    path = ROOT / "templates" / f"{stem}.idl"
    text = path.read_text(encoding="utf-8")
    desc, command = description(text)
    n = check(path)
    return f"""---
title: {title}
parent: Templates
nav_order: {order}
---

# {title}

{desc}

{{: .proof }}
> {n} scenarios, all passing, so the template is a working product before you change a line.

Copy [`templates/{stem}.idl`](https://github.com/jorjives/open-idl/blob/main/templates/{stem}.idl), rename the product, and replace each
block as the comments direct. Keep `check` passing as you go.

{source_block(path, f'templates/{stem}.idl')}"""


def examples_index() -> str:
    rows = "\n".join(f"| [{line}]({stem}.md) | {shows} |" for stem, line, shows in EXAMPLES)
    stem, title, shows = VERSIONED
    rows += f"\n| [{title}]({stem}.md) | {shows} |"
    return f"""---
title: Examples
nav_order: 4
has_children: true
has_toc: false
---

# Examples

Sixteen products and one product in three versions, each a complete `.idl` file with the
scenarios that prove it. These pages are generated from the files in
[`examples/`](https://github.com/jorjives/open-idl/tree/main/examples) and every scenario
passes; a file whose proof fails cannot be published here. The files are dedicated to the
public domain under [CC0](https://github.com/jorjives/open-idl/blob/main/examples/LICENSE):
copy them into your own products without attribution.

Start with [Cycle](cycle.md): it uses every part of the language and its scenarios are
commented with the arithmetic. The rest take the same language across the industry.

| Product | What it shows |
|---|---|
{rows}
"""


def templates_index() -> str:
    rows = "\n".join(f"| [{title}]({stem}.md) | {shows} |" for stem, title, shows in TEMPLATES)
    stem, title, shows = VERSIONED_TEMPLATE
    rows += f"\n| [{title}]({stem}.md) | {shows} |"
    return f"""---
title: Templates
nav_order: 5
has_children: true
has_toc: false
---

# Templates

Starting points, one per shape of product. Each is a small working product with comments
that say what to change, and each passes its own scenarios, so you begin from something
proven and keep it that way. Copy the file from
[`templates/`](https://github.com/jorjives/open-idl/tree/main/templates), rename the product,
and run `check` after every change. The templates are dedicated to the public domain under
[CC0](https://github.com/jorjives/open-idl/blob/main/templates/LICENSE), so what you build
from one is yours without attribution.

| Template | For |
|---|---|
{rows}

Not sure which? [Annual product](annual-product.md) fits most personal lines; the
[examples](../examples/index.md) show each shape grown into a real product.
"""


def render() -> dict[str, str]:
    """Every generated page, by path relative to the repository."""
    pages = {"docs/examples/index.md": examples_index(), "docs/templates/index.md": templates_index()}
    for n, (stem, line, shows) in enumerate(EXAMPLES, start=1):
        pages[f"docs/examples/{stem}.md"] = example_page(stem, line, shows, n)
    stem, title, shows = VERSIONED
    pages[f"docs/examples/{stem}.md"] = versioned_page(sorted((ROOT / "examples" / "versioned").glob("*.idl")), title, shows, len(EXAMPLES) + 1, "Examples", "examples/versioned")
    for n, (stem, title, shows) in enumerate(TEMPLATES, start=1):
        pages[f"docs/templates/{stem}.md"] = template_page(stem, title, shows, n)
    stem, title, shows = VERSIONED_TEMPLATE
    pages[f"docs/templates/{stem}.md"] = versioned_page(sorted((ROOT / "templates" / "versioned").glob("*.idl")), title, shows, len(TEMPLATES) + 1, "Templates", "templates/versioned")
    return pages


def main() -> int:
    for rel, content in render().items():
        path = ROOT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(rel)
    return 0


if __name__ == "__main__":
    sys.exit(main())
