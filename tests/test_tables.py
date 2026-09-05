import unittest
from decimal import Decimal

from ideclare.tables import Table, TableError, load_table


ROWS = """driver_age, area, vehicle_group, rate, note
17-20, 1, 1-5, 2.50, young
17-20, 1, 6+, 3.00, young
21-24, *, 1-5, 1.80, mid
21-24, *, 6+, 2.20, mid
25+, 1, *, 1.00, base
25+, 2, *, 1.10, base
""".splitlines()


class Loading(unittest.TestCase):
    def test_keys_and_value_columns(self):
        t = load_table("Rates", ["driver_age", "area", "vehicle_group"], ROWS)
        self.assertEqual(t.values, ["rate", "note"])
        self.assertEqual(len(t.rows), 6)

    def test_cells_are_typed(self):
        t = load_table("Rates", ["driver_age", "area", "vehicle_group"], ROWS)
        self.assertEqual(t.rows[0]["rate"], Decimal("2.50"))
        self.assertEqual(t.rows[0]["note"], "young")

    def test_missing_key_column(self):
        with self.assertRaisesRegex(TableError, "no column 'postcode'"):
            load_table("Rates", ["postcode"], ROWS)

    def test_needs_a_value_column(self):
        with self.assertRaisesRegex(TableError, "no value column"):
            load_table("Rates", ["a"], ["a", "1"])

    def test_duplicate_keys(self):
        with self.assertRaisesRegex(TableError, "row 3 repeats the keys of row 2"):
            load_table("Rates", ["a"], ["a, v", "1, 10", "1, 20"])

    def test_ragged_row(self):
        with self.assertRaisesRegex(TableError, "row 2 has 3 cells, expected 2"):
            load_table("Rates", ["a"], ["a, v", "1, 10, 3"])

    def test_empty_table(self):
        with self.assertRaisesRegex(TableError, "no rows"):
            load_table("Rates", ["a"], ["a, v"])


class Lookup(unittest.TestCase):
    def setUp(self):
        self.t = load_table("Rates", ["driver_age", "area", "vehicle_group"], ROWS)

    def look(self, **ctx):
        return self.t.lookup({k: Decimal(v) if isinstance(v, int) else v for k, v in ctx.items()})

    def test_band_and_exact(self):
        self.assertEqual(self.look(driver_age=19, area=1, vehicle_group=3)["rate"], Decimal("2.50"))
        self.assertEqual(self.look(driver_age=20, area=1, vehicle_group=6)["rate"], Decimal("3.00"))

    def test_wildcard(self):
        self.assertEqual(self.look(driver_age=22, area=4, vehicle_group=9)["rate"], Decimal("2.20"))

    def test_open_band(self):
        self.assertEqual(self.look(driver_age=80, area=2, vehicle_group=50)["rate"], Decimal("1.10"))

    def test_no_row(self):
        with self.assertRaisesRegex(TableError, "no row in Rates for driver_age 19, area 2, vehicle_group 3"):
            self.look(driver_age=19, area=2, vehicle_group=3)

    def test_ambiguous(self):
        t = load_table("T", ["age"], ["age, v", "17-25, 1", "20-30, 2"])
        with self.assertRaisesRegex(TableError, "T is ambiguous for age 22"):
            t.lookup({"age": Decimal(22)})

    def test_text_and_yes_no_keys(self):
        t = load_table("T", ["security", "racing"], ["security, racing, v", "gold, yes, 1", "gold, no, 2", "*, *, 3"])
        self.assertEqual(t.lookup({"security": "gold", "racing": False})["v"], Decimal(2))
        self.assertEqual(t.lookup({"security": "silver", "racing": True})["v"], Decimal(3))

    def test_band_needs_a_number(self):
        with self.assertRaisesRegex(TableError, "no row in Rates"):
            self.look(driver_age="young", area=1, vehicle_group=1)


if __name__ == "__main__":
    unittest.main()
