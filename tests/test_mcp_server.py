import json
import unittest
from unittest.mock import patch

import httpx

from app import mcp_server


class MCPServerTests(unittest.TestCase):
    def use_transport(self, handler):
        client = httpx.Client
        transport = httpx.MockTransport(handler)
        mocked_client = patch(
            "app.mcp_server.httpx.Client",
            side_effect=lambda **kwargs: client(transport=transport, **kwargs),
        )
        mocked_client.start()
        self.addCleanup(mocked_client.stop)

    def test_search_uses_api_auth_and_clamps_limit(self):
        def handler(request):
            self.assertEqual(str(request.url), f"{mcp_server.BASE_URL}/api/search")
            self.assertEqual(request.method, "POST")
            self.assertEqual(request.headers["Authorization"], mcp_server.HEADERS["Authorization"])
            payload = json.loads(request.content)
            self.assertEqual(payload, {"query": "P5-35", "limit": mcp_server.settings.max_search_limit})
            return httpx.Response(200, json={"query": payload["query"], "items": [{"chunk_id": 1}]})

        self.use_transport(handler)
        result = mcp_server.search_documents("P5-35", limit=10000)
        self.assertEqual(result["items"], [{"chunk_id": 1}])

    def test_document_routes(self):
        def handler(request):
            self.assertEqual(request.method, "GET")
            return httpx.Response(200, json={"path": request.url.path})

        self.use_transport(handler)
        self.assertEqual(mcp_server.list_documents(), {"path": "/api/documents"})
        self.assertEqual(mcp_server.get_document(7), {"path": "/api/documents/7"})

    def test_connection_error_explains_how_to_start_api(self):
        def handler(request):
            raise httpx.ConnectError("connection refused", request=request)

        self.use_transport(handler)
        with self.assertRaisesRegex(RuntimeError, "Cannot reach knowledge API.*APP_HOST/APP_PORT"):
            mcp_server.list_documents()

    def test_authentication_error_does_not_echo_credentials_or_response(self):
        self.use_transport(lambda request: httpx.Response(401, text="private response body"))
        with self.assertRaises(RuntimeError) as caught:
            mcp_server.list_documents()
        self.assertIn("API_TOKEN", str(caught.exception))
        self.assertNotIn(mcp_server.HEADERS["Authorization"], str(caught.exception))
        self.assertNotIn("private response body", str(caught.exception))

    def test_missing_document_reports_status(self):
        self.use_transport(lambda request: httpx.Response(404))
        with self.assertRaisesRegex(RuntimeError, "HTTP 404 for /api/documents/999"):
            mcp_server.get_document(999)


if __name__ == "__main__":
    unittest.main()
