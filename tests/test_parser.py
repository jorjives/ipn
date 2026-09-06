import unittest
from datetime import date
from decimal import Decimal

from ideclare.parser import parse, ParseError


HEADER = '''
product "Cycle Cover"
  territory UK
  currency GBP
  term 12 months

inputs
  bike_value: money
  rider_age: integer
  security: choice of bronze, silver, gold
  racing: yes/no
  notes: text
'''


class HeaderAndInputs(unittest.TestCase):
    def test_product_header(self):
        p = parse(HEADER)
        self.assertEqual(p.name, "Cycle Cover")
        self.assertEqual(p.territory, "UK")
        self.assertEqual(p.currency, "GBP")
        self.assertEqual(p.term, (("num", Decimal(12)), "months"))

    def test_inputs(self):
        p = parse(HEADER)
        self.assertEqual(p.inputs["bike_value"].kind, "money")
        self.assertEqual(p.inputs["rider_age"].kind, "integer")
        self.assertEqual(p.inputs["security"].kind, "choice")
        self.assertEqual(p.inputs["security"].choices, ["bronze", "silver", "gold"])
        self.assertEqual(p.inputs["racing"].kind, "yes/no")
        self.assertEqual(p.inputs["notes"].kind, "text")

    def test_comments_and_blank_lines_ignored(self):
        p = parse("# a comment\n\nproduct \"X\"  # trailing\n  term 6 months\n")
        self.assertEqual(p.name, "X")
        self.assertEqual(p.term, (("num", Decimal(6)), "months"))

    def test_unknown_block_reports_line(self):
        with self.assertRaises(ParseError) as cm:
            parse('product "X"\n\nbanana\n  yes\n')
        self.assertIn("line 3", str(cm.exception))

    def test_unknown_input_type_reports_line(self):
        with self.assertRaises(ParseError) as cm:
            parse('product "X"\ninputs\n  a: colour\n')
        self.assertIn("line 3", str(cm.exception))
        self.assertIn("colour", str(cm.exception))

    def test_inconsistent_indent_is_error(self):
        with self.assertRaises(ParseError):
            parse('product "X"\n   territory UK\n  currency GBP\n')


if __name__ == "__main__":
    unittest.main()


FULL = HEADER + '''
eligibility
  decline when rider_age < 16 because "Rider must be at least 16"
  refer when bike_value > 10000 because "Underwriter review"

cover Theft
  limit bike_value
  excess 10% of claim, minimum 50
  excludes when security is bronze and bike_value > 2000 because "Gold or silver lock required"

cover "Accidental Damage"
  limit bike_value
  excess 100

cover Racing optional
  limit 5000
  excess 250
  available when racing is yes

scenario "Young rider"
  given bike_value 2000, rider_age 22, security gold, racing no
  select Racing
  expect eligible
'''


class RulesCoversScenarios(unittest.TestCase):
    def test_eligibility_rules(self):
        p = parse(FULL)
        self.assertEqual([r.kind for r in p.eligibility], ["decline", "refer"])
        self.assertEqual(p.eligibility[0].reason, "Rider must be at least 16")
        self.assertEqual(p.eligibility[0].condition, ("<", ("name", "rider_age"), ("num", Decimal(16))))

    def test_covers(self):
        p = parse(FULL)
        theft, ad, racing = p.covers
        self.assertEqual(theft.name, "Theft")
        self.assertFalse(theft.optional)
        self.assertEqual(theft.limit, ("name", "bike_value"))
        self.assertEqual(theft.excess.amount, ("*", ("pct", ("num", Decimal(10))), ("name", "claim")))
        self.assertEqual(theft.excess.minimum, ("num", Decimal(50)))
        self.assertEqual(theft.exclusions[0].reason, "Gold or silver lock required")
        self.assertEqual(ad.name, "Accidental Damage")
        self.assertEqual(ad.excess.amount, ("num", Decimal(100)))
        self.assertIsNone(ad.excess.minimum)
        self.assertTrue(racing.optional)
        self.assertEqual(racing.available, ("is", ("name", "racing"), ("bool", True)))

    def test_excess_maximum_and_deductible(self):
        p = parse(HEADER + 'cover Theft\n  limit bike_value\n  excess 10% of claim, minimum 50, maximum 500\ncover Fire\n  limit bike_value\n  deductible 250\nclaims\n  claim Fire\n    pays claimed amount up to limit, less deductible\n')
        self.assertEqual(p.cover("Theft").excess.maximum, ("num", Decimal(500)))
        self.assertEqual(p.cover("Fire").excess.amount, ("num", Decimal(250)))
        self.assertEqual(p.claims["Fire"].pays, ["limit", "excess"])

    def test_scenario(self):
        p = parse(FULL)
        s = p.scenarios[0]
        self.assertEqual(s.name, "Young rider")
        self.assertEqual(s.given, {"bike_value": Decimal(2000), "rider_age": Decimal(22), "security": "gold", "racing": False})
        self.assertEqual(s.selected, {"Racing"})
        self.assertEqual([st.tokens for st in s.steps], [["expect", "eligible"]])

    def test_unknown_input_in_rule_is_error(self):
        with self.assertRaises(ParseError) as cm:
            parse(HEADER + 'eligibility\n  decline when ridder_age < 16 because "x"\n')
        self.assertIn("ridder_age", str(cm.exception))

    def test_unknown_choice_in_rule_is_error(self):
        with self.assertRaises(ParseError) as cm:
            parse(HEADER + 'eligibility\n  decline when security is platinum because "x"\n')
        self.assertIn("platinum", str(cm.exception))

    def test_given_checks_input_type(self):
        with self.assertRaises(ParseError) as cm:
            parse(FULL + 'scenario "bad"\n  given rider_age gold\n')
        self.assertIn("rider_age", str(cm.exception))

    def test_select_unknown_cover_is_error(self):
        with self.assertRaises(ParseError):
            parse(FULL + 'scenario "bad"\n  select Flying\n')


RATING = FULL + '''
rating
  base 3.5% of bike_value
  factor "Rider age"
    rider_age < 25: x 1.40
    rider_age < 40: x 1.00
    otherwise: x 0.90
  factor "Security"
    security is gold: - 10
    otherwise: + 0
  add "Racing cover" 45 when Racing selected
  discount 10% when security is gold
  load 25% when rider_age < 21
  minimum 60
  tax IPT 12%
  fee "Admin fee" 10
  round to 0.01
'''


class Rating(unittest.TestCase):
    def test_steps_parse_in_order(self):
        p = parse(RATING)
        self.assertEqual([s.kind for s in p.rating], ["base", "factor", "factor", "add", "discount", "load", "minimum", "tax", "fee", "round"])

    def test_factor_rows(self):
        p = parse(RATING)
        age = p.rating[1]
        self.assertEqual(age.label, "Rider age")
        self.assertEqual([(r.op, r.amount) for r in age.rows], [("x", ("num", Decimal("1.40"))), ("x", ("num", Decimal("1.00"))), ("x", ("num", Decimal("0.90")))])
        self.assertIsNone(age.rows[2].condition)
        self.assertEqual(p.rating[2].rows[0].op, "-")

    def test_conditional_add_and_labels(self):
        p = parse(RATING)
        add, disc, load, tax, fee = p.rating[3], p.rating[4], p.rating[5], p.rating[7], p.rating[8]
        self.assertEqual(add.label, "Racing cover")
        self.assertEqual(add.condition, ("selected", ("name", "Racing")))
        self.assertEqual(disc.amount, ("pct", ("num", Decimal(10))))
        self.assertEqual(load.condition, ("<", ("name", "rider_age"), ("num", Decimal(21))))
        self.assertEqual(tax.label, "IPT")
        self.assertEqual(fee.label, "Admin fee")
        self.assertEqual(p.rating[9].amount, ("num", Decimal("0.01")))

    def test_otherwise_must_be_last(self):
        with self.assertRaises(ParseError) as cm:
            parse(FULL + 'rating\n  base 10\n  factor "A"\n    otherwise: x 1\n    rider_age < 5: x 2\n')
        self.assertIn("otherwise", str(cm.exception))

    def test_unknown_rating_step(self):
        with self.assertRaises(ParseError):
            parse(FULL + 'rating\n  multiply 10\n')


LIFECYCLE = RATING + '''
lifecycle
  cooling off 14 days, full refund
  cancellation by customer: refund pro rata, fee 25
  cancellation by insurer: refund pro rata
  adjustment: reprice, charge pro rata difference, fee 10
  lapse when unpaid after 30 days
  renewal
    invite 21 days before expiry
    increase capped at 20%
    decline when claims in term >= 2 because "Too many claims"
    decline when rider_age > 80 because "Age limit"
'''


class Lifecycle(unittest.TestCase):
    def test_lifecycle_block(self):
        lc = parse(LIFECYCLE).lifecycle
        self.assertEqual(lc.cooling_off_days, 14)
        self.assertEqual(lc.cancellation["customer"].refund, "pro rata")
        self.assertEqual(lc.cancellation["customer"].fee, Decimal(25))
        self.assertEqual(lc.cancellation["insurer"].fee, Decimal(0))
        self.assertTrue(lc.adjustment_allowed)
        self.assertEqual(lc.adjustment_fee, Decimal(10))
        self.assertEqual(lc.lapse_days, 30)
        self.assertEqual(lc.renewal_invite_days, 21)
        self.assertEqual(lc.renewal_cap, Decimal("0.20"))
        self.assertEqual([r.reason for r in lc.renewal_decline], ["Too many claims", "Age limit"])
        self.assertEqual(lc.renewal_decline[0].condition, (">=", ("name", "claims_in_term"), ("num", Decimal(2))))

    def test_refund_by_an_expression_over_time_in_force(self):
        src = FULL + 'table "Short rate" keyed on months in force\n  months_in_force, proportion\n  0-2, 75%\n  3-5, 50%\n  6+, 0%\nlifecycle\n  cancellation by customer: refund proportion from "Short rate", fee 20\n  cancellation by insurer: refund 100% - days in force / 365 * 100%\n'
        lc = parse(src).lifecycle
        self.assertEqual(lc.cancellation["customer"].refund, "amount")
        self.assertEqual(lc.cancellation["customer"].amount, ("lookup", "proportion", "Short rate"))
        self.assertEqual(lc.cancellation["customer"].fee, Decimal(20))
        self.assertEqual(lc.cancellation["insurer"].amount[0], "-")

    def test_no_refund_and_adjustment_not_allowed(self):
        lc = parse(FULL + "lifecycle\n  cancellation by customer: no refund\n  adjustment: not allowed\n").lifecycle
        self.assertEqual(lc.cancellation["customer"].refund, "none")
        self.assertFalse(lc.adjustment_allowed)

    def test_date_token(self):
        p = parse(FULL + 'scenario "d"\n  given bike_value 1, rider_age 1, security gold, racing no\n  when bound on 2026-01-31\n')
        self.assertEqual(p.scenarios[-1].steps[0].tokens, ["when", "bound", "on", "2026-01-31"])

    def test_bad_lifecycle_line(self):
        with self.assertRaises(ParseError):
            parse(FULL + "lifecycle\n  cancellation by dog: refund pro rata\n")


CLAIMS = LIFECYCLE + '''
claims
  claim Theft
    requires police_report, crime_reference
    pays claimed amount up to limit, less excess
    decline when reported after 30 days because "Late notification"
    decline when claimed > bike_value because "Claim exceeds insured value"
  claim "Accidental Damage"
    pays claimed amount up to limit
  after 2 claims in term: renewal load x 1.25
  after 3 claims in term: renewal load x 1.50
'''


class Claims(unittest.TestCase):
    def test_claim_rules(self):
        p = parse(CLAIMS)
        theft = p.claims["Theft"]
        self.assertEqual(theft.requires, ["police_report", "crime_reference"])
        self.assertEqual(theft.pays, ["limit", "excess"])
        self.assertEqual(theft.decline[0].reason, "Late notification")
        self.assertEqual(theft.decline[0].condition, (">", ("name", "days_to_report"), ("num", Decimal(30))))
        self.assertEqual(theft.decline[1].condition, (">", ("name", "claimed"), ("name", "bike_value")))
        self.assertEqual(p.claims["Accidental Damage"].pays, ["limit"])

    def test_terms_imposed_after_a_claim(self):
        src = CLAIMS.replace("  after 2 claims in term: renewal load x 1.25\n",
                             "  after 1 claim in term\n    cancellation by customer: no refund\n    adjustment: not allowed\n  after 2 claims in term: renewal load x 1.25\n")
        p = parse(src)
        (count, terms, unless), = p.claims_terms
        self.assertEqual((count, unless), (1, None))
        self.assertEqual((terms.cancellation["customer"].refund, terms.adjustment_allowed), ("none", False))
        # only the stated settings change; the product's own lifecycle is untouched
        self.assertEqual(terms.cooling_off_days, p.lifecycle.cooling_off_days)
        self.assertNotEqual(p.lifecycle.cancellation["customer"].refund, "none")
        self.assertTrue(p.lifecycle.adjustment_allowed)

    def test_claims_loading(self):
        p = parse(CLAIMS)
        self.assertEqual(p.claims_loading, [(2, Decimal("1.25"), None), (3, Decimal("1.50"), None)])

    def test_unless_on_imposed_terms_and_loading(self):
        src = CLAIMS.replace("  after 2 claims in term: renewal load x 1.25\n",
                             '  after 1 claim in term unless Racing selected\n    adjustment: not allowed\n  after 2 claims in term: renewal load x 1.25 unless security is gold\n')
        p = parse(src)
        self.assertEqual(p.claims_terms[0][2], ("selected", ("name", "Racing")))
        self.assertEqual(p.claims_loading[0], (2, Decimal("1.25"), ("is", ("name", "security"), ("name", "gold"))))

    def test_claim_on_unknown_cover(self):
        with self.assertRaises(ParseError):
            parse(FULL + "claims\n  claim Flying\n    pays claimed amount up to limit\n")


FLEET = '''
product "Family Cycle Cover"
  term 12 months

inputs
  rider_age: integer
  bikes: collection of bike, 1 to 3
    value: money
    age: integer
    security: choice of bronze, silver, gold

eligibility
  decline when any bike where value > 10000 because "Too valuable"
  refer when total value of bikes > 12000 because "Fleet review"

cover Theft
  limit value
  excess 10% of claim, minimum 50
  excludes when security is bronze and value > 2000 because "Better lock needed"

rating
  for each bike
    base 3% of value
    factor "Bike age"
      age < 1: x 1.00
      otherwise: x 0.90
  factor "Fleet"
    count of bikes > 1: x 0.95
    otherwise: x 1.00
  minimum 40
  tax IPT 12%

lifecycle
  cancellation by customer: refund pro rata
  adjustment: reprice, charge pro rata difference
  renewal
    index bike value by 10%

claims
  claim Theft
    pays claimed amount up to limit, less excess

scenario "two bikes"
  given rider_age 30
  given bike value 2000, age 0, security gold
  given bike value 1000, age 3, security silver
  expect eligible
'''


class Collections(unittest.TestCase):
    def test_collection_input(self):
        bikes = parse(FLEET).inputs["bikes"]
        self.assertEqual((bikes.kind, bikes.singular, bikes.min_items, bikes.max_items), ("collection", "bike", 1, 3))
        self.assertEqual(list(bikes.fields), ["value", "age", "security"])
        self.assertEqual(bikes.fields["security"].choices, ["bronze", "silver", "gold"])

    def test_bounds_forms(self):
        for spec, bounds in [("collection of bike", (0, None)), ("collection of bike, at least 2", (2, None)), ("collection of bike, at most 4", (0, 4))]:
            p = parse(f'product "X"\ninputs\n  bikes: {spec}\n    value: money\n')
            self.assertEqual((p.inputs["bikes"].min_items, p.inputs["bikes"].max_items), bounds)

    def test_aggregates_and_any(self):
        p = parse(FLEET)
        self.assertEqual(p.eligibility[0].condition, ("any", "bike", (">", ("name", "value"), ("num", Decimal(10000)))))
        self.assertEqual(p.eligibility[1].condition, (">", ("agg", "total", "value", "bikes"), ("num", Decimal(12000))))
        self.assertEqual(p.rating[1].rows[0].condition, (">", ("count", "bikes"), ("num", Decimal(1))))

    def test_for_each_rating_block(self):
        each = parse(FLEET).rating[0]
        self.assertEqual((each.kind, each.label), ("each", "bike"))
        self.assertEqual([s.kind for s in each.steps], ["base", "factor"])

    def test_for_each_ordered_by(self):
        src = FLEET.replace("  for each bike\n", "  for each bike, ordered by value descending, age\n").replace("  factor \"Fleet\"\n", "    factor \"Position\"\n      position is 1: x 1.00\n      otherwise: x 0.50\n  factor \"Fleet\"\n")
        each = parse(src).rating[0]
        self.assertEqual(each.order, [(("name", "value"), True), (("name", "age"), False)])
        self.assertEqual(each.steps[-1].rows[0].condition, ("is", ("name", "position"), ("num", Decimal(1))))

    def test_calculated_field(self):
        src = FLEET.replace("    security: choice of bronze, silver, gold\n",
                            "    security: choice of bronze, silver, gold\n    rank: calculated\n      base value\n      add 5000 when security is gold\n")
        rank = parse(src).collections[0].fields["rank"]
        self.assertEqual(rank.kind, "calculated")
        self.assertEqual([s.kind for s in rank.steps], ["base", "add"])

    def test_calculated_field_is_not_given(self):
        src = FLEET.replace("    security: choice of bronze, silver, gold\n",
                            "    security: choice of bronze, silver, gold\n    rank: calculated\n      base value\n")
        parse(src)  # scenario lines give value, age, security only
        with self.assertRaises(ParseError) as cm:
            parse(src.replace("security gold\n", "security gold, rank 1\n", 1))
        self.assertIn("rank", str(cm.exception))

    def test_position_outside_for_each_is_error(self):
        with self.assertRaises(ParseError) as cm:
            parse(FLEET.replace("    count of bikes > 1: x 0.95\n", "    position is 1: x 0.95\n"))
        self.assertIn("position", str(cm.exception))

    def test_tax_inside_for_each_is_error(self):
        with self.assertRaises(ParseError):
            parse(FLEET.replace("    base 3% of value\n", "    base 3% of value\n    tax IPT 5%\n"))

    def test_field_clashing_with_input_is_error(self):
        with self.assertRaises(ParseError) as cm:
            parse(FLEET.replace("    age: integer\n", "    rider_age: integer\n"))
        self.assertIn("rider_age", str(cm.exception))

    def test_given_items(self):
        sc = parse(FLEET).scenarios[0]
        self.assertEqual(sc.given["rider_age"], Decimal(30))
        self.assertEqual(sc.given["bikes"][1], {"value": Decimal(1000), "age": Decimal(3), "security": "silver"})

    def test_index_item_field(self):
        self.assertEqual(parse(FLEET).lifecycle.renewal_index, [("bike.value", "%", ("num", Decimal(10)), None, None)])


ENRICHED = FLEET.replace("  rider_age: integer\n", "  rider_age: integer\n  postcode: text\n") + '''
enrichment "Postcode risk" from postcode
  provides
    theft_area: choice of low, medium, high
  when unavailable: refer because "Postcode not recognised"

enrichment "Bike catalogue" for each bike from value
  provides
    category: choice of road, folding, other
  when unavailable: category is other
  held for the term
'''


class Enrichments(unittest.TestCase):
    def test_declares_shape_and_registers_fields(self):
        p = parse(ENRICHED)
        risk, catalogue = p.enrichments
        self.assertEqual((risk.name, risk.keys, risk.item), ("Postcode risk", ["postcode"], ""))
        self.assertEqual((risk.unavailable, risk.reason), ("refer", "Postcode not recognised"))
        self.assertEqual(p.inputs["theft_area"].provided, "Postcode risk")
        self.assertEqual((catalogue.item, catalogue.keys, catalogue.held), ("bike", ["value"], True))
        self.assertEqual(catalogue.defaults, {"category": "other"})
        self.assertEqual(p.collections[0].fields["category"].provided, "Bike catalogue")

    def test_provided_fields_usable_in_rules(self):
        src = ENRICHED + "eligibility\n  decline when theft_area is high because \"No\"\n"
        self.assertEqual(parse(src).eligibility[-1].reason, "No")

    def test_unknown_key_is_error(self):
        with self.assertRaises(ParseError) as cm:
            parse(ENRICHED.replace("from postcode", "from post_code"))
        self.assertIn("post_code", str(cm.exception))

    def test_default_must_be_a_provided_field(self):
        with self.assertRaises(ParseError):
            parse(ENRICHED.replace("category is other", "colour is red"))

    def test_scenario_may_omit_provided_item_fields(self):
        parse(ENRICHED + 'scenario "s"\n  given rider_age 30\n  given bike value 1, age 0, security gold\n  expect eligible\n')


class Terms(unittest.TestCase):
    def test_term_in_days_and_years(self):
        self.assertEqual(parse('product "X"\n  term 10 days\n').term, (("num", Decimal(10)), "days"))
        self.assertEqual(parse('product "X"\n  term 25 years\n').term, (("num", Decimal(25)), "years"))

    def test_term_from_an_input(self):
        p = parse('product "X"\n  term term_years years\ninputs\n  term_years: integer\n')
        self.assertEqual(p.term, (("name", "term_years"), "years"))

    def test_term_until_a_date_input(self):
        p = parse('product "X"\n  term until return_date\ninputs\n  return_date: date\n')
        self.assertEqual(p.term, (("name", "return_date"), "until"))
        self.assertEqual(p.inputs["return_date"].kind, "date")

    def test_term_must_name_a_known_input(self):
        with self.assertRaises(ParseError) as cm:
            parse('product "X"\n  term until return_date\n')
        self.assertIn("return_date", str(cm.exception))

    def test_date_given_in_scenario(self):
        p = parse('product "X"\ninputs\n  start: date\nscenario "s"\n  given start 2026-03-01\n')
        self.assertEqual(p.scenarios[0].given["start"], date(2026, 3, 1))


class CalculatedInputs(unittest.TestCase):
    SRC = 'product "X"\ninputs\n  height_cm: number\n  weight_kg: number\n  bmi: calculated\n    base weight_kg / ( height_cm / 100 * height_cm / 100 )\n'

    def test_top_level_calculated_input_has_steps(self):
        p = parse(self.SRC)
        self.assertEqual(p.inputs["bmi"].kind, "calculated")
        self.assertEqual(p.inputs["bmi"].steps[0].kind, "base")

    def test_scenario_need_not_give_it(self):
        parse(self.SRC + 'eligibility\n  decline when bmi > 40 because "BMI"\nscenario "s"\n  given height_cm 180, weight_kg 80\n  expect eligible\n')

    def test_needs_steps(self):
        with self.assertRaises(ParseError):
            parse('product "X"\ninputs\n  bmi: calculated\n')


TRAVEL = '''
product "Trip"
  term until return_date

inputs
  departure_date: date
  return_date: date

cover Cancellation
  limit 2000
  in force until departure_date

cover Medical
  limit 5000000
  in force from departure_date

cover "Vet fees"
  limit 7000
  waiting period 14 days

rating
  base 100
'''


class CoverWindows(unittest.TestCase):
    def test_in_force_from_and_until(self):
        p = parse(TRAVEL)
        self.assertEqual(p.cover("Cancellation").until, ("name", "departure_date"))
        self.assertIsNone(p.cover("Cancellation").from_)
        self.assertEqual(p.cover("Medical").from_, ("name", "departure_date"))

    def test_waiting_period(self):
        self.assertEqual(parse(TRAVEL).cover("Vet fees").waiting_days, 14)
        self.assertEqual(parse(TRAVEL).cover("Medical").waiting_days, 0)


class AggregateLimit(unittest.TestCase):
    def test_limit_per_term_is_aggregate(self):
        p = parse('product "X"\ninputs\n  a: money\ncover Vet\n  limit 7000 per term\ncover Other\n  limit a\n')
        self.assertTrue(p.cover("Vet").aggregate)
        self.assertEqual(p.cover("Vet").limit, ("num", Decimal(7000)))
        self.assertFalse(p.cover("Other").aggregate)


class PaysClauses(unittest.TestCase):
    def test_order_written_is_kept(self):
        p = parse('product "X"\ninputs\n  a: money\ncover V\n  limit a\nclaims\n  claim V\n    pays claimed amount, less excess, up to limit\n')
        self.assertEqual(p.claims["V"].pays, ["excess", "limit"])

    def test_unknown_clause_is_error(self):
        with self.assertRaises(ParseError):
            parse('product "X"\ninputs\n  a: money\ncover V\n  limit a\nclaims\n  claim V\n    pays claimed amount, less tax\n')


LIFE = '''
product "Life"
  term term_years years

inputs
  sum_assured: money
  term_years: integer
  pet_age: integer

cover Death
  limit sum_assured

cover Vet
  limit 7000 per term
  excess 100

claims
  claim Death
    asks
      cause: choice of natural, accident, suicide
    requires death_certificate
    pays sum_assured
    decline when cause is suicide and within 12 months of inception because "Suicide in the first year"
  claim Vet
    asks
      condition: text
    co-payment 20% when pet_age >= 9
    pays claimed amount, less excess, less co-payment, up to limit
    settlement
      otherwise: x 0.5
'''


class ClaimFacts(unittest.TestCase):
    def test_asks_declares_claim_facts(self):
        p = parse(LIFE)
        self.assertEqual(p.claims["Death"].asks["cause"].choices, ["natural", "accident", "suicide"])
        self.assertEqual(p.claims["Death"].requires, ["death_certificate"])

    def test_within_months_of_inception_folds(self):
        p = parse(LIFE)
        cond = p.claims["Death"].decline[0].condition
        self.assertEqual(cond, ("and", ("is", ("name", "cause"), ("name", "suicide")), ("<", ("name", "months_since_inception"), ("num", Decimal(12)))))

    def test_fixed_benefit(self):
        p = parse(LIFE)
        self.assertEqual(p.claims["Death"].pays_amount, ("name", "sum_assured"))
        self.assertIsNone(p.claims["Vet"].pays_amount)

    def test_co_payment_and_settlement(self):
        p = parse(LIFE)
        vet = p.claims["Vet"]
        self.assertEqual(vet.pays, ["excess", "co-payment", "limit"])
        self.assertEqual(vet.co_payments[0].amount, ("pct", ("num", Decimal(20))))
        self.assertEqual(vet.co_payments[0].condition, (">=", ("name", "pet_age"), ("num", Decimal(9))))
        self.assertEqual(vet.depreciation[0].op, "x")

    def test_claim_fact_usable_only_in_its_own_claim(self):
        with self.assertRaises(ParseError) as cm:
            parse(LIFE.replace('    asks\n      condition: text\n', '    decline when cause is suicide because "x"\n'))
        self.assertIn("cause", str(cm.exception))

    def test_scenario_with_facts(self):
        p = parse(LIFE + 'rating\n  base 100\nscenario "s"\n  given sum_assured 100000, term_years 20, pet_age 3\n  when bound on 2026-01-01\n  when claim Death for 0 on 2026-06-01 with death_certificate, cause suicide\n  expect claim declined "Suicide in the first year"\n')
        self.assertEqual(p.scenarios[0].steps[1].tokens[-3:], ["death_certificate", ",", "cause", "suicide"][-3:])


class NonRenewable(unittest.TestCase):
    def test_renewal_none(self):
        p = parse('product "X"\nlifecycle\n  renewal: none\n')
        self.assertFalse(p.lifecycle.renewable)
        self.assertTrue(parse('product "X"\n').lifecycle.renewable)


MOTOR = '''
product "Motor"

inputs
  vehicle_value: money
  ncd_years: integer
  voluntary_excess: money

cover "Accidental Damage"
  limit vehicle_value
  excess
    driver_age < 25: 550 + voluntary_excess
    otherwise: 250 + voluntary_excess

cover Windscreen
  limit 1000
  excess 75

lifecycle
  renewal
    index ncd_years by 1, at most 9

claims
  claim "Accidental Damage"
    asks
      driver_age: integer
      fault: yes/no
    pays claimed amount up to limit, less excess
    counts towards claims in term when fault is yes
  claim Windscreen
    pays claimed amount up to limit, less excess
    does not count towards claims in term
  after 1 claim in term
    renewal
      index ncd_years by -2, at least 0
'''


class MotorFeatures(unittest.TestCase):
    def test_excess_table_uses_claim_facts(self):
        p = parse(MOTOR)
        rows = p.cover("Accidental Damage").excess.rows
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].condition, ("<", ("name", "driver_age"), ("num", Decimal(25))))
        self.assertIsNone(rows[1].condition)
        self.assertIsNone(p.cover("Accidental Damage").excess.amount)

    def test_excess_table_must_end_with_otherwise(self):
        with self.assertRaises(ParseError) as cm:
            parse(MOTOR.replace("    otherwise: 250 + voluntary_excess\n", ""))
        self.assertIn("line 11", str(cm.exception))
        self.assertIn("otherwise", str(cm.exception))

    def test_excess_table_may_only_use_facts_some_claim_asks(self):
        with self.assertRaises(ParseError) as cm:
            parse(MOTOR.replace("driver_age < 25", "pilot_age < 25"))
        self.assertIn("pilot_age", str(cm.exception))

    def test_index_bounds_and_negative(self):
        p = parse(MOTOR)
        self.assertEqual(p.lifecycle.renewal_index[0], ("ncd_years", "+", ("num", Decimal(1)), None, Decimal(9)))
        imposed = p.claims_terms[0][1]  # (count, terms, unless)
        self.assertEqual(imposed.renewal_index, [("ncd_years", "+", ("neg", ("num", Decimal(2))), Decimal(0), None)])

    def test_counting(self):
        p = parse(MOTOR)
        self.assertEqual(p.claims["Accidental Damage"].counts, ("is", ("name", "fault"), ("bool", True)))
        self.assertEqual(p.claims["Windscreen"].counts, ("bool", False))


class ClaimsLoadingSingular(unittest.TestCase):
    def test_after_one_claim_singular(self):
        p = parse('product "X"\ninputs\n  a: money\ncover V\n  limit a\nclaims\n  claim V\n    pays claimed amount\n  after 1 claim in term: renewal load x 1.30\n')
        self.assertEqual(p.claims_loading, [(1, Decimal("1.30"), None)])


class FixedBenefitWithClauses(unittest.TestCase):
    def test_pays_amount_then_clauses(self):
        p = parse('product "X"\ninputs\n  benefit: money\ncover I\n  limit benefit * 12 per term\nclaims\n  claim I\n    asks\n      months: integer\n    pays benefit * months, up to limit\n')
        self.assertEqual(p.claims["I"].pays_amount, ("*", ("name", "benefit"), ("name", "months")))
        self.assertEqual(p.claims["I"].pays, ["limit"])


TABLES = HEADER + '''
table "Age and lock" keyed on rider_age, security
  rider_age, security, rate, excess
  17-24, gold, 1.20, 50
  17-24, *, 1.50, 100
  25+, *, 1.00, 50
'''


class ItemsFromFile(unittest.TestCase):
    def test_given_collection_from_csv(self):
        import os, tempfile
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "bikes.csv"), "w") as f:
                f.write("value,age,security\n2000,0,gold\n1000,3,silver\n")
            p = parse(FLEET + 'scenario "file"\n  given rider_age 30\n  given bikes from "bikes.csv"\n', base=d)
            self.assertEqual(p.scenarios[-1].given["bikes"], [
                {"value": Decimal(2000), "age": Decimal(0), "security": "gold"},
                {"value": Decimal(1000), "age": Decimal(3), "security": "silver"}])

    def test_csv_errors_name_the_row(self):
        import os, tempfile
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "bikes.csv"), "w") as f:
                f.write("value,age\n2000,0\n")
            with self.assertRaisesRegex(ParseError, "line 50: bikes.csv row 2: bike is missing security"):
                parse(FLEET + 'scenario "file"\n  given rider_age 30\n  given bikes from "bikes.csv"\n', base=d)
            with open(os.path.join(d, "bikes.csv"), "w") as f:
                f.write("value,age,security\n2000,0,platinum\n")
            with self.assertRaisesRegex(ParseError, "line 50: bikes.csv row 2: security is choice, cannot be 'platinum'"):
                parse(FLEET + 'scenario "file"\n  given rider_age 30\n  given bikes from "bikes.csv"\n', base=d)
            with self.assertRaisesRegex(ParseError, "line 50: cannot read 'nowhere.csv'"):
                parse(FLEET + 'scenario "file"\n  given rider_age 30\n  given bikes from "nowhere.csv"\n', base=d)


class PerItemCovers(unittest.TestCase):
    def test_cover_using_item_fields_is_per_item(self):
        p = parse(FLEET)
        self.assertEqual(p.cover("Theft").item, "bike")

    def test_cover_using_no_item_field_is_not(self):
        p = parse(FLEET + 'cover Liability\n  limit 1000000\n')
        self.assertEqual(p.cover("Liability").item, "")


class Tables(unittest.TestCase):
    def test_inline_table(self):
        p = parse(TABLES)
        t = p.tables["Age and lock"]
        self.assertEqual(t.keys, ["rider_age", "security"])
        self.assertEqual(t.values, ["rate", "excess"])
        self.assertEqual(len(t.rows), 3)
        self.assertEqual(t.line, 14)

    def test_table_from_file(self):
        import os, tempfile
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "rates.csv"), "w") as f:
                f.write("rider_age,security,rate\n17-24,*,1.5\n25+,*,1.0\n")
            p = parse(HEADER + '\ntable "Rates" from "rates.csv" keyed on rider_age, security\n', base=d)
            self.assertEqual(len(p.tables["Rates"].rows), 2)

    def test_missing_file_reports_line(self):
        with self.assertRaisesRegex(ParseError, "line 14: cannot read 'nowhere.csv'"):
            parse(HEADER + '\ntable "Rates" from "nowhere.csv" keyed on rider_age\n')

    def test_key_must_be_an_input(self):
        with self.assertRaisesRegex(ParseError, "line 14: unknown input 'postcode'"):
            parse(HEADER + '\ntable "Rates" keyed on postcode\n  postcode, rate\n  M1, 1\n')

    def test_cells_are_checked_against_the_key_input(self):
        with self.assertRaisesRegex(ParseError, "line 14: Rates row 3: 'glod' is not one of bronze, silver, gold"):
            parse(HEADER + '\ntable "Rates" keyed on rider_age, security\n  rider_age, security, rate\n  17-24, gold, 1\n  25+, glod, 2\n')
        with self.assertRaisesRegex(ParseError, "line 14: Rates row 2: 'young' is not a number"):
            parse(HEADER + '\ntable "Rates" keyed on rider_age\n  rider_age, rate\n  young, 1\n')

    def test_item_field_and_provided_field_cells_are_checked_too(self):
        with self.assertRaisesRegex(ParseError, "line 48: T row 2: 'platinum' is not one of bronze, silver, gold"):
            parse(FLEET + 'table "T" keyed on security\n  security, v\n  platinum, 1\n')

    def test_table_errors_report_line(self):
        with self.assertRaisesRegex(ParseError, "line 14: Rates has no column 'security'"):
            parse(HEADER + '\ntable "Rates" keyed on rider_age, security\n  rider_age, rate\n  17-24, 1\n')

    def test_duplicate_table_name(self):
        with self.assertRaisesRegex(ParseError, "line 19: table 'Age and lock' is already declared"):
            parse(TABLES + 'table "Age and lock" keyed on rider_age\n  rider_age, rate\n  17+, 1\n')

    def test_single_row_factor_from_table(self):
        p = parse(TABLES + 'rating\n  base 100\n  factor "Age and lock" x rate from "Age and lock" when racing is no\n')
        step = p.rating[1]
        self.assertEqual(step.kind, "factor")
        self.assertEqual([(r.condition, r.op, r.amount) for r in step.rows], [(None, "x", ("lookup", "rate", "Age and lock"))])
        self.assertEqual(step.condition, ("is", ("name", "racing"), ("bool", False)))

    def test_lookup_anywhere_an_amount_goes(self):
        p = parse(TABLES + 'cover Theft\n  limit bike_value\n  excess excess from "Age and lock"\n')
        self.assertEqual(p.covers[0].excess.amount, ("lookup", "excess", "Age and lock"))

    def test_unknown_table_in_expression(self):
        with self.assertRaisesRegex(ParseError, "line 20: unknown table 'Other'"):
            parse(TABLES + 'rating\n  base rate from "Other"\n')

    def test_unknown_column_in_expression(self):
        with self.assertRaisesRegex(ParseError, "line 20: 'Age and lock' has no column 'fee'; its values are rate, excess"):
            parse(TABLES + 'rating\n  base fee from "Age and lock"\n')


class Formulas(unittest.TestCase):
    def test_power_and_functions_in_a_step(self):
        p = parse(HEADER + 'rating\n  base 100 * ( rider_age / 30 ) ^ 2\n  add round ( exp ( 0.01 * bike_value ) , 0.01 )\n')
        self.assertEqual(p.rating[0].amount, ("*", ("num", Decimal(100)), ("^", ("/", ("name", "rider_age"), ("num", Decimal(30))), ("num", Decimal(2)))))
        self.assertEqual(p.rating[1].amount[0], "fn")

    def test_unknown_function_reports_line(self):
        with self.assertRaisesRegex(ParseError, "line 14: unknown function 'sin'"):
            parse(HEADER + 'rating\n  base sin ( rider_age )\n')


class Interpolation(unittest.TestCase):
    CURVE = HEADER + '\ntable "Curve" keyed on rider_age, security\n  rider_age, security, rate\n  20, *, 1\n  40, *, 2\n'

    def test_interpolated_lookup(self):
        p = parse(self.CURVE + 'rating\n  base rate from "Curve" interpolated geometrically on rider_age\n')
        self.assertEqual(p.rating[0].amount, ("interp", "rate", "Curve", "rider_age", "geometrically"))

    def test_key_must_be_a_table_key(self):
        with self.assertRaisesRegex(ParseError, "line 19: 'Curve' is not keyed on bike_value; its keys are rider_age, security"):
            parse(self.CURVE + 'rating\n  base rate from "Curve" interpolated on bike_value\n')
