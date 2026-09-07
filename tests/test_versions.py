import unittest
from datetime import date
from decimal import Decimal

from ideclare.parser import ParseError, parse
from ideclare.versions import History


def version(published: str, inputs: str) -> str:
    return f'product "Bike"\n  published {published}\n  term 12 months\n\ninputs\n{inputs}\nrating\n  base 100\n'


V1 = version("2026-01-01", "  bike_value: money\n  security: choice of bronze, silver, gold\n")
V2 = version("2026-07-01", "  bike_value: money\n  security: choice of bronze, silver, gold\n  racing: yes/no, default no\n")


class LiveOn(unittest.TestCase):
    def setUp(self):
        self.h = History([parse(V2), parse(V1)])  # any order in

    def test_versions_are_sorted_by_published_date(self):
        self.assertEqual([p.published for p in self.h.versions], [date(2026, 1, 1), date(2026, 7, 1)])

    def test_the_latest_version_published_on_or_before_the_date_is_live(self):
        self.assertEqual(self.h.live_on(date(2026, 1, 1)).published, date(2026, 1, 1))
        self.assertEqual(self.h.live_on(date(2026, 6, 30)).published, date(2026, 1, 1))
        self.assertEqual(self.h.live_on(date(2026, 7, 1)).published, date(2026, 7, 1))
        self.assertEqual(self.h.live_on(date(2030, 1, 1)).published, date(2026, 7, 1))

    def test_nothing_is_live_before_the_first_version(self):
        with self.assertRaises(ValueError) as cm:
            self.h.live_on(date(2025, 12, 31))
        self.assertEqual(str(cm.exception), "no version of Bike was on sale on 2025-12-31")

    def test_two_versions_on_one_date_is_an_error(self):
        with self.assertRaises(ParseError) as cm:
            History([parse(V1), parse(V1)])
        self.assertIn("published 2026-01-01", str(cm.exception))

    def test_a_lone_unpublished_product_is_a_history_of_one_live_always(self):
        p = parse('product "X"\n  term 12 months\n')
        h = History([p])
        self.assertIs(h.live_on(date(1990, 1, 1)), p)
        self.assertIs(h.live_on(date(2090, 1, 1)), p)


class Upgrade(unittest.TestCase):
    def test_inputs_carry_by_name_and_new_inputs_take_their_default(self):
        h = History([parse(V1), parse(V2)])
        answers, needs = h.upgrade({"bike_value": Decimal(2000), "security": "gold"}, h.versions[0], h.versions[1])
        self.assertEqual(answers, {"bike_value": Decimal(2000), "security": "gold", "racing": False})
        self.assertEqual(needs, [])

    def test_a_dropped_input_is_left_behind(self):
        v3 = version("2027-01-01", "  bike_value: money\n")
        h = History([parse(V1), parse(v3)])
        answers, _ = h.upgrade({"bike_value": Decimal(1), "security": "gold"}, h.versions[0], h.versions[1])
        self.assertEqual(answers, {"bike_value": Decimal(1)})

    def test_a_new_input_without_a_default_is_a_load_time_error(self):
        v3 = version("2027-01-01", "  bike_value: money\n  annual_mileage: integer\n")
        with self.assertRaises(ParseError) as cm:
            History([parse(V1), parse(v3)])
        self.assertIn("annual_mileage is new in the version published 2027-01-01", str(cm.exception))
        self.assertIn("line 7", str(cm.exception))

    def test_a_choice_that_lost_a_value_cannot_carry(self):
        v3 = version("2027-01-01", "  bike_value: money\n  security: choice of silver, gold\n")
        with self.assertRaises(ParseError) as cm:
            History([parse(V1), parse(v3)])
        self.assertIn("security", str(cm.exception))

    def test_a_choice_that_gained_a_value_carries(self):
        v3 = version("2027-01-01", "  bike_value: money\n  security: choice of bronze, silver, gold, diamond\n")
        h = History([parse(V1), parse(v3)])
        answers, _ = h.upgrade({"bike_value": Decimal(1), "security": "gold"}, h.versions[0], h.versions[1])
        self.assertEqual(answers["security"], "gold")

    def test_upgrading_to_the_same_version_changes_nothing(self):
        h = History([parse(V1)])
        answers, needs = h.upgrade({"bike_value": Decimal(1), "security": "gold"}, h.versions[0], h.versions[0])
        self.assertEqual((answers, needs), ({"bike_value": Decimal(1), "security": "gold"}, []))

    def test_the_chain_composes_across_versions(self):
        v3 = version("2027-01-01", "  bike_value: money\n  security: choice of bronze, silver, gold\n  racing: yes/no, default no\n  helmet: yes/no, default yes\n")
        h = History([parse(V1), parse(V2), parse(v3)])
        answers, _ = h.upgrade({"bike_value": Decimal(1), "security": "gold"}, h.versions[0], h.versions[2])
        self.assertEqual(answers, {"bike_value": Decimal(1), "security": "gold", "racing": False, "helmet": True})
