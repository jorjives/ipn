# Choices from tables: long lists and dependent choices

## Purpose

`choice of a, b, c` is fine for a handful of values and useless for an occupation list
of a thousand. Insurers also ask dependent questions: the industry first, then an
occupation that only makes sense within it, and each such list is normally owned as a
spreadsheet by the pricing team, with a rating class beside every row. This spec lets a
choice input take its values from a `table`'s key column, narrow them by the value of one
or more other inputs, and do both as fields of a collection item (each person's industry
and occupation). It also lets a choice value be any text, not only a single word.

Agreed with Jorj on 2026-09-07. Decisions marked (Jorj) are his.

## Decisions

- **Choice lists come from a `table`, not a second file format** (Jorj). One CSV is both
  the list and the rating table, loaded by one loader and checked by one validator;
  `class from "Occupations"` works in `rating` with no extra file. A table used only as
  a list may have no value column.
- **A value that is not a single word is written in quotes** (Jorj). `industry is
  construction` for a plain word, `industry is "Health & Social Care"` otherwise. The same
  rule applies to the inline form: `choice of construction, "Health & Social Care"`. A
  cell such as `1234` in a column that feeds a choice is a code, read as text.
- **A choice that is not listed under its keys is an input error**, the same as a value
  that is not one of an inline choice's words today: `occupation "Nurse" is not an
  occupation for industry "Construction"`. It is not an eligibility decline; a platform
  constrains the question before it is asked, and a scenario that gives such a pair is
  wrong.
- **Multi-key is the same feature as single-key.** `for industry, sector` narrows on both.
  Nothing is built for one key that would be rebuilt for two.
- **Not in scope**: display labels beside codes, a `list` block, interpolation on a
  choice column, a key that is an enrichment-provided field, a claim fact (`asks`) drawn
  from a table (tables are keyed on inputs and a fact is not one; the parser refuses it),
  and any user-interface behaviour. The engine offers the list and validates against it; showing it is the
  platform's job.

## Language

### inputs

```idl
inputs
  industry: choice of industry from "Occupations"
  occupation: choice of occupation from "Occupations" for industry
  people: collection of person, 1 to 5
    industry: choice of industry from "Occupations"
    occupation: choice of occupation from "Occupations" for industry
```

- `choice of <column> from "<table>"`: the values are the distinct cells of that key
  column of the named table.
- `for <key>[, <key>]`: the values are the distinct cells of the column on the rows whose
  named key columns match the given inputs. Each key names a column of the same table
  and an input (or, in a collection, a sibling field of the same item) with that name.
  A key may be any input the table can be keyed on: a choice, a `yes/no`, a number.
- `, default <value>` follows as for any input, checked against the list once the table
  is read.
- The inline form `choice of a, "b c", d` accepts quoted values beside words.
- The table must be declared before the choice is used in an expression (the convention
  in every example: `inputs`, then `table`). An input drawing on a table that is never
  declared is an error naming the input and the table when the file has been read.

### table

`table "Occupations" from "occupations.csv" keyed on industry, occupation` is unchanged
in form. Two rules relax or tighten when a choice draws on it:

- A key column that feeds a choice is read as text: every cell is a value, none is `*`,
  a band or a number. A `*` or band in such a column is an error with its row number.
- A table whose every column is a key is allowed when a choice draws on it (it is a list
  with nothing to look up), and still an error otherwise.

Key cells of a column matched against an input whose choices come from the table are, by
construction, within those choices; the existing check is skipped for them rather than
run against an empty list.

### expressions

A choice value from a table is an expression word when it is a word, and a quoted string
otherwise. `industry is construction`, `industry is "Health & Social Care"`. Comparison is
exact text, as `text` inputs compare today. Bare words are added to the product's known
words as inline choices are.

### scenarios, quote and batch

`given industry construction, occupation "Site manager"`, `given person industry
construction, occupation "Site manager"`, a CSV of items whose cells hold the values
unquoted, and `quote ... industry=construction occupation="Site manager"` all take the
value as text and check it against the list. A keyed choice is checked after every input
of the risk (or every field of the item) is known, since the check needs its keys.

## Engine

### Model

`Input` gains `source: tuple[str, str, list[str]] | None`: the table name, the column
and the key names. `choices` is filled from the table as today's inline list is, so every
reader of `choices` (expression words, defaults, `given_value`, table key checks) works
unchanged. `Product.choice_sources` is a convenience over `inputs` and each collection's
`fields` listing every input with a source.

### Table

`Table.values_for(column, ctx) -> list[str]`: the distinct cells of the column, in file
order, on the rows whose other key columns named by the choice's keys match `ctx`. With no
keys it is the whole column. It uses `candidates` and `matches` as `lookup` does, so a
key that is a band or `*` on the table's other columns still narrows correctly.

`load_table` takes `text_columns: set[str]`: columns whose cells are kept as the text
written (stripped), with `*` and bands rejected. It also takes `allow_no_values: bool`.

### Parser

`parse_input_lines` reads `choice of <column> from "<table>" [for key, key]` into an
`Input("choice", source=(table, column, keys))`. `parse_table`, on reading a table,
finds every input (top-level, item field) whose source names it, verifies the column and
every key is a key of the table, verifies each key is an input (or sibling field) the
product knows, passes the source columns as `text_columns`, and fills each input's
`choices` with `values_for(column, {})`; a `default` given on the input line is then
checked. Deferred work at the end of the file reports any input whose table was never
declared. `given_value` unquotes a token before checking a choice.

### Checking a risk

`engine.check_inputs(product, inputs) -> list[str]`: the reasons a risk's answers are
not acceptable, empty when they are. It reports every input that is missing (today's
rule: not text, calculated, collection or provided) and every keyed choice whose value is
not in `values_for(column, keys from the same record)`, at the top level and for each
item of each collection, as `people item 2: occupation "Nurse" is not an occupation for
industry "Construction"`. Scenarios and the `quote` and `batch` commands call it in
place of their own missing-input checks, which are removed. A scenario that fails it
fails with the reason on the scenario's line; `quote` prints the reason and exits 2, as for a missing input;
`batch` records it in the row's error column.

## Buy-vs-build

Nothing new is bought: `csv` from the standard library and the existing `Table` do the
loading, indexing and matching. Rejected: a separate one-column list file and a `list`
block, each a second format for what is already a table.

## Operability / DX

Developed with the existing `python3 -m unittest` suite; no new tooling. Verified by the
parser, table, scenario and CLI tests, by `examples/income.idl` moving from
`occupation_class: choice of class1, class2, class3, class4` to `industry` and
`occupation` drawn from `examples/occupations.csv` (industry, occupation, class) and rated
by `class from "Occupations"`, and by a collection-field case in the tests. The grammar
page gains the new `type` alternative and the site's completion table and example pages
are regenerated by `scripts/site_pages.py`, which `tests.test_site` and
`tests.test_grammar` hold to the page. `docs/reference/inputs.md` and `table.md` document
the forms; `not-yet-supported.md` names labels beside codes.

## Error handling

| Fault | Where | Message |
|---|---|---|
| `choice of x from "T"` where T is never declared | end of file | `industry draws on table 'T', which is not declared` |
| column or key not a key of the table | table line | `'occupation' is not a key of Occupations; keys are industry, occupation` |
| key is not an input or sibling field | table line | `unknown input 'sector'; a choice's keys must be inputs` |
| `*` or band in a column feeding a choice | table line | `Occupations row 4: '*' is not a value; industry lists choices` |
| a table keyed on a choice whose own table comes later | table line | `Other is keyed on industry, which draws on table 'Occupations'; declare Occupations first` |
| a claim fact drawn from a table | asks line | `'why' cannot draw on a table; a claim fact lists its choices` |
| every column a key, no choice draws on it | table line | unchanged: `has no value column; every column is a key` |
| value not in the list (unkeyed) | given / quote | unchanged: `industry is choice, cannot be 'farming'` |
| value not listed under its keys | scenario / quote / batch | `occupation "Nurse" is not an occupation for industry "Construction"` |
| default not in the list | table line | `industry cannot default to 'farming'` |

## Testing

- Parser: the new input form, quoted inline values, defaults, the errors above.
- Tables: `values_for` with no keys, one key, two keys, a band key on another column;
  text columns keep `1234` and reject `*`.
- Scenarios: a keyed pair accepted, a wrong pair failed with its reason, the same for an
  item of a collection and for a CSV of items.
- CLI: `quote` with a quoted value and with a wrong pair.
- Grammar: the example parses under the page; the completion table is regenerated.
