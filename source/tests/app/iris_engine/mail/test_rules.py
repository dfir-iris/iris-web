#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org

"""Unit tests for the mail rules regex predicate.

Kept pure-python — the `_regex_matches` helper is the entire
predicate logic and doesn't touch the DB. The full `evaluate_rules`
function needs a Flask app context (SQLAlchemy query), which is
covered by the docker-compose integration tests.
"""

from unittest import TestCase

from app.iris_engine.mail.rules import _regex_matches


class TestRegexMatches(TestCase):

    def test_none_pattern_matches_anything(self):
        self.assertTrue(_regex_matches(None, 'anything'))
        self.assertTrue(_regex_matches(None, None))
        self.assertTrue(_regex_matches('', 'anything'))

    def test_none_value_is_no_match_when_pattern_set(self):
        self.assertFalse(_regex_matches('foo', None))

    def test_simple_prefix_matches(self):
        self.assertTrue(_regex_matches(r'^alerts', 'alerts@example.com'))

    def test_case_insensitive_by_default(self):
        # The router only cares about content match, not case — a rule
        # like `abuse@` should match `Abuse@company.com` too.
        self.assertTrue(_regex_matches(r'abuse@', 'Abuse@Company.com'))

    def test_mid_string_pattern(self):
        self.assertTrue(_regex_matches(r'\bCRITICAL\b',
                                        'Subject: [critical] queue full'))

    def test_pattern_that_should_not_match(self):
        self.assertFalse(_regex_matches(r'^alerts', 'no-alerts@example.com'))

    def test_bad_regex_is_treated_as_no_match(self):
        # A stray `(` from an admin typo should not raise into the
        # poller — the router logs and skips the rule.
        self.assertFalse(_regex_matches(r'(unclosed', 'anything'))
