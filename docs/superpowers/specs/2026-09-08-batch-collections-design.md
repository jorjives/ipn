# Batch collections: a book whose risks carry items

> **Status:** Approved — 2026-09-08

Date: 2026-09-08. An underwriter simulating a rate change needs the book to include
the schedules that actually move premium: specified items, named drivers, travellers,
fleet bikes, scheme members. `batch` already prices a rectangular CSV of scalar
answers. A collection is a nested table, so those schedules cannot live in a cell.
This spec is how `batch` takes them.

The engine already rates collections. `quote` and scenarios already load them from a
CSV of fields (`specified_items=jewellery.csv`, `given specified_items from "…"`).
`batch` does not grow a new rating path. It grows a way to bind that same CSV shape
to many risks at once.

## Goal

`python3 -m ipngine batch FILE.ipn RISKS.csv specified_items=items.csv` prices every
row of the book with that row's items. A risk with no matching item rows has an empty
collection (home's `at most 10` still holds). A product that requires items
(`drivers, 1 to 4`) declines those rows with the existing bounds reason. A book of
leasing schemes is one members file, not one file per scheme.

Out of scope: wide numbered columns (`item1_value`, `item2_value`), packed cells
(`watch:2000; necklace:4000`), Excel workbooks, changing `quote`, changing the
language, per-item columns on the batch output, and a second live Price a book
sample (the terrace-factor contents book stays the in-browser demo). The site
copy, CLI pages, and example notes that today say items cannot be batched are
in scope: after this work they describe the two-file join.

## Decisions

- **Buy-vs-build: a second CSV joined on `risk`, not a new file format.** Policy
  extracts and item extracts already look like this. `quote` already reads a CSV
  whose columns are the item's fields (`items_from_file` / `given_item`). The new
  work is grouping those rows by a join key and handing each risk its list. No
  pandas, no JSON-in-a-cell, no second parser.
- **The join key is `risk`, matching the column `batch` already writes.** If the
  book omits `risk`, items join to the 1-based row number as text (`"1"`, `"2"`),
  which is today's output. If the book includes `risk`, that value is the identifier
  (a policy number is fine), it must be unique and non-blank, and the output uses
  it. Match is stripped text, not numeric: `"01"` and `"1"` are different, so a
  leading-zero policy number survives.
- **Collection files are named like `quote`.** Extra arguments are
  `collection=file.csv`. A name that is not a collection is an error. Several
  collections are several files, each joined on `risk` independently. A collection
  with no file is empty, as today.
- **Path-in-cell stays for one risk.** A collection column on the book whose cell
  is a filename still loads that file through `items_from_file` (path relative to
  the product, as `quote` does). If the same collection is also given as a CLI
  file, that is a run-level error. The joined file is the book form; the cell is
  the existing one-risk hook.
- **Joined file paths are the path the user gave**, the same as `RISKS.csv`. They
  are not resolved against the product directory. `quote`'s `items=file.csv`
  behaviour is unchanged.
- **A stray item is a book error, not a silent drop.** An item row whose `risk` is
  not in the book stops the run (exit 2) before any premium is written. A typo in a
  join key would otherwise leave jewellery off a policy and look like a rate
  change. A bad field on an item that *does* join is reported on that risk's
  `error` column; the other risks still price.
- **Operability / DX.** Standard library `csv` only. Tests in `tests/test_cli.py`
  and `tests.test_site` (the site cannot keep the old limitation).
  `python3 -m ipngine batch` is how a real book is run; the Price a book page
  keeps calling `cli.batch` for the prepared contents sample. Docs live in
  `docs/` and ship with GitHub Pages as they do today. A small
  `examples/home-risks.csv` and `examples/home-specified-items.csv` make the
  documented command real. `python3 -m unittest` is the check. The engine,
  grammar, and playground editor do not change. Generated example pages are
  still written only by `scripts/site_pages.py`.
- **The site tells the truth.** No public page says a repeatable item cannot be
  given to `batch`. Underwriters meet the two-file shape on Price a book and in
  the language reference, not only under For engineers. The live comparison
  stays the twelve-risk contents sample (no collection); the page then shows
  the home jewellery files as the shape for products that have items, and
  points at the command that runs them.

## Why not the other shapes

A wide row (`item1_description` … `item10_value`) fits home and motor and dies on
leasing (`members, at least 1` with no upper bound). A packed cell is not how a
book is held. Path-in-cell already works in tests (`bikes=bikes.csv` on a single
batch row) and does not scale: ten thousand policies with jewellery would be ten
thousand files, and the path is resolved next to the `.ipn`, not the book.

## Components

```
RISKS.csv ──▶ batch ──▶ one output row per risk
                 ▲
collection=items.csv ──▶ items grouped by `risk` ──▶ inputs[collection] for that row
                 ▲
path-in-cell (optional, existing) ──▶ items_from_file, product directory

docs/book.md, cli.md, inputs.md, getting-started.md, glossary.md, embedding.md,
README, examples/home.ipn comment ──▶ site (generated home.md via site_pages.py)
```

`engine.check_inputs`, `engine.check_eligibility`, and `engine.rate` are unchanged.
Collection bounds (`at least`, `at most`) already decline in `check_eligibility`.
`for each` already walks `inputs[collection]`.

### CLI

```
python3 -m ipngine batch FILE.ipn RISKS.csv [collection=file.csv ...]
```

`main` accepts `batch` with two or more arguments after the product, as `quote`
does: the first is the book, the rest are `name=value`. Today `len(argv) == 3` is
required; that check becomes “at least the book, then optional bindings”.

### The book

Columns are input names, optional `select`, and optional `risk`. `risk` is
reserved, like `select`: it is not an input. Duplicate or blank `risk` values are
a run-level error, the same class as an unknown column (exit 2, one line, no
premiums).

A collection's name may still appear as a column whose cells are filenames, unless
that collection was given on the command line.

### The items file

Header: `risk`, then the item's field names. `risk` is required. A blank `risk`
on an items row is a run-level error, the same as a stray id. Unknown field
names are the existing `unknown <singular> field '…'` error, attached to that
risk. Missing required fields are the existing `<singular> is missing …`, same
place. Calculated and provided fields follow `given_item` as they do for `quote`.
Blank cells are fields not given. Completely empty rows are skipped. Row order
in the file is item order on the risk.

The load groups rows into `dict[str, list[dict]]` keyed by stripped `risk`. A
sibling of `items_from_file` in `parser.py` owns this: it reuses `given_item` and
does not treat `risk` as a field. `cli.batch` opens the path as given and passes
each risk its list, or `[]`.

### Errors

| Condition | Where | Exit |
|---|---|---|
| Unknown book column; unknown extra argument; extra argument is not a collection; CLI file and path-in-cell for the same collection; book `risk` blank or duplicated; items file missing `risk`; item row whose `risk` is blank or not in the book; cannot read a collection file | Before any premium row | 2 |
| Unknown or missing item field; table/expression error on that risk | That risk's `error` column; other rows still price | 0 |
| Empty collection on a product that requires items | That risk is declined with the existing bounds reason, and still priced | 0 |

A run-level error prints one line on stdout (batch already writes its
unknown-column message as a single CSV row). Keep that pattern: one row, the
message in the first cell.

### Example

Home contents, enrichment stubbed as provided columns, two risks with jewellery
and one without:

```
python3 -m ipngine batch examples/home.ipn examples/home-risks.csv specified_items=examples/home-specified-items.csv
```

```
# home-risks.csv
risk,postcode,contents_sum,property_type,alarm,occupied_during_day,previous_claims,flood_risk,theft_area
A,SW1A 1AA,20000,terrace,no,yes,0,low,low
B,E1 6AN,20000,terrace,no,yes,0,low,low
C,M1 1AE,80000,detached,yes,no,1,medium,high

# home-specified-items.csv
risk,description,value
A,watch,2000
C,necklace,4000
C,painting,8000
```

Risk `B` has no jewellery. Risk `C` has two items; `for each item` adds them. A
row that put specified items over half the contents refers for the reason the
product already declares. `specified_items` is omitted from the book columns.

## Testing

`tests/test_cli.py`, beside the existing `BatchCommand` cases.

- Two book rows, items only for the first: first net includes `for each`, second
  does not; output `risk` is `"1"` / `"2"` when the book has no `risk` column.
- Book `risk` column `H-1`, `H-2`: output and join use those strings.
- Product requiring items (`1 to 4`): a row with no item rows is declined
  `…: at least 1 required` and still has a premium.
- Item file names a `risk` that is not in the book: exit 2, no premium rows.
- One item missing a field: that risk's `error` column; the next risk prices.
- Path-in-cell with a sidecar next to the product still works (the fleet test
  that already does this).
- `specified_items=…` and a `specified_items` column on the book: exit 2.
- Extra argument `colour=x.csv` or `contents_sum=x.csv`: exit 2.

The home example files are part of the docs contract: the command in `cli.md`
runs and writes three priced rows (A with one item, B with none, C with two).

`tests.test_site` (or a focused test beside it) pins the site:

- No hand-written page under `docs/` except this spec tree contains
  “cannot be given in a batch row” (or equivalent). `book.md` and `cli.md` are
  the pages that say it today.
- `cli.md` usage and the `batch` section show
  `[collection=file.csv …]` and the home command with
  `specified_items=examples/home-specified-items.csv`.
- `book.md` does not claim items are impossible; it contains the two-file
  shape (the `risk` column on both CSVs).
- `examples/home-risks.csv` and `examples/home-specified-items.csv` exist.
- After `scripts/site_pages.py`, `docs/examples/home.md` mentions the batch
  command (via the leading comment on `examples/home.ipn`).

## Site

The public site is the underwriter path. Leaving the join only in For engineers
would keep the gap this work closes. Pages keep their current paths and
`nav_order`. No new nav entry. Voice follows Design: the files are the
explanation, then one sentence of meaning.

### Price a book (`docs/book.md`)

The live demo stays the prepared contents pair in `docs/assets/book/`
(`before.ipn`, `after.ipn`, `risks.csv`): terrace factor 1.00 against 1.15,
twelve scalar risks. `book.js` still calls `cli.batch` twice on that sample.
It does not grow an items-file editor in this work.

The intro that today says a repeatable item cannot be given in a batch row is
removed. After the comparison, a short **Risks with items** section:

- A book with specified items, drivers, or members is two CSVs, joined on
  `risk`.
- Show the home example files (the same pair as `cli.md`), as tables or fenced
  CSV, not as a second live run.
- The command that prices them, and a link to [Command line](cli.md).
- One sentence that an empty collection is what you get when the items file
  has no row for that risk, and that a product which requires items declines
  those rows.

`tests.test_site.Book` keeps pinning `before.ipn`, `after.ipn`, `risks.csv`.
It also asserts the page no longer contains the old limitation and that it
shows `specified_items`.

### Command line (`docs/cli.md`)

The three-command synopsis at the top includes the optional bindings. The
`batch` section: columns of the book (inputs, `select`, `risk`); the extra
`collection=file.csv` arguments; the `risk` join (row number when omitted);
the home command and the two files; a declined row is still priced. Delete
“A repeatable item cannot be given in a batch row”. Path-in-cell stays one
sentence so the fleet-style sidecar is not a secret. The link to Price a book
stays: that page is the in-browser comparison, this page is a real book,
including items.

### Repeatable items (`docs/reference/inputs.md`)

The Repeatable items section already shows `given specified_items from "…"`
and `quote` with an items file. Add that `batch` takes the same CSV with a
`risk` column, one file per collection, joined to the book. Do not duplicate
the CLI flags here; link to `cli.md`. Defaulting: a batch row still takes
input defaults; a collection with no file and no matching item rows is empty.

### Getting started (`docs/getting-started.md`)

Under **Where next**, the Price a book bullet stays. Add that a book whose
risks carry specified items (or drivers, members) is a second CSV, shown on
that page and run with `batch` on the command line. No worked items example
in Getting started; the teaching product there has no collection. The
playground page already points at Price a book; it needs no extra sentence.

### Example pages (generated)

Do not hand-edit `docs/examples/*.md`. Add one line to the leading comment of
`examples/home.ipn` so the generated Home contents page names the sample book
and `python3 -m ipngine check` remains the last “Run it with” line the
generator already consumes. The batch command belongs in the prose of the
comment, not as a second `Run it with`. `python3 scripts/site_pages.py`
rewrites `docs/examples/home.md`; `tests.test_site` already fails when that
page is stale.

Other collection examples (motor, travel, family, leasing) do not each need a
sample book in this work. Home is the teaching product.

### For engineers

`docs/embedding.md`: `batch` may take collection files, same join as the CLI;
the supported interface is still text in, CSV out. `docs/engineers.md` needs
no extra paragraph if it only names the three commands. `docs/contributing.md`
module table stays `check`, `quote` and `batch`. README: the household
one-file example stays; a second line shows home with `specified_items=`.

### Glossary (`docs/glossary.md`)

**Collection, item** already names specified items. Add that a book prices
them from a second CSV joined on `risk`, with a link to the command line
(or to Price a book). One clause, not a new entry.

### What the site does not do in this work

- A second live Price a book product with jewellery, drivers, or members.
- Uploading an items CSV in the browser.
- Changing the playground Check page.
- A new sidebar entry.
- Hand-editing generated example or template pages.
