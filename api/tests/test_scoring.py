# api/tests/test_scoring.py
from django.test import TestCase
from api.models import Lead, Offer
from api.scoring import calculate_rule_score

class RuleLayerTests(TestCase):
    def setUp(self):
        # Create a common offer used by tests
        self.offer_exact = Offer.objects.create(
            name="TestOffer Exact",
            value_props=["vp1"],
            ideal_use_cases=["SaaS", "Software"]
        )
        self.offer_adj = Offer.objects.create(
            name="TestOffer Adjacent",
            value_props=["vp1"],
            ideal_use_cases=["B2B SaaS mid-market"]
        )

    def test_decision_maker_full_match(self):
        """Decision maker + industry exact + all fields => 20 + 20 + 10 = 50"""
        lead = Lead.objects.create(
            name="John CEO",
            role="CEO",
            company="Acme",
            industry="SaaS",
            location="USA",
            linkedin_bio="bio"
        )
        score, reasoning = calculate_rule_score(lead, self.offer_exact)
        self.assertEqual(score, 50)
        self.assertIn("Role is decision maker (+20)", reasoning)
        self.assertIn("Industry matches ICP (+20)", reasoning)
        self.assertIn("All fields present (+10)", reasoning)

    def test_influencer_full_match(self):
        """Influencer + industry exact + all fields => 10 + 20 + 10 = 40"""
        lead = Lead.objects.create(
            name="Sara Lead",
            role="Lead Engineer",
            company="Acme",
            industry="Software",
            location="USA",
            linkedin_bio="bio"
        )
        score, reasoning = calculate_rule_score(lead, self.offer_exact)
        self.assertEqual(score, 40)
        self.assertIn("Role is influencer (+10)", reasoning)
        self.assertIn("Industry matches ICP (+20)", reasoning)
        self.assertIn("All fields present (+10)", reasoning)

    def test_role_not_relevant_missing_fields(self):
        """Role not relevant + industry adjacent + missing fields => 0 + 10 + 0 = 10"""
        lead = Lead.objects.create(
            name="NoRole",
            role="Engineer",              # not in decision_makers or influencers
            company="",                   # missing company -> completeness fails
            industry="UnknownIndustry",
            location="",
            linkedin_bio=""
        )
        score, reasoning = calculate_rule_score(lead, self.offer_adj)
        self.assertEqual(score, 10)
        self.assertIn("Role not relevant (+0)", reasoning)
        self.assertIn("Industry adjacent (+10)", reasoning)
        self.assertIn("Missing some fields (+0)", reasoning)

    def test_case_insensitive_industry_match(self):
        """Industry matching is case-insensitive"""
        lead = Lead.objects.create(
            name="Case Test",
            role="Manager",
            company="Co",
            industry="software",  # lower-case
            location="loc",
            linkedin_bio="bio"
        )
        score, reasoning = calculate_rule_score(lead, self.offer_exact)
        # Manager => decision maker (+20), industry exact (+20), completeness (+10) = 50
        self.assertEqual(score, 50)
        self.assertIn("Industry matches ICP (+20)", reasoning)

    def test_missing_completeness_no_bonus(self):
        """If any field empty -> completeness not awarded"""
        lead = Lead.objects.create(
            name="Partial",
            role="Manager",
            company="Acme",
            industry="SaaS",
            location="",               # empty -> completeness fails
            linkedin_bio="bio"
        )
        score, reasoning = calculate_rule_score(lead, self.offer_exact)
        # Manager + industry exact + missing completeness -> 20 + 20 + 0 = 40
        self.assertEqual(score, 40)
        self.assertIn("Missing some fields (+0)", reasoning)

    def test_influencer_adjacent_industry(self):
        """Influencer + adjacent industry + all fields => 10 + 10 + 10 = 30"""
        lead = Lead.objects.create(
            name="Influencer",
            role="Marketing Specialist",
            company="M",
            industry="SomeOther",   # not in offer_exact list so treated as adjacent
            location="loc",
            linkedin_bio="bio"
        )
        score, reasoning = calculate_rule_score(lead, self.offer_exact)
        self.assertEqual(score, 30)
        self.assertIn("Role is influencer (+10)", reasoning)
        self.assertIn("Industry adjacent (+10)", reasoning)
        self.assertIn("All fields present (+10)", reasoning)
