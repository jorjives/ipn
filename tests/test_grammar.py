"""The grammar page compiles to the playground's completion table, and every product parses under it."""
import unittest

from scripts.grammar_table import GrammarError, Walker, build, mark_lines, product_tokens, read


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


NL, IN, DE = ("tok", "NEWLINE"), ("tok", "INDENT"), ("tok", "DEDENT")


class Lines(unittest.TestCase):
    GRAMMAR = ("```\n"
               "file   = header { line }\n"
               "header = 'product' string\n"
               "           { 'term' number }\n"
               "line   = 'x' [ 'y' ]\n"
               "       | 'z'\n"
               "           { line }\n"
               "       | 'w' tail\n"
               "tail   = 'p' | 'q'\n"
               "```\n")

    def test_file_is_a_run_of_lines(self):
        rules = mark_lines(read(self.GRAMMAR))
        self.assertEqual(rules["file"], ("seq", [("ref", "header$line"), ("rep", ("ref", "line$line"))]))

    def test_a_line_ends_with_newline_before_its_nested_lines(self):
        rules = mark_lines(read(self.GRAMMAR))
        self.assertEqual(rules["header$line"], ("seq", [
            ("lit", "product"), ("cls", "string"), NL,
            ("opt", ("seq", [IN, ("rep", ("seq", [("lit", "term"), ("cls", "number"), NL])), DE])),
        ]))

    def test_a_line_ending_in_a_rule_delegates_to_that_rule_as_lines(self):
        rules = mark_lines(read(self.GRAMMAR))
        self.assertEqual(rules["line$line"], ("alt", [
            ("seq", [("lit", "x"), ("opt", ("lit", "y")), NL]),
            ("seq", [("lit", "z"), NL, ("opt", ("seq", [IN, ("rep", ("ref", "line$line")), DE]))]),
            ("seq", [("lit", "w"), ("ref", "tail$line")]),
        ]))
        self.assertEqual(rules["tail$line"], ("alt", [("seq", [("lit", "p"), NL]), ("seq", [("lit", "q"), NL])]))

    def test_rules_never_used_as_lines_keep_no_newline(self):
        rules = mark_lines(read(self.GRAMMAR))
        self.assertEqual(rules["tail"], ("alt", [("lit", "p"), ("lit", "q")]))


class Compiled(unittest.TestCase):
    def table(self, grammar):
        return build("```\n" + grammar + "```\n")

    def walk(self, table, start, toks):
        w = Walker(table, start)
        for kind, text in toks:
            self.assertTrue(w.feed(kind, text), f"{text!r} refused; expected {sorted(w.expected())}")
        return w

    def test_states_edges_and_acceptance(self):
        table = self.table("file = line\nline = 'a' { ',' 'a' }\n")
        self.assertEqual(table["start"], "file")
        self.assertEqual(table["rules"]["file"], [{"accept": False, "edges": [["call", "line$line", 1]]}, {"accept": True, "edges": []}])
        self.assertEqual(table["rules"]["line$line"], [
            {"accept": False, "edges": [["lit", "a", 1]]},
            {"accept": False, "edges": [["lit", ",", 0], ["tok", "NEWLINE", 2]]},
            {"accept": True, "edges": []},
        ])
        w = self.walk(table, "file", [("id", "a"), ("op", ","), ("id", "a"), ("NEWLINE", "")])
        self.assertTrue(w.accepted())
        self.assertFalse(Walker(table, "file").feed("id", "b"))

    def test_recursion_through_calls(self):
        table = self.table("file = e\ne = 'n' | '(' e ')'\n")
        w = self.walk(table, "file", [("op", "("), ("op", "("), ("id", "n"), ("op", ")"), ("op", ")"), ("NEWLINE", "")])
        self.assertTrue(w.accepted())
        w = self.walk(table, "file", [("op", "("), ("id", "n")])
        self.assertFalse(w.accepted())
        self.assertEqual(w.expected(), {("e$line", "lit", ")")})
        w = self.walk(table, "file", [("op", "("), ("op", "("), ("id", "n")])
        self.assertEqual(w.expected(), {("e", "lit", ")")})

    def test_expected_names_the_rule_wanting_each_token(self):
        table = self.table("file = 'limit' amount\namount = number | name\n")
        w = self.walk(table, "file", [("id", "limit")])
        self.assertEqual(w.expected(), {("amount$line", "cls", "number"), ("amount$line", "cls", "name")})

    def test_classes_match_token_kinds(self):
        table = self.table("file = 'n' integer | 'd' date | 's' string | 'w' word\n")
        for prefix, kind, text in [("n", "num", "3"), ("d", "date", "2026-01-01"), ("s", "str", '"x"'), ("w", "id", "gold")]:
            self.assertTrue(self.walk(table, "file", [("id", prefix)]).feed(kind, text), text)
        self.assertFalse(self.walk(table, "file", [("id", "n")]).feed("num", "3.5"))
        self.assertTrue(self.walk(table, "file", [("id", "w")]).feed("id", "n"), "a keyword is still a word")

    def test_nested_lines_are_indent_and_dedent(self):
        table = self.table("file = 'cover' name\n         { 'limit' number }\n")
        w = self.walk(table, "file", [("id", "cover"), ("id", "Theft"), ("NEWLINE", ""), ("INDENT", ""),
                                      ("id", "limit"), ("num", "5"), ("NEWLINE", ""), ("DEDENT", "")])
        self.assertTrue(w.accepted())
        self.assertTrue(self.walk(table, "file", [("id", "cover"), ("id", "Theft"), ("NEWLINE", "")]).accepted())

    def test_table_is_deterministic_and_minimal(self):
        g = "file = line\nline = 'a' { ',' 'a' }\n"
        self.assertEqual(self.table(g), self.table(g))
        self.assertEqual(len(self.table(g)["rules"]["line$line"]), 3)


class ProductTokens(unittest.TestCase):
    def test_structure_tokens(self):
        toks = product_tokens('cover Theft  # note\n\n  limit 5\n  excess 10% of claim\nrating\n')
        self.assertEqual(toks, [
            ("id", "cover"), ("id", "Theft"), ("NEWLINE", ""), ("INDENT", ""),
            ("id", "limit"), ("num", "5"), ("NEWLINE", ""),
            ("id", "excess"), ("num", "10"), ("op", "%"), ("id", "of"), ("id", "claim"), ("NEWLINE", ""),
            ("DEDENT", ""), ("id", "rating"), ("NEWLINE", ""),
        ])

    def test_two_dedents_at_once_and_strings_with_hashes(self):
        toks = product_tokens('a\n  b\n    c "x # y"\nd\n')
        self.assertEqual([t for t in toks if t[0] in ("INDENT", "DEDENT")], [("INDENT", ""), ("INDENT", ""), ("DEDENT", ""), ("DEDENT", "")])
        self.assertIn(("str", '"x # y"'), toks)


if __name__ == "__main__":
    unittest.main()
