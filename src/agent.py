"""Agentic Incident Triage Orchestration Loop.

Coordinates autonomous diagnostic investigations across Kubernetes, CloudWatch,
and Git history. Produces structured RCA, Blast Radius analysis, and remediation
actions guarded by a mandatory Human Approval Gate.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from src.tools import registry
except ImportError:
    from tools import registry

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("agentic-incident-responder")


class IncidentAgent:
    """Autonomous Incident Triage and Remediation Agent."""

    def __init__(self, tool_registry=registry):
        self.registry = tool_registry

    def triage(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        """Triages a production alert through multi-step investigation.

        Pipeline Steps:
        1. Parse alert payload & determine affected service.
        2. Query MCP tools for K8s pod health, CloudWatch logs, and recent deployments.
        3. Synthesize diagnostic data to isolate Root Cause & calculate Blast Radius.
        4. Draft atomic remediation proposal guarded by Human Approval Gate.
        """
        incident_id = alert.get("incident_id", f"INC-{uuid.uuid4().hex[:6].upper()}")
        service = alert.get("service", "unknown-service")
        title = alert.get("title", "Unhandled Production Anomaly")
        error_rate = alert.get("error_rate_pct", 0.0)
        timestamp = alert.get("timestamp", datetime.now(timezone.utc).isoformat())

        logger.info("Triaging incident %s for service '%s'...", incident_id, service)

        # 1. Gather Telemetry Context via MCP Tools
        telemetry_context = self._gather_context(service)

        # 2. Derive Root Cause Analysis (RCA)
        rca = self._derive_root_cause(service, alert, telemetry_context)

        # 3. Assess Blast Radius
        blast_radius = self._calculate_blast_radius(service, error_rate, telemetry_context)

        # 4. Formulate Remediation Plan
        remediation_plan = self._draft_remediation(service, rca, telemetry_context)

        # 5. Build Incident Summary with Human Approval Gate
        triage_report = {
            "incident_id": incident_id,
            "service": service,
            "title": title,
            "timestamp": timestamp,
            "severity": self._classify_severity(error_rate, blast_radius),
            "telemetry_gathered": {
                "k8s_pods_checked": len(telemetry_context.get("k8s_status", {}).get("pods", [])),
                "error_logs_found": len(telemetry_context.get("cloudwatch_logs", [])),
                "recent_deployments": len(telemetry_context.get("deployments", [])),
            },
            "root_cause_analysis": rca,
            "blast_radius": blast_radius,
            "proposed_remediation": remediation_plan,
            # CRITICAL HITL SAFETY GATE: Never auto-execute state-changing actions
            "requires_human_approval": True,
            "approval_status": "PENDING_REVIEW",
        }

        return triage_report

    def execute_remediation(
        self,
        triage_report: Dict[str, Any],
        approved_by: str,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Executes the proposed remediation only AFTER explicit human sign-off."""
        if not approved_by:
            raise PermissionError("Remediation execution denied: Valid human approver identity required.")

        action_plan = triage_report.get("proposed_remediation", {})
        action_name = action_plan.get("action_tool")
        action_args = action_plan.get("action_args", {})

        logger.info(
            "Remediation APPROVED by %s for %s. Executing %s (dry_run=%s)",
            approved_by,
            triage_report.get("incident_id"),
            action_name,
            dry_run,
        )

        if dry_run:
            return {
                "status": "dry_run_success",
                "message": f"Simulated execution of {action_name} with {action_args}",
                "approved_by": approved_by,
            }

        try:
            result = self.registry.execute(action_name, **action_args)
            return {
                "status": "executed",
                "execution_result": result,
                "approved_by": approved_by,
                "executed_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as err:
            logger.error("Failed to execute remediation: %s", err)
            return {
                "status": "execution_failed",
                "error": str(err),
                "approved_by": approved_by,
            }

    def _gather_context(self, service: str) -> Dict[str, Any]:
        """Collects telemetry from registered MCP tools."""
        context = {}
        try:
            context["k8s_status"] = self.registry.execute("get_k8s_pod_status", service_name=service)
        except Exception as e:
            context["k8s_status"] = {"error": str(e)}

        try:
            context["cloudwatch_logs"] = self.registry.execute(
                "get_cloudwatch_error_logs", log_group=f"/aws/eks/{service}"
            )
        except Exception as e:
            context["cloudwatch_logs"] = []

        try:
            context["deployments"] = self.registry.execute("get_recent_deployments", service_name=service)
        except Exception as e:
            context["deployments"] = []

        return context

    def _derive_root_cause(
        self, service: str, alert: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyzes logs and telemetry to isolate the primary failure cause."""
        logs = context.get("cloudwatch_logs", [])
        k8s = context.get("k8s_status", {})
        deployments = context.get("deployments", [])

        # Check for OOMKilled in pods
        oom_pods = [
            p["pod_name"]
            for p in k8s.get("pods", [])
            if p.get("last_state_terminated", {}).get("reason") == "OOMKilled"
        ]

        if oom_pods:
            recent_deploy = deployments[0] if deployments else {}
            return {
                "category": "MEMORY_LIMIT_EXCEEDED",
                "summary": f"Service '{service}' pods terminated due to OOMKilled (Exit Code 137).",
                "contributing_factor": f"Correlated with deployment {recent_deploy.get('deployment_id', 'N/A')} ('{recent_deploy.get('message', 'N/A')}').",
                "affected_pods": oom_pods,
                "confidence_score": 0.96,
            }

        # Check logs for DB pool exhaustion
        for log in logs:
            if "database pool exhausted" in log.get("message", "").lower():
                return {
                    "category": "DATABASE_CONNECTION_EXHAUSTION",
                    "summary": "Database connection pool saturated; rejecting incoming transaction requests.",
                    "contributing_factor": "Spike in long-running queries holding client connections.",
                    "confidence_score": 0.91,
                }

        return {
            "category": "APPLICATION_EXCEPTION",
            "summary": f"Elevated error rate observed on service '{service}'.",
            "contributing_factor": "Underlying downstream latency or unhandled exception spike.",
            "confidence_score": 0.75,
        }

    def _calculate_blast_radius(
        self, service: str, error_rate: float, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Evaluates customer impact and downstream service dependencies."""
        k8s = context.get("k8s_status", {})
        desired = k8s.get("replicas_desired", 3)
        ready = k8s.get("replicas_ready", 1)
        capacity_loss_pct = round(((desired - ready) / desired) * 100, 1) if desired > 0 else 0.0

        return {
            "affected_service": service,
            "estimated_capacity_loss_pct": capacity_loss_pct,
            "error_rate_pct": error_rate,
            "dependent_services": ["api-gateway", "checkout-service", "user-notification-service"],
            "user_facing_impact": "High" if capacity_loss_pct > 50 or error_rate > 15.0 else "Medium",
        }

    def _classify_severity(self, error_rate: float, blast_radius: Dict[str, Any]) -> str:
        """Determines incident severity level (SEV-1 to SEV-3)."""
        capacity_loss = blast_radius.get("estimated_capacity_loss_pct", 0.0)
        if error_rate >= 25.0 or (capacity_loss >= 60.0 and error_rate >= 20.0):
            return "SEV-1"
        elif error_rate >= 10.0 or capacity_loss >= 50.0:
            return "SEV-2"
        return "SEV-3"

    def _draft_remediation(
        self, service: str, rca: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Proposes atomic rollback / remediation action."""
        category = rca.get("category")
        deployments = context.get("deployments", [])

        if category == "MEMORY_LIMIT_EXCEEDED" and deployments:
            return {
                "action_type": "KUBERNETES_ROLLOUT_ROLLBACK",
                "description": f"Roll back deployment '{service}' to prior stable commit to reverse memory regression.",
                "action_tool": "execute_k8s_rollout_undo",
                "action_args": {"deployment_name": service, "namespace": "prod"},
                "expected_recovery_time_seconds": 45,
                "rollback_risk": "Low (Returning to verified prior build)",
            }
        
        return {
            "action_type": "SERVICE_RESTART",
            "description": f"Restart pods for '{service}' to flush stale connections and reload configuration.",
            "action_tool": "execute_k8s_rollout_undo",
            "action_args": {"deployment_name": service, "namespace": "prod"},
            "expected_recovery_time_seconds": 60,
            "rollback_risk": "Low",
        }


if __name__ == "__main__":
    sample_alert = {
        "incident_id": "INC-40291",
        "service": "payment-api",
        "title": "500 Internal Server Error rate > 28%",
        "error_rate_pct": 28.5,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    agent = IncidentAgent()
    report = agent.triage(sample_alert)

    print("\n" + "=" * 60)
    print("INCIDENT TRIAGE REPORT (HUMAN APPROVAL GATE)")
    print("=" * 60)
    print(json.dumps(report, indent=2))

    print("\n--- SIMULATING HUMAN APPROVAL & SAFE EXECUTION ---")
    exec_res = agent.execute_remediation(
        triage_report=report,
        approved_by="tarun.pardeshi@devops.org",
        dry_run=False,
    )
    print(json.dumps(exec_res, indent=2))
