"""The published versions of one product, and how a policy's answers move between them.

Nothing else in the engine knows how a history is found: the CLI builds one from the
files beside the product; another tool could build one from git. A History of one version,
or none at all, leaves every behaviour as it was.
"""
from __future__ import annotations

import glob
import os
from datetime import date

from .model import Input, Product
from .parser import ParseError, parse


class History:
    def __init__(self, products: list[Product]):
        self.versions = sorted(products, key=lambda p: p.published or date.min)
        for earlier, later in zip(self.versions, self.versions[1:]):
            if earlier.published == later.published:
                raise ParseError(f"two versions of {later.name} are published {later.published}")
            check_upgrade(earlier, later)

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
        Returns the answers and the names of the inputs still to be asked."""
        start, end = self.versions.index(from_version), self.versions.index(to_version)
        needs: list[str] = []
        for earlier, later in zip(self.versions[start:end], self.versions[start + 1:end + 1]):
            answers = upgrade_step(answers, earlier, later)
        return answers, needs


def carries(old: Input | None, new: Input) -> bool:
    """Whether an answer to the old input can be held by the new one unchanged."""
    if old is None or old.kind != new.kind:
        return False
    if new.kind == "choice":
        return set(old.choices) <= set(new.choices)
    if new.kind == "collection":
        return all(carries(old.fields.get(n), f) for n, f in new.fields.items() if f.kind not in ("calculated",) and not f.provided)
    return True


def check_upgrade(earlier: Product, later: Product) -> None:
    """Every input of the later version must be carried or defaulted; otherwise the author has to say."""
    for name, inp in later.inputs.items():
        if inp.kind == "calculated" or inp.provided or name == "territory":
            continue
        if carries(earlier.inputs.get(name), inp) or inp.default is not None:
            continue
        raise ParseError(f"line {inp.line}: {name} is new in the version published {later.published}; add it to upgrading, or give it a default")


def upgrade_step(answers: dict, earlier: Product, later: Product) -> dict:
    out = {}
    for name, inp in later.inputs.items():
        if inp.kind == "calculated" or inp.provided:
            continue
        if name in answers and (name == "territory" or carries(earlier.inputs.get(name), inp)):
            out[name] = answers[name]
        elif inp.default is not None:
            out[name] = inp.default
    return out
