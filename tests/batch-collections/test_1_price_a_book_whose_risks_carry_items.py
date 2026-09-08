# Slice 1: Price a book whose risks carry items
# Source: docs/superpowers/specs/2026-09-08-batch-collections-slices.md
# Recorded: 2026-09-08 against commit 5457875
#
# UAT: price the home contents sample book (risks A, B, C) against its jewellery
# file in one `batch` run and see the items move the premium.
#
# The full acceptance-criteria matrix (join-key rules, malformed-file exit 2s,
# per-row item field errors, path-in-cell handling, ...) is already exhaustively
# unit-tested against a synthetic product in tests/test_cli.py::BatchCollections;
# this file re-drives only the UAT itself plus the two ACs the UAT narrative
# calls out by name, against the real home files, so a regression in the
# documented command is caught end to end.
import contextlib
import csv
import io
import os
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from tests.test_cli import run

ROOT = Path(__file__).resolve().parent.parent.parent
HOME = ROOT / "examples" / "home.ipn"
HOME_RISKS = ROOT / "examples" / "home-risks.csv"
HOME_ITEMS = ROOT / "examples" / "home-specified-items.csv"


class PriceABookWhoseRisksCarryItems(unittest.TestCase):
    def test_uat_three_risks_priced_with_their_jewellery(self):
        """Steps 1-3: point batch at the home book and its jewellery file."""
        code, out = run("batch", str(HOME), str(HOME_RISKS), f"specified_items={HOME_ITEMS}")
        rows = list(csv.DictReader(io.StringIO(out)))

        self.assertEqual(code, 0, out)
        self.assertEqual([r["risk"] for r in rows], ["A", "B", "C"])
        self.assertTrue(all(r["error"] == "" for r in rows), rows)  # "No error column filled"
        self.assertTrue(all(r["eligibility"] == "eligible" for r in rows), rows)
        a, b, c = (Decimal(r["net"]) for r in rows)
        self.assertLess(b, a)  # B is cheaper than A: no specified-item load
        self.assertGreater(c, a)  # C's two items are included

    def test_ac_a_risk_with_no_matching_items_has_an_empty_collection(self):
        """B has no row in the jewellery file at all; it must still price, unloaded."""
        code, out = run("batch", str(HOME), str(HOME_RISKS), f"specified_items={HOME_ITEMS}")
        rows = list(csv.DictReader(io.StringIO(out)))
        self.assertEqual(code, 0, out)
        b = next(r for r in rows if r["risk"] == "B")
        self.assertEqual(b["error"], "")
        self.assertEqual(b["eligibility"], "eligible")

    def test_ac_an_unknown_item_field_is_that_risks_error_and_the_others_still_price(self):
        """A stray column on one risk's item row is reported as that risk's error only."""
        with tempfile_items("risk,description,value,colour\nA,watch,2000,gold\nC,necklace,4000,\nC,painting,8000,\n") as items:
            code, out = run("batch", str(HOME), str(HOME_RISKS), f"specified_items={items}")
        rows = list(csv.DictReader(io.StringIO(out)))
        self.assertEqual(code, 0, out)
        a = next(r for r in rows if r["risk"] == "A")
        b = next(r for r in rows if r["risk"] == "B")
        c = next(r for r in rows if r["risk"] == "C")
        self.assertIn("unknown item field 'colour'", a["error"])
        self.assertEqual(b["error"], "")
        self.assertEqual(c["error"], "")


@contextlib.contextmanager
def tempfile_items(text: str):
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "items.csv")
        with open(path, "w") as f:
            f.write(text)
        yield path


if __name__ == "__main__":
    unittest.main()
