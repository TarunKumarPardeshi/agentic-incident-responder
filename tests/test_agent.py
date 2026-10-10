"""Unit tests for IncidentAgent and MCP tools."""
import pytest
from src.agent import IncidentAgent
from src.tools import registry, ToolRegistry


def test_tool_registry_registration_and_execution():
    """Test registering and running custom tools."""
    test_reg = ToolRegistry()
    
    @test_reg.register("mock_ping", "Pings host", {"type": "object"})
    def mock_ping(host: str):
        return f"pong-{host}"

    assert len(test_reg.schemas) == 1
    assert test_reg.schemas[0]["name"] == "mock_ping"
    assert test_reg.execute("mock_ping", host="10.0.0.1") == "pong-10.0.0.1"


def test_incident_agent_triage_flow():
    """Test full triage lifecycle of an incident alert."""
    agent = IncidentAgent()
    alert = {
        "incident_id": "INC-TEST-01",
        "service": "checkout-service",
        "title": "500 Error rate spike",
        "error_rate_pct": 32.0,
    }
    
    report = agent.triage(alert)
    
    assert report["incident_id"] == "INC-TEST-01"
    assert report["severity"] == "SEV-1"
    assert report["requires_human_approval"] is True
    assert report["approval_status"] == "PENDING_REVIEW"
    assert report["root_cause_analysis"]["category"] in [
        "MEMORY_LIMIT_EXCEEDED",
        "DATABASE_CONNECTION_EXHAUSTION",
        "APPLICATION_EXCEPTION",
    ]


def test_human_approval_gate_enforcement():
    """Verify that execution fails without explicit human approver."""
    agent = IncidentAgent()
    alert = {"service": "payment-api", "error_rate_pct": 20.0}
    report = agent.triage(alert)

    # Missing approver must raise PermissionError
    with pytest.raises(PermissionError):
        agent.execute_remediation(report, approved_by="", dry_run=False)

    # Valid approver executes cleanly
    res = agent.execute_remediation(report, approved_by="sre-oncall@company.com", dry_run=True)
    assert res["status"] == "dry_run_success"
    assert res["approved_by"] == "sre-oncall@company.com"
