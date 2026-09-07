"""The grammar page compiles to the playground's completion table, and every product parses under it."""
import unittest

from scripts.grammar_table import GrammarError, read


class Reader(unittest.TestCase):
    def test_reads_rules_from_fenced_blocks_only(self):
        rules = read("prose\n```\na = 'x' b\nb = 'y'\n```\nmore prose a = 'not a rule'\n")
        self.assertEqual(rules, {"a": ("seq", [("lit", "x"), ("ref", "b")]), "b": ("lit", "y")})

    def test_alternatives_optionals_repetitions_groups_and_comments(self):
        rules = read("```\na = 'x' [ 'y' ] { 'z' }     -- a comment\n  | ( 'p' | 'q' ) string\n```\n")
        self.assertEqual(rules["a"], ("alt", [
            ("seq", [("lit", "x"), ("opt", ("lit", "y")), ("rep", ("lit", "z"))]),
            ("seq", [("alt", [("lit", "p"), ("lit", "q")]), ("cls", "string")]),
        ]))

    def test_quoted_string_literal(self):
        self.assertEqual(read("```\na = '\"not selected\"'\n```\n"), {"a": ("lit", '"not selected"')})

    def test_indented_continuation_is_nested_lines(self):
        rules = read("```\nblock = 'cover' name\n          { line }\nline  = 'limit' number\n```\n")
        self.assertEqual(rules["block"], ("seq", [("lit", "cover"), ("cls", "name"), ("indent", ("rep", ("ref", "line")))]))

    def test_deeper_and_shallower_continuations_nest_and_close(self):
        rules = read("```\na   = 'p'\n      'q'\n        { 'r' }\n      [ 's' ]\n    | 't'\n```\n")
        self.assertEqual(rules["a"], ("alt", [
            ("seq", [("lit", "p"), ("indent", ("seq", [("lit", "q"), ("indent", ("rep", ("lit", "r"))), ("opt", ("lit", "s"))]))]),
            ("lit", "t"),
        ]))

    def test_bracket_crossing_an_indent_is_an_error(self):
        with self.assertRaisesRegex(GrammarError, "claim"):
            read("```\nclaim = 'claim'\n          [ 'asks'\n              { field } ]\n```\n")

    def test_continuation_shallower_than_the_rule_is_an_error(self):
        with self.assertRaisesRegex(GrammarError, "a"):
            read("```\na    = 'p'\n  'q'\n```\n")

    def test_undefined_name_that_is_not_a_terminal_class_is_an_error(self):
        with self.assertRaisesRegex(GrammarError, "nowhere"):
            read("```\na = nowhere\n```\n")

    def test_rule_defined_twice_is_an_error(self):
        with self.assertRaisesRegex(GrammarError, "a"):
            read("```\na = 'x'\na = 'y'\n```\n")


if __name__ == "__main__":
    unittest.main()
