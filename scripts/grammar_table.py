"""Compile the grammar page into the playground's completion table.

`docs/reference/grammar.md` holds the language's EBNF in fenced blocks. This reads it,
holds it to the page's notation (indentation in the grammar is indentation in the product;
a bracket opens and closes at one indent), and compiles every rule to a small automaton
whose edges are literals, terminal classes, structural tokens and calls to other rules.
The browser walks the table to offer what may come next; the tests walk it over every
example and template to prove the page complete.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRAMMAR = ROOT / "docs" / "reference" / "grammar.md"
TABLE = ROOT / "docs" / "assets" / "idl-grammar.json"

# Names the grammar uses without defining: matched by token kind, offered by the runtime.
TERMINALS = {"string", "date", "number", "integer",
             "name", "word", "item_name", "field_name", "collection_name", "old_item_name"}


class GrammarError(Exception):
    pass


# --- reading the page -------------------------------------------------------

FENCE = re.compile(r"^```[^\n]*\n(.*?)^```", re.M | re.S)
RULE_START = re.compile(r"^([a-z_][a-z0-9_]*)\s*=(.*)$")
COMMENT = re.compile(r"(?<=\s)--(?=\s).*$")
EBNF_TOKEN = re.compile(r"\s*(?:'([^']*)'|([a-z_][a-z0-9_]*)|([\[\]{}()|]))")


def read(text: str) -> dict:
    """The page's rules as trees: lit, cls, ref, seq, alt, opt, rep, indent nodes."""
    rules, order = {}, []
    for block in FENCE.findall(text):
        for raw in block.splitlines():
            line = COMMENT.sub("", raw).rstrip()
            if not line.strip():
                continue
            m = RULE_START.match(line)
            if m:
                name, body = m.group(1), m.group(2)
                if name in rules:
                    raise GrammarError(f"rule {name} is defined twice")
                rules[name] = [(line.index("="), body)]
                order.append(name)
            elif order:
                rules[order[-1]].append((len(line) - len(line.lstrip(" ")), line.strip()))
            else:
                raise GrammarError(f"text before the first rule: {line.strip()!r}")
    trees = {name: _parse_rule(name, _tokenise_rule(name, lines)) for name, lines in rules.items()}
    for name, tree in trees.items():
        for ref in _refs(tree):
            if ref not in trees:
                raise GrammarError(f"rule {name} uses {ref}, which is neither a rule nor a terminal class")
    return trees


def _tokenise_rule(name: str, lines: list) -> list:
    """Tokens of one rule, with INDENT and DEDENT from the continuation lines' columns."""
    toks, stack = [], [lines[0][0]]
    for col, text in lines:
        if col > stack[-1]:
            stack.append(col)
            toks.append(("INDENT", ""))
        else:
            while len(stack) > 1 and col < stack[-1]:
                stack.pop()
                toks.append(("DEDENT", ""))
            if col != stack[-1]:
                raise GrammarError(f"rule {name}: inconsistent indentation at {text!r}")
        pos = 0
        while pos < len(text):
            m = EBNF_TOKEN.match(text, pos)
            if not m or m.end() == pos:
                raise GrammarError(f"rule {name}: cannot read {text[pos:]!r}")
            lit, word, op = m.groups()
            toks.append(("lit", lit) if lit is not None else ("name", word) if word else ("op", op))
            pos = m.end()
    toks.extend([("DEDENT", "")] * (len(stack) - 1))
    return toks


def _parse_rule(name: str, toks: list) -> tuple:
    pos = 0

    def peek():
        return toks[pos] if pos < len(toks) else ("end", "")

    def take(kind, value=None):
        nonlocal pos
        tok = peek()
        if tok[0] != kind or (value is not None and tok[1] != value):
            raise GrammarError(f"rule {name}: expected {value or kind}, found {tok[1] or tok[0]}")
        pos += 1
        return tok

    def alt():
        seqs = [seq()]
        while peek() == ("op", "|"):
            take("op", "|")
            seqs.append(seq())
        return seqs[0] if len(seqs) == 1 else ("alt", seqs)

    def seq():
        items = []
        while peek()[0] not in ("end", "DEDENT") and peek() not in (("op", "|"), ("op", "]"), ("op", "}"), ("op", ")")):
            items.append(item())
        if not items:
            raise GrammarError(f"rule {name}: empty sequence before {peek()[1] or peek()[0]}")
        return items[0] if len(items) == 1 else ("seq", items)

    def item():
        kind, value = peek()
        if kind == "lit":
            take("lit")
            return ("lit", value)
        if kind == "name":
            take("name")
            return ("cls", value) if value in TERMINALS else ("ref", value)
        if kind == "INDENT":
            take("INDENT")
            inner = alt()
            take("DEDENT")
            return ("indent", inner)
        if kind == "op" and value in "[{(":
            take("op")
            inner = alt()
            take("op", {"[": "]", "{": "}", "(": ")"}[value])
            return {"[": ("opt", inner), "{": ("rep", inner), "(": inner}[value]
        raise GrammarError(f"rule {name}: unexpected {value or kind}")

    tree = alt()
    if pos != len(toks):
        raise GrammarError(f"rule {name}: unexpected {toks[pos][1] or toks[pos][0]}")
    return tree


def _refs(tree):
    kind = tree[0]
    if kind == "ref":
        yield tree[1]
    elif kind in ("seq", "alt"):
        for sub in tree[1]:
            yield from _refs(sub)
    elif kind in ("opt", "rep", "indent"):
        yield from _refs(tree[1])
