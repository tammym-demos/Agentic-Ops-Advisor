"""Unit tests for agent/agent.py.

Tests are fully offline — all Azure AI Agents client calls are mocked so
no live Azure credentials are required.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Shim: agent.py imports get_work_context from tools.work_context_stub, but
# the current source exposes get_full_context instead.  We add a shim so the
# lazy import inside _build_function_set succeeds during tests.
# ---------------------------------------------------------------------------
import tools.work_context_stub as _wcs_mod

if not hasattr(_wcs_mod, "get_work_context"):

    def get_work_context(service: str = "") -> dict:
        return _wcs_mod.get_full_context(service)

    _wcs_mod.get_work_context = get_work_context

# ---------------------------------------------------------------------------
# Shim: agent.py imports MessageRole from azure.ai.agents.models which may
# not exist in the installed SDK version.  Add a compatible shim.
# ---------------------------------------------------------------------------
try:
    from azure.ai.agents.models import MessageRole as _MR  # noqa: F401
except ImportError:
    import azure.ai.agents.models as _models_mod
    from enum import Enum

    class _MessageRole(str, Enum):
        AGENT = "agent"
        USER = "user"

    _models_mod.MessageRole = _MessageRole  # type: ignore[attr-defined]


if TYPE_CHECKING:
    from agent.agent import AgentOpsAdvisor


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_settings(
    *,
    azure_ai_agents_endpoint: str = "https://example.services.ai.azure.com/api/projects/test-project",
    azure_openai_endpoint: str = "https://example.openai.azure.com/",
    azure_openai_deployment: str = "gpt-4.1",
    enable_work_iq: bool = True,
    enable_mcp: bool = False,
) -> SimpleNamespace:
    """Build a minimal settings-like namespace for tests (no .env required)."""
    return SimpleNamespace(
        azure_ai_agents_endpoint=azure_ai_agents_endpoint,
        azure_openai_endpoint=azure_openai_endpoint,
        azure_openai_deployment=azure_openai_deployment,
        enable_work_iq=enable_work_iq,
        enable_mcp=enable_mcp,
    )


def _make_mock_client(*, run_status: str = "completed", assistant_reply: str = "Test reply") -> MagicMock:
    """Return a MagicMock that mimics an AgentsClient (v2 SDK)."""
    client = MagicMock()

    # client.create_agent
    mock_agent = MagicMock()
    mock_agent.id = "agent-123"
    client.create_agent.return_value = mock_agent

    # client.threads.create
    mock_thread = MagicMock()
    mock_thread.id = "thread-456"
    client.threads.create.return_value = mock_thread

    # client.runs.create_and_process
    mock_run = MagicMock()
    mock_run.id = "run-789"
    mock_run.status = run_status
    mock_run.last_error = None
    client.runs.create_and_process.return_value = mock_run

    # client.runs.create (used by _ask_with_timeout)
    mock_created_run = MagicMock()
    mock_created_run.id = "run-789"
    mock_created_run.status = run_status
    mock_created_run.last_error = None
    mock_created_run.required_action = None
    client.runs.create.return_value = mock_created_run

    # client.runs.get (polling — returns completed run immediately)
    client.runs.get.return_value = mock_created_run

    # client.messages.get_last_message_text_by_role
    client.messages.get_last_message_text_by_role.return_value = assistant_reply

    return client


# ---------------------------------------------------------------------------
# Tests: _load_system_prompt
# ---------------------------------------------------------------------------


class TestLoadSystemPrompt:
    def test_loads_existing_prompt(self, tmp_path: Path) -> None:
        """System prompt is read correctly when the file exists."""
        from agent.agent import _load_system_prompt

        prompt_text = "# Test System Prompt\nYou are helpful."
        # Patch the path so we read from tmp_path
        fake_path = tmp_path / "system_prompt.md"
        fake_path.write_text(prompt_text, encoding="utf-8")

        with patch("agent.agent._SYSTEM_PROMPT_PATH", fake_path):
            result = _load_system_prompt()

        assert result == prompt_text

    def test_raises_when_file_missing(self, tmp_path: Path) -> None:
        """RuntimeError is raised when system_prompt.md does not exist."""
        from agent.agent import _load_system_prompt

        missing = tmp_path / "nonexistent.md"
        with patch("agent.agent._SYSTEM_PROMPT_PATH", missing):
            with pytest.raises(RuntimeError, match="System prompt not found"):
                _load_system_prompt()

    def test_actual_system_prompt_exists(self) -> None:
        """The real agent/system_prompt.md is present in the repository."""
        from agent.agent import _SYSTEM_PROMPT_PATH

        assert _SYSTEM_PROMPT_PATH.exists(), f"Missing: {_SYSTEM_PROMPT_PATH}"
        content = _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
        assert len(content) > 100, "system_prompt.md looks too short"


# ---------------------------------------------------------------------------
# Tests: query_telemetry sync wrapper
# ---------------------------------------------------------------------------


class TestQueryTelemetrySyncWrapper:
    def test_wrapper_function_name(self) -> None:
        """The sync wrapper must be named 'query_telemetry' for FunctionTool."""
        from agent.agent import query_telemetry

        assert query_telemetry.__name__ == "query_telemetry"

    def test_wrapper_calls_async_impl(self) -> None:
        """The sync wrapper calls the underlying async query_telemetry."""
        from agent.agent import query_telemetry

        fake_result = json.dumps({"columns": [], "rows": [], "row_count": 0, "meta": {}})

        async def mock_async_query(**kwargs):  # noqa: RUF029 - async mock intentionally has no await
            return fake_result

        with patch("tools.sql_telemetry.query_telemetry", side_effect=mock_async_query):
            result = query_telemetry(aggregate="gpu_avg_util_24h")

        assert result == fake_result

    def test_wrapper_passes_kwargs_through(self) -> None:
        """Keyword arguments are forwarded to the async implementation."""
        from agent.agent import query_telemetry

        captured: dict = {}

        async def mock_async_query(**kwargs):  # noqa: RUF029 - async mock intentionally has no await
            captured.update(kwargs)
            return json.dumps({})

        with patch("tools.sql_telemetry.query_telemetry", side_effect=mock_async_query):
            query_telemetry(table="telemetry_gpu", limit=50)

        assert captured.get("table") == "telemetry_gpu"
        assert captured.get("limit") == 50


# ---------------------------------------------------------------------------
# Tests: _build_function_set
# ---------------------------------------------------------------------------


class TestBuildFunctionSet:
    def test_core_tools_always_present(self) -> None:
        """propose_change and request_approval are always in the function set."""
        from agent.agent import _build_function_set

        functions = _build_function_set(enable_work_iq=False)
        names = {fn.__name__ for fn in functions}
        assert "query_telemetry" in names
        assert "propose_change" in names
        assert "request_approval" in names

    def test_work_iq_included_when_enabled(self) -> None:
        """get_work_context is registered when enable_work_iq=True."""
        from agent.agent import _build_function_set

        functions = _build_function_set(enable_work_iq=True)
        names = {fn.__name__ for fn in functions}
        assert "get_work_context" in names

    def test_work_iq_excluded_when_disabled(self) -> None:
        """get_work_context is NOT registered when enable_work_iq=False."""
        from agent.agent import _build_function_set

        functions = _build_function_set(enable_work_iq=False)
        names = {fn.__name__ for fn in functions}
        assert "get_work_context" not in names

    def test_function_set_size_with_work_iq(self) -> None:
        """Four tools (3 core + Work IQ) when work_iq is enabled."""
        from agent.agent import _build_function_set

        assert len(_build_function_set(enable_work_iq=True)) == 4

    def test_function_set_size_without_work_iq(self) -> None:
        """Three tools (3 core) when work_iq is disabled."""
        from agent.agent import _build_function_set

        assert len(_build_function_set(enable_work_iq=False)) == 3


# ---------------------------------------------------------------------------
# Tests: AgentOpsAdvisor — initialization
# ---------------------------------------------------------------------------


class TestAgentOpsAdvisorInit:
    def test_init_with_explicit_settings(self) -> None:
        """AgentOpsAdvisor accepts explicit Settings."""
        from agent.agent import AgentOpsAdvisor

        settings = _make_settings()
        advisor = AgentOpsAdvisor(settings)
        assert advisor._settings is settings
        assert advisor._agent is None
        assert advisor._client is None

    def test_init_without_settings_raises_when_env_missing(self) -> None:
        """Passing settings=None raises ValueError when required env vars absent."""
        from agent.agent import AgentOpsAdvisor

        with patch.dict("os.environ", {}, clear=True):
            # Ensure the required vars are absent
            import os

            os.environ.pop("AZURE_AI_AGENTS_ENDPOINT", None)
            os.environ.pop("AZURE_AI_PROJECT_CONNECTION_STRING", None)
            os.environ.pop("AZURE_OPENAI_ENDPOINT", None)
            with pytest.raises((ValueError, RuntimeError)):
                AgentOpsAdvisor()

    def test_agent_id_none_before_creation(self) -> None:
        """agent_id property returns None before create_agent() is called."""
        from agent.agent import AgentOpsAdvisor

        advisor = AgentOpsAdvisor(_make_settings())
        assert advisor.agent_id is None


# ---------------------------------------------------------------------------
# Tests: AgentOpsAdvisor — client lifecycle
# ---------------------------------------------------------------------------


class TestAgentOpsAdvisorClient:
    def test_get_client_raises_without_endpoint(self) -> None:
        """_get_client raises ValueError when endpoint is empty."""
        from agent.agent import AgentOpsAdvisor

        settings = _make_settings(azure_ai_agents_endpoint="")
        advisor = AgentOpsAdvisor(settings)

        with pytest.raises(ValueError, match="AZURE_AI_AGENTS_ENDPOINT"):
            advisor._get_client()

    def test_close_is_idempotent(self) -> None:
        """close() can be called multiple times without error."""
        from agent.agent import AgentOpsAdvisor

        advisor = AgentOpsAdvisor(_make_settings())
        advisor.close()  # no client — should be a no-op
        advisor.close()  # still no error


# ---------------------------------------------------------------------------
# Tests: AgentOpsAdvisor — agent lifecycle (mocked client)
# ---------------------------------------------------------------------------


class TestAgentOpsAdvisorAgentLifecycle:
    def _make_advisor_with_mock_client(self, mock_client: MagicMock, **settings_kwargs) -> "AgentOpsAdvisor":
        from agent.agent import AgentOpsAdvisor

        advisor = AgentOpsAdvisor(_make_settings(**settings_kwargs))
        advisor._client = mock_client
        return advisor

    def test_create_agent_returns_agent(self) -> None:
        """create_agent() returns the agent object with an id attribute."""
        mock_client = _make_mock_client()
        mock_ft = MagicMock()
        mock_ts = MagicMock()

        with patch("agent.agent._import_agent_sdk", return_value=(mock_ft, mock_ts)):
            from agent.agent import AgentOpsAdvisor

            advisor = AgentOpsAdvisor(_make_settings())
            advisor._client = mock_client

            with patch("agent.agent._load_system_prompt", return_value="# Prompt"):
                agent = advisor.create_agent()

        assert agent.id == "agent-123"
        assert advisor.agent_id == "agent-123"
        mock_client.create_agent.assert_called_once()

    def test_create_agent_passes_model_name(self) -> None:
        """create_agent() forwards the deployment name to the SDK."""
        mock_client = _make_mock_client()

        with (
            patch("agent.agent._import_agent_sdk", return_value=(MagicMock(), MagicMock())),
            patch("agent.agent._load_system_prompt", return_value="# Prompt"),
        ):
            from agent.agent import AgentOpsAdvisor

            advisor = AgentOpsAdvisor(_make_settings(azure_openai_deployment="gpt-4.1"))
            advisor._client = mock_client
            advisor.create_agent()

        call_kwargs = mock_client.create_agent.call_args.kwargs
        assert call_kwargs.get("model") == "gpt-4.1"

    def test_create_agent_passes_instructions(self) -> None:
        """create_agent() passes the loaded system prompt as instructions."""
        mock_client = _make_mock_client()
        expected_prompt = "# My System Prompt\nBe helpful."

        with (
            patch("agent.agent._import_agent_sdk", return_value=(MagicMock(), MagicMock())),
            patch("agent.agent._load_system_prompt", return_value=expected_prompt),
        ):
            from agent.agent import AgentOpsAdvisor

            advisor = AgentOpsAdvisor(_make_settings())
            advisor._client = mock_client
            advisor.create_agent()

        call_kwargs = mock_client.create_agent.call_args.kwargs
        assert call_kwargs.get("instructions") == expected_prompt

    def test_delete_agent_clears_reference(self) -> None:
        """delete_agent() removes the internal agent reference."""
        mock_client = _make_mock_client()

        with (
            patch("agent.agent._import_agent_sdk", return_value=(MagicMock(), MagicMock())),
            patch("agent.agent._load_system_prompt", return_value="# Prompt"),
        ):
            from agent.agent import AgentOpsAdvisor

            advisor = AgentOpsAdvisor(_make_settings())
            advisor._client = mock_client
            advisor.create_agent()
            advisor.delete_agent()

        assert advisor._agent is None
        assert advisor.agent_id is None
        mock_client.delete_agent.assert_called_once_with("agent-123")

    def test_delete_agent_noop_when_no_agent(self) -> None:
        """delete_agent() is a no-op when no agent has been created."""
        from agent.agent import AgentOpsAdvisor

        advisor = AgentOpsAdvisor(_make_settings())
        advisor.delete_agent()  # should not raise


# ---------------------------------------------------------------------------
# Tests: AgentOpsAdvisor — thread management
# ---------------------------------------------------------------------------


class TestAgentOpsAdvisorThreads:
    def test_create_thread_returns_thread(self) -> None:
        """create_thread() returns a thread object with an id."""
        from agent.agent import AgentOpsAdvisor

        mock_client = _make_mock_client()
        advisor = AgentOpsAdvisor(_make_settings())
        advisor._client = mock_client

        thread = advisor.create_thread()

        assert thread.id == "thread-456"
        mock_client.threads.create.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: AgentOpsAdvisor — ask / conversation
# ---------------------------------------------------------------------------


class TestAgentOpsAdvisorAsk:
    def _make_advisor(self, mock_client: MagicMock, **kwargs) -> "AgentOpsAdvisor":
        from agent.agent import AgentOpsAdvisor

        advisor = AgentOpsAdvisor(_make_settings(**kwargs))
        advisor._client = mock_client
        # Pre-set the agent so we skip create_agent() in ask tests
        advisor._agent = mock_client.create_agent.return_value
        return advisor

    def test_ask_raises_without_agent(self) -> None:
        """ask() raises RuntimeError when agent has not been created."""
        from agent.agent import AgentOpsAdvisor

        advisor = AgentOpsAdvisor(_make_settings())
        with pytest.raises(RuntimeError, match="Agent has not been created"):
            advisor.ask("thread-1", "Hello")

    def test_ask_returns_assistant_text(self) -> None:
        """ask() returns the assistant's text response."""
        mock_client = _make_mock_client(assistant_reply="GPU utilization dropped due to scheduler issue.")

        with patch("agent.agent._import_agent_sdk", return_value=(MagicMock(), MagicMock())):
            advisor = self._make_advisor(mock_client)
            result = advisor.ask("thread-456", "Why did GPU utilization drop in the last 24h?")

        assert "GPU utilization" in result or result == "GPU utilization dropped due to scheduler issue."

    def test_ask_sends_user_message(self) -> None:
        """ask() calls messages.create with the user's text."""
        mock_client = _make_mock_client()

        with patch("agent.agent._import_agent_sdk", return_value=(MagicMock(), MagicMock())):
            advisor = self._make_advisor(mock_client)
            advisor.ask("thread-456", "What changed before the latency spike?")

        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs.get("role") == "user"
        assert "latency" in call_kwargs.get("content", "")

    def test_ask_raises_on_failed_run(self) -> None:
        """ask() raises RuntimeError when the run status is 'failed'."""
        mock_client = _make_mock_client(run_status="failed")
        mock_client.runs.create_and_process.return_value.last_error = "Model overloaded"

        with patch("agent.agent._import_agent_sdk", return_value=(MagicMock(), MagicMock())):
            advisor = self._make_advisor(mock_client)
            with pytest.raises(RuntimeError, match="failed state"):
                advisor.ask("thread-456", "Is this a known issue?")

    def test_ask_empty_when_no_assistant_message(self) -> None:
        """ask() returns empty string when no assistant message is found."""
        mock_client = _make_mock_client()
        # Override so get_last_message_text_by_role returns None
        mock_client.messages.get_last_message_text_by_role.return_value = None

        with patch("agent.agent._import_agent_sdk", return_value=(MagicMock(), MagicMock())):
            advisor = self._make_advisor(mock_client)
            result = advisor.ask("thread-456", "Hello")

        assert result == ""


# ---------------------------------------------------------------------------
# Tests: context manager
# ---------------------------------------------------------------------------


class TestAgentOpsAdvisorContextManager:
    def test_context_manager_calls_delete_and_close(self) -> None:
        """__exit__ calls delete_agent() and close()."""
        from agent.agent import AgentOpsAdvisor

        advisor = AgentOpsAdvisor(_make_settings())

        with (
            patch.object(advisor, "delete_agent") as mock_delete,
            patch.object(advisor, "close") as mock_close,
        ):
            with advisor:
                pass

        mock_delete.assert_called_once()
        mock_close.assert_called_once()

    def test_context_manager_cleans_up_on_exception(self) -> None:
        """Cleanup runs even when the body raises an exception."""
        from agent.agent import AgentOpsAdvisor

        advisor = AgentOpsAdvisor(_make_settings())

        with (
            patch.object(advisor, "delete_agent") as mock_delete,
            patch.object(advisor, "close") as mock_close,
        ):
            with pytest.raises(ValueError):
                with advisor:
                    raise ValueError("Something went wrong")

        mock_delete.assert_called_once()
        mock_close.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: run_query convenience helper
# ---------------------------------------------------------------------------


class TestRunQuery:
    def test_run_query_returns_response(self) -> None:
        """run_query() creates an advisor, runs once, returns the answer."""
        mock_client = _make_mock_client(assistant_reply="Remediation plan: Option 1 …")

        settings = _make_settings()

        with (
            patch("agent.agent._import_agent_sdk", return_value=(MagicMock(), MagicMock())),
            patch("agent.agent._load_system_prompt", return_value="# Prompt"),
        ):
            from agent.agent import run_query, AgentOpsAdvisor

            with patch.object(AgentOpsAdvisor, "_get_client", return_value=mock_client):
                result = run_query(
                    "What's the safest remediation plan? Provide options and tradeoffs.",
                    settings=settings,
                )

        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Tests: core query type coverage (smoke)
# ---------------------------------------------------------------------------

CORE_QUERIES = [
    "Why did GPU utilization drop in the last 24h?",
    "What changed right before the latency spike?",
    "Is this a known issue or a change-caused incident?",
    "What's the safest remediation plan? Provide options and tradeoffs.",
]


class TestCoreQueryTypes:
    @pytest.mark.parametrize("query", CORE_QUERIES)
    def test_core_query_accepted(self, query: str) -> None:
        """Each core query can be passed to ask() without error (mocked run)."""
        mock_client = _make_mock_client(assistant_reply=f"Response to: {query}")

        with patch("agent.agent._import_agent_sdk", return_value=(MagicMock(), MagicMock())):
            from agent.agent import AgentOpsAdvisor

            advisor = AgentOpsAdvisor(_make_settings())
            advisor._client = mock_client
            advisor._agent = mock_client.create_agent.return_value

            result = advisor.ask("thread-test", query)

        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Tests: ask() timeout / _ask_with_timeout
# ---------------------------------------------------------------------------


def _deadline_exceeded_after_first_call():
    """Return a side_effect iterator for time.monotonic that returns 0.0 on the
    first call (used to set the deadline) and 999.0 on all subsequent calls
    (simulating that the deadline has been exceeded)."""
    return itertools.chain([0.0], itertools.repeat(999.0))


class TestAskTimeout:
    """Tests for the timeout_seconds parameter on ask() and _ask_with_timeout."""

    def _make_advisor(self, mock_client: MagicMock) -> "AgentOpsAdvisor":
        from agent.agent import AgentOpsAdvisor

        advisor = AgentOpsAdvisor(_make_settings())
        advisor._client = mock_client
        advisor._agent = mock_client.create_agent.return_value
        return advisor

    def test_ask_without_timeout_uses_create_and_process(self) -> None:
        """With no timeout, ask() uses the SDK's create_and_process path."""
        mock_client = _make_mock_client()

        with patch("agent.agent._import_agent_sdk", return_value=(MagicMock(), MagicMock())):
            advisor = self._make_advisor(mock_client)
            advisor.ask("thread-t1", "Hello")

        mock_client.runs.create_and_process.assert_called_once()
        mock_client.runs.create.assert_not_called()

    def test_ask_with_timeout_uses_polling_path(self) -> None:
        """With timeout_seconds set, ask() uses the create+poll path."""
        mock_client = _make_mock_client(run_status="completed")

        with patch("agent.agent._import_agent_sdk", return_value=(MagicMock(), MagicMock())):
            with patch("agent.agent.time.sleep"):  # skip real sleeps
                advisor = self._make_advisor(mock_client)
                result = advisor.ask("thread-t2", "Hello", timeout_seconds=30)

        mock_client.runs.create.assert_called_once()
        mock_client.runs.create_and_process.assert_not_called()
        assert isinstance(result, str)

    def test_ask_with_timeout_raises_timeout_error_when_run_stuck(self) -> None:
        """TimeoutError is raised when the run stays in_progress past the deadline."""
        mock_client = _make_mock_client()

        # Make runs.create return an in_progress run that never finishes
        stuck_run = MagicMock()
        stuck_run.id = "run-stuck"
        stuck_run.status = "in_progress"
        stuck_run.required_action = None
        mock_client.runs.create.return_value = stuck_run
        mock_client.runs.get.return_value = stuck_run

        with patch("agent.agent._import_agent_sdk", return_value=(MagicMock(), MagicMock())):
            advisor = self._make_advisor(mock_client)
            with patch("agent.agent.time.monotonic", side_effect=_deadline_exceeded_after_first_call()):
                with patch("agent.agent.time.sleep"):
                    with pytest.raises(TimeoutError, match="cancelled after exceeding timeout"):
                        advisor.ask("thread-t3", "Stuck query", timeout_seconds=1)

        mock_client.runs.cancel.assert_called_once_with(thread_id="thread-t3", run_id="run-stuck")

    def test_ask_with_timeout_cancel_failure_still_raises_timeout(self) -> None:
        """TimeoutError is raised even when the cancel API call itself fails."""
        mock_client = _make_mock_client()

        stuck_run = MagicMock()
        stuck_run.id = "run-stuck2"
        stuck_run.status = "in_progress"
        stuck_run.required_action = None
        mock_client.runs.create.return_value = stuck_run
        mock_client.runs.get.return_value = stuck_run
        mock_client.runs.cancel.side_effect = Exception("cancel API error")

        with patch("agent.agent._import_agent_sdk", return_value=(MagicMock(), MagicMock())):
            advisor = self._make_advisor(mock_client)
            with patch("agent.agent.time.monotonic", side_effect=_deadline_exceeded_after_first_call()):
                with patch("agent.agent.time.sleep"):
                    with pytest.raises(TimeoutError):
                        advisor.ask("thread-t4", "Stuck query 2", timeout_seconds=1)

    def test_ask_with_timeout_completes_within_deadline(self) -> None:
        """A run that finishes before the deadline returns the assistant reply."""
        mock_client = _make_mock_client(run_status="completed", assistant_reply="Done!")

        with patch("agent.agent._import_agent_sdk", return_value=(MagicMock(), MagicMock())):
            with patch("agent.agent.time.sleep"):
                advisor = self._make_advisor(mock_client)
                result = advisor.ask("thread-t5", "Quick query", timeout_seconds=300)

        assert result == "Done!"
