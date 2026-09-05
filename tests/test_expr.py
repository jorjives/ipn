import unittest
from decimal import Decimal

from ideclare.expr import parse_expr, evaluate, names, ExprError


def ev(src, **ctx):
    node, rest = parse_expr(src.split())
    assert rest == [], rest
    return evaluate(node, ctx)


class Expressions(unittest.TestCase):
    def test_arithmetic_and_precedence(self):
        self.assertEqual(ev("1 + 2 * 3"), Decimal(7))
        self.assertEqual(ev("( 1 + 2 ) * 3"), Decimal(9))
        self.assertEqual(ev("10 / 4"), Decimal("2.5"))
        self.assertEqual(ev("- 5 + 8"), Decimal(3))

    def test_percent_of(self):
        self.assertEqual(ev("3.5 % of bike_value", bike_value=Decimal(2000)), Decimal(70))
        self.assertEqual(ev("12 %"), Decimal("0.12"))

    def test_comparisons(self):
        self.assertTrue(ev("rider_age < 25", rider_age=22))
        self.assertFalse(ev("rider_age >= 25", rider_age=22))
        self.assertTrue(ev("security is gold", security="gold"))
        self.assertTrue(ev("security is not gold", security="silver"))
        self.assertTrue(ev("racing is yes", racing=True))
        self.assertTrue(ev("racing is no", racing=False))

    def test_boolean_logic(self):
        self.assertTrue(ev("a < 1 or b < 1", a=5, b=0))
        self.assertFalse(ev("a < 1 and b < 1", a=5, b=0))
        self.assertTrue(ev("not a < 1", a=5))
        self.assertTrue(ev("a < 1 or b < 1 and c < 1", a=0, b=5, c=5))

    def test_selected(self):
        self.assertTrue(ev("Racing selected", selected={"Racing"}))
        self.assertFalse(ev("Racing selected", selected=set()))

    def test_quoted_names(self):
        node, _ = parse_expr(['"Accidental Damage"', "selected"])
        self.assertTrue(evaluate(node, {"selected": {"Accidental Damage"}}))

    def test_quoted_string_is_a_literal(self):
        node, _ = parse_expr(['make', 'is', '"Brompton"'])
        self.assertEqual(node, ("is", ("name", "make"), ("str", "Brompton")))
        self.assertTrue(evaluate(node, {"make": "Brompton"}))
        self.assertEqual(names(node), {"make"})

    def test_selected_still_names_the_cover(self):
        node, _ = parse_expr(['"Accidental Damage"', "selected"])
        self.assertEqual(names(node), {"Accidental Damage"})

    def test_stops_at_keyword(self):
        node, rest = parse_expr("rider_age < 25 because".split(), stop={"because"})
        self.assertEqual(rest, ["because"])

    def test_names_lists_identifiers(self):
        node, _ = parse_expr("rider_age < 25 and security is gold".split())
        self.assertEqual(names(node), {"rider_age", "security", "gold"})

    def test_missing_value_is_error(self):
        with self.assertRaises(ExprError):
            ev("rider_age < 25")

    def test_syntax_error(self):
        with self.assertRaises(ExprError):
            parse_expr("1 +".split())


if __name__ == "__main__":
    unittest.main()


class Collections(unittest.TestCase):
    bikes = [{"value": Decimal(2000), "age": 0}, {"value": Decimal(500), "age": 3}]

    def test_count_and_aggregates(self):
        self.assertEqual(ev("count of bikes", bikes=self.bikes), Decimal(2))
        self.assertEqual(ev("total value of bikes", bikes=self.bikes), Decimal(2500))
        self.assertEqual(ev("highest value of bikes", bikes=self.bikes), Decimal(2000))
        self.assertEqual(ev("lowest value of bikes", bikes=self.bikes), Decimal(500))
        self.assertEqual(ev("total value of bikes", bikes=[]), Decimal(0))

    def test_any_and_every(self):
        self.assertTrue(ev("any bike where age > 2", bike=self.bikes))
        self.assertFalse(ev("every bike where age > 2", bike=self.bikes))
        self.assertTrue(ev("every bike where value >= 500 and age <= 3", bike=self.bikes))

    def test_not_a_collection(self):
        with self.assertRaises(ExprError):
            ev("count of bikes", bikes=3)
