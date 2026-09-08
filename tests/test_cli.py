import csv
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout

from ipngine.cli import main
from tests.test_parser import DEFAULTS, FLEET, LIFECYCLE, RATING, occupations


def run(*argv) -> tuple[int, str]:
    out = io.StringIO()
    with redirect_stdout(out):
        code = main(list(argv))
    return code, out.getvalue()


class QuoteCommand(unittest.TestCase):
    def test_items_come_from_a_csv(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "fleet.ipn"), "w") as f:
                f.write(FLEET)
            with open(os.path.join(d, "bikes.csv"), "w") as f:
                f.write("value,age,security\n2000,0,gold\n1000,3,silver\n")
            code, out = run("quote", os.path.join(d, "fleet.ipn"), "rider_age=30", "bikes=bikes.csv")
        self.assertEqual(code, 0, out)
        self.assertIn("Theft on bike 1: included, limit 2000.00", out)
        self.assertIn("Theft on bike 2: included, limit 1000.00", out)
        self.assertIn("bike 2 Bike age", out)
        self.assertIn("= 82.65", out)  # 60 + 27, x 0.95


class QuoteDefaults(unittest.TestCase):
    def test_defaulted_inputs_need_not_be_given(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "x.ipn"), "w") as f:
                f.write(DEFAULTS)
            with open(os.path.join(d, "bikes.csv"), "w") as f:
                f.write("price,security\n500,\n")
            code, out = run("quote", os.path.join(d, "x.ipn"), "value=1", "bikes=bikes.csv")
        self.assertEqual(code, 0, out)
        self.assertIn("= 110.00", out)


class QuoteInstalments(unittest.TestCase):
    def test_the_schedule_is_shown_when_the_product_offers_one(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "cycle.ipn"), "w") as f:
                f.write(LIFECYCLE + "  instalments 12 monthly, charge 8%\n")
            code, out = run("quote", os.path.join(d, "cycle.ipn"), "bike_value=2000", "rider_age=22", "security=gold", "racing=no")
        self.assertEqual(code, 0, out)
        self.assertIn("or 12 monthly: 8.92 then 8.88 (credit charge 7.90)", out)


class BatchCommand(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        with open(os.path.join(self.d.name, "cycle.ipn"), "w") as f:
            f.write(RATING)

    def tearDown(self):
        self.d.cleanup()

    def batch(self, rows: str) -> tuple[int, list[list[str]]]:
        import csv
        with open(os.path.join(self.d.name, "risks.csv"), "w") as f:
            f.write(rows)
        code, out = run("batch", os.path.join(self.d.name, "cycle.ipn"), os.path.join(self.d.name, "risks.csv"))
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
        with open(os.path.join(self.d.name, "cycle.ipn"), "a") as f:
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


class BatchCollections(unittest.TestCase):
    SRC = '''product "X"
  term 12 months
inputs
  rider_age: integer
  bikes: collection of bike, at most 10
    value: money
    age: integer
    security: choice of gold, silver, bronze
rating
  base 10
  for each bike
    add 3% of value
  tax IPT 12%
'''

    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.product = os.path.join(self.d.name, "fleet.ipn")
        with open(self.product, "w") as f:
            f.write(self.SRC)

    def tearDown(self):
        self.d.cleanup()

    def run_batch(self, book: str, items: str | None = None, extra: list[str] | None = None) -> tuple[int, list[list[str]]]:
        risks = os.path.join(self.d.name, "risks.csv")
        with open(risks, "w") as f:
            f.write(book)
        argv = ["batch", self.product, risks]
        if items is not None:
            path = os.path.join(self.d.name, "bikes.csv")
            with open(path, "w") as f:
                f.write(items)
            argv.append(f"bikes={path}")
        argv.extend(extra or [])
        code, out = run(*argv)
        return code, list(csv.reader(io.StringIO(out)))

    def test_items_join_to_row_numbers_when_the_book_has_no_risk_column(self):
        code, rows = self.run_batch(
            "rider_age\n30\n30\n",
            "risk,value,age,security\n1,1000,0,gold\n",
        )
        self.assertEqual(code, 0, rows)
        self.assertEqual([r[0] for r in rows[1:]], ["1", "2"])
        self.assertEqual(rows[1][3], "40.00")  # 10 + 30
        self.assertEqual(rows[2][3], "10.00")  # empty collection

    def test_usage_accepts_the_extra_binding(self):
        code, out = run("batch", self.product)
        self.assertEqual(code, 2)
        self.assertIn("RISKS.csv", out)

    def test_book_risk_column_is_the_join_key_and_the_output(self):
        code, rows = self.run_batch(
            "risk,rider_age\nH-1,30\nH-2,30\n",
            "risk,value,age,security\nH-1,1000,0,gold\n",
        )
        self.assertEqual(code, 0, rows)
        self.assertEqual([r[0] for r in rows[1:]], ["H-1", "H-2"])
        self.assertEqual(rows[1][3], "40.00")
        self.assertEqual(rows[2][3], "10.00")

    def test_stray_item_risk_stops_before_any_premium(self):
        code, rows = self.run_batch(
            "risk,rider_age\nH-1,30\n",
            "risk,value,age,security\nH-9,1000,0,gold\n",
        )
        self.assertEqual(code, 2)
        self.assertEqual(len(rows), 1)
        self.assertIn("unknown risk", rows[0][0])
        self.assertNotEqual(rows[0][0], "risk")

    def test_duplicate_book_risk_is_a_run_error(self):
        code, rows = self.run_batch("risk,rider_age\nH-1,30\nH-1,30\n", "risk,value,age,security\n")
        self.assertEqual(code, 2)
        self.assertIn("duplicate risk", rows[0][0])

    def test_blank_book_risk_is_a_run_error(self):
        code, rows = self.run_batch("risk,rider_age\n,30\n", "risk,value,age,security\n")
        self.assertEqual(code, 2)
        self.assertIn("blank risk", rows[0][0])

    def test_items_file_needs_a_risk_column(self):
        code, rows = self.run_batch("rider_age\n30\n", "value,age,security\n1000,0,gold\n")
        self.assertEqual(code, 2)
        self.assertIn("missing column 'risk'", rows[0][0])

    def test_unreadable_collection_file_is_a_run_error(self):
        code, rows = self.run_batch("rider_age\n30\n", extra=["bikes=/no/such/bikes.csv"])
        self.assertEqual(code, 2)
        self.assertIn("cannot read", rows[0][0])

    def test_extra_argument_must_be_a_collection(self):
        code, rows = self.run_batch("rider_age\n30\n", extra=["rider_age=x.csv"])
        self.assertEqual(code, 2)
        self.assertIn("not a collection", rows[0][0])

    def test_cli_file_and_path_in_cell_conflict(self):
        sidecar = os.path.join(self.d.name, "one.csv")
        with open(sidecar, "w") as f:
            f.write("value,age,security\n1000,0,gold\n")
        code, rows = self.run_batch(
            "rider_age,bikes\n30,one.csv\n",
            "risk,value,age,security\n1,1000,0,gold\n",
        )
        self.assertEqual(code, 2)
        self.assertIn("command line and as a column", rows[0][0])


if __name__ == "__main__":
    unittest.main()


class CheckVersions(unittest.TestCase):
    V1 = 'product "Bike"\n  published 2026-01-01\n  term 12 months\ninputs\n  bike_value: money\nrating\n  base 100\nlifecycle\n  renewal\n    invite 21 days before expiry\n'

    def test_check_finds_the_earlier_versions_beside_the_file(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "bike-2026-01-01.ipn"), "w") as f:
                f.write(self.V1)
            v2 = os.path.join(d, "bike-2026-07-01.ipn")
            with open(v2, "w") as f:
                f.write(self.V1.replace("2026-01-01", "2026-07-01").replace("base 100", "base 150") + '''
scenario "renews onto this version"
  given bike_value 2000
  when bound on 2026-03-01
  expect premium 100.00
  when renewed on 2027-03-01
  expect version 2026-07-01
  expect premium 150.00
''')
            code, out = run("check", v2)
        self.assertEqual(code, 0, out)
        self.assertIn("PASS renews onto this version", out)

    def test_a_broken_history_is_reported_like_a_parse_error(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "bike-2026-01-01.ipn"), "w") as f:
                f.write(self.V1)
            v2 = os.path.join(d, "bike-2026-07-01.ipn")
            with open(v2, "w") as f:
                f.write(self.V1.replace("2026-01-01", "2026-07-01").replace("  bike_value: money\n", "  bike_value: money\n  mileage: integer\n"))
            code, out = run("check", v2)
        self.assertEqual(code, 1)
        self.assertIn("mileage is new in the version published 2026-07-01", out)


class CheckErrors(unittest.TestCase):
    def test_a_parse_error_names_the_file_once_as_given(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "bad.ipn")
            with open(path, "w") as f:
                f.write('product "X"\n  territory UK\n\ninputs\n  age: integer\n\nrating\n  base 10 when agee < 25\n')
            code, out = run("check", path)
        self.assertEqual(code, 1)
        self.assertEqual(out, f"{path}: line 8: unknown word 'agee'\n")


class BatchColumnsForPerItemLines(unittest.TestCase):
    def test_a_tax_inside_for_each_has_its_own_column(self):
        import csv
        src = FLEET.replace("    base 3% of value\n", "    base 3% of value\n    tax \"Fire\" 22% of 20% of net\n")
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "fleet.ipn"), "w") as f:
                f.write(src)
            with open(os.path.join(d, "bikes.csv"), "w") as f:
                f.write("value,age,security\n1000,2,gold\n")
            with open(os.path.join(d, "risks.csv"), "w") as f:
                f.write("rider_age,bikes\n30,bikes.csv\n")
            code, out = run("batch", os.path.join(d, "fleet.ipn"), os.path.join(d, "risks.csv"))
        rows = list(csv.reader(io.StringIO(out)))
        self.assertEqual(rows[0], ["risk", "eligibility", "reasons", "net", "Fire", "IPT", "total", "currency", "error"])
        self.assertEqual(rows[1][4], "1.32")  # 22% of 20% of 30.00


ATTRIBUTED = RATING.replace("cover Theft\n", "cover Theft\n  class 9\n").replace('cover "Accidental Damage"\n', 'cover "Accidental Damage"\n  class 3\n').replace(
    "cover Racing optional\n", "cover Racing optional\n  class 3\n").replace(
    '  add "Racing cover" 45 when Racing selected\n', '  add "Racing cover" 45 for Racing when Racing selected\n  allocate\n    "Accidental Damage" 60%\n    Theft 40%\n')


class SharesInTheCli(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.d.name, "cycle.ipn")
        with open(self.path, "w") as f:
            f.write(ATTRIBUTED)

    def tearDown(self):
        self.d.cleanup()

    def test_quote_prints_each_covers_share_and_the_class_subtotals(self):
        code, out = run("quote", self.path, "bike_value=2000", "rider_age=30", "security=gold", "racing=yes", "select=Racing")
        self.assertEqual(code, 0, out)
        # 70 - 10 = 60 pool, + 45 Racing, less 10% = 94.50: Theft 21.60, AD 32.40, Racing 40.50; IPT 12% each
        self.assertIn("Shares:\n", out)
        self.assertIn("  Theft (class 9)              net 21.60  IPT 2.59\n", out)
        self.assertIn("  Accidental Damage (class 3)  net 32.40  IPT 3.89\n", out)
        self.assertIn("  Racing (class 3)             net 40.50  IPT 4.86\n", out)
        self.assertIn("By class:\n  9                            net 21.60  IPT 2.59\n  3                            net 72.90  IPT 8.75\n", out)

    def test_a_plain_product_prints_no_shares(self):
        with open(self.path, "w") as f:
            f.write(RATING)
        code, out = run("quote", self.path, "bike_value=2000", "rider_age=30", "security=gold", "racing=no")
        self.assertNotIn("Shares", out)

    def test_batch_has_a_column_per_cover_per_figure_after_the_existing_ones(self):
        import csv
        with open(os.path.join(self.d.name, "risks.csv"), "w") as f:
            f.write("bike_value,rider_age,security,racing,select\n2000,30,gold,yes,Racing\n")
        code, out = run("batch", self.path, os.path.join(self.d.name, "risks.csv"))
        rows = list(csv.reader(io.StringIO(out)))
        self.assertEqual(rows[0], ["risk", "eligibility", "reasons", "net", "IPT", "Admin fee", "total", "currency",
                                   "net:Theft", "IPT:Theft", "net:Accidental Damage", "IPT:Accidental Damage", "net:Racing", "IPT:Racing", "error"])
        self.assertEqual(rows[1][8:14], ["21.60", "2.59", "32.40", "3.89", "40.50", "4.86"])


class KeyedChoices(unittest.TestCase):
    PRODUCT = occupations('inputs\n  industry: choice of industry from "Occupations"\n  occupation: choice of occupation from "Occupations" for industry\n') + 'rating\n  base 100\n'

    def test_quote_rejects_an_occupation_outside_its_industry(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "x.ipn"), "w") as f:
                f.write(self.PRODUCT)
            code, out = run("quote", os.path.join(d, "x.ipn"), "industry=construction", "occupation=Nurse")
            self.assertEqual((code, out), (2, 'occupation "Nurse" is not an occupation for industry "construction"\n'))
            code, out = run("quote", os.path.join(d, "x.ipn"), "industry=construction")
            self.assertEqual((code, out), (2, "missing occupation\n"))
            code, out = run("quote", os.path.join(d, "x.ipn"), "industry=Health & Social Care", "occupation=Nurse")
        self.assertEqual(code, 0, out)
        self.assertIn("= 100.00", out)

    def test_batch_records_the_reason_in_the_error_column(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "x.ipn"), "w") as f:
                f.write(self.PRODUCT)
            with open(os.path.join(d, "risks.csv"), "w") as f:
                f.write('industry,occupation\nconstruction,Nurse\nconstruction,Labourer\n')
            code, out = run("batch", os.path.join(d, "x.ipn"), os.path.join(d, "risks.csv"))
        rows = list(csv.reader(io.StringIO(out)))
        self.assertEqual(rows[1][-1], 'occupation "Nurse" is not an occupation for industry "construction"')
        self.assertEqual(rows[2][-1], "")
