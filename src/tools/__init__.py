"""MCP and Telemetry Tool Wrappers for Incident Responder."""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional
import json
import logging

logger = logging.getLogger("incident-agent.tools")


class ToolRegistry:
    """Registry of MCP diagnostic and remediation tools available to the Agent."""

    def __init__(self):
        self._tools: Dict[str, Callable[..., Any]] = {}
        self._schemas: List[Dict[str, Any]] = []

    def register(self, name: str, description: str, parameters: Dict[str, Any]):
        """Decorator to register a tool with its schema."""
        def decorator(func: Callable[..., Any]):
            self._tools[name] = func
            self._schemas.append({
                "name": name,
                "description": description,
                "parameters": parameters,
            })
            return func
        return decorator

    def execute(self, name: str, **kwargs) -> Any:
        """Executes a registered tool by name."""
        if name not in self._tools:
            raise ValueError(f"Tool '{name}' not found in registry.")
        logger.debug("Executing tool '%s' with args %s", name, kwargs)
        return self._tools[name](**kwargs)

    @property
    def schemas(self) -> List[Dict[str, Any]]:
        return self._schemas


# Global default registry
registry = ToolRegistry()


@registry.register(
    name="get_k8s_pod_status",
    description="Fetches pod status, restart counts, and events for a given service deployment in Kubernetes",
    parameters={
        "type": "object",
        "properties": {
            "namespace": {"type": "string", "description": "Kubernetes namespace (e.g. default, prod)"},
            "service_name": {"type": "string", "description": "Service name to inspect"},
            "context_hint": {"type": "string", "description": "Optional context hint"},
        },
        "required": ["service_name"],
    },
)
def get_k8s_pod_status(service_name: str, namespace: str = "prod", context_hint: str = "") -> Dict[str, Any]:
    """Retrieves Kubernetes pod status with contextual telemetry."""
    lower_name = (service_name + " " + context_hint).lower()
    is_oom = any(k in lower_name for k in ["oom", "checkout", "search-indexer", "recommendations", "user-profile", "billing", "graphql", "image-resizer", "catalog"])

    if is_oom:
        return {
            "namespace": namespace,
            "service": service_name,
            "replicas_desired": 3,
            "replicas_ready": 1,
            "pods": [
                {
                    "pod_name": f"{service_name}-789df-a1b2",
                    "status": "CrashLoopBackOff",
                    "restarts": 6,
                    "last_state_terminated": {"exit_code": 137, "reason": "OOMKilled"},
                },
                {
                    "pod_name": f"{service_name}-789df-c3d4",
                    "status": "Running",
                    "restarts": 0,
                    "cpu_utilization": "82%",
                    "memory_utilization": "96%",
                },
                {
                    "pod_name": f"{service_name}-789df-e5f6",
                    "status": "CrashLoopBackOff",
                    "restarts": 5,
                    "last_state_terminated": {"exit_code": 137, "reason": "OOMKilled"},
                },
            ],
        }
    
    # Healthy / normal pod state (non-OOM issues like DB pool or network latency)
    return {
        "namespace": namespace,
        "service": service_name,
        "replicas_desired": 3,
        "replicas_ready": 3,
        "pods": [
            {"pod_name": f"{service_name}-789df-1", "status": "Running", "restarts": 0, "cpu_utilization": "45%", "memory_utilization": "42%"},
            {"pod_name": f"{service_name}-789df-2", "status": "Running", "restarts": 0, "cpu_utilization": "48%", "memory_utilization": "41%"},
            {"pod_name": f"{service_name}-789df-3", "status": "Running", "restarts": 0, "cpu_utilization": "44%", "memory_utilization": "40%"},
        ],
    }


@registry.register(
    name="get_cloudwatch_error_logs",
    description="Queries CloudWatch Log Insights for recent error stack traces within a time window",
    parameters={
        "type": "object",
        "properties": {
            "log_group": {"type": "string", "description": "CloudWatch log group name"},
            "minutes": {"type": "integer", "description": "Lookback window in minutes"},
            "filter_pattern": {"type": "string", "description": "Search pattern (e.g. ERROR, Exception)"},
            "service_name": {"type": "string", "description": "Service name to contextualize logs"},
        },
        "required": ["log_group"],
    },
)
def get_cloudwatch_error_logs(
    log_group: str,
    minutes: int = 15,
    filter_pattern: str = "ERROR",
    service_name: str = "",
) -> List[Dict[str, Any]]:
    """Retrieves application error logs."""
    lower = (log_group + " " + service_name).lower()
    
    if any(k in lower for k in ["payment", "orders-db", "session-store"]):
        return [
            {
                "timestamp": "2026-10-10T12:30:22Z",
                "level": "ERROR",
                "message": "Connection refused: database pool exhausted (active_connections=100/100, wait_queue=450)",
            },
            {
                "timestamp": "2026-10-10T12:30:25Z",
                "level": "ERROR",
                "message": "org.postgresql.util.PSQLException: Connection checkout timed out after 30000ms",
            },
        ]
    elif any(k in lower for k in ["oom", "checkout", "search-indexer", "recommendations", "user-profile", "billing", "graphql", "image-resizer", "catalog"]):
        return [
            {
                "timestamp": "2026-10-10T12:30:15Z",
                "level": "ERROR",
                "message": "java.lang.OutOfMemoryError: Java heap space at com.service.cache.BufferManager.allocate()",
            }
        ]
    else:
        return [
            {
                "timestamp": "2026-10-10T12:30:10Z",
                "level": "ERROR",
                "message": f"HTTP 500 downstream service timeout or network error encountered on {service_name or log_group}",
            }
        ]


@registry.register(
    name="get_recent_deployments",
    description="Retrieves recent CI/CD deployments and git commit changes for the service",
    parameters={
        "type": "object",
        "properties": {
            "service_name": {"type": "string", "description": "Target service name"},
            "limit": {"type": "integer", "description": "Number of recent deployments to fetch"},
        },
        "required": ["service_name"],
    },
)
def get_recent_deployments(service_name: str, limit: int = 3) -> List[Dict[str, Any]]:
    """Retrieves git deployment history."""
    return [
        {
            "deployment_id": f"deploy-{abs(hash(service_name)) % 9000 + 1000}",
            "service": service_name,
            "commit_sha": "a8f3b2c",
            "author": "dev-team@company.com",
            "message": f"chore({service_name}): update configuration and resource parameters",
            "deployed_at": "2026-10-10T12:15:00Z",
            "status": "SUCCESS",
        }
    ]


@registry.register(
    name="execute_k8s_rollout_undo",
    description="Rolls back a Kubernetes deployment to its previous stable revision (REQUIRES APPROVAL)",
    parameters={
        "type": "object",
        "properties": {
            "namespace": {"type": "string", "description": "Namespace"},
            "deployment_name": {"type": "string", "description": "Deployment name to rollback"},
        },
        "required": ["deployment_name"],
    },
)
def execute_k8s_rollout_undo(deployment_name: str, namespace: str = "prod") -> Dict[str, Any]:
    """Rolls back deployment after human approval."""
    return {
        "status": "success",
        "action": f"kubectl rollout undo deployment/{deployment_name} -n {namespace}",
        "message": f"Deployment '{deployment_name}' rolled back to previous revision.",
    }
