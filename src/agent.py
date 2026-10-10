"""Agentic incident triage orchestration loop."""

class IncidentAgent:
    def triage(self, alert):
        # 1. gather context via MCP tools
        # 2. draft summary: cause, blast radius, remediation
        # 3. HUMAN APPROVAL GATE — never auto-executes
        return {"summary": "TODO", "requires_approval": True}
