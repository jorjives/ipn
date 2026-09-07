---
title: Grammar
parent: Language reference
nav_order: 12
---

# Grammar

The language, formally. The pages before this one say what each line means; this one says
exactly what may be written, for anyone implementing another engine or tool. It is
transcribed from the reference parser (`ideclare/parser.py`, `expr.py` and
`scenarios.py`); where they disagree, the parser is the specification and the disagreement
is a bug to report.

Notation: `[ x ]` optional, `{ x }` zero or more, `a | b` alternatives, `'word'` a literal
word, and lower-case names are rules. Indented rules are lines nested under the line above:
indentation in the grammar is indentation in the product, and a bracket opens and closes at
one indent. The site's tooling reads the grammar from this page (`scripts/grammar_table.py`
compiles it into the playground's completion table, and `tests.test_grammar` checks every
example and template parses under it), so the notation is held to exactly.

## Lexical structure

A file is lines. Structure comes from indentation, not brackets.

- **Indentation** is by spaces. A line indented deeper than the one above is inside it. A
  line indented less must match the indent of an earlier line, and lines inside one block
  must share the same indent, otherwise the error is `inconsistent indentation`. Two
  spaces is the convention.
- **Comments** run from `#` to the end of the line, except inside a quoted string. Blank
  lines are ignored.
- **Tokens**, longest match first:

  | Token | Form |
  |---|---|
  | string | `"` any characters but `"` `"`; no escapes |
  | date | `YYYY-MM-DD` |
  | number | digits, optionally `.` digits; no sign (see `unary`) |
  | word | a letter or `_`, then letters, digits, `_` or `/`; so `yes/no` is one word, and `co-payment` is a word by exception |
  | operator | `<=` `>=` `<` `>` `:` `,` `%` `(` `)` `+` `-` `*` `/` `^` |

  A `%` directly after a number makes a percentage. Names with spaces (a cover, a label, a
  reason, a table) are strings.

## File

```
file            = product_block { block }
block           = inputs_block | enrichment_block | table_block | eligibility_block
                | cover_block | rating_block | lifecycle_block | claims_block
                | scenario_block | upgrading_block
```

`product` comes first. The other blocks may follow in any order and, except `lifecycle` and
`upgrading`, may repeat: a second `inputs` block adds inputs, a second `rating` block adds
steps. A block that names something must come after the block that declares it: a table
`keyed on` an input, an eligibility rule that says `Racing selected`, an enrichment `for
each bike`, a `claims` block that restates `lifecycle` lines.

## product

```
product_block   = 'product' string
                    { 'published' date
                    | 'territory' word { ',' word }
                    | 'currency' word
                    | 'term' ( expression ( 'days' | 'months' | 'years' ) | 'until' name ) }
```

Header lines may come in any order. `term` defaults to 12 months. With several
territories, `territory` becomes a `choice` input. The currency follows the territory
unless `currency` is given; a territory the engine has no currency for needs one.

## inputs

```
inputs_block    = 'inputs'
                    { input_line }
input_line      = name ':' type [ ',' 'default' value ]
                | name ':' 'collection' 'of' name [ bounds ]
                    { field_line }
                | name ':' 'calculated'
                    { rating_step }
field_line      = name ':' type [ ',' 'default' value ]
                | name ':' 'calculated'
                    { rating_step }
type            = 'money' | 'number' | 'integer' | 'text' | 'yes/no' | 'date'
                | 'choice' 'of' choice_value { ',' choice_value }
                | 'choice' 'of' name 'from' string [ 'for' name { ',' name } ]
choice_value    = word | string
bounds          = ',' integer 'to' integer | ',' 'at' 'least' integer | ',' 'at' 'most' integer
value           = number | date | word | string
```

A collection needs at least one field; a field cannot itself be a collection, and cannot
share a name with an input. The steps under `calculated` are those allowed inside `for
each` (see `rating`), with the item's other fields, or the other inputs, in scope.

A choice value that is not one word is a string. A choice `from` a table takes the distinct
cells of that key column of the table named; the names after `for` are keys of the same
table and inputs (or, for an item's field, the item's other fields), and a value is then
accepted only when the table lists it on a row matching them. The table is declared after
the inputs that draw on it.

## enrichment

```
enrichment_block = 'enrichment' string [ 'for' 'each' name ] 'from' name { ',' name }
                     'provides'
                       { field_line }
                     [ 'when' 'unavailable' ':' fallback ]
                     [ 'held' 'for' 'the' 'term' ]
fallback         = name 'is' value { ',' name 'is' value }
                 | ( 'refer' | 'decline' ) 'because' string
```

`provides` is required and its fields are plain types (not `calculated`). The keys after
`from` are inputs, or the item's fields when `for each` is given.

## table

```
table_block     = 'table' string [ 'from' string ] 'keyed' 'on' key { ',' key }
                    { csv_line }
key             = name | 'months' 'in' 'force' | 'days' 'in' 'force'
csv_line        = cell { ',' cell }          -- the first line is the header
cell            = number | number '%' | number '-' number | number '+' | '*' | word
```

Rows come from the file or from the lines below, never both. The header names every key
column (as the input's name; `months_in_force` for `months in force`) and at least one
value column, unless a choice draws on the table, when it may be keys alone. A key cell is
checked against its input: a choice must be one of the choices, a `yes/no` cell `yes`,
`no` or `*`, a numeric cell a number, a band or `*`. A key column a choice draws on is
read as text: every cell is a value, and `*` or a band there is an error.

## eligibility

```
eligibility_block = 'eligibility'
                      { ( 'decline' | 'refer' ) 'when' condition 'because' string }
```

## cover

```
cover_block     = 'cover' cover_name [ 'optional' ]
                    { [ dated ] cover_line }
cover_name      = word | string
dated           = { 'from' date | 'until' date }
cover_line      = 'class' ( word | number )
                | 'premium' expression [ 'when' condition ]
                | 'premium'
                    { premium_step }
                | 'limit' expression [ 'per' 'term' [ 'per' name ] ]
                | excess_word expression [ 'per' 'term' ] [ ',' 'minimum' expression ] [ ',' 'maximum' expression ]
                | excess_word
                    { excess_row }
                | 'excludes' 'when' condition 'because' string
                | 'available' 'when' condition
                | 'in' 'force' ( 'from' | 'until' ) expression
                | 'waiting' 'period' integer 'days'
                | 'reinstatement' 'at' number '%' 'of' 'premium' 'pro' 'rata'
premium_step    = 'base' [ string ] expression [ 'when' condition ]
                | 'factor' string
                    { factor_row }
                | 'factor' string operator expression [ 'when' condition ]
                | 'add' [ string ] expression [ 'when' condition ]
                | ( 'discount' | 'load' ) [ string ] expression [ 'when' condition ]
                | ( 'minimum' | 'maximum' ) [ string ] expression [ 'when' condition ]
excess_word     = 'excess' | 'deductible'
excess_row      = condition ':' expression
                | 'otherwise' ':' expression      -- required, and last
```

`per term per X` names an item (which makes the cover per item) or a fact a claim on the
cover `asks` for. A `premium` reads inputs only: not `net`, `premium`, a tax or a cover
name, and the fields of at most one collection. `reinstatement` needs a `limit ... per term`. Rows of an excess table
may use the facts the cover's claim asks for. See [Versions](versions.md) for what
`dated` lines may replace or accumulate.

## rating

```
rating_block    = 'rating'
                    { rating_step | each_block | allocate_block }
allocate_block  = 'allocate'
                    { cover_name number '%' }
each_block      = 'for' 'each' name [ ',' 'ordered' 'by' order_key { ',' order_key } ]
                    { rating_step }
order_key       = expression [ 'descending' ]
rating_step     = 'base' [ string ] expression [ 'for' cover_name ] [ 'when' condition ]
                | 'factor' string [ 'for' cover_name ]
                    { factor_row }
                | 'factor' string operator expression [ 'for' cover_name ] [ 'when' condition ]
                | 'add' [ string ] expression [ 'for' cover_name ] [ 'when' condition ]
                | 'add' 'cover' 'premiums'
                | ( 'discount' | 'load' ) [ string ] expression [ 'for' cover_name ] [ 'when' condition ]
                | ( 'minimum' | 'maximum' ) [ string ] expression [ 'when' condition ]
                | 'tax' ( word | string ) expression [ 'when' condition ]
                | 'fee' string expression [ 'when' condition ]
                | 'commission' string expression [ 'when' condition ]
                | 'round' 'to' expression
factor_row      = condition ':' operator expression
                | 'otherwise' ':' operator expression     -- last, if present
operator        = 'x' | '+' | '-'
```

Inside `for each` and under `calculated` only `base`, `factor`, `add`, `discount`, `load`,
`minimum` and `maximum` are allowed (and `tax` inside `for each`), and `position` is a
word. A `for each` block cannot nest. The rows of a factor need not end in `otherwise`; a
factor with no matching row applies nothing. A `tax` or `commission` expression without
`N% of` is a rate of the net; with it, the expression is the amount. In a line's expression
or condition `net`, `premium`, every `tax` above it (a quoted label as a string) and every
cover name are words. A cover's `class` is a word or a number. The rows of `allocate` must sum to 100%.
`add cover premiums` is written exactly once, at the top level or inside `for each`, when any
cover has a `premium`, and not at all otherwise.

## lifecycle

```
lifecycle_block = 'lifecycle'
                    { lifecycle_line }
lifecycle_line  = 'cooling' 'off' expression 'days' ',' 'full' 'refund'
                | 'cancellation' 'by' ( 'customer' | 'insurer' ) ':' refund [ ',' 'fee' number ]
                | 'adjustment' ':' 'not' 'allowed'
                | 'adjustment' ':' 'reprice' [ 'on' 'the' 'current' 'version' ] ',' 'charge' 'pro' 'rata' 'difference' [ ',' 'fee' number ]
                | 'lapse' 'when' 'unpaid' 'after' integer 'days'
                | 'instalments' integer 'monthly' [ ',' 'charge' number '%' ]
                | 'renewal' ':' 'none'
                | 'renewal'
                    { renewal_line }
refund          = 'refund' 'pro' 'rata' | 'full' 'refund' | 'no' 'refund' | 'refund' expression
renewal_line    = 'invite' integer 'days' 'before' 'expiry'
                | 'increase' 'capped' 'at' number '%'
                | 'decrease' 'collared' 'at' number '%'
                | 'index' target 'by' expression [ ',' 'at' 'least' number ] [ ',' 'at' 'most' number ]
                | 'decline' 'when' condition 'because' string
target          = name | name name        -- an input, or an item and its field: bike value
```

The expression after `refund` may use `days in force` and `months in force`. The `index`
expression may use `claims in term`; a percentage (`by 5%`) scales, anything else adds.
Restating `index` for the same target replaces the earlier line.

## claims

```
claims_block    = 'claims'
                    { claim_block | loading_line | terms_block }
claim_block     = 'claim' cover_name
                    [ asks_block ]
                    { [ dated ] claim_line }
asks_block      = 'asks'
                    { field_line }
claim_line      = 'requires' name { ',' name }
                | 'pays' 'claimed' 'amount' [ [ ',' ] pays_clause { ',' pays_clause } ]
                | 'pays' expression [ monthly ] { ',' pays_clause }
                | 'co-payment' expression [ 'when' condition ]
                | 'decline' 'when' condition 'because' string
                | ( 'depreciation' | 'settlement' )
                    { factor_row }
                | 'does' 'not' 'count' 'towards' 'claims' 'in' 'term'
                | 'counts' 'towards' 'claims' 'in' 'term' 'when' condition
monthly         = 'per' 'month' 'for' expression 'months' [ 'after' expression ( 'days' | 'weeks' | 'months' ) ]
pays_clause     = 'up' 'to' 'limit'
                | 'less' excess_word
                | 'less' 'co-payment'
                | 'up' 'to' expression [ 'when' condition ]
loading_line    = 'after' integer ( 'claim' | 'claims' ) 'in' 'term' ':' 'renewal' 'load' 'x' number [ 'unless' condition ]
terms_block     = 'after' integer ( 'claim' | 'claims' ) 'in' 'term' [ 'unless' condition ]
                    { lifecycle_line }
```

A `claim` names a declared cover. Facts under `asks` are plain types and may not reuse a
known word; `asks` cannot be dated. Lines in a `terms_block` cannot be dated. The
`pays_clause`s apply in the order written.

## upgrading

```
upgrading_block = 'upgrading'
                    { upgrade }
upgrade         = name ':' 'ask'
                | name ':' old_expression
                | name ':' old_expression 'when' old_condition { ',' old_expression 'when' old_condition } ',' 'otherwise' old_value
                | name
                    { upgrade_row }
                | name ':' 'for' 'each' old_item_name
                    { upgrade }
upgrade_row     = old_condition ':' old_value
                | 'otherwise' ':' old_value          -- required, and last
old_value       = 'ask' | old_expression
old_expression  = expression
old_condition   = condition
```

`name` is an input of this version (or, under `for each`, a field of the collection).
`old_expression` and `old_condition` are expressions whose words belong to the previous
version, checked when the history is loaded, plus the choice values of the input being
set.

## scenario

```
scenario_block  = 'scenario' string
                    { given_line | select_line | when_line | expect_line }
given_line      = 'given' name value { ',' name value }
                | 'given' item_name field_name value { ',' field_name value }
                | 'given' collection_name 'from' string
select_line     = 'select' cover_name { [ ',' ] cover_name }
when_line       = 'when' event
expect_line     = 'expect' expectation
```

Every event carries `'on' date`; the first date on the line is the event's. A `given` for
a date input is `given departure_date 2026-07-10`; text values are quoted.

```
event           = 'bound' 'on' date [ 'unpaid' ]
                | 'paid' 'on' date
                | 'accepted' 'by' 'underwriter' 'on' date [ 'with' underwriting_term { ',' underwriting_term } ]
                | 'declined' 'by' 'underwriter' 'on' date
                | 'reinstated' cover_name 'on' date
                | 'cancelled' 'by' ( 'customer' | 'insurer' ) 'on' date
                | 'adjusted' 'on' date 'with' name value { ',' name value }
                | 'adjusted' 'on' date 'adding' item_name field_name value { ',' field_name value }
                | 'adjusted' 'on' date 'removing' item_name integer
                | 'claim' cover_name [ 'on' item_name integer ] [ 'for' number ] 'on' date claim_detail
                | 'renewed' 'on' date [ 'with' name value { ',' name value } ]
underwriting_term = ( 'load' | 'discount' ) number '%'
                  | 'excess' number 'on' cover_name
                  | 'excluding' cover_name
claim_detail    = [ 'reported' date ] [ 'with' with_item { ',' with_item } ]
with_item       = name                       -- a piece of evidence
                | name value                 -- a fact the claim asks for
```

```
expectation     = 'eligible' | ( 'declined' | 'referred' ) [ string ]
                | 'cover' cover_name [ 'on' item_name integer ] cover_state [ string ]
                | 'cover' cover_name [ 'on' item_name integer ] 'limit' number
                | 'cover' cover_name [ 'on' item_name integer ] 'remaining' number [ 'for' name string ]
                | 'cover' cover_name 'excess' 'remaining' number
                | 'net' [ 'for' item_name integer | 'for' share ] number
                | 'premium' number | 'tax' ( word | string ) [ 'for' share ] number | 'fee' string number
                | 'commission' string [ 'for' share ] number | 'currency' word
                | 'factor' string operator number
                | 'instalment' 'charge' number | 'instalment' integer number
                | 'status' word [ 'on' date ] | 'expiry' date
                | 'refund' [ 'for' share ] number | 'additional' 'premium' [ 'for' share ] number | 'return' 'premium' [ 'for' share ] number
                | 'refused' [ string ]
                | 'claim' 'paid' | 'claim' 'declined' [ string ] | 'payout' number
                | 'claims' 'in' 'term' integer
                | 'benefit' 'paid' number 'by' date
                | 'renewal' 'premium' [ 'for' share ] number | 'renewal' 'invite' date
                | 'renewal' 'offered' | 'renewal' 'declined' [ string ]
                | 'renewal' 'needs' name { ',' name }
                | 'version' date
                | name value                 -- an input as the policy now holds it
cover_state     = 'included' | 'excluded' | '"not selected"' | '"not available"'
share           = cover_name | 'class' ( word | number )
```

Amounts in expectations are compared as numbers, so `2100` equals `2100.00`.

## Expressions

Conditions and amounts share one grammar. Precedence runs from loosest at the top to
tightest at the bottom; `^` is right-associative. `less` is `-`, and `N% of` takes the whole sum
after it (`12% of net less Fire`).

```
condition       = expression
expression      = or_expr
or_expr         = and_expr { 'or' and_expr }
and_expr        = not_expr { 'and' not_expr }
not_expr        = 'not' not_expr | comparison
comparison      = sum [ ( '<' | '<=' | '>' | '>=' | 'is' | 'is' 'not' ) sum ]
sum             = term { ( '+' | '-' | 'less' ) term }
term            = unary { ( '*' | '/' ) unary }
unary           = '-' unary | power
power           = postfix [ '^' unary ]
postfix         = primary [ '%' [ 'of' sum ] ] [ 'selected' ] [ lookup ]
lookup          = 'from' string [ 'interpolated' [ 'linearly' | 'geometrically' ] 'on' name ]
primary         = number | string | date | 'yes' | 'no' | name
                | '(' expression ')'
                | function '(' expression { ',' expression } ')'
                | 'count' 'of' collection_name
                | ( 'total' | 'highest' | 'lowest' ) field_name 'of' collection_name
                | ( 'any' | 'every' ) item_name 'where' condition
                | 'claims' 'in' 'term'
                | ( 'days' | 'months' ) 'in' 'force'
                | 'reported' 'after' number 'days'
                | 'within' number ( 'days' | 'months' ) 'of' 'inception'
function        = 'exp' | 'ln' | 'sqrt' | 'round' | 'min' | 'max'
```

`x from "Table"` is only read when `x` is a bare name: the value column. `N%` alone is
the number N/100; `N% of x` multiplies. `X selected` names an optional cover. Dates
subtract to a number of days and compare like numbers.

The last four `primary` forms are English phrases the engine folds into single words before
it parses the expression; they are only meaningful in some places:

| Phrase | Becomes | Where |
|---|---|---|
| `claims in term` | the count of paid claims that count, this term | renewal rules and `index`, claims |
| `reported after N days` | `days_to_report > N` | claim `decline when` |
| `within N days of inception`, `within N months of inception` | `days_since_inception < N`, `months_since_inception < N` | claim rules |
| `days in force`, `months in force` | the policy's age at the event | cancellation `refund`, tables keyed on them |

**Words.** An expression may use: every input and enrichment-provided field; every
choice value; every cover name (before `selected`); the singular item name and the item's
fields (inside `for each`, a per-item cover or claim, a `where`, or a `calculated` field);
`position` inside `for each`; `claim` and `claimed` (the amount claimed) in a cover's
excess and in claim lines; the facts a claim `asks` for, in that claim's lines and its
cover's excess table; `territory`; `yes` and `no`. Any other word is an error when the
file is read, with its line.

**Evaluation.** All arithmetic is decimal. `and` and `or` short-circuit. A comparison
between a number and a missing value, or an aggregate over an empty collection, is an
error rather than a guess.
