import unittest
from decimal import Decimal

from ipngine.parser import parse, with_defaults
from ipngine.engine import Underwriting, check_eligibility, check_inputs, context, cover_state, cover_states, instalments
from ipngine.scenarios import run_all
from tests.test_parser import FULL, occupations


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

    def test_rules_can_see_the_selected_covers(self):
        p = parse(FULL + 'eligibility\n  refer when Racing selected and rider_age > 60 because "Racing over 60"\n')
        self.assertEqual(check_eligibility(p, risk(rider_age=Decimal(65)), {"Racing"}).reasons, ["Racing over 60"])
        self.assertEqual(check_eligibility(p, risk(rider_age=Decimal(65))).outcome, "eligible")

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


from ipngine.engine import rate
from tests.test_parser import RATING


JP = '''
product "X"
  territory JP
inputs
  v: money
rating
  base v / 3
  tax CT 7%
lifecycle
  cooling off 0 days, full refund
  cancellation by customer: refund pro rata
  instalments 3 monthly, charge 5%
'''


class RatingEngine(unittest.TestCase):
    def setUp(self):
        self.p = parse(RATING)

    def test_currency_is_a_fact_of_the_territory(self):
        p = parse('product "X"\n  territory DE, CH\ninputs\n  v: money\nrating\n  base v\n')
        self.assertEqual(rate(p, {"v": Decimal(1), "territory": "CH"}, set()).currency, "CHF")
        self.assertEqual(rate(p, {"v": Decimal(1), "territory": "DE"}, set()).currency, "EUR")

    def test_rounding_unit_follows_the_currency(self):
        jp = parse(JP)
        q = rate(jp, {"v": Decimal(1000), "territory": "JP"}, set())
        self.assertEqual((str(q.net), str(q.lines[0][1]), str(q.total), q.currency), ("333", "23", "356", "JPY"))  # 333.33 and 23.31 to whole yen
        kw = parse(JP.replace("territory JP", "territory KW"))
        self.assertEqual(str(rate(kw, {"v": Decimal(10), "territory": "KW"}, set()).net), "3.333")

    def test_currency_line_overrides_the_territory(self):
        p = parse('product "X"\n  territory CH\n  currency EUR\ninputs\n  v: money\nrating\n  base v\n')
        self.assertEqual(rate(p, {"v": Decimal(1), "territory": "CH"}, set()).currency, "EUR")

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

    def test_commission_is_reported_on_the_net_and_never_added(self):
        p = parse(FULL + 'rating\n  base 112.455\n  commission "Broker" 15%\n  commission "Scheme" 2.5%\n  tax IPT 12%\n')
        q = rate(p, risk(), set())
        self.assertEqual(q.commission, [("Broker", Decimal("16.87")), ("Scheme", Decimal("2.81"))])
        self.assertEqual(q.lines, [("IPT", Decimal("13.50"))])
        self.assertEqual(q.total, Decimal("125.96"))

    def test_no_rating_block_gives_zero(self):
        q = rate(parse(FULL), risk(), set())
        self.assertEqual(q.total, Decimal("0.00"))


from datetime import date
from ipngine.engine import Policy, add_months
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

    def test_cooling_off_from_a_table(self):
        table = 'table "Cooling" keyed on security\n  security, days\n  gold, 30\n  *, 14\n'
        src = LIFECYCLE.replace("lifecycle\n", table + "lifecycle\n").replace("cooling off 14 days", 'cooling off days from "Cooling" days')
        pol = Policy(parse(src), risk(), set())
        pol.bind(date(2026, 1, 1))
        self.assertEqual(pol.cancel(date(2026, 1, 25), "customer"), Decimal("77.20"))  # gold: 30 days

    def test_refunds_and_instalments_in_whole_yen(self):
        pol = Policy(parse(JP), {"v": Decimal(1000), "territory": "JP"}, set())
        pol.bind(date(2026, 1, 1))
        # premium 356; charge 17.8 -> 18; 374 over three: 124.67 -> 125, the first takes the difference
        self.assertEqual(instalments(pol.premium, 3, Decimal("0.05"), pol.quantum), (Decimal(18), [Decimal(124), Decimal(125), Decimal(125)]))
        # 183 of 365 days remaining: 356 * 183 / 365 = 178.49 -> 178
        self.assertEqual(str(pol.cancel(date(2026, 7, 2), "customer")), "178")

    def test_pro_rata_cancellation_less_fee(self):
        pol = self.policy
        pol.bind(date(2026, 1, 1))  # 365 day term
        # 100 days used, 265 remaining: 67.20 * 265/365 = 48.79 - 25 fee = 23.79
        self.assertEqual(pol.cancel(date(2026, 4, 11), "customer"), Decimal("23.79"))

    def test_short_rate_refund_from_a_table(self):
        table = 'table "Short rate" keyed on months in force\n  months_in_force, proportion\n  0-2, 75%\n  3-5, 50%\n  6+, 0%\n'
        src = LIFECYCLE.replace("lifecycle\n", table + "lifecycle\n")
        src = src.replace("  cancellation by customer: refund pro rata, fee 25\n", '  cancellation by customer: refund proportion from "Short rate", fee 25\n')
        pol = Policy(parse(src), risk(), set())
        pol.bind(date(2026, 1, 1))
        # four full months in force: half of the 67.20 earning, less the 25 fee
        self.assertEqual(pol.cancel(date(2026, 5, 15), "customer"), Decimal("8.60"))
        pol.cancelled_on = None
        self.assertEqual(pol.cancel(date(2026, 7, 1), "customer"), Decimal(0))

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

    def test_a_capped_renewal_is_what_the_customer_pays_and_what_is_refunded(self):
        pol = self.policy
        pol.bind(date(2026, 1, 1))
        pol.inputs["bike_value"] = Decimal(4000)
        pol.accept_renewal()
        self.assertEqual(pol.premium, Decimal("92.64"))  # capped, not the 141.04 re-rated price
        # earning part is the capped total less the 10 fee; 92.64 - 10 = 82.64 over the unused 300 of 365 days
        self.assertEqual(pol.cancel(date(2027, 3, 7), "insurer"), Decimal("67.92"))

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

    def test_terms_are_not_imposed_when_the_unless_condition_holds(self):
        src = CLAIMS.replace("  after 2 claims in term: renewal load x 1.25\n",
                             "  after 1 claim in term unless Racing selected\n    adjustment: not allowed\n  after 2 claims in term: renewal load x 1.25 unless Racing selected\n")
        pol = Policy(parse(src), risk(racing=True), {"Racing"})
        pol.bind(date(2026, 1, 1))
        for _ in range(2):
            pol.claim("Theft", Decimal(1500), date(2026, 3, 1), date(2026, 3, 1), {"police_report", "crime_reference"})
        pol.adjust(date(2026, 7, 1), {"rider_age": Decimal(40)})  # still allowed
        self.assertEqual(pol.claims_loading(), Decimal(1))

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

    def test_percentage_excess_is_capped_at_its_maximum(self):
        self.pol.product.cover("Theft").excess.maximum = ("num", Decimal(100))
        self.assertEqual(self.claim(amount=1500).amount, Decimal("1400.00"))  # 10% = 150, capped at 100

    def test_a_fixed_benefit_claim_need_not_say_an_amount(self):
        src = CLAIMS.replace("    pays claimed amount up to limit\n", "    pays 500\n")
        src += 'scenario "fixed"\n  given bike_value 2000, rider_age 30, security gold, racing no\n  when bound on 2026-01-01\n  when claim "Accidental Damage" on 2026-03-01\n  expect payout 500.00\n'
        self.assertEqual(run_all(parse(src))[-1].failures, [])

    def test_claim_within_the_excess_is_declined_and_does_not_count(self):
        c = self.claim(amount=40)  # the minimum excess is 50
        self.assertEqual((c.status, c.reason), ("declined", "nothing is payable after the excess"))
        self.assertEqual(self.pol.claims_in_term, 0)

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
        # the net is loaded, tax follows it and the fee is untouched: 60 x 1.25 = 75, IPT 9, fee 10
        self.assertEqual(offer.uncapped, Decimal("94.00"))
        self.assertEqual(offer.premium, Decimal("92.64"))  # capped at 20%
        self.assertEqual(rate(self.pol.product, self.pol.inputs, set(), loading=Decimal("1.25")).trail[-1].applied, "x 1.25")


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
        self.assertEqual(self.p.lifecycle.renewal_index, [("item_value", "%", ("num", Decimal(5)), None, None)])
        self.assertEqual(self.pol.renew().inputs["item_value"], Decimal("1050.00"))
        self.assertEqual(self.pol.inputs["item_value"], Decimal(1000))  # offer only
        self.pol.accept_renewal()
        self.assertEqual(self.pol.inputs["item_value"], Decimal("1050.00"))
        self.assertEqual(self.pol.renew().inputs["item_value"], Decimal("1102.50"))

    def test_index_by_an_expression_rolls_claims_history_forward(self):
        p = parse(DEPRECIATION.replace("    index item_value by 5%\n", "    index item_value by 5%\n    index item_age by claims in term\n"))
        pol = Policy(p, {"item_value": Decimal(1000), "item_age": Decimal(2)}, set())
        pol.bind(date(2026, 1, 1))
        self.assertEqual(pol.renew().inputs["item_age"], Decimal(2))
        pol.claim("Damage", Decimal(500), date(2026, 2, 1), date(2026, 2, 1), set())
        self.assertEqual(pol.renew().inputs["item_age"], Decimal(3))

    def test_index_unknown_input_is_error(self):
        from ipngine.parser import ParseError
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
            ("bike 1 base", "60.00"), ("bike 1 Bike age", "x 1.00"), ("bike 1", "net"),
            ("bike 2 base", "30.00"), ("bike 2 Bike age", "x 0.90"), ("bike 2", "net"),
            ("bikes", "87.00"), ("Fleet", "x 0.95"), ("minimum", "40")])

    def test_ordered_items_and_position(self):
        src = FLEET.replace("  for each bike\n", "  for each bike, ordered by value descending\n").replace("  factor \"Fleet\"\n", "    factor \"Position\"\n      position is 1: x 1.00\n      otherwise: x 0.50\n  factor \"Fleet\"\n")
        q = rate(parse(src), fleet((1000, 0, "gold"), (2000, 0, "gold")), set())
        # bike 2 is rated first at full rate (60), bike 1 second at half (15); total 75 x 0.95 = 71.25
        self.assertEqual(q.net, Decimal("71.25"))
        self.assertEqual([t.label for t in q.trail][:8], [
            "bike 2 base", "bike 2 Bike age", "bike 2 Position", "bike 2",
            "bike 1 base", "bike 1 Bike age", "bike 1 Position", "bike 1"])

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

    def test_claim_on_a_per_item_cover_must_name_the_item(self):
        pol = Policy(self.p, fleet((2000, 0, "gold")), set())
        pol.bind(date(2026, 1, 1))
        c = pol.claim("Theft", Decimal(1500), date(2026, 2, 1), date(2026, 2, 1), set())
        self.assertEqual((c.status, c.reason), ("declined", "Theft is per bike; say which bike the claim is on"))

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


class AggregateExcess(unittest.TestCase):
    def setUp(self):
        from tests.test_parser import AGGREGATE_EXCESS
        self.pol = Policy(parse(AGGREGATE_EXCESS), {"a": Decimal(1)}, set())
        self.pol.bind(date(2026, 1, 1))

    def claim(self, amount):
        on = date(2026, 3, 1)
        return self.pol.claim("Fleet", Decimal(amount), on, on, set())

    def test_the_insured_bears_the_first_1000_across_the_term(self):
        r = self.claim(600)
        self.assertEqual((r.status, r.reason), ("declined", "nothing is payable after the excess"))
        self.assertEqual(self.pol.excess_remaining("Fleet"), Decimal(400))
        self.assertEqual(self.pol.claims_in_term, 0)
        self.assertEqual(self.claim(900).amount, Decimal(500))
        self.assertEqual(self.pol.excess_remaining("Fleet"), Decimal(0))
        self.assertEqual(self.claim(700).amount, Decimal(700))
        self.assertEqual(self.pol.claims_in_term, 2)

    def test_restored_at_renewal(self):
        self.claim(5000)
        self.pol.product.lifecycle.renewal_invite_days = 21
        self.pol.accept_renewal()
        self.assertEqual(self.pol.excess_remaining("Fleet"), Decimal(1000))


class AggregatePerCondition(unittest.TestCase):
    def setUp(self):
        from tests.test_parser import PER_CONDITION
        self.pol = Policy(parse(PER_CONDITION), {"a": Decimal(1)}, set())
        self.pol.bind(date(2026, 1, 1))

    def claim(self, amount, condition):
        on = date(2026, 3, 1)
        return self.pol.claim("Vet", Decimal(amount), on, on, set(), facts={"condition": condition})

    def test_each_condition_has_its_own_limit(self):
        self.assertEqual(self.claim(5000, "knee").amount, Decimal(4900))
        self.assertEqual(self.claim(5000, "knee").amount, Decimal(2100))
        self.assertEqual(self.claim(5000, "ear").amount, Decimal(4900))
        self.assertEqual(self.pol.remaining("Vet", facts={"condition": "knee"}), Decimal(0))
        self.assertEqual(self.pol.remaining("Vet", facts={"condition": "ear"}), Decimal(2100))
        r = self.claim(500, "knee")
        self.assertEqual((r.status, r.reason), ("declined", "Vet limit for the term is used up for condition knee"))


class AggregatePerItem(unittest.TestCase):
    def setUp(self):
        from tests.test_parser import PER_TRAVELLER
        self.pol = Policy(parse(PER_TRAVELLER), {"travellers": [{"age": Decimal(40)}, {"age": Decimal(40)}]}, set())
        self.pol.bind(date(2026, 1, 1))

    def claim(self, amount, n):
        on = date(2026, 3, 1)
        return self.pol.claim("Baggage", Decimal(amount), on, on, set(), item=self.pol.inputs["travellers"][n - 1])

    def test_identical_travellers_still_have_their_own_limits(self):
        self.assertEqual(self.claim(1000, 1).amount, Decimal(1000))
        self.assertEqual(self.claim(1000, 1).amount, Decimal(500))
        self.assertEqual(self.claim(1000, 2).amount, Decimal(1000))
        self.assertEqual(self.pol.remaining("Baggage", self.pol.inputs["travellers"][1]), Decimal(500))
        r = self.claim(100, 1)
        self.assertEqual((r.status, r.reason), ("declined", "Baggage limit for the term is used up for traveller 1"))


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


class MotorFeatures(unittest.TestCase):
    def setUp(self):
        from tests.test_parser import MOTOR
        self.p = parse(MOTOR + 'rating\n  base 500\n  factor "NCD"\n    ncd_years >= 5: x 0.40\n    ncd_years >= 3: x 0.60\n    otherwise: x 1.00\n')
        self.pol = Policy(self.p, {"vehicle_value": Decimal(10000), "ncd_years": Decimal(5), "voluntary_excess": Decimal(100)}, set())
        self.pol.bind(date(2026, 1, 1))

    def ad(self, age, fault, amount=3000, on=date(2026, 3, 1)):
        return self.pol.claim("Accidental Damage", Decimal(amount), on, on, set(), facts={"driver_age": Decimal(age), "fault": fault})

    def test_excess_depends_on_the_driver(self):
        self.assertEqual(self.ad(19, True).amount, Decimal(2350))
        self.assertEqual(self.ad(40, True).amount, Decimal(2650))

    def test_only_fault_claims_count(self):
        self.ad(40, False)
        self.pol.claim("Windscreen", Decimal(300), date(2026, 3, 1), date(2026, 3, 1), set())
        self.assertEqual(self.pol.claims_in_term, 0)
        self.assertEqual(self.pol.renew().inputs["ncd_years"], Decimal(6))
        self.ad(40, True)
        self.assertEqual(self.pol.claims_in_term, 1)

    def test_fault_claim_steps_back_the_discount_instead_of_adding_a_year(self):
        self.ad(40, True)
        offer = self.pol.renew()
        self.assertEqual(offer.inputs["ncd_years"], Decimal(3))
        self.assertEqual(offer.premium, Decimal(300))

    def test_index_bounds(self):
        self.pol.inputs["ncd_years"] = Decimal(9)
        self.assertEqual(self.pol.renew().inputs["ncd_years"], Decimal(9))
        self.pol.inputs["ncd_years"] = Decimal(1)
        self.ad(40, True)
        self.assertEqual(self.pol.renew().inputs["ncd_years"], Decimal(0))


class UnavailableEnrichmentInRules(unittest.TestCase):
    def test_rule_on_a_missing_provided_field_is_skipped(self):
        p = parse('product "X"\ninputs\n  reg: text\nenrichment "V" from reg\n  provides\n    group: integer\n  when unavailable: refer because "Unknown vehicle"\neligibility\n  refer when group > 45 because "Performance"\n')
        e = check_eligibility(p, {"reg": "ZZ"})
        self.assertEqual((e.outcome, e.reasons), ("referred", ["Unknown vehicle"]))


TABLED = '''
product "Fleet"
  currency GBP

inputs
  area: integer
  vans: collection of van
    value: money
    driver_age: integer

table "Rates" keyed on driver_age, area
  driver_age, area, rate
  17-24, 1-2, 1.50
  17-24, 3+, 2.00
  25+, *, 1.00

table "Excess" keyed on area
  area, theft
  1-2, 150
  3+, 300

cover Theft
  limit value
  excess theft from "Excess"

rating
  for each van
    base 5% of value
    factor "Age and area" x rate from "Rates"
  factor "Fleet" - 10 when count of vans >= 2
'''


class TableEngine(unittest.TestCase):
    def setUp(self):
        self.p = parse(TABLED)

    def test_lookup_per_item_and_single_row_factor(self):
        from ipngine.engine import rate
        q = rate(self.p, {"area": Decimal(3), "vans": [{"value": Decimal(1000), "driver_age": Decimal(19)}, {"value": Decimal(2000), "driver_age": Decimal(40)}]}, set())
        self.assertEqual(q.net, Decimal("190.00"))  # 50 x 2.00 + 100 x 1.00 - 10
        self.assertEqual([(t.label, t.applied) for t in q.trail if t.label.endswith("Age and area")], [("van 1 Age and area", "x 2.00"), ("van 2 Age and area", "x 1.00")])
        self.assertEqual(q.trail[-1].applied, "- 10")

    def test_lookup_in_an_excess(self):
        from ipngine.engine import excess_amount
        ctx = context(self.p, {"area": Decimal(1), "vans": []}, set())
        self.assertEqual(excess_amount(self.p.cover("Theft").excess, ctx), Decimal(150))

    def test_no_row_is_an_error_not_a_default(self):
        from ipngine.engine import rate
        from ipngine.tables import TableError
        with self.assertRaisesRegex(TableError, "no row in Rates for driver_age 16, area 1"):
            rate(self.p, {"area": Decimal(1), "vans": [{"value": Decimal(1000), "driver_age": Decimal(16)}]}, set())


class Instalments(unittest.TestCase):
    def test_charge_then_equal_parts_with_the_first_absorbing_the_rounding(self):
        # 98.70 + 8% (7.90) = 106.60; 106.60 / 12 = 8.883.. so eleven of 8.88 and a first of 8.92
        charge, parts = instalments(Decimal("98.70"), 12, Decimal("0.08"), Decimal("0.01"))
        self.assertEqual(charge, Decimal("7.90"))
        self.assertEqual(parts, [Decimal("8.92")] + [Decimal("8.88")] * 11)
        self.assertEqual(sum(parts), Decimal("106.60"))

    def test_no_charge_splits_the_premium_exactly(self):
        self.assertEqual(instalments(Decimal("100.00"), 4, Decimal(0), Decimal("0.01")), (Decimal("0.00"), [Decimal("25.00")] * 4))


class UnderwriterTerms(unittest.TestCase):
    def setUp(self):
        from tests.test_parser import REFERRED
        self.product = parse(REFERRED)

    def policy(self, a=100, risky=True):
        return Policy(self.product, {"a": Decimal(a), "risky": risky}, set())

    def test_a_referred_risk_cannot_be_bound_until_accepted(self):
        pol = self.policy()
        with self.assertRaises(ValueError) as e:
            pol.bind(date(2026, 1, 1))
        self.assertEqual(str(e.exception), "referred: Needs an underwriter; the underwriter must accept it first")
        self.assertIsNone(pol.inception)

    def test_a_declined_risk_cannot_be_bound_at_all(self):
        with self.assertRaises(ValueError) as e:
            self.policy(a=5000, risky=False).bind(date(2026, 1, 1))
        self.assertEqual(str(e.exception), "declined: Too big")

    def test_the_underwriter_may_decline(self):
        pol = self.policy()
        pol.decline_by_underwriter()
        with self.assertRaises(ValueError) as e:
            pol.bind(date(2026, 1, 1))
        self.assertEqual(str(e.exception), "declined by the underwriter")

    def test_accepted_terms_load_the_net_and_change_the_cover(self):
        pol = self.policy(a=1000)
        pol.accept(Underwriting(load=Decimal("0.20"), excess={"Main": Decimal(200)}, excluded={"Extra"}))
        pol.bind(date(2026, 1, 1))
        self.assertEqual(pol.quote.net, Decimal("1200.00"))
        self.assertEqual([t.label for t in pol.quote.trail][-1], "Underwriter load")
        self.assertEqual(pol.premium, Decimal("1344.00"))
        on = date(2026, 3, 1)
        self.assertEqual(pol.claim("Main", Decimal(500), on, on, set()).amount, Decimal(300))
        r = pol.claim("Extra", Decimal(50), on, on, set())
        self.assertEqual((r.status, r.reason), ("declined", "Extra is excluded: underwriter terms"))
        self.assertEqual((pol.cover_state("Extra").status, pol.cover_state("Extra").reason), ("excluded", "underwriter terms"))

    def test_an_eligible_risk_binds_without_any_underwriting(self):
        pol = self.policy(risky=False)
        pol.bind(date(2026, 1, 1))
        self.assertEqual(pol.premium, Decimal("112.00"))


class BenefitOverTime(unittest.TestCase):
    def setUp(self):
        from tests.test_parser import BENEFIT
        self.pol = Policy(parse(BENEFIT), {"monthly_benefit": Decimal(1500), "deferred_weeks": Decimal(8)}, set())
        self.pol.bind(date(2026, 1, 1))

    def claim(self, on, weeks):
        return self.pol.claim("Incapacity", Decimal(0), on, on, set(), facts={"weeks_off_work": Decimal(weeks)})

    def test_a_month_of_benefit_is_paid_at_the_end_of_each_month_after_the_deferred_period(self):
        r = self.claim(date(2026, 3, 1), 20)  # 12 weeks of benefit: 3 months from 26 April
        self.assertEqual(r.amount, Decimal(4500))
        self.assertEqual(r.payments, [(date(2026, 5, 26), Decimal(1500)), (date(2026, 6, 26), Decimal(1500)), (date(2026, 7, 26), Decimal(1500))])

    def test_a_part_month_is_paid_last_and_the_limit_cuts_the_tail(self):
        r = self.claim(date(2026, 1, 1), 62)  # 54 weeks = 13.5 months, capped at the 18,000 limit: 12 months
        self.assertEqual(r.amount, Decimal(18000))
        self.assertEqual(len(r.payments), 12)
        r = Policy(self.pol.product, self.pol.inputs, set())
        r.bind(date(2026, 1, 1))
        c = r.claim("Incapacity", Decimal(0), date(2026, 1, 1), date(2026, 1, 1), set(), facts={"weeks_off_work": Decimal(18)})  # 10 weeks = 2.5 months
        self.assertEqual([a for _, a in c.payments], [Decimal(1500), Decimal(1500), Decimal(750)])

    def test_payments_run_past_expiry_and_survive_renewal(self):
        self.claim(date(2026, 11, 1), 28)  # 20 weeks of benefit from 27 December: five months into 2027
        self.assertEqual(self.pol.paid_by(date(2026, 12, 31)), Decimal(0))
        self.assertEqual(self.pol.paid_by(date(2027, 2, 1)), Decimal(1500))
        self.pol.accept_renewal()
        self.assertEqual(self.pol.paid_by(date(2027, 6, 1)), Decimal(7500))
        self.assertEqual(self.pol.remaining("Incapacity"), Decimal(18000))  # the new term's limit is untouched
        self.assertEqual(self.pol.claims_in_term, 0)


class SubLimits(unittest.TestCase):
    def setUp(self):
        from tests.test_parser import SUBLIMIT
        self.pol = Policy(parse(SUBLIMIT), {"travellers": [{"age": Decimal(40)}]}, set())
        self.pol.bind(date(2026, 1, 1))

    def claim(self, amount, kind):
        on = date(2026, 3, 1)
        return self.pol.claim("Baggage", Decimal(amount), on, on, set(), item=self.pol.inputs["travellers"][0], facts={"kind": kind})

    def test_a_conditional_cap_applies_only_when_its_condition_holds(self):
        self.assertEqual(self.claim(900, "valuables").amount, Decimal(350))  # capped at 400, less the 50 excess
        self.assertEqual(self.claim(900, "other").amount, Decimal(850))
        self.assertEqual(self.claim(300, "cash").amount, Decimal(150))

    def test_a_capped_claim_still_erodes_the_aggregate_it_sits_within(self):
        self.claim(900, "valuables")
        self.claim(900, "other")
        self.assertEqual(self.pol.remaining("Baggage", self.pol.inputs["travellers"][0]), Decimal(300))  # 1500 - 350 - 850
        self.assertEqual(self.claim(900, "other").amount, Decimal(250))


class Reinstatement(unittest.TestCase):
    def setUp(self):
        from tests.test_parser import REINSTATE
        self.pol = Policy(parse(REINSTATE), {"a": Decimal(1)}, set())
        self.pol.bind(date(2026, 1, 1))

    def claim(self, amount, on=date(2026, 3, 1)):
        return self.pol.claim("PI", Decimal(amount), on, on, set())

    def test_reinstating_restores_the_limit_for_a_pro_rata_share_of_the_premium(self):
        self.claim(200000)
        self.assertEqual(self.pol.remaining("PI"), Decimal(50000))
        # 100% of the 1,120 earning premium for the 265 days left of 365
        self.assertEqual(self.pol.reinstate("PI", date(2026, 4, 11)), Decimal("813.15"))
        self.assertEqual(self.pol.remaining("PI"), Decimal(250000))
        self.assertEqual(self.claim(240000, date(2026, 6, 1)).amount, Decimal(240000))

    def test_once_a_term_and_only_when_the_product_allows_it(self):
        self.claim(200000)
        self.pol.reinstate("PI", date(2026, 4, 11))
        with self.assertRaises(ValueError) as e:
            self.pol.reinstate("PI", date(2026, 5, 1))
        self.assertEqual(str(e.exception), "PI has already been reinstated this term")
        self.pol.accept_renewal()
        self.assertEqual(self.pol.remaining("PI"), Decimal(250000))
        self.pol.product.cover("PI").reinstatement = None
        with self.assertRaises(ValueError) as e:
            self.pol.reinstate("PI", date(2027, 2, 1))
        self.assertEqual(str(e.exception), "PI has no reinstatement")


from datetime import date
from ipngine.engine import Policy
from ipngine.versions import History


def versioned(published: str, base: str, extra_inputs: str = "") -> str:
    return f'''product "Bike"
  published {published}
  term 12 months

inputs
  bike_value: money
  security: choice of bronze, silver, gold
{extra_inputs}
rating
  base {base}

lifecycle
  adjustment: reprice, charge pro rata difference
  renewal
    invite 21 days before expiry
    increase capped at 20%
'''


class Versions(unittest.TestCase):
    def setUp(self):
        self.h = History([parse(versioned("2026-01-01", "100")), parse(versioned("2026-07-01", "150", "  racing: yes/no, default no\n"))])
        self.v1, self.v2 = self.h.versions

    def policy(self):
        return Policy(self.v2, {"bike_value": Decimal(2000), "security": "gold"}, set(), history=self.h)

    def test_binding_places_the_policy_on_the_version_live_that_day(self):
        p = self.policy()
        p.bind(date(2026, 3, 1))
        self.assertIs(p.product, self.v1)
        self.assertEqual(p.version, date(2026, 1, 1))
        self.assertEqual(p.premium, Decimal(100))

    def test_binding_before_any_version_is_refused(self):
        with self.assertRaises(ValueError) as cm:
            self.policy().bind(date(2025, 1, 1))
        self.assertEqual(str(cm.exception), "no version of Bike was on sale on 2025-01-01")

    def test_renewal_moves_to_the_version_live_at_the_new_term_and_is_capped(self):
        p = self.policy()
        p.bind(date(2026, 3, 1))
        offer = p.renew()
        self.assertIs(offer.version, self.v2)
        self.assertEqual(offer.uncapped, Decimal(150))
        self.assertEqual(offer.premium, Decimal(120))
        self.assertEqual(offer.inputs, {"bike_value": Decimal(2000), "security": "gold", "racing": False})
        p.accept_renewal()
        self.assertIs(p.product, self.v2)
        self.assertEqual(p.inputs["racing"], False)
        self.assertEqual(p.premium, Decimal(120))

    def test_without_a_history_nothing_changes(self):
        p = Policy(self.v1, {"bike_value": Decimal(2000), "security": "gold"}, set())
        p.bind(date(2026, 9, 1))
        self.assertIs(p.renew().version, self.v1)
        self.assertEqual(p.version, date(2026, 1, 1))


class RenewalNeeds(unittest.TestCase):
    def setUp(self):
        v1 = versioned("2026-01-01", "100")
        v2 = versioned("2026-07-01", "150", "  lock_rating: choice of low, high\n").replace("  security: choice of bronze, silver, gold\n", "") + "upgrading\n  lock_rating: high when security is gold, otherwise ask\n"
        self.h = History([parse(v1), parse(v2)])
        self.v1, self.v2 = self.h.versions

    def policy(self, security):
        p = Policy(self.v2, {"bike_value": Decimal(2000), "security": security}, set(), history=self.h)
        p.bind(date(2026, 3, 1))
        return p

    def test_an_offer_that_needs_answers_is_neither_priced_nor_declined(self):
        offer = self.policy("bronze").renew()
        self.assertEqual(offer.needs, ["lock_rating"])
        self.assertIsNone(offer.declined)
        self.assertNotIn("lock_rating", offer.inputs)

    def test_accepting_without_the_answers_is_refused(self):
        p = self.policy("bronze")
        with self.assertRaises(ValueError) as cm:
            p.accept_renewal()
        self.assertEqual(str(cm.exception), "renewal needs lock_rating")
        self.assertIs(p.product, self.v1)

    def test_answers_fill_the_needs(self):
        p = self.policy("bronze")
        offer = p.renew({"lock_rating": "low"})
        self.assertEqual((offer.needs, offer.premium), ([], Decimal(120)))
        p.accept_renewal({"lock_rating": "low"})
        self.assertEqual((p.product, p.inputs["lock_rating"]), (self.v2, "low"))

    def test_an_answer_nobody_asked_for_is_refused(self):
        with self.assertRaises(ValueError) as cm:
            self.policy("gold").renew({"bike_value": Decimal(1)})
        self.assertEqual(str(cm.exception), "bike_value was not asked at renewal")

    def test_a_policy_that_needs_nothing_renews_as_before(self):
        p = self.policy("gold")
        self.assertEqual(p.renew().needs, [])
        p.accept_renewal()
        self.assertEqual(p.inputs["lock_rating"], "high")


class AdjustmentAcrossVersions(unittest.TestCase):
    def history(self, upgrades: bool):
        v1 = versioned("2026-01-01", "100")
        v2 = versioned("2026-07-01", "150", "  lock_rating: choice of low, high\n").replace("  security: choice of bronze, silver, gold\n", "") + "upgrading\n  lock_rating: high when security is gold, otherwise ask\n"
        if upgrades:
            v1, v2 = (v.replace("adjustment: reprice,", "adjustment: reprice on the current version,") for v in (v1, v2))
        return History([parse(v1), parse(v2)])

    def policy(self, h, security="gold"):
        p = Policy(h.versions[1], {"bike_value": Decimal(2000), "security": security}, set(), history=h)
        p.bind(date(2026, 3, 1))
        return p

    def test_by_default_an_adjustment_stays_on_the_policy_version(self):
        h = self.history(upgrades=False)
        p = self.policy(h)
        p.adjust(date(2026, 9, 1), {"bike_value": Decimal(3000)})
        self.assertIs(p.product, h.versions[0])
        self.assertEqual(p.premium, Decimal(100))

    def test_on_the_current_version_the_policy_is_upgraded_first(self):
        h = self.history(upgrades=True)
        p = self.policy(h)
        charge = p.adjust(date(2026, 9, 1), {"bike_value": Decimal(3000)})
        self.assertIs(p.product, h.versions[1])
        self.assertEqual(p.inputs, {"bike_value": Decimal(3000), "lock_rating": "high"})
        self.assertEqual(p.premium, Decimal(150))
        self.assertEqual(charge, (Decimal(50) * Decimal(181) / Decimal(365)).quantize(Decimal("0.01")))

    def test_an_unanswered_ask_refuses_the_adjustment(self):
        h = self.history(upgrades=True)
        p = self.policy(h, "bronze")
        with self.assertRaises(ValueError) as cm:
            p.adjust(date(2026, 9, 1), {"bike_value": Decimal(3000)})
        self.assertEqual(str(cm.exception), "adjustment needs lock_rating")
        self.assertIs(p.product, h.versions[0])
        self.assertEqual(p.inputs["bike_value"], Decimal(2000))

    def test_the_changes_answer_the_ask(self):
        h = self.history(upgrades=True)
        p = self.policy(h, "bronze")
        p.adjust(date(2026, 9, 1), {"lock_rating": "low"})
        self.assertEqual((p.product, p.inputs["lock_rating"]), (h.versions[1], "low"))

    def test_before_a_newer_version_exists_nothing_is_upgraded(self):
        h = self.history(upgrades=True)
        p = self.policy(h)
        p.adjust(date(2026, 5, 1), {"bike_value": Decimal(3000)})
        self.assertIs(p.product, h.versions[0])


DATED = '''product "Bike"
  term 12 months
inputs
  bike_value: money
  racing: yes/no
cover Theft
  limit bike_value
  excess 50
  from 2027-03-01 excess 100
  until 2027-03-01 excludes when racing is yes because "Racing was excluded until March 2027"
rating
  base 100
lifecycle
  renewal
    invite 21 days before expiry
claims
  claim Theft
    pays claimed amount up to limit, less excess
    from 2027-06-01 pays claimed amount up to limit
'''


class DatedWording(unittest.TestCase):
    def setUp(self):
        self.p = parse(DATED)

    def policy(self, racing=False):
        pol = Policy(self.p, {"bike_value": Decimal(2000), "racing": racing}, set())
        pol.bind(date(2026, 9, 1))
        return pol

    def test_a_claim_is_settled_on_the_wording_in_force_at_the_loss(self):
        pol = self.policy()
        self.assertEqual(pol.claim("Theft", Decimal(1000), date(2027, 1, 1), date(2027, 1, 1), set()).amount, Decimal(950))
        self.assertEqual(pol.claim("Theft", Decimal(1000), date(2027, 4, 1), date(2027, 4, 1), set()).amount, Decimal(900))
        self.assertEqual(pol.claim("Theft", Decimal(1000), date(2027, 7, 1), date(2027, 7, 1), set()).amount, Decimal(1000))

    def test_an_until_exclusion_stops_on_its_date(self):
        pol = self.policy(racing=True)
        self.assertEqual(pol.claim("Theft", Decimal(1000), date(2027, 2, 1), date(2027, 2, 1), set()).reason, "Theft is excluded: Racing was excluded until March 2027")
        self.assertEqual(pol.claim("Theft", Decimal(1000), date(2027, 3, 1), date(2027, 3, 1), set()).status, "paid")

    def test_cover_state_takes_a_date_and_is_undated_without_one(self):
        pol = self.policy(racing=True)
        self.assertEqual(pol.cover_state("Theft").status, "included")
        self.assertEqual(pol.cover_state("Theft", on=date(2027, 1, 1)).status, "excluded")


class AmendmentsAcrossVersions(unittest.TestCase):
    def test_a_policy_on_the_old_version_is_settled_with_the_later_amendment(self):
        from tests.test_versions import bike
        h = History([parse(bike("2026-01-01")), parse(bike("2026-07-01", "  from 2027-03-01 excess 100\n", "    from 2027-03-01 requires lock_photo\n"))])
        pol = Policy(h.versions[1], {"bike_value": Decimal(2000), "racing": False}, set(), history=h)
        pol.bind(date(2026, 6, 1))
        self.assertIs(pol.product, h.versions[0])
        self.assertEqual(pol.claim("Theft", Decimal(1000), date(2027, 2, 1), date(2027, 2, 1), set()).amount, Decimal(950))
        self.assertEqual(pol.claim("Theft", Decimal(1000), date(2027, 4, 1), date(2027, 4, 1), set()).reason, "lock_photo is required")
        self.assertEqual(pol.claim("Theft", Decimal(1000), date(2027, 4, 1), date(2027, 4, 1), {"lock_photo"}).amount, Decimal(900))
        self.assertEqual(pol.cover_state("Theft", on=date(2027, 4, 1)).status, "included")


class ConditionalTaxAndFee(unittest.TestCase):
    """A tax or fee line may carry a `when`, and the condition can read the rounded net."""

    def quote(self, base):
        p = parse(FULL + f'rating\n  base {base}\n  tax "Levy" 3% when "Racing" selected\n  fee "Stamp duty" 1 when net >= 20\n')
        return rate(p, risk(), set())

    def test_fee_below_the_threshold_is_not_charged(self):
        self.assertEqual(self.quote("19.99").lines, [])

    def test_threshold_reads_the_rounded_net(self):
        self.assertEqual(self.quote("19.996").lines, [("Stamp duty", Decimal("1.00"))])

    def test_tax_only_when_the_cover_is_selected(self):
        p = parse(FULL + 'rating\n  base 100\n  tax "Levy" 3% when Racing selected\n')
        self.assertEqual(rate(p, risk(racing=True), {"Racing"}).lines, [("Levy", Decimal("3.00"))])
        self.assertEqual(rate(p, risk(), set()).lines, [])


class LinesInOrder(unittest.TestCase):
    """Tax, fee and commission lines are steps: evaluated where they stand, on the figures above them."""

    def lines(self, rating, **over):
        return rate(parse(FULL + "rating\n" + rating), risk(**over), set()).lines

    def test_a_tax_on_a_tax(self):
        self.assertEqual(self.lines('  base 100\n  tax IPT 12%\n  tax "Surcharge" 10% of IPT\n'),
                         [("IPT", Decimal("12.00")), ("Surcharge", Decimal("1.20"))])

    def test_a_tax_on_the_running_total(self):
        self.assertEqual(self.lines('  base 100\n  tax IPT 12%\n  fee "Admin" 5\n  tax "QST" 9% of premium\n'),
                         [("IPT", Decimal("12.00")), ("Admin", Decimal("5.00")), ("QST", Decimal("10.53"))])

    def test_order_is_semantic(self):
        q = rate(parse(FULL + "rating\n  base 100\n  tax IPT 12%\n  add 10\n"), risk(), set())
        self.assertEqual((q.net, q.lines, q.total), (Decimal("110.00"), [("IPT", Decimal("12.00"))], Decimal("122.00")))

    def test_loads_apply_before_the_first_line(self):
        q = rate(parse(FULL + "rating\n  base 100\n  tax IPT 12%\n  fee \"Admin\" 5\n"), risk(), set(), loading=Decimal("1.5"), underwriter=Decimal("0.1"))
        self.assertEqual((q.net, q.lines), (Decimal("165.00"), [("IPT", Decimal("19.80")), ("Admin", Decimal("5.00"))]))
        self.assertEqual([t.label for t in q.trail], ["base", "Claims loading", "Underwriter load"])

    def test_round_to_is_read_before_any_step(self):
        q = rate(parse(FULL + "rating\n  base 100.4\n  tax IPT 12%\n  round to 1\n"), risk(), set())
        self.assertEqual((q.net, q.lines), (Decimal("100"), [("IPT", Decimal("12"))]))

    def test_a_tax_inside_for_each_is_on_each_items_net_and_lines_merge(self):
        src = FLEET.replace("    value: money\n", "    value: money\n    ebike: yes/no, default no\n").replace(
            "    base 3% of value\n", "    base 3% of value\n    tax \"Fire\" 22% of 20% of net when ebike is yes\n")
        bikes = [dict(value=Decimal(1000), age=Decimal(2), security="gold", ebike=True), dict(value=Decimal(500), age=Decimal(0), security="gold", ebike=True),
                 dict(value=Decimal(2000), age=Decimal(2), security="gold", ebike=False)]
        q = rate(parse(src), {"rider_age": Decimal(30), "bikes": bikes}, set())
        # the tax sits before the age factor: bike 1 net 30.00 -> 22% of 6.00 = 1.32; bike 2 15.00 -> 0.66; bike 3 none
        self.assertEqual(q.lines[0], ("Fire", Decimal("1.98")))
        self.assertEqual(q.lines[1][0], "IPT")

    def test_an_items_second_line_reads_only_that_items_lines(self):
        src = FLEET.replace("    base 3% of value\n", "    base 3% of value\n    tax \"Fire\" 10% of net\n    tax \"QST\" 10% of premium\n")
        q = rate(parse(src), fleet((1000, 2, "gold"), (1000, 2, "gold")), set())
        # each bike: net 30.00, Fire 3.00, QST 10% of 33.00 = 3.30; not 10% of (30 + both bikes' Fire + the first bike's QST)
        self.assertEqual(q.lines[:2], [("Fire", Decimal("6.00")), ("QST", Decimal("6.60"))])

    def test_a_commission_may_take_a_base_too(self):
        q = rate(parse(FULL + 'rating\n  base 100\n  tax IPT 12%\n  commission "Broker" 15% of premium\n'), risk(), set())
        self.assertEqual(q.commission, [("Broker", Decimal("16.80"))])


from ipngine.engine import split
from ipngine.expr import ExprError

CLASSED = FULL.replace("cover Theft\n", "cover Theft\n  class 9\n").replace('cover "Accidental Damage"\n', 'cover "Accidental Damage"\n  class 3\n').replace("cover Racing optional\n", "cover Racing optional\n  class 3\n")
ATTRIBUTED = CLASSED + '''rating
  base 100
  add "Racing cover" 45 for Racing when Racing selected
  allocate
    "Accidental Damage" 60%
    Theft 40%
'''


def shares_of(q):
    return {s.name: s.net for s in q.shares}


class Attribution(unittest.TestCase):
    """The net is a partition across covers; every step keeps it so."""

    def test_split_rounds_each_share_and_gives_the_residue_to_the_largest(self):
        self.assertEqual(split(Decimal("10.00"), {"a": Decimal(1), "b": Decimal(1), "c": Decimal(1)}, Decimal("0.01")),
                         {"a": Decimal("3.34"), "b": Decimal("3.33"), "c": Decimal("3.33")})
        self.assertEqual(split(Decimal("10.00"), {"a": Decimal(1), "b": Decimal(3)}, Decimal("0.01")), {"a": Decimal("2.50"), "b": Decimal("7.50")})
        self.assertEqual(split(Decimal("5.00"), {"a": Decimal(0), "b": Decimal(0)}, Decimal("0.01")), {"a": Decimal("5.00"), "b": Decimal("0.00")})

    def test_allocate_shares_the_pool_and_for_credits_a_cover(self):
        q = rate(parse(ATTRIBUTED), risk(racing=True), {"Racing"})
        self.assertEqual(shares_of(q), {"Theft": Decimal("40.00"), "Accidental Damage": Decimal("60.00"), "Racing": Decimal("45.00")})
        self.assertEqual([s.class_ for s in q.shares], ["9", "3", "3"])
        self.assertEqual(shares_of(rate(parse(ATTRIBUTED), risk(), set())), {"Theft": Decimal("40.00"), "Accidental Damage": Decimal("60.00")})

    def test_bounds_and_whole_net_factors_scale_every_share_alike(self):
        q = rate(parse(ATTRIBUTED + "  discount 10%\n  minimum 200\n"), risk(racing=True), {"Racing"})
        # 145 less 10% = 130.50, raised to 200: each share x 200/130.50
        self.assertEqual(q.net, Decimal("200.00"))
        self.assertEqual(shares_of(q), {"Theft": Decimal("55.17"), "Accidental Damage": Decimal("82.76"), "Racing": Decimal("62.07")})
        self.assertEqual(sum(shares_of(q).values()), q.net)

    def test_for_scales_one_cover_only(self):
        q = rate(parse(ATTRIBUTED + "  factor \"Theft area\" x 1.5 for Theft\n"), risk(), set())
        self.assertEqual((q.net, shares_of(q)), (Decimal("120.00"), {"Theft": Decimal("60.00"), "Accidental Damage": Decimal("60.00")}))

    def test_items_shares_add_up(self):
        src = FLEET.replace("cover Theft\n", "cover Theft\n  class 9\n").replace("    base 3% of value\n", "    base 3% of value for Theft\n")
        q = rate(parse(src), fleet((2000, 0, "gold"), (1000, 3, "silver")), set())
        self.assertEqual(shares_of(q), {"Theft": q.net})

    def test_unattributed_premium_with_no_allocate_is_an_error(self):
        with self.assertRaises(ExprError) as cm:
            rate(parse(CLASSED + "rating\n  base 100\n  add 45 for Racing\n"), risk(), set())
        self.assertEqual(str(cm.exception), "100.00 of the premium is not attributed to a cover; add allocate")

    def test_a_plain_product_has_no_shares(self):
        self.assertEqual(rate(parse(RATING), risk(), set()).shares, [])

    def test_by_class_sums_the_covers(self):
        q = rate(parse(ATTRIBUTED), risk(racing=True), {"Racing"})
        self.assertEqual([(s.name, s.net) for s in q.by_class()], [("9", Decimal("40.00")), ("3", Decimal("105.00"))])


class LineAttribution(unittest.TestCase):
    """A line is attributed in proportion to its base worked out with each cover's figures."""

    def quote(self, lines):
        return rate(parse(ATTRIBUTED + lines), risk(racing=True), {"Racing"})

    def test_a_tax_of_net_follows_the_net(self):
        q = self.quote("  tax IPT 12%\n")
        self.assertEqual({s.name: dict(s.lines)["IPT"] for s in q.shares}, {"Theft": Decimal("4.80"), "Accidental Damage": Decimal("7.20"), "Racing": Decimal("5.40")})

    def test_a_tax_of_one_cover_is_wholly_that_covers(self):
        q = self.quote('  tax "Racing levy" 10% of Racing\n  tax IPT 12% of net less Racing\n')
        by = {s.name: dict(s.lines) for s in q.shares}
        self.assertEqual(q.lines, [("Racing levy", Decimal("4.50")), ("IPT", Decimal("12.00"))])
        self.assertEqual(by["Racing"], {"Racing levy": Decimal("4.50"), "IPT": Decimal("0.00")})
        self.assertEqual((by["Theft"]["IPT"], by["Accidental Damage"]["IPT"]), (Decimal("4.80"), Decimal("7.20")))

    def test_a_fee_has_no_share_and_a_commission_is_split(self):
        q = self.quote('  fee "Admin" 10\n  commission "Broker" 10%\n')
        self.assertEqual([dict(s.lines) for s in q.shares], [{}, {}, {}])
        self.assertEqual({s.name: dict(s.commission)["Broker"] for s in q.shares}, {"Theft": Decimal("4.00"), "Accidental Damage": Decimal("6.00"), "Racing": Decimal("4.50")})

    def test_a_tax_on_a_tax_follows_the_first_taxs_shares(self):
        q = self.quote('  tax IPT 12% of net less Racing\n  tax "Surcharge" 10% of IPT\n')
        self.assertEqual({s.name: dict(s.lines)["Surcharge"] for s in q.shares}, {"Theft": Decimal("0.48"), "Accidental Damage": Decimal("0.72"), "Racing": Decimal("0.00")})

    def test_premium_per_cover_is_its_net_plus_its_lines(self):
        q = self.quote('  tax "Racing levy" 10% of Racing\n  tax "QST" 10% of premium\n')
        self.assertEqual({s.name: dict(s.lines)["QST"] for s in q.shares}, {"Theft": Decimal("4.00"), "Accidental Damage": Decimal("6.00"), "Racing": Decimal("4.95")})


HOUSEHOLD = '''
product "Household"
  term 12 months

inputs
  rebuild_cost: money, default 0
  contents_sum: money, default 0
  property_type: choice of flat, house

cover Buildings optional
  class 8
  premium 0.15% of rebuild_cost
  limit rebuild_cost

cover Contents optional
  class 9
  premium 0.5% of contents_sum
  limit contents_sum
  excludes when contents_sum > 100000 because "Too much"

rating
  add cover premiums
  factor "Property type"
    property_type is flat: x 0.90
    otherwise: x 1.00
  discount 10% when Buildings selected and Contents selected
  minimum 60
  tax IPT 12%
'''


def house(**over):
    return {"rebuild_cost": Decimal(300000), "contents_sum": Decimal(40000), "property_type": "house", **over}


class CoverPremiums(unittest.TestCase):
    """A cover prices itself; `add cover premiums` credits each included cover's price to its share."""

    def test_cover_premiums_join_where_written_and_are_each_covers_share(self):
        q = rate(parse(HOUSEHOLD), house(), {"Buildings", "Contents"})
        # 450 + 200 = 650, less 10% = 585
        self.assertEqual(q.net, Decimal("585.00"))
        self.assertEqual(shares_of(q), {"Buildings": Decimal("405.00"), "Contents": Decimal("180.00")})
        self.assertEqual([(t.label, t.applied) for t in q.trail[:2]], [("Buildings", "+ 450.00"), ("Contents", "+ 200.00")])

    def test_an_unselected_or_excluded_cover_contributes_nothing(self):
        q = rate(parse(HOUSEHOLD), house(), {"Buildings"})
        self.assertEqual((q.net, shares_of(q)), (Decimal("450.00"), {"Buildings": Decimal("450.00")}))
        q = rate(parse(HOUSEHOLD), house(contents_sum=Decimal(200000)), {"Buildings", "Contents"})
        self.assertEqual((q.net, shares_of(q)), (Decimal("405.00"), {"Buildings": Decimal("405.00")}))  # the bundle discount is on selection

    def test_a_premium_block_prices_like_a_calculated_input(self):
        src = HOUSEHOLD.replace("  premium 0.15% of rebuild_cost\n", "  premium\n    base 0.15% of rebuild_cost\n    factor \"Type\" x 1.2 when property_type is house\n    minimum 600\n")
        q = rate(parse(src), house(), {"Buildings"})
        self.assertEqual(q.net, Decimal("600.00"))  # 450 x 1.2 = 540, floored to 600
        self.assertEqual([(t.label, t.applied) for t in q.trail[:3]], [("Buildings base", "450.00"), ("Buildings Type", "x 1.2"), ("Buildings minimum", "600")])

    def test_a_premium_with_when_is_nothing_when_the_condition_fails(self):
        src = HOUSEHOLD.replace("  premium 0.5% of contents_sum\n", "  premium 0.5% of contents_sum when property_type is flat\n")
        q = rate(parse(src), house(), {"Buildings", "Contents"})
        self.assertEqual(shares_of(q), {"Buildings": Decimal("405.00")})

    def test_a_when_inside_a_calculated_field_reads_before_the_pool_is_allocated(self):
        src = HOUSEHOLD.replace("  property_type: choice of flat, house\n", "  property_type: choice of flat, house\n  size: calculated\n    base 1\n    add 1 when rebuild_cost > 100000\n")
        self.assertEqual(rate(parse(src), house(), {"Buildings"}).net, Decimal("450.00"))

    def test_a_cover_with_a_premium_and_an_allocate_row_takes_both(self):
        src = HOUSEHOLD.replace("  add cover premiums\n", "  base 100\n  add cover premiums\n  allocate\n    Buildings 100%\n")
        q = rate(parse(src), house(), {"Buildings", "Contents"})
        # (100 + 450 + 200) less 10% = 675: Buildings 495, Contents 180
        self.assertEqual(shares_of(q), {"Buildings": Decimal("495.00"), "Contents": Decimal("180.00")})


EBIKES = FLEET.replace("    security: choice of bronze, silver, gold\n", "    security: choice of bronze, silver, gold\n    ebike: yes/no, default no\n").replace(
    "cover Theft\n", "cover Fire\n  class 8\n  premium 0.5% of value when ebike is yes\n  limit value\n\ncover Theft\n  class 9\n").replace(
    "    base 3% of value\n", "    base 3% of value for Theft\n")


def ebikes(*bikes):
    return {"rider_age": Decimal(30), "bikes": [dict(value=Decimal(v), age=Decimal(a), security="gold", ebike=e) for v, a, e in bikes]}


class PerItemCoverPremiums(unittest.TestCase):
    """A premium that reads an item's fields is priced once per item."""

    def test_outside_the_loop_the_sum_over_items_joins(self):
        src = EBIKES.replace("  factor \"Fleet\"\n", "  add cover premiums\n  factor \"Fleet\"\n")
        q = rate(parse(src), ebikes((2000, 0, True), (1000, 0, False), (3000, 0, True)), set())
        # Theft 3% of 6000 = 180; Fire 0.5% of the e-bikes' 5000 = 25; fleet x 0.95
        self.assertEqual(shares_of(q), {"Fire": Decimal("23.75"), "Theft": Decimal("171.00")})
        self.assertEqual([(t.label, t.applied) for t in q.trail if t.label == "Fire"], [("Fire", "+ 25.00")])

    def test_inside_the_loop_each_items_premium_joins_with_the_item(self):
        src = EBIKES.replace("      otherwise: x 0.90\n", "      otherwise: x 0.90\n    add cover premiums\n")
        q = rate(parse(src), ebikes((2000, 0, True), (1000, 3, False)), set())
        # bike 1: 60 + 10 = 70; bike 2: 30 x 0.9 = 27; fleet x 0.95 -> Theft (60 + 27) x 0.95 = 82.65, Fire 9.50
        self.assertEqual(shares_of(q), {"Fire": Decimal("9.50"), "Theft": Decimal("82.65")})
        self.assertEqual([(t.label, t.applied) for t in q.trail if "Fire" in t.label], [("bike 1 Fire", "+ 10.00"), ("bike 2 Fire", "+ 0.00")])

    def test_an_item_excluded_from_the_cover_contributes_nothing(self):
        src = EBIKES.replace("  premium 0.5% of value when ebike is yes\n", "  premium 0.5% of value when ebike is yes\n  excludes when value > 2500 because \"Too hot\"\n").replace("  factor \"Fleet\"\n", "  add cover premiums\n  factor \"Fleet\"\n")
        q = rate(parse(src), ebikes((2000, 0, True), (3000, 0, True)), set())
        self.assertEqual(shares_of(q)["Fire"], Decimal("9.50"))


class LifecycleSplit(unittest.TestCase):
    """Any amount a policy produces splits by each cover's earning share of the quote it came from."""

    def policy(self):
        src = EBIKES.replace('  factor "Fleet"\n', '  add cover premiums\n  factor "Fleet"\n')
        p = Policy(parse(src), ebikes((2000, 0, True), (1000, 3, False)), set())
        p.bind(date(2026, 1, 1))
        return p

    def test_a_refund_splits_by_net_plus_tax(self):
        p = self.policy()
        refund = p.cancel(date(2026, 7, 1), "customer")
        # theft 82.65 + 9.92, fire 9.50 + 1.14 of 103.21; refund 103.21 x 184/365 = 52.03
        self.assertEqual(refund, Decimal("52.03"))
        self.assertEqual(p.split(refund), {"Fire": Decimal("5.36"), "Theft": Decimal("46.67")})

    def test_a_renewal_offer_keeps_its_quote(self):
        offer = self.policy().renew()
        self.assertEqual(offer.quote.split(offer.premium), {"Fire": Decimal("11.70"), "Theft": Decimal("101.83")})

    def test_a_plain_product_has_one_unnamed_share(self):
        self.assertEqual(rate(parse(RATING), risk(), set()).split(Decimal("10.00")), {"": Decimal("10.00")})


class CheckInputs(unittest.TestCase):
    def test_missing_inputs_are_reported(self):
        p = parse(occupations('inputs\n  industry: choice of industry from "Occupations"\n  occupation: text\n  age: integer\n'))
        self.assertEqual(check_inputs(p, with_defaults(p.inputs, {})), ["missing industry, age"])

    def test_keyed_choice_must_be_listed_under_its_keys(self):
        p = parse(occupations('inputs\n  industry: choice of industry from "Occupations"\n  occupation: choice of occupation from "Occupations" for industry\n'))
        self.assertEqual(check_inputs(p, with_defaults(p.inputs, {"industry": "construction", "occupation": "Nurse"})),
                         ['occupation "Nurse" is not an occupation for industry "construction"'])
        self.assertEqual(check_inputs(p, with_defaults(p.inputs, {"industry": "construction", "occupation": "Labourer"})), [])

    def test_items_are_checked_with_their_position(self):
        p = parse(occupations('inputs\n  people: collection of person\n    industry: choice of industry from "Occupations"\n    occupation: choice of occupation from "Occupations" for industry\n'))
        items = [{"industry": "construction", "occupation": "Labourer"}, {"industry": "construction", "occupation": "Nurse"}]
        self.assertEqual(check_inputs(p, with_defaults(p.inputs, {"people": items})),
                         ['people item 2: occupation "Nurse" is not an occupation for industry "construction"'])

    def test_a_missing_field_in_a_collection_item_is_reported(self):
        p = parse(occupations('inputs\n  people: collection of person\n    industry: choice of industry from "Occupations"\n    occupation: choice of occupation from "Occupations" for industry\n    age: integer\n'))
        items = [{"industry": "construction", "occupation": "Labourer"}]
        self.assertEqual(check_inputs(p, with_defaults(p.inputs, {"people": items})), ["people item 1: missing age"])

    def test_a_number_key_reads_plainly(self):
        p = parse('product "X"\n  territory UK\n\ninputs\n  band: integer\n  plan: choice of plan from "Plans" for band\n\ntable "Plans" keyed on band, plan\n  band, plan\n  1, basic\n  2, basic\n  2, plus\n')
        self.assertEqual(check_inputs(p, with_defaults(p.inputs, {"band": Decimal(1), "plan": "plus"})), ['plan "plus" is not a plan for band 1'])
        self.assertEqual(check_inputs(p, with_defaults(p.inputs, {"band": Decimal(2), "plan": "plus"})), [])
