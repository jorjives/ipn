# Batch collections — Slice Scope

> Based on spec: `docs/superpowers/specs/2026-09-08-batch-collections-design.md`
> Next step: invoke writing-plans with this document

---

## Slice 1: Price a book whose risks carry items

**Delivers:** An underwriter can price a whole book with specified items, drivers, or members from one second CSV joined on `risk`, instead of one file per policy.

**Operational note:** Verification stays the existing unit tests. A small home sample book and jewellery file make the later documented command real. Standard-library CSV only.

**Build note:** Reuse the item CSV shape quote already reads, and the same field checks. Group by `risk`; do not add a new file format, packed cells, or a wide row of numbered item columns.

### Prerequisites

- None. `batch` already prices a rectangular book of scalar answers, and `quote` already loads one risk's items from a CSV of fields.

### Acceptance Criteria

- [ ] Extra `collection=file.csv` arguments on `batch` attach that file's rows to the matching book risks. Several collections are several files, each joined independently. A collection with no file is empty.
- [ ] When the book has no `risk` column, items join to the 1-based row number as text (`"1"`, `"2"`), which is also the output. When the book has `risk`, that stripped text is the identifier, it must be unique and non-blank, and the output uses it. `"01"` and `"1"` are different.
- [ ] A risk with no matching item rows has an empty collection. A product that requires items (`1 to 4`) declines those rows with the existing bounds reason and still prices them.
- [ ] An item row whose `risk` is blank or not in the book, a book `risk` that is blank or duplicated, a missing `risk` header on the items file, an extra argument that is not a collection, a CLI file and a path-in-cell for the same collection, or an unreadable collection file: the run stops with exit 2, one message row, no premium header or premium rows.
- [ ] An unknown or missing item field on a row that did join is that risk's `error` column; the other risks still price. Completely empty item rows are skipped. Row order in the file is item order on the risk.
- [ ] A collection column whose cell is a filename still loads that file relative to the product (the existing one-risk sidecar). Joined file paths are the path the user gave, not resolved against the product.
- [ ] The home sample book of three risks and its jewellery file exist. Pricing them yields three rows: one item, none, two. `specified_items` is not a column on the book.

### UAT

**What you can now do:** Price the home book so jewellery on some policies, and none on others, moves the premium in one run.

**How to try it:**
1. Take the home contents product and its sample book of three risks (A, B, C).
2. Point `batch` at that book and at the jewellery file (`specified_items=`).
3. Compare the three output rows: A has a watch, B has no jewellery, C has a necklace and a painting.

**What you should see:** Three priced rows. B is cheaper than A (no specified-item load). C's two items are included. No error column filled. Exit 0.

**Why this matters:** A rate-change simulation is only honest if the schedules that actually move premium are on the book.

---

## Slice 2: The site tells the two-file shape

**Delivers:** An underwriter looking at Price a book, the command line, or the language reference sees how a book with items is two CSVs joined on `risk`, and no public page still says a repeatable item cannot be batched.

**Operational note:** Generated example pages are still written only by the site generator. The live Price a book comparison stays the twelve-risk contents sample with no items file in the browser.

**Build note:** No new nav entry, no second live demo, no items-file editor. Voice follows Design: the files are the explanation, then one sentence of meaning.

### Prerequisites

- A book whose risks carry items can be priced from a second CSV joined on `risk`, and the home sample pair exists so the documented command is real.

### Acceptance Criteria

- [ ] No hand-written page under the public docs (except this spec tree) still says a repeatable item cannot be given in a batch row, or equivalent.
- [ ] Price a book keeps the live contents comparison as it is, then adds a short **Risks with items** section: two CSVs joined on `risk`, the home example files, the command that prices them, a link to Command line, and one sentence that an empty collection is no matching row (and a product that requires items declines those rows).
- [ ] Command line usage and the `batch` section show optional `collection=file.csv` bindings, the `risk` join (row number when omitted), the home command and files, that a declined row is still priced, and one sentence that path-in-cell still works. The three-command synopsis includes the optional bindings.
- [ ] Repeatable items in the language reference says `batch` takes the same CSV with a `risk` column, one file per collection, and links to Command line rather than duplicating flags. Getting started's **Where next** mentions a second CSV for books with items. Glossary **Collection, item** adds one clause with a link.
- [ ] For engineers: embedding notes that `batch` may take collection files, same join, still text in / CSV out. README shows a second line for home with `specified_items=`. The leading comment on the home product names the sample book so the generated Home contents page mentions the batch command, while `check` remains the last "Run it with" line.

### UAT

**What you can now do:** Learn on the public site how to include jewellery (or drivers, or members) when you price a book, then run that command.

**How to try it:**
1. Open Price a book. Confirm the live twelve-risk comparison is still there, then read **Risks with items**.
2. Follow the link to Command line and find the home command with the jewellery file.
3. Run that command (or open the generated Home contents page and follow it from there).

**What you should see:** No sentence that items cannot be batched. The two-file shape with a `risk` column on both CSVs. The same three priced rows as slice 1.

**Why this matters:** Underwriters meet this job on the site, not only under For engineers. Leaving the join undocumented would keep the gap this work closes.
