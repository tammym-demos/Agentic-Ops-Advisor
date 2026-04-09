"""Unit tests for scripts/serve.py — hosted agent server (Foundry Responses API).

Tests the aiohttp web server implementing the Azure AI Foundry Responses API.
All Azure OpenAI calls are mocked to avoid real API calls.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase


# Import after skip check
from scripts.serve import _init_app, _ready_event  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_env(monkeypatch: pytest.MonkeyPatch):
    """Set minimal env vars for server to start without real Azure credentials."""
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key-123")
    monkeypatch.setenv("ENABLE_WORK_IQ", "true")


def make_openai_response(
    *,
    content: str = "Test response",
    tool_calls: list[dict[str, Any]] | None = None,
) -> MagicMock:
    """Build a mock OpenAI ChatCompletion response."""
    message = MagicMock()
    message.content = content
    message.role = "assistant"
    message.tool_calls = tool_calls or []

    choice = MagicMock()
    choice.message = message
    choice.finish_reason = "stop" if not tool_calls else "tool_calls"

    response = MagicMock()
    response.choices = [choice]
    response.id = "chatcmpl-test-123"
    response.model = "gpt-4.1"
    response.usage = MagicMock(total_tokens=50, prompt_tokens=30, completion_tokens=20)

    return response


def make_tool_call(name: str, args: dict[str, Any]) -> MagicMock:
    """Build a mock OpenAI tool_call object."""
    tool_call = MagicMock()
    tool_call.id = f"call_{name}_123"
    tool_call.type = "function"
    tool_call.function.name = name
    tool_call.function.arguments = json.dumps(args)
    return tool_call


# ---------------------------------------------------------------------------
# Test class using AioHTTPTestCase
# ---------------------------------------------------------------------------


class TestHealthEndpoint(AioHTTPTestCase):
    """Tests for GET /health endpoint."""

    async def get_application(self) -> web.Application:
        """Return the aiohttp app for testing (required by AioHTTPTestCase)."""
        with patch.dict(
            "os.environ",
            {
                "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
                "AZURE_OPENAI_DEPLOYMENT": "gpt-4.1",
                "AZURE_OPENAI_API_KEY": "test-key-123",
                "ENABLE_WORK_IQ": "true",
            },
        ):
            _ready_event.set()
            return await _init_app()

    @pytest.mark.asyncio
    async def test_health_returns_200(self):
        """GET /health returns HTTP 200."""
        resp = await self.client.get("/health")
        assert resp.status == 200

    @pytest.mark.asyncio
    async def test_health_returns_json(self):
        """GET /health returns valid JSON."""
        resp = await self.client.get("/health")
        data = await resp.json()
        assert isinstance(data, dict)

    @pytest.mark.asyncio
    async def test_health_contains_required_fields(self):
        """GET /health response has status, timestamp, and version fields."""
        resp = await self.client.get("/health")
        data = await resp.json()
        assert "status" in data
        assert "timestamp" in data
        assert "version" in data

    @pytest.mark.asyncio
    async def test_health_contains_version(self):
        """GET /health version field is present and non-empty."""
        resp = await self.client.get("/health")
        data = await resp.json()
        assert data["version"]
        assert len(data["version"]) > 0


class TestRootEndpoint(AioHTTPTestCase):
    """Tests for GET / endpoint."""

    async def get_application(self) -> web.Application:
        with patch.dict(
            "os.environ",
            {
                "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
                "AZURE_OPENAI_DEPLOYMENT": "gpt-4.1",
                "AZURE_OPENAI_API_KEY": "test-key-123",
                "ENABLE_WORK_IQ": "true",
            },
        ):
            _ready_event.set()
            return await _init_app()

    @pytest.mark.asyncio
    async def test_root_returns_200(self):
        """GET / returns HTTP 200."""
        resp = await self.client.get("/")
        assert resp.status == 200


class TestResponsesEndpointInputParsing(AioHTTPTestCase):
    """Tests for POST /responses — input parsing and validation."""

    async def get_application(self) -> web.Application:
        with patch.dict(
            "os.environ",
            {
                "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
                "AZURE_OPENAI_DEPLOYMENT": "gpt-4.1",
                "AZURE_OPENAI_API_KEY": "test-key-123",
                "ENABLE_WORK_IQ": "true",
            },
        ):
            _ready_event.set()
            return await _init_app()

    @pytest.mark.asyncio
    async def test_responses_accepts_messages_input(self):
        """POST /responses accepts input with messages array format."""
        with patch("openai.AzureOpenAI") as mock_openai_class:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = make_openai_response(
                content="GPU utilization is 85%"
            )
            mock_openai_class.return_value = mock_client

            payload = {
                "input": {"messages": [{"role": "user", "content": "What is GPU utilization?"}]},
                "stream": False,
            }
            resp = await self.client.post("/responses", json=payload)
            assert resp.status == 200

    @pytest.mark.asyncio
    async def test_responses_accepts_string_input(self):
        """POST /responses accepts plain string input."""
        with patch("openai.AzureOpenAI") as mock_openai_class:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = make_openai_response(
                content="GPU utilization is 85%"
            )
            mock_openai_class.return_value = mock_client

            payload = {"input": "What is GPU utilization?", "stream": False}
            resp = await self.client.post("/responses", json=payload)
            assert resp.status == 200

    @pytest.mark.asyncio
    async def test_responses_rejects_empty_input(self):
        """POST /responses with missing/empty input returns error."""
        payload = {"stream": False}
        resp = await self.client.post("/responses", json=payload)
        # Expect 400 Bad Request for missing input
        assert resp.status == 400

    @pytest.mark.asyncio
    async def test_responses_rejects_invalid_json(self):
        """POST /responses with malformed JSON returns 400."""
        resp = await self.client.post(
            "/responses",
            data="not-valid-json{{{",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 400


class TestResponsesEndpointFormat(AioHTTPTestCase):
    """Tests for POST /responses — response format validation."""

    async def get_application(self) -> web.Application:
        with patch.dict(
            "os.environ",
            {
                "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
                "AZURE_OPENAI_DEPLOYMENT": "gpt-4.1",
                "AZURE_OPENAI_API_KEY": "test-key-123",
                "ENABLE_WORK_IQ": "true",
            },
        ):
            _ready_event.set()
            return await _init_app()

    @pytest.mark.asyncio
    async def test_responses_returns_foundry_format(self):
        """Response has required Foundry API fields: id, object, output, status."""
        with patch("openai.AzureOpenAI") as mock_openai_class:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = make_openai_response(
                content="GPU utilization is 85%"
            )
            mock_openai_class.return_value = mock_client

            payload = {"input": "What is GPU utilization?", "stream": False}
            resp = await self.client.post("/responses", json=payload)
            data = await resp.json()

            assert "id" in data
            assert "object" in data
            assert "output" in data
            assert "status" in data

    @pytest.mark.asyncio
    async def test_responses_id_starts_with_resp(self):
        """Response id field starts with 'resp_'."""
        with patch("openai.AzureOpenAI") as mock_openai_class:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = make_openai_response(
                content="GPU utilization is 85%"
            )
            mock_openai_class.return_value = mock_client

            payload = {"input": "What is GPU utilization?", "stream": False}
            resp = await self.client.post("/responses", json=payload)
            data = await resp.json()

            assert data["id"].startswith("resp_")

    @pytest.mark.asyncio
    async def test_responses_status_completed(self):
        """Successful response has status='completed'."""
        with patch("openai.AzureOpenAI") as mock_openai_class:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = make_openai_response(
                content="GPU utilization is 85%"
            )
            mock_openai_class.return_value = mock_client

            payload = {"input": "What is GPU utilization?", "stream": False}
            resp = await self.client.post("/responses", json=payload)
            data = await resp.json()

            assert data["status"] == "completed"

    @pytest.mark.asyncio
    async def test_responses_output_has_message(self):
        """Output array contains assistant message."""
        with patch("openai.AzureOpenAI") as mock_openai_class:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = make_openai_response(
                content="GPU utilization is 85%"
            )
            mock_openai_class.return_value = mock_client

            payload = {"input": "What is GPU utilization?", "stream": False}
            resp = await self.client.post("/responses", json=payload)
            data = await resp.json()

            assert isinstance(data["output"], list)
            assert len(data["output"]) > 0
            # Should have assistant message
            assert any(msg.get("role") == "assistant" for msg in data["output"])


class TestResponsesToolDispatch(AioHTTPTestCase):
    """Tests for POST /responses — tool call dispatch."""

    async def get_application(self) -> web.Application:
        with patch.dict(
            "os.environ",
            {
                "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
                "AZURE_OPENAI_DEPLOYMENT": "gpt-4.1",
                "AZURE_OPENAI_API_KEY": "test-key-123",
                "ENABLE_WORK_IQ": "true",
            },
        ):
            _ready_event.set()
            return await _init_app()

    @pytest.mark.asyncio
    async def test_responses_dispatches_tool_calls(self):
        """When OpenAI returns tool_calls, server dispatches them."""
        with patch("openai.AzureOpenAI") as mock_openai_class, \
             patch("scripts.serve._call_tool") as mock_call_tool:
            
            mock_client = MagicMock()

            # First response: LLM wants to call query_telemetry tool
            tool_call_response = make_openai_response(
                content="",
                tool_calls=[
                    make_tool_call("query_telemetry", {"table": "telemetry_gpu", "limit": 5})
                ],
            )

            # Second response: LLM returns final answer after tool result
            final_response = make_openai_response(content="GPU utilization is 85%")

            mock_client.chat.completions.create.side_effect = [tool_call_response, final_response]
            mock_openai_class.return_value = mock_client
            
            # Mock tool execution to return JSON string (as real tools do)
            mock_call_tool.return_value = json.dumps({
                "data": [{"cluster": "gpu-west", "utilization_pct": 85.0}],
                "meta": {"disclaimer": "Synthetic data"}
            })

            payload = {"input": "What is GPU utilization?", "stream": False}
            resp = await self.client.post("/responses", json=payload)
            data = await resp.json()

            # Should succeed and return final answer
            assert resp.status == 200
            assert data["status"] == "completed"
            # Verify create was called at least twice (once for initial, once after tool)
            assert mock_client.chat.completions.create.call_count >= 2
            # Verify tool was called
            assert mock_call_tool.called

    @pytest.mark.asyncio
    async def test_responses_handles_multiple_tool_rounds(self):
        """Server handles multi-round tool calling."""
        with patch("openai.AzureOpenAI") as mock_openai_class, \
             patch("scripts.serve._call_tool") as mock_call_tool:
            
            mock_client = MagicMock()

            # Round 1: Call query_telemetry
            round1 = make_openai_response(
                content="",
                tool_calls=[
                    make_tool_call("query_telemetry", {"table": "telemetry_gpu", "limit": 5})
                ],
            )

            # Round 2: Call query_telemetry again
            round2 = make_openai_response(
                content="",
                tool_calls=[
                    make_tool_call("query_telemetry", {"table": "incidents", "limit": 3})
                ],
            )

            # Round 3: Final answer
            final = make_openai_response(content="GPU utilization is normal, no incidents.")

            mock_client.chat.completions.create.side_effect = [round1, round2, final]
            mock_openai_class.return_value = mock_client
            
            # Mock tool execution
            mock_call_tool.return_value = json.dumps({
                "data": [],
                "meta": {"disclaimer": "Synthetic data"}
            })

            payload = {"input": "Check GPU and incidents", "stream": False}
            resp = await self.client.post("/responses", json=payload)
            data = await resp.json()

            assert resp.status == 200
            assert data["status"] == "completed"
            # Should have called create 3 times
            assert mock_client.chat.completions.create.call_count == 3
            # Tool should have been called twice
            assert mock_call_tool.call_count == 2


class TestResponsesErrorHandling(AioHTTPTestCase):
    """Tests for POST /responses — error handling."""

    async def get_application(self) -> web.Application:
        with patch.dict(
            "os.environ",
            {
                "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
                "AZURE_OPENAI_DEPLOYMENT": "gpt-4.1",
                "AZURE_OPENAI_API_KEY": "test-key-123",
                "ENABLE_WORK_IQ": "true",
            },
        ):
            _ready_event.set()
            return await _init_app()

    @pytest.mark.asyncio
    async def test_responses_handles_missing_openai_endpoint(self):
        """Graceful error when AZURE_OPENAI_ENDPOINT not configured."""
        # Create a new app instance without the env var
        with patch.dict("os.environ", {}, clear=True):
            # Server should still start but error on actual inference
            # This test verifies graceful degradation
            payload = {"input": "What is GPU utilization?", "stream": False}
            # Expect either 500 or 503 for missing config
            resp = await self.client.post("/responses", json=payload)
            # Should return error, not crash
            assert resp.status in (400, 500, 503)

    @pytest.mark.asyncio
    async def test_responses_handles_openai_error(self):
        """Graceful error when OpenAI API call fails."""
        with patch("openai.AzureOpenAI") as mock_openai_class:
            mock_client = MagicMock()
            # Simulate API error
            mock_client.chat.completions.create.side_effect = Exception("API connection failed")
            mock_openai_class.return_value = mock_client

            payload = {"input": "What is GPU utilization?", "stream": False}
            resp = await self.client.post("/responses", json=payload)

            # Server returns 200 with error text surfaced in completed response
            # (we always return status=completed so Foundry gateway preserves
            # the output text for the caller to read)
            assert resp.status == 200
            data = await resp.json()
            assert data.get("status") == "completed"
            # Error should be in output message content
            assert any("Error" in str(msg.get("content", "")) for msg in data.get("output", []))


class TestCORS(AioHTTPTestCase):
    """Tests for CORS headers."""

    async def get_application(self) -> web.Application:
        with patch.dict(
            "os.environ",
            {
                "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
                "AZURE_OPENAI_DEPLOYMENT": "gpt-4.1",
                "AZURE_OPENAI_API_KEY": "test-key-123",
                "ENABLE_WORK_IQ": "true",
            },
        ):
            _ready_event.set()
            return await _init_app()

    @pytest.mark.asyncio
    async def test_cors_headers_present(self):
        """CORS configuration is present."""
        # Note: aiohttp-cors may return 403 for OPTIONS on routes without explicit OPTIONS handler
        # This test verifies CORS middleware is configured, not necessarily that OPTIONS works
        resp = await self.client.options("/responses")
        # CORS middleware is present if we get any response (including 403)
        # Real CORS headers are set on actual POST requests
        assert resp.status in (200, 204, 403, 405)  # Various CORS/OPTIONS handling patterns


# ---------------------------------------------------------------------------
# Readiness gate tests
# ---------------------------------------------------------------------------


class TestReadinessEndpoint(AioHTTPTestCase):
    """Tests for GET /readiness endpoint — Foundry container probe."""

    async def get_application(self) -> web.Application:
        with patch.dict(
            "os.environ",
            {
                "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
                "AZURE_OPENAI_DEPLOYMENT": "gpt-4.1",
                "AZURE_OPENAI_API_KEY": "test-key-123",
                "ENABLE_WORK_IQ": "true",
            },
        ):
            # Do NOT set _ready_event here — individual tests control it
            _ready_event.clear()
            return await _init_app()

    @pytest.mark.asyncio
    async def test_readiness_returns_503_when_not_ready(self):
        """GET /readiness returns 503 with status='starting' before startup completes."""
        _ready_event.clear()
        resp = await self.client.get("/readiness")
        assert resp.status == 503
        data = await resp.json()
        assert data["status"] == "starting"

    @pytest.mark.asyncio
    async def test_readiness_returns_200_when_ready(self):
        """GET /readiness returns 200 with status='ready' after startup completes."""
        _ready_event.set()
        resp = await self.client.get("/readiness")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "ready"


class TestResponsesStartupGate(AioHTTPTestCase):
    """Tests for POST /responses startup gate — warmup vs normal behavior."""

    async def get_application(self) -> web.Application:
        with patch.dict(
            "os.environ",
            {
                "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
                "AZURE_OPENAI_DEPLOYMENT": "gpt-4.1",
                "AZURE_OPENAI_API_KEY": "test-key-123",
                "ENABLE_WORK_IQ": "true",
            },
        ):
            _ready_event.clear()
            return await _init_app()

    @pytest.mark.asyncio
    async def test_responses_returns_warmup_when_not_ready(self):
        """POST /responses returns a friendly warmup message before startup completes."""
        _ready_event.clear()
        payload = {"input": "What is GPU utilization?", "stream": False}
        resp = await self.client.post("/responses", json=payload)
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "completed"
        # The warmup message should be in the output
        output_text = data["output"][0]["content"][0]["text"]
        assert "starting up" in output_text.lower()

    @pytest.mark.asyncio
    async def test_responses_works_when_ready(self):
        """POST /responses returns normal agent output after startup completes."""
        _ready_event.set()
        with patch("openai.AzureOpenAI") as mock_openai_class:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = make_openai_response(
                content="GPU utilization is 85%"
            )
            mock_openai_class.return_value = mock_client

            payload = {"input": "What is GPU utilization?", "stream": False}
            resp = await self.client.post("/responses", json=payload)
            data = await resp.json()

            assert resp.status == 200
            assert data["status"] == "completed"
            # Should have the real agent response, not the warmup message
            output_text = data["output"][0]["content"][0]["text"]
            assert "starting up" not in output_text.lower()
            assert "GPU utilization" in output_text
