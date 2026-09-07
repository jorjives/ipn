# Open IDL website: GitHub Pages site for the language

Date: 2026-09-07. Autonomous run: Jorj asked for a comprehensive GitHub Pages site for the
language under its release name, Open IDL, covering the full spec, example uses and templates,
published with `gh`. Decisions below are recorded with their reasoning.

## Decisions

- **Name.** The site, README and repo use *Open IDL* (Open Insurance Declaration Language, which is
  what the `.idl` extension and the codename iDeclare both point at). The Python package stays
  `ideclare`: renaming it touches every module and test and is a code decision, not a site one.
  Flagged as a follow-up.
- **Buy-vs-build: Jekyll on GitHub Pages with the Just the Docs remote theme**, source in `docs/`
  on `main`. GitHub builds it; nothing to install, no workflow file, no `node_modules`. The theme
  supplies navigation, search, anchors, callouts and a responsive layout. No sibling project in
  the estate has a Pages site, so there is no local precedent to conform to. A hand-written site
  would re-implement navigation and search; MkDocs would add a build step and a dependency for
  documentation alone.
- **The reference is split into one page per block** under `docs/reference/`, so the sidebar shows
  the language's structure and each page has its own contents. `docs/reference.md` goes; CLAUDE.md
  and README point at the directory.
- **Example and template pages are generated, never hand-written.** `scripts/site_pages.py`
  (stdlib only) reads every `examples/*.idl`, `examples/versioned/*.idl` and `templates/*.idl`,
  runs its scenarios (a failing example fails the build), takes the leading comment block as the
  description and writes `docs/examples/*.md` and `docs/templates/*.md`. `tests/test_site.py`
  asserts the committed pages equal what the script renders, so the site cannot drift from the
  code. Jekyll cannot include files from outside its source directory, which rules out reading
  `examples/` at build time.
- **Templates** are starter products in `templates/`, one per product shape (annual personal
  lines, several items on one policy, a fixed-term benefit with no renewal, commercial
  claims-made, and a versioned pair). Each passes `check`, so they are proven like the examples.
- **`.idl` code is highlighted client-side** by a small script in `_includes/head_custom.html`.
  Rouge has no lexer for this language (`idl` is not a Rouge tag; `idlang` is Interactive Data
  Language), so fenced ```` ```idl ```` blocks arrive as plain text and the script colours them.
- **Operability.** `gh repo create jorjives/open-idl --public`, push, then enable Pages through
  the API with source `main:/docs`. Build status is read from `GET /repos/{o}/{r}/pages/builds/latest`.
  Local preview uses the same image GitHub uses (`ghcr.io/actions/jekyll-build-pages`) via Docker
  when available; otherwise the GitHub build is the check.
- **Licence** is not chosen here; it is Jorj's call. The contributing page says so.

## Design plan (visual)

Subject: a language whose files read like a policy wording and prove themselves. Audience:
product managers, underwriters and pricing actuaries first; engineers evaluating it second. The
landing page's job: make a reader believe in thirty seconds that they could write their product
in this and prove it.

- **Hero is the language itself**: a real excerpt (cover, rating, one scenario) and the `check`
  output with its PASS lines. One page-load moment: the PASS lines print in, disabled under
  `prefers-reduced-motion`.
- **Palette**: paper white body `#FFFFFF`, ink `#1C2331` for text, marine `#274C77` for links,
  buttons and keywords, sepia `#7A4E1E` for quoted wording strings, teal `#0E6E6A` for amounts and
  dates, pass green `#2F7D5B`, decline red `#B23A48`, rule grey `#D9D6CC`. Not the cream and
  terracotta default, not near-black with an acid accent.
- **Type**: Literata (a screen serif, reads like a wording) for text and headings; IBM Plex Mono
  for code, since the code is English and must read at length. Body line length under 80
  characters, line height 1.6.
- **Layout**: the theme's sidebar and content column for the reference. The landing page walks
  down one product the way a file does (inputs, eligibility, cover, rating, lifecycle, claims,
  scenario), each block a short real excerpt with one sentence beside it; then the proven lines of
  business as a table; then the three commands. No card grid, no numbered markers, no eyebrows.
- **Principle**: the code is the memorable thing; everything else is quiet.
