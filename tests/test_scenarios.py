import unittest

from ideclare.parser import parse
from ideclare.scenarios import run_all
from tests.test_parser import FULL


def outcomes(extra):
    return {r.scenario.name: r.failures for r in run_all(parse(FULL + extra))}


class ScenarioRunner(unittest.TestCase):
    def test_passing_eligibility_and_cover_expectations(self):
        res = outcomes('''
scenario "ok"
  given bike_value 3000, rider_age 22, security bronze, racing yes
  select Racing
  expect eligible
  expect cover Theft excluded "Gold or silver lock required"
  expect cover Racing included
  expect cover Racing limit 5000
  expect cover "Accidental Damage" included
''')
        self.assertEqual(res["ok"], [])

    def test_failure_names_line_and_values(self):
        res = outcomes('''
scenario "wrong"
  given bike_value 2000, rider_age 15, security gold, racing no
  expect eligible
''')
        self.assertEqual(len(res["wrong"]), 1)
        self.assertIn("expected eligible", res["wrong"][0])
        self.assertIn("declined", res["wrong"][0])
        self.assertIn("Rider must be at least 16", res["wrong"][0])

    def test_declined_with_reason(self):
        res = outcomes('''
scenario "declined"
  given bike_value 2000, rider_age 15, security gold, racing no
  expect declined "Rider must be at least 16"
  expect declined "some other reason"
''')
        self.assertEqual(len(res["declined"]), 1)

    def test_unknown_expectation_is_failure(self):
        res = outcomes('''
scenario "odd"
  given bike_value 2000, rider_age 30, security gold, racing no
  expect sunshine
''')
        self.assertIn("do not understand", res["odd"][0])

    def test_missing_given_is_failure(self):
        res = outcomes('''
scenario "short"
  given bike_value 2000
  expect eligible
''')
        self.assertIn("rider_age", res["short"][0])
