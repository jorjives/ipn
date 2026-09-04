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
