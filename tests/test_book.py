"""The Price a book page's prepared files must demonstrate a rate change over a sample."""
import csv
import io
import unittest
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
