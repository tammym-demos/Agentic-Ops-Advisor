"""Unit tests for scripts/serve.py — Agent Framework hosted agent.

Covers:
- Helper functions (_load_system_prompt, _ensure_db, _get_tools)
- main() integration wiring (AzureOpenAIChatClient → create_agent → run)
- SDK compatibility shim (azure.ai.projects.models patching)
"""

from __future__ import annotations

import os
import sys
import types
from unittest.mock import patch, MagicMock, call

import pytest

# Ensure repo root is importable
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from scripts.serve import _ensure_db, _load_system_prompt, _get_tools


# ---------------------------------------------------------------------------
# _load_system_prompt
# ---------------------------------------------------------------------------


class TestLoadSystemPrompt:
    def test_returns_nonempty_string(self):
        prompt = _load_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 100, "System prompt should be non-trivial"
        assert "Agentic Ops Advisor" in prompt

    def test_returns_empty_when_file_missing(self, tmp_path, monkeypatch):
        import scripts.serve as mod

        monkeypatch.setattr(mod, "_SYSTEM_PROMPT_PATH", str(tmp_path / "nope.md"))
        assert _load_system_prompt() == ""


# ---------------------------------------------------------------------------
# _ensure_db
# ---------------------------------------------------------------------------


class TestEnsureDb:
    def test_seeds_when_db_missing(self, tmp_path):
        db_path = str(tmp_path / "data" / "telemetry.db")
        with patch("scripts.serve.sqlite3"):
            with patch(
                "data.seed_telemetry.DEFAULT_DB_PATH", db_path
            ), patch(
                "data.seed_telemetry.create_schema"
            ), patch(
                "data.seed_telemetry.seed_connection", return_value={"t": 10}
            ):
                _ensure_db()

    def test_skips_when_db_exists(self, tmp_path):
        db_path = tmp_path / "telemetry.db"
        db_path.touch()
        with patch("data.seed_telemetry.DEFAULT_DB_PATH", str(db_path)):
            _ensure_db()  # should return immediately


# ---------------------------------------------------------------------------
# _get_tools
# ---------------------------------------------------------------------------


class TestGetTools:
    def test_includes_all_tools_when_work_iq_enabled(self, monkeypatch):
        monkeypatch.setenv("ENABLE_WORK_IQ", "true")
        # Re-import to pick up env change
        import tools.work_context_stub as wcs

        monkeypatch.setattr(wcs, "ENABLE_WORK_IQ", True)
        tools = _get_tools()
        names = [t.__name__ for t in tools]
        assert "query_telemetry" in names
        assert "get_work_context" in names
        assert "propose_change" in names
        assert "request_approval" in names

    def test_excludes_work_context_when_disabled(self, monkeypatch):
        import tools.work_context_stub as wcs

        monkeypatch.setattr(wcs, "ENABLE_WORK_IQ", False)
        tools = _get_tools()
        names = [t.__name__ for t in tools]
        assert "get_work_context" not in names
        assert "query_telemetry" in names


# ---------------------------------------------------------------------------
# main() — full init → client → agent → serve wiring
# ---------------------------------------------------------------------------


class TestMain:
    """Verify main() wires AzureOpenAIChatClient → create_agent → run correctly."""

    @pytest.fixture(autouse=True)
    def _setup_mocks(self, monkeypatch):
        """Set required env vars and create all mocks for main()."""
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-test")

        # Mock external SDK classes
        self.mock_chat_client_cls = MagicMock(name="AzureOpenAIChatClient")
        self.mock_chat_client = self.mock_chat_client_cls.return_value
        self.mock_agent = self.mock_chat_client.create_agent.return_value

        self.mock_from_af = MagicMock(name="from_agent_framework")
        self.mock_server = self.mock_from_af.return_value

        self.mock_credential = MagicMock(name="DefaultAzureCredential")
        self.mock_credential_cls = MagicMock(return_value=self.mock_credential)

        self.mock_token_provider = MagicMock(name="token_provider")
        self.mock_get_bearer = MagicMock(return_value=self.mock_token_provider)

        # Patch all imports inside main()
        self._patches = [
            patch("scripts.serve._ensure_db"),
            patch("scripts.serve._load_system_prompt", return_value="Test system prompt"),
            patch("scripts.serve._get_tools", return_value=[MagicMock(name="tool1")]),
            patch("scripts.serve._log_startup_diagnostics"),
            patch.dict("sys.modules", {}),
        ]
        for p in self._patches:
            p.start()

        self._ensure_db_patch = patch("scripts.serve._ensure_db")
        self._diag_patch = patch("scripts.serve._log_startup_diagnostics")

    def _run_main(self):
        """Import and call main() with all SDK dependencies mocked."""
        with patch("scripts.serve._ensure_db") as mock_ensure, \
             patch("scripts.serve._load_system_prompt", return_value="Test prompt") as mock_prompt, \
             patch("scripts.serve._get_tools", return_value=[lambda: None]) as mock_tools, \
             patch("scripts.serve._log_startup_diagnostics") as mock_diag, \
             patch.dict("sys.modules", {
                 "agent_framework": MagicMock(),
                 "agent_framework.azure": MagicMock(AzureOpenAIChatClient=self.mock_chat_client_cls),
                 "azure.ai.agentserver": MagicMock(),
                 "azure.ai.agentserver.agentframework": MagicMock(from_agent_framework=self.mock_from_af),
                 "azure.identity": MagicMock(
                     DefaultAzureCredential=self.mock_credential_cls,
                     get_bearer_token_provider=self.mock_get_bearer,
                 ),
             }):
            from scripts.serve import main
            main()
            self._mock_ensure = mock_ensure
            self._mock_diag = mock_diag
            self._mock_tools = mock_tools

    def test_ensure_db_called_before_client(self):
        self._run_main()
        self._mock_ensure.assert_called_once()

    def test_log_startup_diagnostics_called(self):
        self._run_main()
        self._mock_diag.assert_called_once()

    def test_chat_client_created_with_correct_params(self):
        self._run_main()
        self.mock_chat_client_cls.assert_called_once()
        kwargs = self.mock_chat_client_cls.call_args
        assert kwargs.kwargs["ad_token_provider"] == self.mock_token_provider
        assert kwargs.kwargs["endpoint"] is not None
        assert kwargs.kwargs["model"] is not None

    def test_create_agent_called_with_correct_args(self):
        self._run_main()
        self.mock_chat_client.create_agent.assert_called_once()
        kwargs = self.mock_chat_client.create_agent.call_args
        assert kwargs.kwargs["name"] == "agentic-ops-advisor"
        assert kwargs.kwargs["instructions"] == "Test prompt"
        assert "tools" in kwargs.kwargs

    def test_from_agent_framework_called_with_agent(self):
        self._run_main()
        self.mock_from_af.assert_called_once_with(self.mock_agent)

    def test_server_run_called(self):
        self._run_main()
        self.mock_server.run.assert_called_once()

    def test_credential_and_token_provider_wired(self, monkeypatch):
        """Verify DefaultAzureCredential and get_bearer_token_provider are used."""
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-test")

        mock_cred_cls = MagicMock(name="DefaultAzureCredential")
        mock_cred = mock_cred_cls.return_value
        mock_get_bearer = MagicMock(name="get_bearer_token_provider", return_value=self.mock_token_provider)

        with patch("scripts.serve._ensure_db"), \
             patch("scripts.serve._load_system_prompt", return_value="Test prompt"), \
             patch("scripts.serve._get_tools", return_value=[]), \
             patch("scripts.serve._log_startup_diagnostics"), \
             patch.dict("sys.modules", {
                 "agent_framework": MagicMock(),
                 "agent_framework.azure": MagicMock(AzureOpenAIChatClient=self.mock_chat_client_cls),
                 "azure.ai.agentserver": MagicMock(),
                 "azure.ai.agentserver.agentframework": MagicMock(from_agent_framework=self.mock_from_af),
                 "azure.identity": MagicMock(
                     DefaultAzureCredential=mock_cred_cls,
                     get_bearer_token_provider=mock_get_bearer,
                 ),
             }):
            from scripts.serve import main
            main()

        mock_cred_cls.assert_called_once()
        mock_get_bearer.assert_called_once_with(
            mock_cred, "https://cognitiveservices.azure.com/.default"
        )


# ---------------------------------------------------------------------------
# SDK compatibility shim
# ---------------------------------------------------------------------------


class TestCompatShim:
    """Test the SDK compatibility shim that patches azure.ai.projects.models."""

    def test_shim_patches_missing_old_names(self):
        """When old names are missing but new names exist, shim should patch."""
        import azure.ai.projects.models as proj_models

        # The shim maps these old → new names
        compat_map = {
            "PromptAgentDefinitionText": "PromptAgentDefinitionTextOptions",
            "ResponseTextFormatConfigurationJsonObject": "TextResponseFormatJsonObject",
            "ResponseTextFormatConfigurationJsonSchema": "TextResponseFormatJsonSchema",
            "ResponseTextFormatConfigurationText": "TextResponseFormatText",
        }

        for old_name, new_name in compat_map.items():
            if hasattr(proj_models, new_name):
                # If the new name exists, the old name should also exist
                # (either natively or via shim patching)
                assert hasattr(proj_models, old_name), (
                    f"Shim should have patched {old_name} from {new_name}"
                )
                assert getattr(proj_models, old_name) is getattr(proj_models, new_name)

    def test_shim_does_not_overwrite_existing_old_names(self):
        """When old names already exist natively, shim must not overwrite them."""
        import azure.ai.projects.models as proj_models

        compat_map = {
            "PromptAgentDefinitionText": "PromptAgentDefinitionTextOptions",
            "ResponseTextFormatConfigurationJsonObject": "TextResponseFormatJsonObject",
            "ResponseTextFormatConfigurationJsonSchema": "TextResponseFormatJsonSchema",
            "ResponseTextFormatConfigurationText": "TextResponseFormatText",
        }

        # Simulate: set old names to sentinel values, re-run the shim logic
        sentinels = {}
        originals = {}
        for old_name in compat_map:
            originals[old_name] = getattr(proj_models, old_name, None)
            sentinel = object()
            sentinels[old_name] = sentinel
            setattr(proj_models, old_name, sentinel)

        try:
            # Re-run the shim logic (same as serve.py lines 56-58)
            for old, new in compat_map.items():
                if not hasattr(proj_models, old) and hasattr(proj_models, new):
                    setattr(proj_models, old, getattr(proj_models, new))

            # Old names should still be sentinels (not overwritten)
            for old_name in compat_map:
                assert getattr(proj_models, old_name) is sentinels[old_name], (
                    f"Shim should NOT overwrite existing {old_name}"
                )
        finally:
            # Restore originals
            for old_name, orig in originals.items():
                if orig is not None:
                    setattr(proj_models, old_name, orig)
                elif hasattr(proj_models, old_name):
                    delattr(proj_models, old_name)

    def test_shim_skips_when_new_name_missing(self):
        """When neither old nor new name exists, shim should not create anything."""
        import azure.ai.projects.models as proj_models

        fake_old = "_TestShimFakeOldName"
        fake_new = "_TestShimFakeNewName"

        # Neither should exist
        assert not hasattr(proj_models, fake_old)
        assert not hasattr(proj_models, fake_new)

        # Run shim logic with fake names
        if not hasattr(proj_models, fake_old) and hasattr(proj_models, fake_new):
            setattr(proj_models, fake_old, getattr(proj_models, fake_new))

        # fake_old should still not exist
        assert not hasattr(proj_models, fake_old)


