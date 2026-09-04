import unittest
from decimal import Decimal

from ideclare.parser import parse
from ideclare.engine import check_eligibility, cover_states
from tests.test_parser import FULL


def risk(**over):
    base = dict(bike_value=Decimal(2000), rider_age=Decimal(30), security="gold", racing=False, notes="")
    base.update(over)
    return base


class Eligibility(unittest.TestCase):
    def setUp(self):
        self.p = parse(FULL)

    def test_eligible(self):
        e = check_eligibility(self.p, risk())
        self.assertEqual(e.outcome, "eligible")
        self.assertEqual(e.reasons, [])

    def test_declined_with_reason(self):
        e = check_eligibility(self.p, risk(rider_age=Decimal(15)))
        self.assertEqual(e.outcome, "declined")
        self.assertEqual(e.reasons, ["Rider must be at least 16"])

    def test_referred(self):
        e = check_eligibility(self.p, risk(bike_value=Decimal(12000)))
        self.assertEqual(e.outcome, "referred")

    def test_decline_beats_refer(self):
        e = check_eligibility(self.p, risk(bike_value=Decimal(12000), rider_age=Decimal(10)))
        self.assertEqual(e.outcome, "declined")
        self.assertEqual(len(e.reasons), 2)


class Covers(unittest.TestCase):
    def setUp(self):
        self.p = parse(FULL)

    def test_standard_covers_included_optional_not(self):
        states = {c.name: c for c in cover_states(self.p, risk(), set())}
        self.assertEqual(states["Theft"].status, "included")
        self.assertEqual(states["Theft"].limit, Decimal(2000))
        self.assertEqual(states["Accidental Damage"].status, "included")
        self.assertEqual(states["Racing"].status, "not selected")

    def test_excluded_with_reason(self):
        states = {c.name: c for c in cover_states(self.p, risk(security="bronze", bike_value=Decimal(3000)), set())}
        self.assertEqual(states["Theft"].status, "excluded")
        self.assertEqual(states["Theft"].reason, "Gold or silver lock required")

    def test_optional_selected_and_available(self):
        states = {c.name: c for c in cover_states(self.p, risk(racing=True), {"Racing"})}
        self.assertEqual(states["Racing"].status, "included")
        self.assertEqual(states["Racing"].limit, Decimal(5000))

    def test_optional_selected_but_unavailable(self):
        states = {c.name: c for c in cover_states(self.p, risk(racing=False), {"Racing"})}
        self.assertEqual(states["Racing"].status, "not available")
