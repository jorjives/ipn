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


import os
import tempfile


class ForFile(unittest.TestCase):
    def write(self, d, name, text):
        path = os.path.join(d, name)
        with open(path, "w") as f:
            f.write(text)
        return path

    def test_the_history_is_the_same_named_products_in_the_directory_published_up_to_this_one(self):
        with tempfile.TemporaryDirectory() as d:
            v1 = self.write(d, "bike-2026-01-01.idl", V1)
            v2 = self.write(d, "bike-2026-07-01.idl", V2)
            self.write(d, "bike-2027-01-01.idl", version("2027-01-01", "  bike_value: money\n  security: choice of bronze, silver, gold\n  racing: yes/no, default no\n  helmet: yes/no, default yes\n"))
            self.write(d, "other.idl", 'product "Other"\n  published 2025-01-01\n  term 12 months\n')
            self.write(d, "notes.txt", "not a product")
            self.assertEqual([p.published for p in History.for_file(v2).versions], [date(2026, 1, 1), date(2026, 7, 1)])
            self.assertEqual([p.published for p in History.for_file(v1).versions], [date(2026, 1, 1)])

    def test_the_file_itself_is_the_version_returned_for_its_own_date(self):
        with tempfile.TemporaryDirectory() as d:
            self.write(d, "bike-2026-01-01.idl", V1)
            v2 = self.write(d, "bike-2026-07-01.idl", V2)
            h = History.for_file(v2)
            self.assertEqual(h.live_on(date(2026, 8, 1)).published, date(2026, 7, 1))
            self.assertTrue(h.live_on(date(2026, 8, 1)).base.startswith(d))

    def test_an_unpublished_file_ignores_its_neighbours(self):
        with tempfile.TemporaryDirectory() as d:
            self.write(d, "bike-2026-01-01.idl", V1)
            lone = self.write(d, "lone.idl", 'product "Bike"\n  term 12 months\n')
            self.assertEqual(len(History.for_file(lone).versions), 1)
            self.assertIsNone(History.for_file(lone).versions[0].published)

    def test_a_broken_neighbour_of_the_same_product_is_reported_with_its_file_name(self):
        with tempfile.TemporaryDirectory() as d:
            self.write(d, "bike-2026-01-01.idl", V1.replace("base 100", "base banana"))
            v2 = self.write(d, "bike-2026-07-01.idl", V2)
            with self.assertRaises(ParseError) as cm:
                History.for_file(v2)
            self.assertIn("bike-2026-01-01.idl", str(cm.exception))


class UpgradingBlock(unittest.TestCase):
    OLD = version("2026-01-01", "  bike_value: money\n  accessories_value: money\n  security: choice of bronze, silver, gold\n")

    def new(self, inputs, upgrading):
        return version("2027-01-01", inputs) + "upgrading\n" + upgrading

    def history(self, inputs, upgrading):
        return History([parse(self.OLD), parse(self.new(inputs, upgrading))])

    def up(self, h, answers):
        return h.upgrade(answers, h.versions[0], h.versions[1])

    def test_a_choice_is_remapped_by_rows(self):
        h = self.history("  bike_value: money\n  lock_rating: choice of bronze, silver, gold, diamond\n",
                         "  lock_rating\n    security is gold: diamond\n    security is silver: silver\n    otherwise: bronze\n")
        self.assertEqual(self.up(h, {"bike_value": Decimal(1), "accessories_value": Decimal(2), "security": "gold"})[0]["lock_rating"], "diamond")
        self.assertEqual(self.up(h, {"bike_value": Decimal(1), "accessories_value": Decimal(2), "security": "bronze"})[0]["lock_rating"], "bronze")

    def test_inputs_merge_by_expression(self):
        h = self.history("  total_value: money\n  security: choice of bronze, silver, gold\n", "  total_value: bike_value + accessories_value\n")
        answers, needs = self.up(h, {"bike_value": Decimal(1000), "accessories_value": Decimal(250), "security": "gold"})
        self.assertEqual((answers["total_value"], needs), (Decimal(1250), []))

    def test_ask_makes_the_input_needed(self):
        h = self.history("  bike_value: money\n  mileage: integer\n", "  mileage: ask\n")
        answers, needs = self.up(h, {"bike_value": Decimal(1), "accessories_value": Decimal(2), "security": "gold"})
        self.assertEqual(needs, ["mileage"])
        self.assertNotIn("mileage", answers)

    def test_ask_in_a_row_is_needed_only_when_reached(self):
        h = self.history("  bike_value: money\n  lock_rating: choice of low, high\n", "  lock_rating\n    security is gold: high\n    otherwise: ask\n")
        self.assertEqual(self.up(h, {"bike_value": Decimal(1), "accessories_value": Decimal(2), "security": "gold"})[1], [])
        self.assertEqual(self.up(h, {"bike_value": Decimal(1), "accessories_value": Decimal(2), "security": "silver"})[1], ["lock_rating"])

    def test_unknown_words_are_checked_against_the_previous_version(self):
        with self.assertRaises(ParseError) as cm:
            self.history("  bike_value: money\n  lock_rating: choice of low, high\n", "  lock_rating: high when lock is gold, otherwise low\n")
        self.assertEqual(str(cm.exception), "line 12: unknown word 'lock' in the version published 2026-01-01")

    def test_a_literal_outside_the_target_choices_is_an_error_at_load(self):
        with self.assertRaises(ParseError) as cm:
            self.history("  bike_value: money\n  lock_rating: choice of low, high\n", "  lock_rating: platinum\n")
        self.assertIn("unknown word 'platinum'", str(cm.exception))

    def test_a_value_the_target_cannot_hold_fails_the_upgrade(self):
        h = self.history("  bike_value: money\n  lock_rating: choice of low, high\n", "  lock_rating: security\n")
        with self.assertRaises(ValueError) as cm:
            self.up(h, {"bike_value": Decimal(1), "accessories_value": Decimal(2), "security": "gold"})
        self.assertEqual(str(cm.exception), "lock_rating cannot be 'gold'; it is a choice of low, high")

    def test_a_mentioned_input_needs_no_default(self):
        self.history("  bike_value: money\n  mileage: integer\n", "  mileage: 5000\n")

    def test_ask_poisons_what_reads_it_along_the_chain(self):
        v2 = version("2026-07-01", "  bike_value: money\n  mileage: integer\n") + "upgrading\n  mileage: ask\n"
        v3 = version("2027-01-01", "  bike_value: money\n  heavy_use: yes/no\n") + "upgrading\n  heavy_use: mileage > 5000\n"
        h = History([parse(self.OLD), parse(v2), parse(v3)])
        answers, needs = h.upgrade({"bike_value": Decimal(1), "accessories_value": Decimal(2), "security": "gold"}, h.versions[0], h.versions[2])
        self.assertEqual((needs, "heavy_use" in answers), (["heavy_use"], False))
        answers, needs = h.upgrade({"bike_value": Decimal(1), "mileage": Decimal(6000)}, h.versions[1], h.versions[2])
        self.assertEqual((answers["heavy_use"], needs), (True, []))

    def test_items_upgrade_one_by_one_and_unmentioned_fields_carry(self):
        old = version("2026-01-01", "  rider_age: integer\n  bikes: collection of bike\n    value: money\n    security: choice of bronze, silver, gold\n")
        new = version("2027-01-01", "  rider_age: integer\n  cycles: collection of cycle\n    value: money\n    lock: choice of low, high\n") + "upgrading\n  cycles: for each bike\n    lock: high when security is gold, otherwise low\n"
        h = History([parse(old), parse(new)])
        answers, needs = h.upgrade({"rider_age": Decimal(30), "bikes": [{"value": Decimal(1), "security": "gold"}, {"value": Decimal(2), "security": "bronze"}]}, h.versions[0], h.versions[1])
        self.assertEqual(answers, {"rider_age": Decimal(30), "cycles": [{"value": Decimal(1), "lock": "high"}, {"value": Decimal(2), "lock": "low"}]})
        self.assertEqual(needs, [])

    def test_an_asked_item_field_is_reported_by_item_name(self):
        old = version("2026-01-01", "  bikes: collection of bike\n    value: money\n")
        new = version("2027-01-01", "  bikes: collection of bike\n    value: money\n    make: text\n    lock: choice of low, high\n") + "upgrading\n  bikes: for each bike\n    lock: ask\n"
        h = History([parse(old), parse(new)])
        answers, needs = h.upgrade({"bikes": [{"value": Decimal(1)}]}, h.versions[0], h.versions[1])
        self.assertEqual(needs, ["bike.lock"])
        self.assertEqual(answers["bikes"], [{"value": Decimal(1)}])

    def test_for_each_must_name_an_item_of_the_previous_version(self):
        new = version("2027-01-01", "  bikes: collection of bike\n    value: money\n") + "upgrading\n  bikes: for each cycle\n    value: 1\n"
        with self.assertRaises(ParseError) as cm:
            History([parse(self.OLD), parse(new)])
        self.assertIn("'cycle' is not an item in the version published 2026-01-01", str(cm.exception))

    def test_a_new_item_field_without_a_line_or_default_is_an_error(self):
        old = version("2026-01-01", "  bikes: collection of bike\n    value: money\n")
        new = version("2027-01-01", "  bikes: collection of bike\n    value: money\n    lock: choice of low, high\n")
        with self.assertRaises(ParseError) as cm:
            History([parse(old), parse(new)])
        self.assertIn("bikes is new in the version published 2027-01-01", str(cm.exception))


class ForFileNeighbours(ForFile):
    def test_a_broken_later_version_does_not_break_an_earlier_file(self):
        with tempfile.TemporaryDirectory() as d:
            v1 = self.write(d, "bike-2026-01-01.idl", V1)
            self.write(d, "bike-2026-07-01.idl", V2.replace("base 100", "base banana"))
            self.assertEqual(len(History.for_file(v1).versions), 1)
