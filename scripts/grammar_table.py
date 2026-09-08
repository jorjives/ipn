"""Compile the grammar page into the playground's completion table.

`docs/reference/grammar.md` holds the language's EBNF in fenced blocks. This reads it,
holds it to the page's notation (indentation in the grammar is indentation in the product;
a bracket opens and closes at one indent), and compiles every rule to a small automaton
whose edges are literals, terminal classes, structural tokens and calls to other rules.
The browser walks the table to offer what may come next; the tests walk it over every
example and template to prove the page complete.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRAMMAR = ROOT / "docs" / "reference" / "grammar.md"
TABLE = ROOT / "docs" / "assets" / "ipn-grammar.json"

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


def render() -> str:
    """The committed table's text, byte-identical across machines."""
    return json.dumps(build(GRAMMAR.read_text(encoding="utf-8")), separators=(",", ":"), sort_keys=True) + "\n"


# --- lines ------------------------------------------------------------------

NEWLINE, INDENT, DEDENT = ("tok", "NEWLINE"), ("tok", "INDENT"), ("tok", "DEDENT")


def mark_lines(rules: dict) -> dict:
    """Place NEWLINE, INDENT and DEDENT.

    `file` is a run of lines. Each element of a run, and each alternative of a bracket group
    in a run, is a line position. A line position ending in a rule reference delegates to a
    line variant of that rule (`name$line`), whose alternatives are line positions in turn;
    any other line position ends with NEWLINE, placed before its nested lines if it has them.
    """
    out = dict(rules)

    def nullable(node, seen=frozenset()):
        kind = node[0]
        if kind in ("lit", "cls", "tok"):
            return False
        if kind == "ref":
            return node[1] not in seen and nullable(rules[node[1]], seen | {node[1]})
        if kind == "seq":
            return all(nullable(n, seen) for n in node[1])
        if kind == "alt":
            return any(nullable(n, seen) for n in node[1])
        return True  # opt, rep, indent

    def variant(name):
        if name + "$line" not in out:
            out[name + "$line"] = None  # claimed, so recursion terminates
            tree = rules[name]
            alts = tree[1] if tree[0] == "alt" else [tree]
            out[name + "$line"] = _alt([line_position(a) for a in alts])
        return ("ref", name + "$line")

    def line_position(node):
        items = list(node[1]) if node[0] == "seq" else [node]
        if items[-1][0] == "ref":
            items[-1] = variant(items[-1][1])
        elif items[-1][0] != "indent":
            items.append(NEWLINE)
        return _seq([transform(i) for i in items])

    def transform(node):
        kind = node[0]
        if kind == "indent":
            nested = ("seq", [INDENT, run(node[1]), DEDENT])
            return ("seq", [NEWLINE, ("opt", nested) if nullable(node[1]) else nested])
        if kind in ("seq", "alt"):
            return (kind, [transform(n) for n in node[1]])
        if kind in ("opt", "rep"):
            return (kind, transform(node[1]))
        return node

    def run(node):
        alts = node[1] if node[0] == "alt" else [node]
        return _alt([run_seq(a) for a in alts])

    def run_seq(node):
        items = list(node[1]) if node[0] == "seq" else [node]
        units, current = [], []
        for item in items:
            if item[0] in ("opt", "rep"):
                if current:
                    units.append(line_position(_seq(current)))
                    current = []
                inner = item[1][1] if item[1][0] == "alt" else [item[1]]
                units.append((item[0], _alt([line_position(a) for a in inner])))
            else:
                current.append(item)
        if current:
            units.append(line_position(_seq(current)))
        return _seq(units)

    out["file"] = run(rules["file"])
    return out


def _seq(items):
    flat = [n for item in items for n in (item[1] if item[0] == "seq" else [item])]
    return flat[0] if len(flat) == 1 else ("seq", flat)


def _alt(items):
    return items[0] if len(items) == 1 else ("alt", items)


# --- automata ---------------------------------------------------------------

def build(text: str) -> dict:
    """The completion table: one minimal automaton per rule reachable from `file`."""
    rules = mark_lines(read(text))
    table, todo, done = {}, ["file"], set()
    while todo:
        name = todo.pop()
        if name in done:
            continue
        done.add(name)
        table[name] = _dfa(rules[name])
        for state in table[name]:
            for kind, value, _ in state["edges"]:
                if kind == "call":
                    todo.append(value)
    return {"start": "file", "rules": {name: table[name] for name in sorted(table)}}


def _dfa(tree) -> list:
    # Thompson construction: states are ints, edges (label | None, target); label None is epsilon.
    edges = []

    def new():
        edges.append([])
        return len(edges) - 1

    def nfa(node):
        kind = node[0]
        if kind in ("lit", "cls", "tok"):
            s, e = new(), new()
            edges[s].append((node, e))
            return s, e
        if kind == "ref":
            s, e = new(), new()
            edges[s].append((("call", node[1]), e))
            return s, e
        if kind == "seq":
            parts = [nfa(n) for n in node[1]]
            for (_, a), (b, _) in zip(parts, parts[1:]):
                edges[a].append((None, b))
            return parts[0][0], parts[-1][1]
        if kind == "alt":
            s, e = new(), new()
            for sub in node[1]:
                a, b = nfa(sub)
                edges[s].append((None, a))
                edges[b].append((None, e))
            return s, e
        if kind in ("opt", "rep"):
            s, e = new(), new()
            a, b = nfa(node[1])
            edges[s].extend([(None, a), (None, e)])
            edges[b].append((None, e))
            if kind == "rep":
                edges[b].append((None, a))
            return s, e
        raise ValueError(kind)

    start, accept = nfa(tree)

    def closure(states):
        out, todo = set(states), list(states)
        while todo:
            for label, target in edges[todo.pop()]:
                if label is None and target not in out:
                    out.add(target)
                    todo.append(target)
        return frozenset(out)

    # Subset construction.
    first = closure({start})
    dfa, order, todo = {first: {}}, [first], [first]
    while todo:
        current = todo.pop(0)
        moves = {}
        for state in current:
            for label, target in edges[state]:
                if label is not None:
                    moves.setdefault(label, set()).add(target)
        for label in sorted(moves):
            nxt = closure(moves[label])
            if nxt not in dfa:
                dfa[nxt] = {}
                order.append(nxt)
                todo.append(nxt)
            dfa[current][label] = nxt
    return _minimise(dfa, first, lambda s: accept in s)


def _minimise(dfa, start, is_accept) -> list:
    """Moore's partition refinement, then number states by a breadth-first walk over sorted labels."""
    block = {s: int(is_accept(s)) for s in dfa}
    while True:
        signature = {s: (block[s], tuple((label, block[t]) for label, t in sorted(dfa[s].items()))) for s in dfa}
        ids = {sig: i for i, sig in enumerate(sorted(set(signature.values()), key=repr))}
        new_block = {s: ids[signature[s]] for s in dfa}
        if len(set(new_block.values())) == len(set(block.values())):
            block = new_block
            break
        block = new_block
    representative = {}
    for s in dfa:
        representative.setdefault(block[s], s)
    number, order = {block[start]: 0}, [block[start]]
    for b in order:
        for label, target in sorted(dfa[representative[b]].items()):
            if block[target] not in number:
                number[block[target]] = len(order)
                order.append(block[target])
    states = []
    for b in order:
        rep = representative[b]
        states.append({"accept": is_accept(rep),
                       "edges": [[label[0], label[1], number[block[t]]] for label, t in sorted(dfa[rep].items())]})
    return states


# --- walking a product ------------------------------------------------------

CLASS_KINDS = {"str": {"string"}, "date": {"date"}, "num": {"number", "integer"},
               "id": {"name", "word", "item_name", "field_name", "collection_name", "old_item_name"}}


def product_tokens(text: str) -> list:
    """A product's tokens as (kind, text, line): the parser's kinds plus NEWLINE, INDENT and DEDENT."""
    from ipngine import parser
    out, stack, number = [], [0], 0
    for number, raw in enumerate(text.splitlines(), start=1):
        body = parser._strip_comment(raw)
        if not body.strip():
            continue
        indent = len(body) - len(body.lstrip(" "))
        if indent > stack[-1]:
            stack.append(indent)
            out.append(("INDENT", "", number))
        while indent < stack[-1]:
            stack.pop()
            out.append(("DEDENT", "", number))
        if indent != stack[-1]:
            raise ValueError(f"line {number}: inconsistent indentation")
        pos, line = 0, body.strip()
        while pos < len(line):
            m = parser.TOKEN.match(line, pos)
            if not m or m.end() == pos:
                raise ValueError(f"line {number}: cannot read {line[pos:]!r}")
            out.append((m.lastgroup, m.group(0).strip(), number))
            pos = m.end()
        out.append(("NEWLINE", "", number))
    out.extend([("DEDENT", "", number)] * (len(stack) - 1))
    return out


def matches(kind: str, value: str, tok_kind: str, tok_text: str) -> bool:
    if kind == "lit":
        return value == tok_text
    if kind == "tok":
        return value == tok_kind
    if value == "integer":
        return tok_kind == "num" and "." not in tok_text
    return value in CLASS_KINDS.get(tok_kind, ())


class Walker:
    """Live configurations (rule, state, stack of return points) over the table; the browser's
    ipn-complete.js is a line-for-line port of this class."""

    def __init__(self, table: dict, start: str):
        self.rules = table["rules"]
        self.live = {(start, 0, ())}

    def _closed(self) -> set:
        seen, todo = set(self.live), list(self.live)
        while todo:
            rule, state, stack = todo.pop()
            node = self.rules[rule][state]
            found = [(value, 0, stack + ((rule, target),)) for kind, value, target in node["edges"] if kind == "call"]
            if node["accept"] and stack:
                found.append(stack[-1] + (stack[:-1],))
            for cfg in found:
                if cfg not in seen:
                    seen.add(cfg)
                    todo.append(cfg)
        return seen

    def expected(self) -> set:
        return {(rule, kind, value) for rule, state, _ in self._closed()
                for kind, value, _ in self.rules[rule][state]["edges"] if kind != "call"}

    def feed(self, tok_kind: str, tok_text: str) -> bool:
        self.live = {(rule, target, stack) for rule, state, stack in self._closed()
                     for kind, value, target in self.rules[rule][state]["edges"]
                     if kind != "call" and matches(kind, value, tok_kind, tok_text)}
        return bool(self.live)

    def accepted(self) -> bool:
        return any(self.rules[rule][state]["accept"] and not stack for rule, state, stack in self._closed())
