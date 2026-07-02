#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org

"""Unit tests for the mention extractor.

These are pure-python — no Flask app context required — because the
extractor only touches SQLAlchemy for the legacy `@handle` fallback and
we can steer the code down the fast path (span-only content) or mock
the resolver for the fallback path.
"""

from unittest import TestCase
from unittest.mock import patch

from app.iris_engine.notifications.mentions import extract_mentioned_user_ids


class TestExtractMentionedUserIds(TestCase):

    def test_returns_empty_set_for_none(self):
        self.assertEqual(set(), extract_mentioned_user_ids(None))

    def test_returns_empty_set_for_empty(self):
        self.assertEqual(set(), extract_mentioned_user_ids(''))

    def test_extracts_single_user_span(self):
        content = (
            '<p>Hey <span data-mention="" data-kind="user" data-id="42" '
            'data-label="John Doe">@John Doe</span> please look</p>'
        )
        self.assertEqual({42}, extract_mentioned_user_ids(content))

    def test_extracts_multiple_user_spans(self):
        content = (
            '<span data-mention data-kind="user" data-id="1" data-label="a">@a</span> '
            'and '
            '<span data-mention data-kind="user" data-id="2" data-label="b">@b</span>'
        )
        self.assertEqual({1, 2}, extract_mentioned_user_ids(content))

    def test_dedupes_repeated_mentions(self):
        content = (
            '<span data-mention data-kind="user" data-id="5">@x</span> '
            '<span data-mention data-kind="user" data-id="5">@x</span>'
        )
        self.assertEqual({5}, extract_mentioned_user_ids(content))

    def test_ignores_non_user_kinds(self):
        # Asset / IOC / note / task chips share the mention span shape
        # but only `data-kind="user"` should count as a user mention.
        content = (
            '<span data-mention data-kind="asset" data-id="99">#server</span>'
            '<span data-mention data-kind="ioc" data-id="7">!ioc</span>'
            '<span data-mention data-kind="user" data-id="3">@alice</span>'
        )
        self.assertEqual({3}, extract_mentioned_user_ids(content))

    def test_ignores_malformed_id(self):
        content = (
            '<span data-mention data-kind="user" data-id="not-a-number">'
            '@x</span>'
        )
        # Regex requires \d+ so a non-numeric id doesn't match at all.
        self.assertEqual(set(), extract_mentioned_user_ids(content))

    def test_span_ordering_of_attributes_does_not_matter(self):
        # The TipTap renderer fixes an order, but the extractor should
        # not depend on it.
        content = (
            '<span data-id="12" data-kind="user" data-mention data-label="Z">'
            '@Z</span>'
        )
        self.assertEqual({12}, extract_mentioned_user_ids(content))

    @patch('app.iris_engine.notifications.mentions.resolve_user_handles')
    def test_legacy_handle_fallback_when_no_spans(self, mock_resolve):
        mock_resolve.return_value = {77}
        content = 'Hey @bob please review'
        self.assertEqual({77}, extract_mentioned_user_ids(content))
        mock_resolve.assert_called_once()
        # Called with the plain handle
        args, _ = mock_resolve.call_args
        self.assertIn('bob', args[0])

    @patch('app.iris_engine.notifications.mentions.resolve_user_handles')
    def test_legacy_fallback_is_skipped_when_spans_present(self, mock_resolve):
        # A note authored with the new editor should NOT double-count
        # via the handle regex — the `@Bob` text inside a live chip is
        # already covered by the span extraction.
        content = (
            'Hey <span data-mention data-kind="user" data-id="1" '
            'data-label="Bob">@Bob</span> please review'
        )
        self.assertEqual({1}, extract_mentioned_user_ids(content))
        mock_resolve.assert_not_called()

    @patch('app.iris_engine.notifications.mentions.resolve_user_handles')
    def test_legacy_handle_ignores_email_mid_word(self, mock_resolve):
        # `foo@bar.com` should not be parsed as `@bar.com` — the
        # non-word char requirement before `@` filters this out.
        mock_resolve.return_value = set()
        content = 'contact me at foo@bar.com'
        extract_mentioned_user_ids(content)
        # No handles resolved → the resolver would have been called
        # with an empty set OR not called at all. Either way, no
        # user id ends up returned.
        if mock_resolve.called:
            args, _ = mock_resolve.call_args
            self.assertNotIn('bar.com', args[0])
