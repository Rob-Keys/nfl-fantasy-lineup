import base64
import json
import os
import unittest

from fantasy_lineup.handler import lambda_handler, parse_event_body


class HandlerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._previous_secret = os.environ.get("BACKEND_SHARED_SECRET")
        os.environ["BACKEND_SHARED_SECRET"] = "test-edge-secret"

    @classmethod
    def tearDownClass(cls):
        if cls._previous_secret is None:
            os.environ.pop("BACKEND_SHARED_SECRET", None)
        else:
            os.environ["BACKEND_SHARED_SECRET"] = cls._previous_secret

    def test_invalid_base64_request_is_a_client_error(self):
        response = lambda_handler(
            {
                "requestContext": {"http": {"method": "POST"}},
                "headers": {"x-internal-api-key": "test-edge-secret"},
                "body": "%%%",
                "isBase64Encoded": True,
            },
            None,
        )
        self.assertEqual(response["statusCode"], 400)

    def test_base64_body_is_decoded(self):
        payload = {"players": []}
        body = base64.b64encode(json.dumps(payload).encode()).decode()
        self.assertEqual(
            parse_event_body({"body": body, "isBase64Encoded": True}),
            payload,
        )

    def test_non_post_requests_are_rejected(self):
        response = lambda_handler(
            {"requestContext": {"http": {"method": "GET"}}, "body": "{}"}, None
        )
        self.assertEqual(response["statusCode"], 405)

    def test_post_without_edge_secret_is_rejected(self):
        response = lambda_handler(
            {
                "requestContext": {"http": {"method": "POST"}},
                "body": "{}",
            },
            None,
        )
        self.assertEqual(response["statusCode"], 401)

    def test_post_with_wrong_edge_secret_is_rejected(self):
        response = lambda_handler(
            {
                "requestContext": {"http": {"method": "POST"}},
                "headers": {"X-Internal-Api-Key": "wrong-secret"},
                "body": "{}",
            },
            None,
        )
        self.assertEqual(response["statusCode"], 401)

    def test_http_api_v2_post_body_is_supported(self):
        payload = {"players": []}
        body = json.dumps(payload)
        event = {"requestContext": {"http": {"method": "POST"}}, "body": body}
        self.assertEqual(parse_event_body(event), payload)

    def test_missing_body_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_event_body({"httpMethod": "POST"})


if __name__ == "__main__":
    unittest.main()
