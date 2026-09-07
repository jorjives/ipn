import unittest
from datetime import date
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


class Less(unittest.TestCase):
    def test_less_is_minus(self):
        self.assertEqual(ev("net less fire", net=Decimal(100), fire=Decimal(30)), Decimal(70))
        self.assertEqual(ev("12 % of net less fire", net=Decimal(100), fire=Decimal(30)), Decimal("8.4"))  # of takes the whole sum
        self.assertEqual(ev("12 % of net less fire", net=Decimal(100), fire=Decimal(30)), ev("12 % of ( net - fire )", net=Decimal(100), fire=Decimal(30)))


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


class Dates(unittest.TestCase):
    def test_date_literal_and_comparison(self):
        self.assertTrue(ev("start < 2026-06-01", start=date(2026, 3, 1)))
        self.assertFalse(ev("start >= 2026-06-01", start=date(2026, 3, 1)))
        self.assertTrue(ev("start is 2026-03-01", start=date(2026, 3, 1)))

    def test_days_between_dates(self):
        self.assertEqual(ev("back - out", out=date(2026, 3, 1), back=date(2026, 3, 15)), Decimal(14))


class Lookups(unittest.TestCase):
    def setUp(self):
        from ideclare.tables import load_table
        self.tables = {"Rates": load_table("Rates", ["age", "area"], ["age, area, rate", "17-20, *, 2.5", "21+, 1, 1.1"])}

    def test_parses_column_from_table(self):
        node, rest = parse_expr(["rate", "from", '"Rates"', "when"], stop={"when"})
        self.assertEqual(node, ("lookup", "rate", "Rates"))
        self.assertEqual(rest, ["when"])

    def test_evaluates_against_the_context(self):
        node, _ = parse_expr(["rate", "from", '"Rates"', "*", "2"])
        self.assertEqual(evaluate(node, {"age": Decimal(19), "area": Decimal(3), "tables": self.tables}), Decimal(5))

    def test_unknown_table(self):
        node, _ = parse_expr(["rate", "from", '"Other"'])
        with self.assertRaisesRegex(ExprError, "no table called 'Other'"):
            evaluate(node, {"tables": self.tables})

    def test_names_and_lookups(self):
        from ideclare.expr import lookups
        node, _ = parse_expr(["rate", "from", '"Rates"', "+", "base"])
        self.assertEqual(names(node), {"base"})
        self.assertEqual(lookups(node), {("rate", "Rates")})

    def test_from_without_a_table_name_is_left_alone(self):
        node, rest = parse_expr(["age", "from"], stop={"from"})
        self.assertEqual(node, ("name", "age"))
        self.assertEqual(rest, ["from"])


class Functions(unittest.TestCase):
    def test_power_is_right_associative_and_binds_tightly(self):
        self.assertEqual(ev("2 ^ 3 ^ 2"), Decimal(512))
        self.assertEqual(ev("2 * 3 ^ 2"), Decimal(18))
        self.assertEqual(ev("- 2 ^ 2"), Decimal(-4))
        self.assertEqual(ev("4 ^ 0.5"), Decimal(2))

    def test_functions(self):
        self.assertEqual(ev("sqrt ( 16 )"), Decimal(4))
        self.assertEqual(ev("min ( 3 , 1 , 2 )"), Decimal(1))
        self.assertEqual(ev("max ( a , 10 )", a=Decimal(3)), Decimal(10))
        self.assertEqual(ev("round ( 2 / 3 , 0.01 )"), Decimal("0.67"))
        self.assertEqual(ev("round ( 2.5 , 1 )"), Decimal(3))
        self.assertEqual(ev("round ( exp ( 1 ) , 0.0001 )"), Decimal("2.7183"))
        self.assertEqual(ev("round ( ln ( exp ( 2 ) ) , 0.0001 )"), Decimal("2.0000"))

    def test_functions_are_not_names(self):
        node, _ = parse_expr("min ( age , 30 )".split())
        self.assertEqual(names(node), {"age"})

    def test_function_arity(self):
        with self.assertRaisesRegex(ExprError, "sqrt takes 1 argument"):
            ev("sqrt ( 1 , 2 )")
        with self.assertRaisesRegex(ExprError, "min takes at least 2 arguments"):
            ev("min ( 1 )")

    def test_unknown_function(self):
        with self.assertRaisesRegex(ExprError, "unknown function 'sin'"):
            ev("sin ( 1 )")


class Interpolated(unittest.TestCase):
    def setUp(self):
        from ideclare.tables import load_table
        self.tables = {"Curve": load_table("Curve", ["age"], ["age, rate", "30, 1", "40, 3"])}

    def test_parses_default_and_named_methods(self):
        node, rest = parse_expr(["rate", "from", '"Curve"', "interpolated", "on", "age", "when"], stop={"when"})
        self.assertEqual(node, ("interp", "rate", "Curve", "age", "linearly"))
        self.assertEqual(rest, ["when"])
        node, _ = parse_expr(["rate", "from", '"Curve"', "interpolated", "geometrically", "on", "age"])
        self.assertEqual(node, ("interp", "rate", "Curve", "age", "geometrically"))

    def test_unknown_method(self):
        with self.assertRaisesRegex(ExprError, "interpolated linearly or geometrically, not 'wildly'"):
            parse_expr(["rate", "from", '"Curve"', "interpolated", "wildly", "on", "age"])

    def test_evaluates(self):
        from ideclare.expr import lookups
        node, _ = parse_expr(["rate", "from", '"Curve"', "interpolated", "on", "age"])
        self.assertEqual(evaluate(node, {"age": Decimal(35), "tables": self.tables}), Decimal(2))
        self.assertEqual(lookups(node), {("rate", "Curve")})
        self.assertEqual(names(node), set())
