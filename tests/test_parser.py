import unittest
from decimal import Decimal

from ideclare.parser import parse, ParseError


HEADER = '''
product "Cycle Cover"
  territory UK
  currency GBP
  term 12 months

inputs
  bike_value: money
  rider_age: integer
  security: choice of bronze, silver, gold
  racing: yes/no
  notes: text
'''


class HeaderAndInputs(unittest.TestCase):
    def test_product_header(self):
        p = parse(HEADER)
        self.assertEqual(p.name, "Cycle Cover")
        self.assertEqual(p.territory, "UK")
        self.assertEqual(p.currency, "GBP")
        self.assertEqual(p.term_months, 12)

    def test_inputs(self):
        p = parse(HEADER)
        self.assertEqual(p.inputs["bike_value"].kind, "money")
        self.assertEqual(p.inputs["rider_age"].kind, "integer")
        self.assertEqual(p.inputs["security"].kind, "choice")
        self.assertEqual(p.inputs["security"].choices, ["bronze", "silver", "gold"])
        self.assertEqual(p.inputs["racing"].kind, "yes/no")
        self.assertEqual(p.inputs["notes"].kind, "text")

    def test_comments_and_blank_lines_ignored(self):
        p = parse("# a comment\n\nproduct \"X\"  # trailing\n  term 6 months\n")
        self.assertEqual(p.name, "X")
        self.assertEqual(p.term_months, 6)

    def test_unknown_block_reports_line(self):
        with self.assertRaises(ParseError) as cm:
            parse('product "X"\n\nbanana\n  yes\n')
        self.assertIn("line 3", str(cm.exception))

    def test_unknown_input_type_reports_line(self):
        with self.assertRaises(ParseError) as cm:
            parse('product "X"\ninputs\n  a: colour\n')
        self.assertIn("line 3", str(cm.exception))
        self.assertIn("colour", str(cm.exception))

    def test_inconsistent_indent_is_error(self):
        with self.assertRaises(ParseError):
            parse('product "X"\n   territory UK\n  currency GBP\n')


if __name__ == "__main__":
    unittest.main()


FULL = HEADER + '''
eligibility
  decline when rider_age < 16 because "Rider must be at least 16"
  refer when bike_value > 10000 because "Underwriter review"

cover Theft
  limit bike_value
  excess 10% of claim, minimum 50
  excludes when security is bronze and bike_value > 2000 because "Gold or silver lock required"

cover "Accidental Damage"
  limit bike_value
  excess 100

cover Racing optional
  limit 5000
  excess 250
  available when racing is yes

scenario "Young rider"
  given bike_value 2000, rider_age 22, security gold, racing no
  select Racing
  expect eligible
'''


class RulesCoversScenarios(unittest.TestCase):
    def test_eligibility_rules(self):
        p = parse(FULL)
        self.assertEqual([r.kind for r in p.eligibility], ["decline", "refer"])
        self.assertEqual(p.eligibility[0].reason, "Rider must be at least 16")
        self.assertEqual(p.eligibility[0].condition, ("<", ("name", "rider_age"), ("num", Decimal(16))))

    def test_covers(self):
        p = parse(FULL)
        theft, ad, racing = p.covers
        self.assertEqual(theft.name, "Theft")
        self.assertFalse(theft.optional)
        self.assertEqual(theft.limit, ("name", "bike_value"))
        self.assertEqual(theft.excess.amount, ("*", ("pct", ("num", Decimal(10))), ("name", "claim")))
        self.assertEqual(theft.excess.minimum, ("num", Decimal(50)))
        self.assertEqual(theft.exclusions[0].reason, "Gold or silver lock required")
        self.assertEqual(ad.name, "Accidental Damage")
        self.assertEqual(ad.excess.amount, ("num", Decimal(100)))
        self.assertIsNone(ad.excess.minimum)
        self.assertTrue(racing.optional)
        self.assertEqual(racing.available, ("is", ("name", "racing"), ("bool", True)))

    def test_scenario(self):
        p = parse(FULL)
        s = p.scenarios[0]
        self.assertEqual(s.name, "Young rider")
        self.assertEqual(s.given, {"bike_value": Decimal(2000), "rider_age": Decimal(22), "security": "gold", "racing": False})
        self.assertEqual(s.selected, {"Racing"})
        self.assertEqual([st.tokens for st in s.steps], [["expect", "eligible"]])

    def test_unknown_input_in_rule_is_error(self):
        with self.assertRaises(ParseError) as cm:
            parse(HEADER + 'eligibility\n  decline when ridder_age < 16 because "x"\n')
        self.assertIn("ridder_age", str(cm.exception))

    def test_unknown_choice_in_rule_is_error(self):
        with self.assertRaises(ParseError) as cm:
            parse(HEADER + 'eligibility\n  decline when security is platinum because "x"\n')
        self.assertIn("platinum", str(cm.exception))

    def test_given_checks_input_type(self):
        with self.assertRaises(ParseError) as cm:
            parse(FULL + 'scenario "bad"\n  given rider_age gold\n')
        self.assertIn("rider_age", str(cm.exception))

    def test_select_unknown_cover_is_error(self):
        with self.assertRaises(ParseError):
            parse(FULL + 'scenario "bad"\n  select Flying\n')


RATING = FULL + '''
rating
  base 3.5% of bike_value
  factor "Rider age"
    rider_age < 25: x 1.40
    rider_age < 40: x 1.00
    otherwise: x 0.90
  factor "Security"
    security is gold: - 10
    otherwise: + 0
  add "Racing cover" 45 when Racing selected
  discount 10% when security is gold
  load 25% when rider_age < 21
  minimum 60
  tax IPT 12%
  fee "Admin fee" 10
  round to 0.01
'''


class Rating(unittest.TestCase):
    def test_steps_parse_in_order(self):
        p = parse(RATING)
        self.assertEqual([s.kind for s in p.rating], ["base", "factor", "factor", "add", "discount", "load", "minimum", "tax", "fee", "round"])

    def test_factor_rows(self):
        p = parse(RATING)
        age = p.rating[1]
        self.assertEqual(age.label, "Rider age")
        self.assertEqual([(r.op, r.amount) for r in age.rows], [("x", ("num", Decimal("1.40"))), ("x", ("num", Decimal("1.00"))), ("x", ("num", Decimal("0.90")))])
        self.assertIsNone(age.rows[2].condition)
        self.assertEqual(p.rating[2].rows[0].op, "-")

    def test_conditional_add_and_labels(self):
        p = parse(RATING)
        add, disc, load, tax, fee = p.rating[3], p.rating[4], p.rating[5], p.rating[7], p.rating[8]
        self.assertEqual(add.label, "Racing cover")
        self.assertEqual(add.condition, ("selected", ("name", "Racing")))
        self.assertEqual(disc.amount, ("pct", ("num", Decimal(10))))
        self.assertEqual(load.condition, ("<", ("name", "rider_age"), ("num", Decimal(21))))
        self.assertEqual(tax.label, "IPT")
        self.assertEqual(fee.label, "Admin fee")
        self.assertEqual(p.rating[9].amount, ("num", Decimal("0.01")))

    def test_otherwise_must_be_last(self):
        with self.assertRaises(ParseError) as cm:
            parse(FULL + 'rating\n  base 10\n  factor "A"\n    otherwise: x 1\n    rider_age < 5: x 2\n')
        self.assertIn("otherwise", str(cm.exception))

    def test_unknown_rating_step(self):
        with self.assertRaises(ParseError):
            parse(FULL + 'rating\n  multiply 10\n')
