"""The Price a book page's prepared files must demonstrate a rate change over a sample."""
import csv
import io
import unittest
from decimal import Decimal
from pathlib import Path

from tests.test_cli import run

ROOT = Path(__file__).resolve().parent.parent
BOOK = ROOT / "docs" / "assets" / "book"


def batch(product: Path, risks: Path) -> list[dict]:
    code, out = run("batch", str(product), str(risks))
    rows = list(csv.DictReader(io.StringIO(out)))
    if code != 0:
        raise AssertionError(f"batch exited {code}: {out}")
    return rows


class PreparedImpact(unittest.TestCase):
    def test_raising_the_terrace_factor_moves_only_terraces(self):
        """A terrace row's total must change; every other property type must not."""
        with (BOOK / "risks.csv").open(encoding="utf-8", newline="") as f:
            risks = list(csv.DictReader(f))
        before = batch(BOOK / "before.ipn", BOOK / "risks.csv")
        after = batch(BOOK / "after.ipn", BOOK / "risks.csv")
        self.assertEqual(len(risks), 12)
        self.assertEqual(len(before), 12)
        self.assertEqual(len(after), 12)
        moved, stayed = [], []
        for risk, b, a in zip(risks, before, after):
            changed = b["total"] != a["total"] or b["eligibility"] != a["eligibility"]
            (moved if changed else stayed).append(risk["property_type"])
        self.assertEqual(moved, ["terrace"] * moved.count("terrace"))
        self.assertTrue(moved)
        self.assertNotIn("terrace", stayed)
        self.assertGreaterEqual(stayed.count("semi") + stayed.count("flat") + stayed.count("detached"), 1)


class HouseholdBook(unittest.TestCase):
    def test_the_documented_csv_prices_every_row(self):
        rows = batch(ROOT / "examples" / "household.ipn", ROOT / "examples" / "household-risks.csv")
        self.assertGreaterEqual(len(rows), 4)
        self.assertTrue(all(r["error"] == "" for r in rows))
        self.assertIn("declined", {r["eligibility"] for r in rows})
        self.assertIn("eligible", {r["eligibility"] for r in rows})


class HomeBookWithItems(unittest.TestCase):
    def test_the_documented_command_prices_three_risks_with_their_jewellery(self):
        code, out = run(
            "batch", str(ROOT / "examples" / "home.ipn"), str(ROOT / "examples" / "home-risks.csv"),
            f"specified_items={ROOT / 'examples' / 'home-specified-items.csv'}",
        )
        self.assertEqual(code, 0, out)
        rows = list(csv.DictReader(io.StringIO(out)))
        self.assertEqual([r["risk"] for r in rows], ["A", "B", "C"])
        self.assertTrue(all(r["error"] == "" for r in rows))
        self.assertTrue(all(r["eligibility"] == "eligible" for r in rows))
        a, b, c = (Decimal(r["net"]) for r in rows)
        self.assertGreater(a, b)  # A carries a watch, B carries nothing
        self.assertGreater(c, a)

    def test_specified_items_is_not_a_column_on_the_book(self):
        with (ROOT / "examples" / "home-risks.csv").open(encoding="utf-8", newline="") as f:
            book = csv.DictReader(f)
            self.assertNotIn("specified_items", book.fieldnames)
            self.assertEqual(book.fieldnames[0], "risk")
        with (ROOT / "examples" / "home-specified-items.csv").open(encoding="utf-8", newline="") as f:
            items = list(csv.DictReader(f))
        self.assertEqual([r["risk"] for r in items], ["A", "C", "C"])
