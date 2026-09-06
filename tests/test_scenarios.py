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

    def test_eligibility_sees_the_selection(self):
        res = outcomes('''
eligibility
  refer when Racing selected and rider_age > 60 because "Racing over 60"
scenario "sel"
  given bike_value 2000, rider_age 65, security gold, racing yes
  select Racing
  expect referred "Racing over 60"
''')
        self.assertEqual(res["sel"], [])

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


from tests.test_parser import RATING


def rated(extra):
    return {r.scenario.name: r.failures for r in run_all(parse(RATING + extra))}


class RatingExpectations(unittest.TestCase):
    def test_premium_net_tax_fee_factor(self):
        res = rated('''
scenario "priced"
  given bike_value 2000, rider_age 30, security gold, racing no
  expect net 60.00
  expect tax IPT 7.20
  expect fee "Admin fee" 10.00
  expect premium 77.20
  expect factor "Rider age" x 1.00
  expect factor "Security" - 10
''')
        self.assertEqual(res["priced"], [])

    def test_commission_line(self):
        res = {r.scenario.name: r.failures for r in run_all(parse(RATING + '  commission "Broker" 15%\n' + '''
scenario "split"
  given bike_value 2000, rider_age 30, security gold, racing no
  expect net 60.00
  expect commission "Broker" 9.00
  expect premium 77.20
  expect commission "Agent" 1.00
'''))}
        self.assertEqual(len(res["split"]), 1)
        self.assertIn("no commission called 'Agent'", res["split"][0])

    def test_wrong_premium_shows_breakdown(self):
        res = rated('''
scenario "wrong"
  given bike_value 2000, rider_age 30, security gold, racing no
  expect premium 99.99
''')
        self.assertIn("expected premium 99.99, got 77.20", res["wrong"][0])


from tests.test_parser import LIFECYCLE


def lived(extra):
    return {r.scenario.name: r.failures for r in run_all(parse(LIFECYCLE + "  instalments 12 monthly, charge 8%\n" + extra))}


class LifecycleSteps(unittest.TestCase):
    def test_instalment_schedule(self):
        res = lived('''
scenario "monthly"
  given bike_value 2000, rider_age 22, security gold, racing no
  expect premium 98.70
  expect instalment charge 7.90
  expect instalment 1 8.92
  expect instalment 12 8.88
  expect instalment 13 8.88
''')
        self.assertEqual(len(res["monthly"]), 1)
        self.assertIn("instalment 13", res["monthly"][0])

    def test_instalments_need_the_lifecycle_line(self):
        res = outcomes('''
scenario "none"
  given bike_value 2000, rider_age 22, security gold, racing no
  expect instalment 1 8.92
''')
        self.assertIn("instalments", res["none"][0])

    def test_cancellation_flow(self):
        res = lived('''
scenario "cancel"
  given bike_value 2000, rider_age 30, security gold, racing no
  when bound on 2026-01-01
  expect status live
  expect expiry 2027-01-01
  when cancelled by customer on 2026-04-11
  expect refund 23.79
  expect status cancelled
  expect status live on 2026-03-01
''')
        self.assertEqual(res["cancel"], [])

    def test_lapse_and_payment(self):
        res = lived('''
scenario "lapse"
  given bike_value 2000, rider_age 30, security gold, racing no
  when bound on 2026-01-01 unpaid
  expect status lapsed on 2026-02-15
  when paid on 2026-02-20
  expect status live on 2026-02-21
''')
        self.assertEqual(res["lapse"], [])

    def test_adjustment_and_renewal(self):
        res = lived('''
scenario "mta"
  given bike_value 2000, rider_age 30, security gold, racing no
  when bound on 2026-01-01
  when adjusted on 2026-04-11 with bike_value 4000
  expect additional premium 56.35
  expect premium 141.04
  expect renewal invite 2026-12-11
  expect renewal premium 141.04
  when adjusted on 2026-04-11 with bike_value 2000
  expect return premium 36.35
  when renewed on 2027-01-01
  expect status live on 2027-06-01
  expect status renewed on 2026-06-01
''')
        self.assertEqual(res["mta"], [])

    def test_renewal_declined(self):
        res = lived('''
scenario "old"
  given bike_value 2000, rider_age 30, security gold, racing no
  when bound on 2026-01-01
  when adjusted on 2026-06-01 with rider_age 85
  expect renewal declined "Age limit"
  when renewed on 2027-01-01
''')
        self.assertEqual(len(res["old"]), 1)
        self.assertIn("Age limit", res["old"][0])

    def test_wrong_status_reports_actual(self):
        res = lived('''
scenario "wrong"
  given bike_value 2000, rider_age 30, security gold, racing no
  when bound on 2026-01-01
  expect status cancelled
''')
        self.assertIn("expected status cancelled, got live", res["wrong"][0])


from tests.test_parser import CLAIMS


def claimed(extra):
    return {r.scenario.name: r.failures for r in run_all(parse(CLAIMS + extra))}


class ClaimSteps(unittest.TestCase):
    def test_claim_flow(self):
        res = claimed('''
scenario "claims"
  given bike_value 2000, rider_age 30, security gold, racing no
  when bound on 2026-01-01
  when claim Theft for 1500 on 2026-03-01 with police_report, crime_reference
  expect claim paid
  expect payout 1350.00
  when claim Theft for 1500 on 2026-03-01 reported 2026-05-01 with police_report, crime_reference
  expect claim declined "Late notification"
  expect claims in term 1
  when claim "Accidental Damage" for 500 on 2026-06-01
  expect payout 500.00
  expect claims in term 2
  expect renewal declined "Too many claims"
''')
        self.assertEqual(res["claims"], [])

    def test_wrong_payout_reports_actual(self):
        res = claimed('''
scenario "wrong"
  given bike_value 2000, rider_age 30, security gold, racing no
  when bound on 2026-01-01
  when claim Theft for 1500 on 2026-03-01 with police_report, crime_reference
  expect payout 1500.00
''')
        self.assertIn("expected payout 1500.00, got 1350.00", res["wrong"][0])


from tests.test_parser import FLEET


def fleeted(extra):
    return {r.scenario.name: r.failures for r in run_all(parse(FLEET + extra))}


class CollectionSteps(unittest.TestCase):
    def test_items_through_the_lifecycle(self):
        res = fleeted('''
scenario "fleet"
  given rider_age 30
  given bike value 2000, age 0, security gold
  given bike value 3000, age 1, security bronze
  expect eligible
  expect cover Theft on bike 1 included
  expect cover Theft on bike 1 limit 2000
  expect cover Theft on bike 2 excluded "Better lock needed"
  # bike 1: 60, bike 2: 90 x 0.90 = 81, total 141 x 0.95 = 133.95
  expect net 133.95
  when bound on 2026-01-01
  when claim Theft on bike 1 for 1500 on 2026-02-01
  expect payout 1350.00
  when claim Theft on bike 2 for 1500 on 2026-02-01
  expect claim declined "Theft is excluded: Better lock needed"
  when adjusted on 2026-01-01 removing bike 2
  expect net 60.00
  when adjusted on 2026-01-01 adding bike value 1000, age 3, security silver
  expect net 82.65
  expect renewal offered
''')
        self.assertEqual(res["fleet"], [])

    def test_too_few_items_is_declined(self):
        res = fleeted('''
scenario "empty"
  given rider_age 30
  expect declined "bikes: at least 1 required"
''')
        self.assertEqual(res["empty"], [])

    def test_unknown_item_number(self):
        res = fleeted('''
scenario "bad"
  given rider_age 30
  given bike value 2000, age 0, security gold
  expect cover Theft on bike 2 included
''')
        self.assertIn("no bike 2", res["bad"][0])


class CalculatedInputs(unittest.TestCase):
    def test_scenario_runs_without_giving_calculated_input(self):
        from tests.test_parser import CalculatedInputs as T
        p = parse(T.SRC + 'eligibility\n  decline when bmi > 40 because "BMI"\nscenario "s"\n  given height_cm 150, weight_kg 100\n  expect declined "BMI"\n')
        self.assertEqual(run_all(p)[0].failures, [])


class AggregateLimit(unittest.TestCase):
    def test_expect_remaining(self):
        p = parse('product "X"\ninputs\n  a: money\ncover Vet\n  limit 7000 per term\nrating\n  base 100\nclaims\n  claim Vet\n    pays claimed amount up to limit\nscenario "s"\n  given a 1\n  when bound on 2026-01-01\n  when claim Vet for 3000 on 2026-02-01\n  expect cover Vet remaining 4000\n  when claim Vet for 5000 on 2026-03-01\n  expect payout 4000\n  expect cover Vet remaining 0\n')
        self.assertEqual(run_all(p)[0].failures, [])


class ClaimFacts(unittest.TestCase):
    def test_with_mixes_evidence_and_facts(self):
        from tests.test_parser import LIFE
        p = parse(LIFE + 'rating\n  base 100\nscenario "s"\n  given sum_assured 100000, term_years 20, pet_age 3\n  when bound on 2026-01-01\n  when claim Death for 0 on 2026-06-01 with death_certificate, cause suicide\n  expect claim declined "Suicide in the first year"\n  when claim Death for 0 on 2028-06-01 with cause natural, death_certificate\n  expect payout 100000\n  when claim Vet for 1000 on 2026-06-01 with condition "sore paw"\n  expect payout 400\n')
        self.assertEqual(run_all(p)[0].failures, [])


class RefusedEvents(unittest.TestCase):
    SRC = 'product "X"\ninputs\n  a: money\nrating\n  base a\nlifecycle\n  adjustment: not allowed\n  cancellation by customer: no refund\n'

    def test_expect_refused_passes_when_the_event_is_refused(self):
        p = parse(self.SRC + 'scenario "s"\n  given a 100\n  when bound on 2026-01-01\n  when adjusted on 2026-02-01 with a 200\n  expect refused "adjustment is not allowed"\n  when cancelled by insurer on 2026-03-01\n  expect refused\n  expect premium 100\n')
        self.assertEqual(run_all(p)[0].failures, [])

    def test_unexpected_refusal_still_fails(self):
        p = parse(self.SRC + 'scenario "s"\n  given a 100\n  when bound on 2026-01-01\n  when adjusted on 2026-02-01 with a 200\n  expect premium 200\n')
        self.assertEqual(len(run_all(p)[0].failures), 2)

    def test_expect_refused_fails_when_the_event_went_through(self):
        p = parse(self.SRC + 'scenario "s"\n  given a 100\n  when bound on 2026-01-01\n  when cancelled by customer on 2026-03-01\n  expect refused\n')
        self.assertIn("was not refused", run_all(p)[0].failures[0])


class PerItemNet(unittest.TestCase):
    def test_expect_net_for_item(self):
        p = parse('product "X"\ninputs\n  bikes: collection of bike\n    value: money\nrating\n  for each bike\n    base 10% of value\n  discount 50%\nscenario "s"\n  given bike value 1000\n  given bike value 500\n  expect net for bike 1 100\n  expect net for bike 2 50\n  expect net 75\n')
        self.assertEqual(run_all(p)[0].failures, [])


class TableSteps(unittest.TestCase):
    def test_missing_cell_fails_the_scenario_with_the_table_message(self):
        from tests.test_parser import TABLES
        res = {r.scenario.name: r.failures for r in run_all(parse(TABLES + '''
rating
  base 100
  factor "Age" x rate from "Age and lock"

scenario "off the table"
  given bike_value 2000, rider_age 16, security gold, racing no
  expect net 100.00
'''))}
        self.assertEqual(len(res["off the table"]), 1)
        self.assertIn("no row in Age and lock for rider_age 16, security gold", res["off the table"][0])
