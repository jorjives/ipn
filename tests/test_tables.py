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


class Interpolation(unittest.TestCase):
    def setUp(self):
        self.t = load_table("Mortality", ["age", "smoker"], [
            "age, smoker, rate", "30, no, 1.00", "40, no, 2.00", "50, no, 8.00", "30, yes, 2.00", "40, yes, 4.00", "50, yes, 16.00"])

    def test_on_a_knot(self):
        self.assertEqual(self.t.interpolate({"age": Decimal(40), "smoker": False}, "rate", "age", "linearly"), Decimal("2.00"))
        self.assertEqual(self.t.interpolate({"age": Decimal(40), "smoker": True}, "rate", "age", "geometrically"), Decimal("4.00"))

    def test_linear_between_knots(self):
        self.assertEqual(self.t.interpolate({"age": Decimal(45), "smoker": False}, "rate", "age", "linearly"), Decimal("5.00"))

    def test_geometric_between_knots(self):
        # halfway from 2 to 8 by ratio is 4, not 5
        self.assertEqual(self.t.interpolate({"age": Decimal(45), "smoker": False}, "rate", "age", "geometrically"), Decimal("4.00"))

    def test_outside_the_knots(self):
        with self.assertRaisesRegex(TableError, "age 29 is outside Mortality, whose knots run from 30 to 50"):
            self.t.interpolate({"age": Decimal(29), "smoker": False}, "rate", "age", "linearly")

    def test_other_keys_must_match(self):
        with self.assertRaisesRegex(TableError, "no rows in Mortality for smoker maybe"):
            self.t.interpolate({"age": Decimal(35), "smoker": "maybe"}, "rate", "age", "linearly")

    def test_knots_must_be_numbers(self):
        t = load_table("T", ["age"], ["age, v", "30-39, 1", "40+, 2"])
        with self.assertRaisesRegex(TableError, "T cannot be interpolated on age: the cell '30-39' is not a single number"):
            t.interpolate({"age": Decimal(35)}, "v", "age", "linearly")

    def test_needs_two_knots(self):
        t = load_table("T", ["age"], ["age, v", "30, 1"])
        with self.assertRaisesRegex(TableError, "T needs at least two knots on age"):
            t.interpolate({"age": Decimal(30)}, "v", "age", "linearly")

    def test_geometric_needs_positive_values(self):
        t = load_table("T", ["age"], ["age, v", "30, 0", "40, 1"])
        with self.assertRaisesRegex(TableError, "T cannot be interpolated geometrically: v is 0 at age 30"):
            t.interpolate({"age": Decimal(35)}, "v", "age", "geometrically")


if __name__ == "__main__":
    unittest.main()
