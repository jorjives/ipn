import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout

from ideclare.cli import main
from tests.test_parser import DEFAULTS, FLEET, LIFECYCLE, RATING


def run(*argv) -> tuple[int, str]:
    out = io.StringIO()
    with redirect_stdout(out):
        code = main(list(argv))
    return code, out.getvalue()


class QuoteCommand(unittest.TestCase):
    def test_items_come_from_a_csv(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "fleet.idl"), "w") as f:
                f.write(FLEET)
            with open(os.path.join(d, "bikes.csv"), "w") as f:
                f.write("value,age,security\n2000,0,gold\n1000,3,silver\n")
            code, out = run("quote", os.path.join(d, "fleet.idl"), "rider_age=30", "bikes=bikes.csv")
        self.assertEqual(code, 0, out)
        self.assertIn("Theft on bike 1: included, limit 2000.00", out)
        self.assertIn("Theft on bike 2: included, limit 1000.00", out)
        self.assertIn("bike 2 Bike age", out)
        self.assertIn("= 82.65", out)  # 60 + 27, x 0.95


class QuoteDefaults(unittest.TestCase):
    def test_defaulted_inputs_need_not_be_given(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "x.idl"), "w") as f:
                f.write(DEFAULTS)
            with open(os.path.join(d, "bikes.csv"), "w") as f:
                f.write("price,security\n500,\n")
            code, out = run("quote", os.path.join(d, "x.idl"), "value=1", "bikes=bikes.csv")
        self.assertEqual(code, 0, out)
        self.assertIn("= 110.00", out)


class QuoteInstalments(unittest.TestCase):
    def test_the_schedule_is_shown_when_the_product_offers_one(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "cycle.idl"), "w") as f:
                f.write(LIFECYCLE + "  instalments 12 monthly, charge 8%\n")
            code, out = run("quote", os.path.join(d, "cycle.idl"), "bike_value=2000", "rider_age=22", "security=gold", "racing=no")
        self.assertEqual(code, 0, out)
        self.assertIn("or 12 monthly: 8.92 then 8.88 (credit charge 7.90)", out)


class BatchCommand(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        with open(os.path.join(self.d.name, "cycle.idl"), "w") as f:
            f.write(RATING)

    def tearDown(self):
        self.d.cleanup()

    def batch(self, rows: str) -> tuple[int, list[list[str]]]:
        import csv
        with open(os.path.join(self.d.name, "risks.csv"), "w") as f:
            f.write(rows)
        code, out = run("batch", os.path.join(self.d.name, "cycle.idl"), os.path.join(self.d.name, "risks.csv"))
        return code, list(csv.reader(io.StringIO(out)))

    def test_one_row_per_risk_with_the_premium_breakdown(self):
        code, rows = self.batch("bike_value,rider_age,security,racing,select\n2000,22,gold,no,\n2000,30,gold,yes,Racing\n")
        self.assertEqual(code, 0)
        self.assertEqual(rows[0], ["risk", "eligibility", "reasons", "net", "IPT", "Admin fee", "total", "currency", "error"])
        # 3.5% of 2000 = 70, x 1.40 = 98, - 10 gold = 88, less 10% = 79.20; IPT 9.50, fee 10
        self.assertEqual(rows[1], ["1", "eligible", "", "79.20", "9.50", "10.00", "98.70", "GBP", ""])
        # 70 x 1.00 = 70, - 10 = 60, + 45 racing = 105, less 10% = 94.50; IPT 11.34
        self.assertEqual(rows[2], ["2", "eligible", "", "94.50", "11.34", "10.00", "115.84", "GBP", ""])

    def test_commission_has_its_own_column(self):
        with open(os.path.join(self.d.name, "cycle.idl"), "a") as f:
            f.write('  commission "Broker" 15%\n')
        code, rows = self.batch("bike_value,rider_age,security,racing\n2000,22,gold,no\n")
        self.assertEqual(rows[0], ["risk", "eligibility", "reasons", "net", "IPT", "Admin fee", "total", "currency", "Broker", "error"])
        self.assertEqual(rows[1][3:9], ["79.20", "9.50", "10.00", "98.70", "GBP", "11.88"])

    def test_declined_and_referred_risks_are_priced_and_say_why(self):
        code, rows = self.batch("bike_value,rider_age,security,racing\n12000,15,gold,no\n")
        self.assertEqual(rows[1][:3], ["1", "declined", "Rider must be at least 16; Underwriter review"])
        self.assertNotEqual(rows[1][3], "")

    def test_a_risk_the_product_cannot_price_is_reported_in_place(self):
        code, rows = self.batch("bike_value,rider_age,security,racing\n2000,22,gold,no\n2000,,gold,no\n2000,22,gold,no\n")
        self.assertEqual(code, 0)
        self.assertEqual([r[0] for r in rows[1:]], ["1", "2", "3"])
        self.assertEqual(rows[2][1:], ["", "", "", "", "", "", "", "missing rider_age"])

    def test_unknown_column_is_an_error_before_any_row_runs(self):
        code, rows = self.batch("bike_value,rider_age,security,racing,colour\n2000,22,gold,no,red\n")
        self.assertEqual(code, 2)
        self.assertIn("colour", rows[0][0])


if __name__ == "__main__":
    unittest.main()
