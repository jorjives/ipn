# Playground autocomplete — standalone plan

> Untracked working document. Spec: `docs/superpowers/specs/2026-09-07-playground-autocomplete-design.md`.

**Slice:** standalone
**Spec:** docs/superpowers/specs/2026-09-07-playground-autocomplete-design.md

Gates resolved autonomously at Jorj's request ("work autonomously to deliver the complete spec").

## Decision audit (resolved)

| Decision | Easy | Right | Chosen |
|---|---|---|---|
| Where the compiler lives | inside `ideclare/` | `scripts/grammar_table.py`: the engine does not need it; generated-site tooling already lives in `scripts/` | Right |
| Walker duplication | run JS under node in tests | Python walker for tests, JS port for the browser; no Node tooling | Right (per spec) |
| Plan execution | haiku per task | implement directly with TDD; the design is fully specified and the change is ~600 lines | pragmatic, recorded |
| JSON layout | nested objects per state | as spec: `rules[name].states[i].edges`, sorted keys | spec |
| Browser verification | trust it | Playwright against the local Docker Pages build | Right |

## Tasks (each its own commit)

1. `.github/workflows/tests.yml` running `python3 -m unittest` on PRs and pushes to main. CLAUDE.md notes CI.
2. `grammar.md` notation tidy: nested lines on indented continuations, `asks_block`, folded phrases in `primary`, `old_expression`/`old_condition`, note that the page is machine-read.
3. `scripts/grammar_table.py` reader: fenced blocks → rules; INDENT/DEDENT; errors. Tests in `tests/test_grammar.py`.
4. Line marking and NEWLINE placement.
5. NFA → DFA → minimise per rule; JSON writer; `site_pages.py` writes `docs/assets/idl-grammar.json`; staleness test.
6. Python tokeniser + walker; corpus tests (parses, every next token offered, tokeniser agrees with parser). Fix grammar.md gaps the corpus finds.
7. `idl.js` exposes `classify`; `idl-complete.js` (tokeniser, walker, names, completion source); `playground.js` on CodeMirror; `playground.md`; scss; `test_site` asset pins; docs (contributing, CLAUDE.md, playground hint).
8. Playwright verification on the local build; fix what it finds.
9. PR.

## Scaffolding impact
- CLAUDE.md commands: regenerate note and CI → tasks 1, 5.
- contributing.md: grammar page is machine-read, regenerate command → task 5.
- playground.md hint → task 7.
