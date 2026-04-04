"""Unit tests for tools/action_stub.py."""

import json

from tools.action_stub import (
    ACTION_STUB_TOOL_DEFINITIONS,
    propose_change,
    request_approval,
)


# ---------------------------------------------------------------------------
# propose_change tests
# ---------------------------------------------------------------------------


class TestProposeChange:
    def _parse(self, plan: str) -> dict:
        return json.loads(propose_change(plan))

    def test_returns_valid_json(self):
        result = propose_change("Restart the app service")
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_required_fields_present(self):
        payload = self._parse("Update the network firewall rules")
        for field in ("id", "description", "risk_level", "affected_services", "rollback_plan", "estimated_duration"):
            assert field in payload, f"Missing field: {field}"

    def test_description_matches_plan(self):
        plan = "Scale up the compute cluster"
        payload = self._parse(plan)
        assert payload["description"] == plan

    def test_id_is_non_empty_string(self):
        payload = self._parse("Some change")
        assert isinstance(payload["id"], str)
        assert len(payload["id"]) > 0

    def test_affected_services_is_list(self):
        payload = self._parse("Restart the database")
        assert isinstance(payload["affected_services"], list)
        assert len(payload["affected_services"]) > 0

    def test_status_is_proposed(self):
        payload = self._parse("Restart the app service")
        assert payload["status"] == "proposed"

    def test_disclaimer_present(self):
        payload = self._parse("Some change")
        assert "disclaimer" in payload
        assert len(payload["disclaimer"]) > 0

    # --- risk level inference ---

    def test_low_risk_plan(self):
        payload = self._parse("Review the configuration")
        assert payload["risk_level"] == "low"

    def test_medium_risk_plan(self):
        payload = self._parse("Restart the app service pods")
        assert payload["risk_level"] == "medium"

    def test_high_risk_plan_delete(self):
        payload = self._parse("Delete the old storage buckets")
        assert payload["risk_level"] == "high"

    def test_high_risk_plan_drop(self):
        payload = self._parse("Drop the legacy database tables")
        assert payload["risk_level"] == "high"

    def test_high_risk_plan_terminate(self):
        payload = self._parse("Terminate the idle VM nodes")
        assert payload["risk_level"] == "high"

    # --- human approval gate ---

    def test_high_risk_includes_human_approval_gate(self):
        payload = self._parse("Delete all stale compute nodes")
        assert "human_approval_gate" in payload
        gate = payload["human_approval_gate"]
        assert gate["required"] is True
        assert "human approval" in gate["message"].lower()

    def test_low_risk_no_human_approval_gate(self):
        payload = self._parse("Check the monitoring dashboard")
        assert "human_approval_gate" not in payload

    def test_medium_risk_no_human_approval_gate(self):
        payload = self._parse("Restart the web app service")
        assert "human_approval_gate" not in payload

    # --- each call produces a unique id ---

    def test_unique_ids_across_calls(self):
        ids = {self._parse("Same plan")["id"] for _ in range(10)}
        # At least 2 distinct IDs among 10 calls (probability of all same is astronomically low)
        assert len(ids) > 1

    # --- affected service inference ---

    def test_gpu_plan_detects_compute(self):
        payload = self._parse("Scale up the GPU compute nodes")
        assert "compute-cluster" in payload["affected_services"]

    def test_network_plan_detects_network(self):
        payload = self._parse("Update the network NSG rules")
        assert "network" in payload["affected_services"]

    def test_database_plan_detects_database(self):
        payload = self._parse("Migrate the SQL database to new server")
        assert "database" in payload["affected_services"]

    def test_unknown_plan_falls_back_to_general(self):
        payload = self._parse("Do something vague")
        assert "general-infrastructure" in payload["affected_services"]

    # --- no external side effects ---

    def test_no_external_modification(self):
        # Calling multiple times with same plan must not raise and must always
        # return a valid, purely synthetic payload.
        for _ in range(5):
            result = propose_change("Purge all logs")
            parsed = json.loads(result)
            assert parsed["status"] == "proposed"


# ---------------------------------------------------------------------------
# request_approval tests
# ---------------------------------------------------------------------------


class TestRequestApproval:
    def _parse(self, change_id: str) -> dict:
        return json.loads(request_approval(change_id))

    def test_returns_valid_json(self):
        result = request_approval("00000000-0000-0000-0000-000000000000")
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_required_fields_present(self):
        payload = self._parse("00000000-0000-0000-0000-000000000000")
        for field in ("change_request_id", "approval_status", "reviewed_by", "message", "disclaimer"):
            assert field in payload, f"Missing field: {field}"

    def test_change_request_id_echoed(self):
        cid = "aaaabbbb-cccc-dddd-eeee-ffffffffffff"
        payload = self._parse(cid)
        assert payload["change_request_id"] == cid

    def test_status_is_valid_value(self):
        for suffix in "0123456789abcdef":
            cid = f"00000000-0000-0000-0000-00000000000{suffix}"
            payload = self._parse(cid)
            assert payload["approval_status"] in ("pending", "approved", "rejected")

    def test_disclaimer_present(self):
        payload = self._parse("00000000-0000-0000-0000-000000000000")
        assert "disclaimer" in payload
        assert len(payload["disclaimer"]) > 0

    def test_cycles_through_states(self):
        # Collect statuses for IDs ending in 0..f; must include all three states
        statuses = set()
        for suffix in "0123456789abcdef":
            cid = f"00000000-0000-0000-0000-00000000000{suffix}"
            payload = self._parse(cid)
            statuses.add(payload["approval_status"])
        assert statuses == {"pending", "approved", "rejected"}

    def test_invalid_id_falls_back_gracefully(self):
        payload = self._parse("not-a-valid-uuid-!!!!")
        assert payload["approval_status"] in ("pending", "approved", "rejected")

    def test_empty_id_falls_back_gracefully(self):
        payload = self._parse("")
        assert payload["approval_status"] in ("pending", "approved", "rejected")

    def test_message_present_for_pending(self):
        # UUID ending in '0' → index 0 % 3 == 0 → 'pending'
        cid = "00000000-0000-0000-0000-000000000000"
        payload = self._parse(cid)
        assert payload["approval_status"] == "pending"
        assert "awaiting" in payload["message"].lower() or "pending" in payload["message"].lower()

    def test_message_present_for_approved(self):
        # Find a UUID that yields 'approved'
        for suffix in "0123456789abcdef":
            cid = f"00000000-0000-0000-0000-00000000000{suffix}"
            payload = self._parse(cid)
            if payload["approval_status"] == "approved":
                assert "approved" in payload["message"].lower() or "proceed" in payload["message"].lower()
                break

    def test_message_present_for_rejected(self):
        for suffix in "0123456789abcdef":
            cid = f"00000000-0000-0000-0000-00000000000{suffix}"
            payload = self._parse(cid)
            if payload["approval_status"] == "rejected":
                assert "rejected" in payload["message"].lower() or "revise" in payload["message"].lower()
                break


# ---------------------------------------------------------------------------
# Tool schema tests
# ---------------------------------------------------------------------------


class TestToolDefinitions:
    def test_two_tool_definitions(self):
        assert len(ACTION_STUB_TOOL_DEFINITIONS) == 2

    def test_all_definitions_are_function_type(self):
        for defn in ACTION_STUB_TOOL_DEFINITIONS:
            assert defn["type"] == "function"

    def test_propose_change_schema(self):
        names = {d["function"]["name"] for d in ACTION_STUB_TOOL_DEFINITIONS}
        assert "propose_change" in names

    def test_request_approval_schema(self):
        names = {d["function"]["name"] for d in ACTION_STUB_TOOL_DEFINITIONS}
        assert "request_approval" in names

    def test_propose_change_has_plan_parameter(self):
        defn = next(d for d in ACTION_STUB_TOOL_DEFINITIONS if d["function"]["name"] == "propose_change")
        params = defn["function"]["parameters"]
        assert "plan" in params["properties"]
        assert "plan" in params["required"]

    def test_request_approval_has_change_request_id_parameter(self):
        defn = next(d for d in ACTION_STUB_TOOL_DEFINITIONS if d["function"]["name"] == "request_approval")
        params = defn["function"]["parameters"]
        assert "change_request_id" in params["properties"]
        assert "change_request_id" in params["required"]

    def test_all_parameters_have_descriptions(self):
        for defn in ACTION_STUB_TOOL_DEFINITIONS:
            for param_name, param_schema in defn["function"]["parameters"]["properties"].items():
                assert "description" in param_schema, f"Missing description for {param_name}"

    def test_all_functions_have_descriptions(self):
        for defn in ACTION_STUB_TOOL_DEFINITIONS:
            assert "description" in defn["function"]
            assert len(defn["function"]["description"]) > 0
