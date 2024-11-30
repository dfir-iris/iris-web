from unittest import TestCase

from tests.test_helper import TestHelper


class TestCaseRestV2CaseEndpoints(TestCase):
    """Responsible for testing the V2 Case endpoints."""
    
    def setUp(self) -> None:
        self._test_helper = TestHelper()
        self._client = self._test_helper.get_flask_test_client()

    def test_get_all(self):
        req = self._test_helper.perform_request(self, "v2_api.case.get_cases", method="get")
        print(req)