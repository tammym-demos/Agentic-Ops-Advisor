"""
Tests for tools/work_context_stub.py and tools/work_context_mcp.py.

These tests validate:
- The Work IQ stub returns the expected synthetic data shapes.
- The MCP server tool listing and dispatch logic work correctly.
- MCP auth can be enforced or skipped based on MCP_REQUIRE_AUTH.
- ENABLE_MCP=false causes the module-level guard to exit.
"""

from __future__ import annotations

import base64
import importlib
import json
import sys
import time
import types as python_types
import unittest
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# work_context_stub tests
# ---------------------------------------------------------------------------


class TestWorkContextStub(unittest.TestCase):
    """Unit tests for the Work IQ context stub."""

    def setUp(self):
        # Ensure ENABLE_WORK_IQ is on for these tests
        import os

        os.environ["ENABLE_WORK_IQ"] = "true"
        # Force re-evaluation of the feature flag by reloading the module
        if "tools.work_context_stub" in sys.modules:
            del sys.modules["tools.work_context_stub"]
        import tools.work_context_stub as stub

        self.stub = stub

    def test_get_change_events_returns_list(self):
        events = self.stub.get_change_events("gpu-cluster")
        self.assertIsInstance(events, list)
        self.assertGreater(len(events), 0)

    def test_change_event_has_required_fields(self):
        events = self.stub.get_change_events("gpu-cluster")
        for event in events:
            self.assertIn("id", event)
            self.assertIn("type", event)
            self.assertIn("description", event)

    def test_get_decisions_returns_list(self):
        decisions = self.stub.get_decisions("network")
        self.assertIsInstance(decisions, list)
        self.assertGreater(len(decisions), 0)

    def test_get_ownership_returns_dict(self):
        ownership = self.stub.get_ownership("gpu-cluster")
        self.assertIsInstance(ownership, dict)
        self.assertIn("team", ownership)
        self.assertIn("primary", ownership)

    def test_get_ownership_unknown_service_returns_default(self):
        ownership = self.stub.get_ownership("totally-unknown-service-xyz")
        self.assertEqual(ownership["team"], "SRE")

    def test_get_runbooks_returns_list(self):
        runbooks = self.stub.get_runbooks("network")
        self.assertIsInstance(runbooks, list)
        self.assertGreater(len(runbooks), 0)

    def test_runbook_has_title_and_url(self):
        runbooks = self.stub.get_runbooks("gpu-cluster")
        for rb in runbooks:
            self.assertIn("title", rb)
            self.assertIn("url", rb)

    def test_get_full_context_includes_all_keys(self):
        ctx = self.stub.get_full_context("gpu-cluster")
        for key in ("service", "disclaimer", "change_events", "decisions", "ownership", "runbooks"):
            self.assertIn(key, ctx)

    def test_get_full_context_disclaimer_present(self):
        ctx = self.stub.get_full_context("gpu-cluster")
        self.assertIn("Work IQ", ctx["disclaimer"])

    def test_enable_work_iq_false_returns_empty(self):
        import os

        os.environ["ENABLE_WORK_IQ"] = "false"
        if "tools.work_context_stub" in sys.modules:
            del sys.modules["tools.work_context_stub"]
        stub = importlib.import_module("tools.work_context_stub")

        self.assertEqual(stub.get_change_events("gpu-cluster"), [])
        self.assertEqual(stub.get_decisions("gpu-cluster"), [])
        self.assertEqual(stub.get_ownership("gpu-cluster"), {})
        self.assertEqual(stub.get_runbooks("gpu-cluster"), [])

        # Restore
        os.environ["ENABLE_WORK_IQ"] = "true"


# ---------------------------------------------------------------------------
# work_context_mcp tests (unit — no real MCP transport)
# ---------------------------------------------------------------------------


class TestWorkContextMcpDisabled(unittest.TestCase):
    """Ensure the module exits when ENABLE_MCP is false."""

    def test_exits_when_flag_disabled(self):
        """Module-level guard should call sys.exit(0) when ENABLE_MCP is false."""
        import os

        os.environ["ENABLE_MCP"] = "false"
        # Remove cached module so the top-level code re-runs
        for mod in list(sys.modules.keys()):
            if "work_context_mcp" in mod:
                del sys.modules[mod]

        with self.assertRaises(SystemExit) as cm:
            importlib.import_module("tools.work_context_mcp")

        self.assertEqual(cm.exception.code, 0)


class TestWorkContextMcpEnabled(unittest.IsolatedAsyncioTestCase):
    """Test MCP handler logic when ENABLE_MCP is enabled."""

    def setUp(self):
        import os

        os.environ["ENABLE_MCP"] = "true"
        os.environ["ENABLE_WORK_IQ"] = "true"
        os.environ["MCP_REQUIRE_AUTH"] = "false"

        # Remove cached module so it reloads with the flag enabled
        for mod in list(sys.modules.keys()):
            if "work_context_mcp" in mod:
                del sys.modules[mod]

    def _load_mcp_module(self):
        """Load the MCP module, stubbing out the mcp package if unavailable."""
        try:
            import mcp  # noqa: F401 — check if available
        except ImportError:
            # Provide a minimal mcp stub so the module can be imported in CI
            # without installing the full mcp package.
            self._inject_mcp_stub()

        for mod in list(sys.modules.keys()):
            if "work_context_mcp" in mod:
                del sys.modules[mod]

        return importlib.import_module("tools.work_context_mcp")

    @staticmethod
    def _make_token(claims: dict[str, object]) -> str:
        def _b64url(data: dict[str, object]) -> str:
            encoded = base64.urlsafe_b64encode(json.dumps(data).encode("utf-8")).decode("utf-8")
            return encoded.rstrip("=")

        return f"{_b64url({'alg': 'none', 'typ': 'JWT'})}.{_b64url(claims)}."

    def _inject_mcp_stub(self):
        """Inject a minimal mcp package stub into sys.modules."""
        mcp_mod = python_types.ModuleType("mcp")
        mcp_types_mod = python_types.ModuleType("mcp.types")
        mcp_server_mod = python_types.ModuleType("mcp.server")
        mcp_stdio_mod = python_types.ModuleType("mcp.server.stdio")

        class _TextContent:
            def __init__(self, *, type, text):
                self.type = type
                self.text = text

        class _ImageContent:
            pass

        class _EmbeddedResource:
            pass

        class _Tool:
            def __init__(self, *, name, description, inputSchema):
                self.name = name
                self.description = description
                self.inputSchema = inputSchema

        mcp_types_mod.TextContent = _TextContent
        mcp_types_mod.ImageContent = _ImageContent
        mcp_types_mod.EmbeddedResource = _EmbeddedResource
        mcp_types_mod.Tool = _Tool

        class _Server:
            def __init__(self, name):
                self.name = name
                self._list_tools_handler = None
                self._call_tool_handler = None

            def list_tools(self):
                def decorator(fn):
                    self._list_tools_handler = fn
                    return fn

                return decorator

            def call_tool(self):
                def decorator(fn):
                    self._call_tool_handler = fn
                    return fn

                return decorator

            def create_initialization_options(self):
                return {}

            async def run(self, *args, **kwargs):
                pass

        mcp_server_mod.Server = _Server
        mcp_stdio_mod.stdio_server = MagicMock()

        sys.modules["mcp"] = mcp_mod
        sys.modules["mcp.types"] = mcp_types_mod
        sys.modules["mcp.server"] = mcp_server_mod
        sys.modules["mcp.server.stdio"] = mcp_stdio_mod

    async def test_list_tools_returns_expected_names(self):
        mod = self._load_mcp_module()
        tools = await mod.handle_list_tools()
        tool_names = {t.name for t in tools}
        expected = {
            "get_change_events",
            "get_decisions",
            "get_ownership",
            "get_runbooks",
            "get_full_context",
        }
        self.assertEqual(tool_names, expected)

    async def test_call_tool_get_change_events(self):
        mod = self._load_mcp_module()
        result = await mod.handle_call_tool("get_change_events", {"service": "gpu-cluster"})
        self.assertEqual(len(result), 1)
        data = json.loads(result[0].text)
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

    async def test_call_tool_get_ownership(self):
        mod = self._load_mcp_module()
        result = await mod.handle_call_tool("get_ownership", {"service": "network"})
        data = json.loads(result[0].text)
        self.assertIn("team", data)

    async def test_call_tool_get_full_context(self):
        mod = self._load_mcp_module()
        result = await mod.handle_call_tool("get_full_context", {"service": "cost"})
        data = json.loads(result[0].text)
        self.assertIn("change_events", data)
        self.assertIn("decisions", data)
        self.assertIn("ownership", data)
        self.assertIn("runbooks", data)

    async def test_call_tool_unknown_raises(self):
        mod = self._load_mcp_module()
        with self.assertRaises(ValueError):
            await mod.handle_call_tool("nonexistent_tool", {"service": "gpu-cluster"})

    async def test_call_tool_result_is_valid_json(self):
        mod = self._load_mcp_module()
        for tool_name in ("get_change_events", "get_decisions", "get_runbooks", "get_full_context"):
            result = await mod.handle_call_tool(tool_name, {"service": "gpu-cluster"})
            # Should not raise
            json.loads(result[0].text)

    async def test_tool_descriptions_are_non_empty(self):
        mod = self._load_mcp_module()
        tools = await mod.handle_list_tools()
        for tool in tools:
            self.assertTrue(tool.description.strip())

    async def test_tool_input_schemas_have_service_property(self):
        mod = self._load_mcp_module()
        tools = await mod.handle_list_tools()
        for tool in tools:
            props = tool.inputSchema.get("properties", {})
            self.assertIn("service", props, f"Tool {tool.name} missing 'service' in inputSchema")


class TestWorkContextMcpAuth(unittest.IsolatedAsyncioTestCase):
    """Test Azure AD token validation paths for MCP tool calls."""

    def setUp(self):
        import os

        os.environ["ENABLE_MCP"] = "true"
        os.environ["ENABLE_WORK_IQ"] = "true"
        os.environ["MCP_REQUIRE_AUTH"] = "true"
        os.environ["AZURE_TENANT_ID"] = "tenant-1234"
        os.environ["SRE_AGENT_RESOURCE_ID"] = "59f0a04a-b322-4310-adc9-39ac41e9631e"

        for mod in list(sys.modules.keys()):
            if "work_context_mcp" in mod:
                del sys.modules[mod]

    def _load_mcp_module(self):
        try:
            import mcp  # noqa: F401 — check if available
        except ImportError:
            TestWorkContextMcpEnabled()._inject_mcp_stub()

        for mod in list(sys.modules.keys()):
            if "work_context_mcp" in mod:
                del sys.modules[mod]

        return importlib.import_module("tools.work_context_mcp")

    @staticmethod
    def _make_token(claims: dict[str, object]) -> str:
        def _b64url(data: dict[str, object]) -> str:
            encoded = base64.urlsafe_b64encode(json.dumps(data).encode("utf-8")).decode("utf-8")
            return encoded.rstrip("=")

        return f"{_b64url({'alg': 'none', 'typ': 'JWT'})}.{_b64url(claims)}."

    async def test_call_tool_requires_token_when_auth_enabled(self):
        mod = self._load_mcp_module()

        with self.assertRaises(PermissionError):
            await mod.handle_call_tool("get_change_events", {"service": "gpu-cluster"})

    async def test_call_tool_accepts_matching_token(self):
        mod = self._load_mcp_module()
        token = self._make_token(
            {
                "aud": "59f0a04a-b322-4310-adc9-39ac41e9631e",
                "tid": "tenant-1234",
                "iss": "https://login.microsoftonline.com/tenant-1234/v2.0",
                "exp": int(time.time()) + 300,
            }
        )

        result = await mod.handle_call_tool(
            "get_change_events",
            {"service": "gpu-cluster", "_meta": {"authorization": f"Bearer {token}"}},
        )

        data = json.loads(result[0].text)
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

    async def test_call_tool_rejects_wrong_audience(self):
        mod = self._load_mcp_module()
        token = self._make_token(
            {
                "aud": "wrong-audience",
                "tid": "tenant-1234",
                "iss": "https://login.microsoftonline.com/tenant-1234/v2.0",
                "exp": int(time.time()) + 300,
            }
        )

        with self.assertRaises(PermissionError):
            await mod.handle_call_tool(
                "get_change_events",
                {"service": "gpu-cluster", "_auth_token": token},
            )


if __name__ == "__main__":
    unittest.main()
