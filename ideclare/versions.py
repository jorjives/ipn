"""The published versions of one product, and how a policy's answers move between them.

Nothing else in the engine knows how a history is found: the CLI builds one from the
files beside the product; another tool could build one from git. A History of one version,
or none at all, leaves every behaviour as it was.
"""
from __future__ import annotations

import glob
import os
from datetime import date

from decimal import Decimal

from .expr import evaluate, names
from .model import ClaimRule, Cover, Input, Product, Upgrade
from .parser import ParseError, known_words, parse, unquote


class History:
    def __init__(self, products: list[Product]):
        self.versions = sorted(products, key=lambda p: p.published or date.min)
        self._wordings: dict = {}  # (version index, kind, name) -> a Cover or ClaimRule carrying every version's dated lines
        for earlier, later in zip(self.versions, self.versions[1:]):
            if earlier.published == later.published:
                raise ParseError(f"two versions of {later.name} are published {later.published}")
            check_upgrade(earlier, later)
        for i, version in enumerate(self.versions):
            check_amendments(version, self.versions[i + 1:])

    def cover(self, version: Product, name: str, on: date | None) -> Cover | None:
        """The cover as worded for a policy on this version on that date: the version's own lines plus
        every dated line later versions added, later ones overriding. None if the version has no such cover."""
        return self.wording(version, "cover", name, on)

    def claim(self, version: Product, name: str, on: date | None) -> ClaimRule | None:
        return self.wording(version, "claim", name, on)

    def wording(self, version: Product, kind: str, name: str, on: date | None):
        own = version.cover(name) if kind == "cover" else version.claim(name)
        if own is None:
            return None
        key = (self.versions.index(version), kind, name)
        if key not in self._wordings:
            self._wordings[key] = merged(own, [v for v in self.versions[key[0] + 1:]], kind, name)
        return self._wordings[key].as_of(on)

    @classmethod
    def for_file(cls, path: str) -> "History":
        """The history a product file sees: itself, plus the other .idl files in its directory that
        declare the same product name and were published on or before it. A file without a
        published date is a history of one."""
        me = load(path)
        if me.published is None:
            return cls([me])
        versions = [me]
        for other in sorted(glob.glob(os.path.join(os.path.dirname(path) or ".", "*.idl"))):
            if os.path.abspath(other) == os.path.abspath(path):
                continue
            name, published = header(other)
            if name == me.name and published is not None and published <= me.published:
                versions.append(load(other))
        return cls(versions)

    @property
    def name(self) -> str:
        return self.versions[0].name

    def live_on(self, on: date) -> Product:
        """The version with the latest published date on or before the date."""
        live = [p for p in self.versions if p.published is None or p.published <= on]
        if not live:
            raise ValueError(f"no version of {self.name} was on sale on {on.isoformat()}")
        return live[-1]

    def upgrade(self, answers: dict, from_version: Product, to_version: Product) -> tuple[dict, list[str]]:
        """Answers in from_version's shape turned into to_version's, one published version at a time.
        Returns the answers and the names of the inputs still to be asked (an item's field as `bike.lock`)."""
        start, end = self.versions.index(from_version), self.versions.index(to_version)
        needs: list[str] = []
        for earlier, later in zip(self.versions[start:end], self.versions[start + 1:end + 1]):
            answers, needs = upgrade_step(answers, earlier, later)
        return answers, needs


def merged(own, later_versions: list[Product], kind: str, name: str):
    """A wording that carries the version's own lines and the dated lines of every later version. The
    version's own build reads them, so the words must be ones it knows."""
    if not later_versions:
        return own
    lines = list(own.lines)
    for later in later_versions:
        block = later.cover(name) if kind == "cover" else later.claim(name)
        lines += [d for d in block.lines if d.dated] if block is not None else []
    if lines == own.lines:
        return own
    fresh = Cover(own.name, own.optional) if kind == "cover" else ClaimRule(own.cover, asks=own.asks)
    fresh.__dict__.update({k: v for k, v in own.__dict__.items() if k not in ("lines", "build", "_windows")})  # the undated wording is the version's own
    fresh.lines, fresh.build = lines, own.build
    return fresh


def check_amendments(version: Product, later_versions: list[Product]) -> None:
    """Every dated line a later version adds must read in this version's words, because it reaches it."""
    for later in later_versions:
        for kind, blocks in (("cover", {c.name: c for c in later.covers}), ("claim", later.claims)):
            for name, block in blocks.items():
                own = version.cover(name) if kind == "cover" else version.claim(name)
                if own is None or not any(d.dated for d in block.lines):
                    continue
                for d in block.lines:
                    if not d.dated:
                        continue
                    try:
                        own.build([l for l in own.lines if not l.dated] + [d])
                    except ParseError as e:
                        word = str(e).split("unknown word ")[-1].split(" ")[0] if "unknown word" in str(e) else None
                        detail = f"{word} is not known to" if word else f"{str(e).split(': ', 1)[-1]}; it does not read in"
                        raise ParseError(f"line {d.line.number}: {detail} the version published {version.published}, which this amendment reaches")


def load(path: str) -> Product:
    try:
        return parse(open(path, encoding="utf-8").read(), os.path.dirname(path))
    except ParseError as e:
        raise ParseError(f"{os.path.basename(path)}: {e}")


def header(path: str) -> tuple[str | None, date | None]:
    """The product name and published date from the file's first block, read without parsing the rest,
    so a neighbour that is not a version of this product, or is a later one, need not even parse."""
    name, published = None, None
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.split("#")[0].rstrip()
            if not line.strip():
                continue
            words = line.split()
            if name is None:
                if words[0] != "product" or len(words) < 2:
                    return None, None
                name = unquote(line.split(None, 1)[1].strip())
            elif not line.startswith(" "):
                break  # the header block has ended
            elif words[:1] == ["published"] and len(words) == 2:
                try:
                    published = date.fromisoformat(words[1])
                except ValueError:
                    return name, None
    return name, published


def carries(old: Input | None, new: Input) -> bool:
    """Whether an answer to the old input can be held by the new one unchanged."""
    if old is None or old.kind != new.kind:
        return False
    if new.kind == "choice":
        return set(old.choices) <= set(new.choices)
    if new.kind == "collection":
        return all(carries(old.fields.get(n), f) for n, f in new.fields.items() if f.kind != "calculated" and not f.provided)
    return True


def upgradable(inputs: dict[str, Input]) -> list[Input]:
    """The inputs an upgrade has to produce: not calculated or provided, which are recomputed."""
    return [i for i in inputs.values() if i.kind != "calculated" and not i.provided]


def check_upgrade(earlier: Product, later: Product) -> None:
    """Every input of the later version must be mentioned, carried or defaulted, and every word in an
    upgrading expression must be one the earlier version knows, or a choice of the target."""
    lines = {u.target: u for u in later.upgrading}
    words = known_words(earlier)
    for inp in upgradable(later.inputs):
        up = lines.get(inp.name)
        if up is None:
            if inp.name == "territory" or inp.kind == "text" or carries(earlier.inputs.get(inp.name), inp) or inp.default is not None:
                continue  # free text is optional everywhere, so a new text input needs no line
            raise ParseError(f"line {inp.line}: {inp.name} is new in the version published {later.published}; add it to upgrading, or give it a default")
        if up.item:
            coll = earlier.collection_for(up.item)
            if coll is None:
                raise ParseError(f"line {up.line}: {up.item!r} is not an item in the version published {earlier.published}")
            item_words = words | set(coll.fields) | {c for f in coll.fields.values() for c in f.choices}
            field_lines = {f.target: f for f in up.fields}
            for f in upgradable(inp.fields):
                if f.name in field_lines:
                    check_words(field_lines[f.name], f, item_words, earlier)
                elif f.kind != "text" and not carries(coll.fields.get(f.name), f) and f.default is None:
                    raise ParseError(f"line {f.line}: {f.name} is new in the version published {later.published}; add it to upgrading, or give it a default")
        else:
            check_words(up, inp, words, earlier)


def check_words(up: Upgrade, target: Input, words: set[str], earlier: Product) -> None:
    allowed = words | set(target.choices)
    for cond, value in up.rows:
        used = (names(cond) if cond is not None else set()) | (names(value) if value != ("ask",) else set())
        unknown = sorted(used - allowed)
        if unknown:
            raise ParseError(f"line {up.line}: unknown word {unknown[0]!r} in the version published {earlier.published}")


UNKNOWN = object()  # an answer that has to be asked for


def upgrade_step(answers: dict, earlier: Product, later: Product) -> tuple[dict, list[str]]:
    lines = {u.target: u for u in later.upgrading}
    ctx = {**answers, "tables": earlier.tables, "selected": set()}
    missing = set(earlier.inputs) - set(answers)  # asked earlier in the chain and still unanswered
    out, needs = {}, []
    for inp in upgradable(later.inputs):
        up = lines.get(inp.name)
        if up is not None and up.item:
            coll = earlier.collection_for(up.item)
            field_lines = {f.target: f for f in up.fields}
            out[inp.name] = []
            for item in answers.get(coll.name, []):
                new_item = {}
                item_missing = missing | (set(coll.fields) - set(item))
                for f in upgradable(inp.fields):
                    if f.name in field_lines:
                        value = resolve(field_lines[f.name], f, {**ctx, **item}, item_missing)
                    elif f.name in item and carries(coll.fields.get(f.name), f):
                        value = item[f.name]
                    elif f.default is not None:
                        value = f.default
                    else:
                        value = UNKNOWN if f.kind != "text" else None
                    if value is None:
                        continue
                    if value is UNKNOWN:
                        if f"{inp.singular}.{f.name}" not in needs:
                            needs.append(f"{inp.singular}.{f.name}")
                    else:
                        new_item[f.name] = value
                out[inp.name].append(new_item)
        elif up is not None:
            value = resolve(up, inp, ctx, missing)
            if value is UNKNOWN:
                needs.append(inp.name)
            else:
                out[inp.name] = value
        elif inp.name in answers and (inp.name == "territory" or carries(earlier.inputs.get(inp.name), inp)):
            out[inp.name] = answers[inp.name]
        elif inp.default is not None:
            out[inp.name] = inp.default
        elif inp.name in missing:
            needs.append(inp.name)
    return out, needs


def resolve(up: Upgrade, target: Input, ctx: dict, missing: set[str]):
    """The first row whose condition holds gives the value; an ask, or a word still unanswered, is UNKNOWN."""
    for cond, value in up.rows:
        if cond is not None:
            if names(cond) & missing:
                return UNKNOWN
            if not evaluate(cond, ctx):
                continue
        if value == ("ask",) or names(value) & missing:
            return UNKNOWN
        return fitted(target, evaluate(value, ctx))
    return UNKNOWN


def fitted(target: Input, value):
    """The value if the target input can hold it; otherwise a loud error."""
    ok = {"money": lambda v: isinstance(v, Decimal), "number": lambda v: isinstance(v, Decimal), "integer": lambda v: isinstance(v, Decimal),
          "yes/no": lambda v: isinstance(v, bool), "choice": lambda v: v in target.choices, "text": lambda v: isinstance(v, str),
          "date": lambda v: isinstance(v, date)}[target.kind]
    if isinstance(value, bool) and target.kind != "yes/no" or not ok(value):
        kind = f"a choice of {', '.join(target.choices)}" if target.kind == "choice" else target.kind
        raise ValueError(f"{target.name} cannot be {value!r}; it is {kind}")
    return value
