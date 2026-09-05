import unittest
from decimal import Decimal

from ideclare.parser import parse
from ideclare.engine import check_eligibility, context, cover_state, cover_states
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

    def test_rounding_is_half_up_and_tax_is_on_rounded_net(self):
        p = parse(FULL + "rating\n  base 112.455\n  tax IPT 12%\n")
        q = rate(p, risk(), set())
        self.assertEqual(q.net, Decimal("112.46"))
        self.assertEqual(q.lines, [("IPT", Decimal("13.50"))])  # 13.4952 on rounded net, not 13.4946
        self.assertEqual(q.total, Decimal("125.96"))

    def test_no_rating_block_gives_zero(self):
        q = rate(parse(FULL), risk(), set())
        self.assertEqual(q.total, Decimal("0.00"))


from datetime import date
from ideclare.engine import Policy, add_months
from tests.test_parser import LIFECYCLE


class Months(unittest.TestCase):
    def test_add_months_clamps_to_month_end(self):
        self.assertEqual(add_months(date(2026, 1, 31), 1), date(2026, 2, 28))
        self.assertEqual(add_months(date(2026, 3, 15), 12), date(2027, 3, 15))
        self.assertEqual(add_months(date(2026, 11, 30), 3), date(2027, 2, 28))


class PolicyLifecycle(unittest.TestCase):
    def setUp(self):
        self.p = parse(LIFECYCLE)
        # net 60 + IPT 7.20 + fee 10 = 77.20; refundable part 67.20
        self.policy = Policy(self.p, risk(), set())

    def test_status_progression(self):
        pol = self.policy
        self.assertEqual(pol.status(date(2026, 1, 1)), "quoted")
        pol.bind(date(2026, 3, 1))
        self.assertEqual(pol.status(date(2026, 2, 1)), "bound")
        self.assertEqual(pol.status(date(2026, 3, 1)), "live")
        self.assertEqual(pol.expiry, date(2027, 3, 1))
        self.assertEqual(pol.status(date(2027, 3, 1)), "expired")

    def test_lapse_when_unpaid(self):
        pol = self.policy
        pol.bind(date(2026, 3, 1), paid=False)
        self.assertEqual(pol.status(date(2026, 3, 20)), "live")
        self.assertEqual(pol.status(date(2026, 4, 1)), "lapsed")
        pol.pay(date(2026, 3, 25))
        self.assertEqual(pol.status(date(2026, 4, 1)), "live")

    def test_cooling_off_full_refund(self):
        pol = self.policy
        pol.bind(date(2026, 1, 1))
        self.assertEqual(pol.cancel(date(2026, 1, 10), "customer"), Decimal("77.20"))
        self.assertEqual(pol.status(date(2026, 1, 10)), "cancelled")
        self.assertEqual(pol.status(date(2026, 1, 5)), "live")

    def test_pro_rata_cancellation_less_fee(self):
        pol = self.policy
        pol.bind(date(2026, 1, 1))  # 365 day term
        # 100 days used, 265 remaining: 67.20 * 265/365 = 48.79 - 25 fee = 23.79
        self.assertEqual(pol.cancel(date(2026, 4, 11), "customer"), Decimal("23.79"))

    def test_insurer_cancellation_has_no_fee(self):
        pol = self.policy
        pol.bind(date(2026, 1, 1))
        self.assertEqual(pol.cancel(date(2026, 4, 11), "insurer"), Decimal("48.79"))

    def test_refund_never_negative(self):
        pol = self.policy
        pol.bind(date(2026, 1, 1))
        self.assertEqual(pol.cancel(date(2026, 12, 25), "customer"), Decimal("0.00"))

    def test_adjustment_charges_pro_rata_difference_plus_fee(self):
        pol = self.policy
        pol.bind(date(2026, 1, 1))
        # bike_value 2000 -> 4000: net 60 -> 140-10=130 x0.9=117; +IPT = 131.04 vs 67.20; diff 63.84 * 265/365 = 46.35 + fee 10
        self.assertEqual(pol.adjust(date(2026, 4, 11), {"bike_value": Decimal(4000)}), Decimal("56.35"))
        self.assertEqual(pol.inputs["bike_value"], Decimal(4000))
        self.assertEqual(pol.quote.total, Decimal("141.04"))

    def test_adjustment_downwards_returns_premium(self):
        pol = self.policy
        pol.bind(date(2026, 1, 1))
        pol.adjust(date(2026, 1, 1), {"bike_value": Decimal(4000)})
        # back to 2000: -63.84 * 265/365 = -46.35 + fee 10 = -36.35
        self.assertEqual(pol.adjust(date(2026, 4, 11), {"bike_value": Decimal(2000)}), Decimal("-36.35"))

    def test_adjustment_not_allowed(self):
        pol = Policy(parse(FULL + "lifecycle\n  adjustment: not allowed\n"), risk(), set())
        pol.bind(date(2026, 1, 1))
        with self.assertRaises(ValueError):
            pol.adjust(date(2026, 2, 1), {"bike_value": Decimal(1)})

    def test_renewal_offer(self):
        pol = self.policy
        pol.bind(date(2026, 1, 1))
        offer = pol.renew()
        self.assertEqual(offer.invite_date, date(2026, 12, 11))
        self.assertEqual(offer.premium, Decimal("77.20"))
        self.assertIsNone(offer.declined)

    def test_renewal_increase_is_capped(self):
        pol = self.policy
        pol.bind(date(2026, 1, 1))
        pol.inputs["bike_value"] = Decimal(4000)  # would reprice to 141.04
        offer = pol.renew()
        self.assertEqual(offer.premium, Decimal("92.64"))  # 77.20 x 1.2
        self.assertEqual(offer.uncapped, Decimal("141.04"))

    def test_renewal_declined(self):
        pol = self.policy
        pol.bind(date(2026, 1, 1))
        pol.inputs["rider_age"] = Decimal(85)
        self.assertEqual(pol.renew().declined, "Age limit")

    def test_accepting_renewal_starts_new_term(self):
        pol = self.policy
        pol.bind(date(2026, 1, 1))
        pol.accept_renewal()
        self.assertEqual(pol.inception, date(2027, 1, 1))
        self.assertEqual(pol.status(date(2027, 1, 1)), "live")
        self.assertEqual(pol.status(date(2026, 12, 31)), "renewed")


from tests.test_parser import CLAIMS


class ImposedTerms(unittest.TestCase):
    def setUp(self):
        src = CLAIMS.replace("  after 2 claims in term: renewal load x 1.25\n",
                             "  after 1 claim in term\n    cancellation by customer: no refund\n    adjustment: not allowed\n  after 2 claims in term: renewal load x 1.25\n")
        self.pol = Policy(parse(src), risk(), set())
        self.pol.bind(date(2026, 1, 1))

    def test_refund_and_adjustment_stop_after_a_paid_claim(self):
        self.assertGreater(self.pol.cancel(date(2026, 7, 1), "customer"), 0)
        self.pol.cancelled_on = None
        self.pol.claim("Theft", Decimal(1500), date(2026, 3, 1), date(2026, 3, 1), {"police_report", "crime_reference"})
        self.assertEqual(self.pol.cancel(date(2026, 7, 1), "customer"), Decimal(0))
        with self.assertRaises(ValueError):
            self.pol.adjust(date(2026, 7, 1), {"rider_age": Decimal(40)})

    def test_declined_claim_imposes_nothing(self):
        self.pol.claim("Theft", Decimal(1500), date(2026, 3, 1), date(2026, 3, 1), set())
        self.assertGreater(self.pol.cancel(date(2026, 7, 1), "customer"), 0)


class ClaimsEngine(unittest.TestCase):
    def setUp(self):
        self.pol = Policy(parse(CLAIMS), risk(), set())
        self.pol.bind(date(2026, 1, 1))

    def claim(self, cover="Theft", amount=1500, on=date(2026, 3, 1), reported=None, evidence=("police_report", "crime_reference")):
        return self.pol.claim(cover, Decimal(amount), on, reported or on, set(evidence))

    def test_paid_up_to_limit_less_percentage_excess_with_minimum(self):
        c = self.claim(amount=1500)
        self.assertEqual((c.status, c.amount), ("paid", Decimal("1350.00")))  # 10% excess = 150
        c = self.claim(amount=300)
        self.assertEqual(c.amount, Decimal("250.00"))  # 10% = 30 < minimum 50
        c = self.claim(amount=1900, cover="Accidental Damage", evidence=())
        self.assertEqual(c.amount, Decimal("1900.00"))  # no excess declared for claims on this cover

    def test_limit_applies_before_excess(self):
        self.pol.product.claims["Theft"].decline.pop()  # allow claimed > bike_value for this test
        c = self.claim(amount=5000)
        self.assertEqual(c.amount, Decimal("1500.00"))  # min(5000, 2000) - 10% of 5000

    def test_missing_evidence_declines(self):
        c = self.claim(evidence=("police_report",))
        self.assertEqual((c.status, c.reason), ("declined", "crime_reference is required"))

    def test_late_notification_declines(self):
        c = self.claim(on=date(2026, 3, 1), reported=date(2026, 4, 15))
        self.assertEqual(c.reason, "Late notification")

    def test_excluded_cover_declines(self):
        self.pol.inputs["security"] = "bronze"
        self.pol.inputs["bike_value"] = Decimal(3000)
        c = self.claim()
        self.assertEqual(c.reason, "Theft is excluded: Gold or silver lock required")

    def test_claim_outside_live_period_declines(self):
        c = self.claim(on=date(2025, 12, 1))
        self.assertEqual(c.reason, "policy was bound on 2025-12-01")

    def test_only_paid_claims_count_and_load_renewal(self):
        self.claim(evidence=())
        self.assertEqual(len(self.pol.claims), 0)
        self.claim(); self.claim()
        self.assertEqual(len(self.pol.claims), 2)
        offer = self.pol.renew()
        self.assertEqual(offer.declined, "Too many claims")
        self.assertEqual(offer.uncapped, Decimal("96.50"))  # 77.20 x 1.25
        self.assertEqual(offer.premium, Decimal("92.64"))  # capped at 20%


class CapAndCollar(unittest.TestCase):
    def test_maximum_caps_net_premium(self):
        p = parse(FULL + "rating\n  base 500\n  maximum 300\n  tax IPT 10%\n")
        q = rate(p, risk(), set())
        self.assertEqual((q.net, q.total), (Decimal("300.00"), Decimal("330.00")))
        self.assertEqual((q.trail[-1].label, q.trail[-1].applied), ("maximum", "300"))

    def test_renewal_decrease_is_collared(self):
        p = parse(LIFECYCLE.replace("increase capped at 20%", "increase capped at 20%\n    decrease collared at 10%"))
        pol = Policy(p, risk(), set())
        pol.bind(date(2026, 1, 1))  # 77.20
        pol.inputs["bike_value"] = Decimal(500)  # reprices to minimum 60 -> 77.20? no: net 60 floor -> same
        pol.product.rating[6].amount = ("num", Decimal(0))  # drop the minimum so the price really falls
        offer = pol.renew()
        self.assertLess(offer.uncapped, Decimal("69.48"))
        self.assertEqual(offer.premium, Decimal("69.48"))  # 77.20 x 0.90


DEPRECIATION = '''
product "Gadget"
  term 12 months
inputs
  item_value: money
  item_age: integer
cover Damage
  limit item_value
  excess 10% of claim
rating
  base 50
lifecycle
  cancellation by customer: no refund
  renewal
    index item_value by 5%
claims
  claim Damage
    pays claimed amount up to limit, less excess
    depreciation
      item_age < 1: x 1.00
      item_age < 3: x 0.80
      otherwise: x 0.50
'''


class DepreciationAndIndexation(unittest.TestCase):
    def setUp(self):
        self.p = parse(DEPRECIATION)
        self.pol = Policy(self.p, {"item_value": Decimal(1000), "item_age": Decimal(2)}, set())
        self.pol.bind(date(2026, 1, 1))

    def test_depreciation_rows_parse_like_a_factor(self):
        rows = self.p.claims["Damage"].depreciation
        self.assertEqual([(r.op, r.amount) for r in rows][1], ("x", ("num", Decimal("0.80"))))
        self.assertIsNone(rows[2].condition)

    def test_depreciation_applies_before_limit_and_excess(self):
        c = self.pol.claim("Damage", Decimal(500), date(2026, 2, 1), date(2026, 2, 1), set())
        self.assertEqual(c.amount, Decimal("350.00"))  # 500 x 0.80 = 400, less 10% of 500
        c = self.pol.claim("Damage", Decimal(2000), date(2026, 2, 1), date(2026, 2, 1), set())
        self.assertEqual(c.amount, Decimal("800.00"))  # 1600 capped at 1000, less 200

    def test_indexation_raises_the_input_at_renewal(self):
        self.assertEqual(self.p.lifecycle.renewal_index, [("item_value", "%", Decimal(5))])
        self.assertEqual(self.pol.renew().inputs["item_value"], Decimal("1050.00"))
        self.assertEqual(self.pol.inputs["item_value"], Decimal(1000))  # offer only
        self.pol.accept_renewal()
        self.assertEqual(self.pol.inputs["item_value"], Decimal("1050.00"))
        self.assertEqual(self.pol.renew().inputs["item_value"], Decimal("1102.50"))

    def test_index_unknown_input_is_error(self):
        from ideclare.parser import ParseError
        with self.assertRaises(ParseError):
            parse(DEPRECIATION.replace("index item_value", "index item_colour"))

    def test_index_by_an_absolute_amount_ages_an_integer_input(self):
        p = parse(DEPRECIATION.replace("index item_value by 5%", "index item_value by 5%\n    index item_age by 1"))
        pol = Policy(p, {"item_value": Decimal(1000), "item_age": Decimal(2)}, set())
        pol.bind(date(2026, 1, 1))
        self.assertEqual(pol.renew().inputs["item_age"], Decimal(3))


from tests.test_parser import ENRICHED, FLEET


def fleet(*bikes, rider_age=30):
    return {"rider_age": Decimal(rider_age), "bikes": [dict(value=Decimal(v), age=Decimal(a), security=s) for v, a, s in bikes]}


class CollectionEngine(unittest.TestCase):
    def setUp(self):
        self.p = parse(FLEET)

    def test_bounds_are_eligibility_declines(self):
        self.assertEqual(check_eligibility(self.p, fleet()).reasons, ["bikes: at least 1 required"])
        four = fleet(*[(100, 0, "gold")] * 4)
        self.assertEqual(check_eligibility(self.p, four).reasons, ["bikes: at most 3 allowed"])
        self.assertEqual(check_eligibility(self.p, fleet((100, 0, "gold"))).outcome, "eligible")

    def test_item_rules(self):
        self.assertEqual(check_eligibility(self.p, fleet((12000, 0, "gold"))).reasons, ["Too valuable"])
        self.assertEqual(check_eligibility(self.p, fleet((7000, 0, "gold"), (6000, 0, "gold"))).outcome, "referred")

    def test_per_item_rating_then_fleet_factor(self):
        q = rate(self.p, fleet((2000, 0, "gold"), (1000, 3, "silver")), set())
        # bike 1: 60 x 1.00 = 60; bike 2: 30 x 0.90 = 27; total 87 x 0.95 = 82.65
        self.assertEqual(q.net, Decimal("82.65"))
        self.assertEqual([(t.label, t.applied) for t in q.trail], [
            ("bike 1 base", "60.00"), ("bike 1 Bike age", "x 1.00"),
            ("bike 2 base", "30.00"), ("bike 2 Bike age", "x 0.90"),
            ("bikes", "87.00"), ("Fleet", "x 0.95"), ("minimum", "40")])

    def test_ordered_items_and_position(self):
        src = FLEET.replace("  for each bike\n", "  for each bike, ordered by value descending\n").replace("  factor \"Fleet\"\n", "    factor \"Position\"\n      position is 1: x 1.00\n      otherwise: x 0.50\n  factor \"Fleet\"\n")
        q = rate(parse(src), fleet((1000, 0, "gold"), (2000, 0, "gold")), set())
        # bike 2 is rated first at full rate (60), bike 1 second at half (15); total 75 x 0.95 = 71.25
        self.assertEqual(q.net, Decimal("71.25"))
        self.assertEqual([t.label for t in q.trail][:6], [
            "bike 2 base", "bike 2 Bike age", "bike 2 Position",
            "bike 1 base", "bike 1 Bike age", "bike 1 Position"])

    def test_calculated_field_orders_items(self):
        src = FLEET.replace("    security: choice of bronze, silver, gold\n",
                            "    security: choice of bronze, silver, gold\n    rank: calculated\n      base value\n      add 5000 when security is gold\n")
        src = src.replace("  for each bike\n", "  for each bike, ordered by rank descending\n").replace("  factor \"Fleet\"\n", "    factor \"Position\"\n      position is 1: x 1.00\n      otherwise: x 0.50\n  factor \"Fleet\"\n")
        q = rate(parse(src), fleet((2000, 0, "silver"), (1000, 0, "gold")), set())
        # bike 2 ranks 6000, bike 1 ranks 2000: bike 2 first at 30, bike 1 half of 60 = 30; 60 x 0.95 = 57
        self.assertEqual(q.net, Decimal("57.00"))
        self.assertEqual([t.label for t in q.trail][0], "bike 2 base")

    def test_cover_state_for_an_item(self):
        inputs = fleet((2000, 0, "gold"), (3000, 1, "bronze"))
        states = [cover_state(self.p, self.p.cover("Theft"), inputs, set(), item=b) for b in inputs["bikes"]]
        self.assertEqual((states[0].status, states[0].limit), ("included", Decimal(2000)))
        self.assertEqual((states[1].status, states[1].reason), ("excluded", "Better lock needed"))

    def test_claim_on_an_item(self):
        pol = Policy(self.p, fleet((2000, 0, "gold"), (3000, 1, "bronze")), set())
        pol.bind(date(2026, 1, 1))
        paid = pol.claim("Theft", Decimal(1500), date(2026, 2, 1), date(2026, 2, 1), set(), item=pol.inputs["bikes"][0])
        self.assertEqual(paid.amount, Decimal("1350.00"))
        declined = pol.claim("Theft", Decimal(1500), date(2026, 2, 1), date(2026, 2, 1), set(), item=pol.inputs["bikes"][1])
        self.assertEqual(declined.reason, "Theft is excluded: Better lock needed")

    def test_index_item_field_at_renewal(self):
        pol = Policy(self.p, fleet((2000, 0, "gold"), (1000, 3, "silver")), set())
        pol.bind(date(2026, 1, 1))
        offer = pol.renew()
        self.assertEqual([b["value"] for b in offer.inputs["bikes"]], [Decimal("2200.00"), Decimal("1100.00")])
        self.assertEqual(pol.inputs["bikes"][0]["value"], Decimal(2000))


class EnrichmentEngine(unittest.TestCase):
    def setUp(self):
        self.p = parse(ENRICHED)

    def test_unavailable_without_default_refers(self):
        e = check_eligibility(self.p, fleet((100, 0, "gold")))
        self.assertEqual((e.outcome, e.reasons), ("referred", ["Postcode not recognised"]))

    def test_provided_value_is_used(self):
        inputs = {**fleet((100, 0, "gold")), "theft_area": "high"}
        self.assertEqual(check_eligibility(self.p, inputs).outcome, "eligible")
        self.assertEqual(context(self.p, inputs, set())["theft_area"], "high")

    def test_default_fills_missing_item_field(self):
        inputs = {**fleet((100, 0, "gold")), "theft_area": "low"}
        ctx = context(self.p, inputs, set())
        self.assertEqual(ctx["bikes"][0]["category"], "other")
        inputs["bikes"][0]["category"] = "folding"
        self.assertEqual(context(self.p, inputs, set())["bikes"][0]["category"], "folding")

    def test_held_field_cannot_change_mid_term(self):
        inputs = {**fleet((100, 0, "gold")), "theft_area": "low"}
        inputs["bikes"][0]["category"] = "road"
        policy = Policy(self.p, inputs, set())
        policy.bind(date(2026, 1, 1))
        with self.assertRaises(ValueError):
            policy.adjust(date(2026, 3, 1), {"bikes": [{**inputs["bikes"][0], "category": "folding"}]})


class Terms(unittest.TestCase):
    def policy(self, term, inputs):
        src = f'product "X"\n  term {term}\ninputs\n  a: integer\n  years: integer\n  back: date\nrating\n  base 100\n'
        return Policy(parse(src), {"a": Decimal(1), "years": Decimal(3), "back": date(2026, 3, 15), **inputs}, set())

    def test_days(self):
        pol = self.policy("10 days", {})
        pol.bind(date(2026, 3, 1))
        self.assertEqual(pol.expiry, date(2026, 3, 11))

    def test_years_from_input(self):
        pol = self.policy("years years", {})
        pol.bind(date(2026, 3, 1))
        self.assertEqual(pol.expiry, date(2029, 3, 1))

    def test_until_date_input(self):
        pol = self.policy("until back", {})
        pol.bind(date(2026, 3, 1))
        self.assertEqual(pol.expiry, date(2026, 3, 15))
        self.assertEqual(pol.status(date(2026, 3, 15)), "expired")


class CalculatedInputs(unittest.TestCase):
    def test_context_fills_in_calculated_input(self):
        from tests.test_parser import CalculatedInputs as T
        ctx = context(parse(T.SRC), {"height_cm": Decimal(200), "weight_kg": Decimal(100)}, set())
        self.assertEqual(ctx["bmi"], Decimal(25))


class CoverWindows(unittest.TestCase):
    def setUp(self):
        from tests.test_parser import TRAVEL
        self.p = parse(TRAVEL + 'claims\n  claim Cancellation\n    pays claimed amount up to limit\n  claim Medical\n    pays claimed amount up to limit\n  claim "Vet fees"\n    pays claimed amount up to limit\n')
        self.pol = Policy(self.p, {"departure_date": date(2026, 6, 10), "return_date": date(2026, 6, 24)}, set())
        self.pol.bind(date(2026, 3, 1))

    def claim(self, cover, on):
        return self.pol.claim(cover, Decimal(100), on, on, set())

    def test_cancellation_before_departure_only(self):
        self.assertEqual(self.claim("Cancellation", date(2026, 5, 1)).status, "paid")
        r = self.claim("Cancellation", date(2026, 6, 12))
        self.assertEqual((r.status, r.reason), ("declined", "Cancellation is not in force on 2026-06-12"))

    def test_medical_from_departure_only(self):
        self.assertEqual(self.claim("Medical", date(2026, 5, 1)).status, "declined")
        self.assertEqual(self.claim("Medical", date(2026, 6, 10)).status, "paid")

    def test_waiting_period_runs_from_first_inception(self):
        r = self.claim("Vet fees", date(2026, 3, 10))
        self.assertEqual((r.status, r.reason), ("declined", "Vet fees is within the 14 day waiting period"))
        self.assertEqual(self.claim("Vet fees", date(2026, 3, 15)).status, "paid")


class AggregateLimit(unittest.TestCase):
    def setUp(self):
        self.p = parse('product "X"\ninputs\n  a: money\ncover Vet\n  limit 7000 per term\n  excess 100\nrating\n  base 100\nlifecycle\n  renewal\n    invite 21 days before expiry\nclaims\n  claim Vet\n    pays claimed amount, less excess, up to limit\n')
        self.pol = Policy(self.p, {"a": Decimal(1)}, set())
        self.pol.bind(date(2026, 1, 1))

    def claim(self, amount, on=date(2026, 3, 1)):
        return self.pol.claim("Vet", Decimal(amount), on, on, set())

    def test_each_claim_erodes_the_limit(self):
        self.assertEqual(self.claim(5000).amount, Decimal(4900))
        self.assertEqual(self.claim(5000).amount, Decimal(2100))  # only 2100 left
        self.assertEqual(self.pol.remaining("Vet"), Decimal(0))
        r = self.claim(500)
        self.assertEqual((r.status, r.reason), ("declined", "Vet limit for the term is used up"))

    def test_limit_restored_on_renewal(self):
        self.claim(7000)
        self.pol.accept_renewal()
        self.assertEqual(self.pol.remaining("Vet"), Decimal(7000))


class ClaimFacts(unittest.TestCase):
    def setUp(self):
        from tests.test_parser import LIFE
        self.p = parse(LIFE + 'rating\n  base 100\n')

    def policy(self, pet_age=3):
        pol = Policy(self.p, {"sum_assured": Decimal(100000), "term_years": Decimal(20), "pet_age": Decimal(pet_age)}, set())
        pol.bind(date(2026, 1, 1))
        return pol

    def test_fixed_benefit_pays_the_sum_assured(self):
        r = self.policy().claim("Death", Decimal(0), date(2027, 6, 1), date(2027, 6, 1), {"death_certificate"}, facts={"cause": "natural"})
        self.assertEqual((r.status, r.amount), ("paid", Decimal(100000)))

    def test_suicide_within_twelve_months_declined_after_not(self):
        pol = self.policy()
        r = pol.claim("Death", Decimal(0), date(2026, 12, 31), date(2026, 12, 31), {"death_certificate"}, facts={"cause": "suicide"})
        self.assertEqual((r.status, r.reason), ("declined", "Suicide in the first year"))
        r = pol.claim("Death", Decimal(0), date(2027, 1, 1), date(2027, 1, 1), {"death_certificate"}, facts={"cause": "suicide"})
        self.assertEqual(r.status, "paid")

    def test_missing_fact_is_required(self):
        r = self.policy().claim("Death", Decimal(0), date(2027, 6, 1), date(2027, 6, 1), {"death_certificate"})
        self.assertEqual((r.status, r.reason), ("declined", "cause is required"))

    def test_co_payment_after_excess_before_limit(self):
        # 1000 x 0.5 settlement = 500, less 100 excess = 400, less 20% = 320
        r = self.policy(pet_age=10).claim("Vet", Decimal(1000), date(2026, 3, 1), date(2026, 3, 1), set(), facts={"condition": "ear"})
        self.assertEqual(r.amount, Decimal(320))
        r = self.policy(pet_age=3).claim("Vet", Decimal(1000), date(2026, 3, 1), date(2026, 3, 1), set(), facts={"condition": "ear"})
        self.assertEqual(r.amount, Decimal(400))


class NonRenewable(unittest.TestCase):
    def test_offer_is_declined(self):
        p = parse('product "X"\n  term 20 years\ninputs\n  a: integer\nrating\n  base 100\nlifecycle\n  renewal: none\n')
        pol = Policy(p, {"a": Decimal(1)}, set())
        pol.bind(date(2026, 1, 1))
        self.assertEqual(pol.renew().declined, "The policy is not renewable")
        with self.assertRaises(ValueError):
            pol.accept_renewal()
