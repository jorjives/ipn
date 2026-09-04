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


from ideclare.engine import rate
from tests.test_parser import RATING


class RatingEngine(unittest.TestCase):
    def setUp(self):
        self.p = parse(RATING)

    def test_full_breakdown(self):
        # base 70, age 30 -> x1.00, gold -> -10 = 60, no racing, discount 10% -> 54, no load, minimum 60 -> 60
        q = rate(self.p, risk(), set())
        self.assertEqual(q.net, Decimal("60.00"))
        self.assertEqual(q.lines, [("IPT", Decimal("7.20")), ("Admin fee", Decimal("10.00"))])
        self.assertEqual(q.total, Decimal("77.20"))

    def test_trail_records_each_step(self):
        q = rate(self.p, risk(rider_age=Decimal(20), security="silver", racing=True), {"Racing"})
        # base 70 x1.40 = 98, +0, +45 = 143, load 25% = 178.75
        self.assertEqual([(t.label, t.applied) for t in q.trail][:6], [
            ("base", "70.00"), ("Rider age", "x 1.40"), ("Security", "+ 0"),
            ("Racing cover", "+ 45"), ("load", "x 1.25"), ("minimum", "60"),
        ])
        self.assertEqual(q.net, Decimal("178.75"))
        self.assertEqual(q.total, Decimal("178.75") + Decimal("21.45") + 10)

    def test_rounding_is_half_up_at_the_end(self):
        p = parse(FULL + "rating\n  base 1.005\n  tax IPT 12%\n")
        q = rate(p, risk(), set())
        self.assertEqual(q.net, Decimal("1.01"))
        self.assertEqual(q.lines, [("IPT", Decimal("0.12"))])
        self.assertEqual(q.total, Decimal("1.13"))

    def test_no_rating_block_gives_zero(self):
        q = rate(parse(FULL), risk(), set())
        self.assertEqual(q.total, Decimal("0.00"))
