"""
Typed facade over the Kubernetes API.

Injectors, remediators and RCA only talk to `Cluster` methods, never to the raw
client. Two implementations exist:

  * KubeCluster          — the real cluster via the official Python client
  * sim.SimulatedCluster — an in-memory, *stateful* model of the same cluster
                           used by `--dry-run` and the test-suite

Both obey the same contract, so dry-runs exercise exactly the code paths a real
run does (unlike a mock that returns canned data and forgets every call).
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from novasurge import config

log = logging.getLogger("novasurge.cluster")


# ── Value objects ────────────────────────────────────────────────────────────
@dataclass
class PodInfo:
    name: str
    app: str
    phase: str
    ready: bool
    ip: str | None
    created_at: datetime | None
    restarts: int = 0
    deleting: bool = False
    labels: dict[str, str] = field(default_factory=dict)
    last_termination_reason: str | None = None
    # container -> {"requests": {...}, "limits": {...}} as currently applied
    resources: dict[str, dict[str, dict[str, str]]] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)


@dataclass
class ContainerSpec:
    name: str
    requests: dict[str, str]
    limits: dict[str, str]


@dataclass
class DeploymentInfo:
    name: str
    replicas: int
    ready_replicas: int
    available_replicas: int
    updated_replicas: int
    containers: list[ContainerSpec]
    annotations: dict[str, str]
    generation: int = 0
    observed_generation: int = 0


@dataclass
class HpaInfo:
    name: str
    min_replicas: int
    max_replicas: int
    current_replicas: int
    desired_replicas: int
    annotations: dict[str, str]


@dataclass
class NetworkPolicyInfo:
    name: str
    pod_selector: dict[str, str]
    policy_types: list[str]
    ingress_rules: int
    egress_rules: int
    labels: dict[str, str]
    created_at: datetime | None

    @property
    def denies_all(self) -> bool:
        """A policy with a type but no rules for it denies all traffic of that type."""
        return ("Ingress" in self.policy_types and self.ingress_rules == 0) or (
            "Egress" in self.policy_types and self.egress_rules == 0
        )


@dataclass
class EventInfo:
    reason: str
    kind: str
    name: str
    message: str
    type: str
    last_seen: datetime | None


@dataclass
class ExecResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class Cluster(Protocol):
    namespace: str

    def list_pods(self, app: str | None = None, namespace: str | None = None) -> list[PodInfo]: ...
    def delete_pod(self, name: str, grace_seconds: int = 0) -> None: ...
    def patch_pod_labels(self, name: str, labels: dict[str, str | None]) -> None: ...
    def annotate_pod(self, name: str, annotations: dict[str, str | None]) -> None: ...
    def resize_pod(self, name: str, container: str, resources: dict[str, dict[str, str]]) -> None: ...
    def get_deployment(self, name: str) -> DeploymentInfo: ...
    def patch_deployment(self, name: str, body: dict) -> None: ...
    def get_hpa(self, name: str) -> HpaInfo: ...
    def patch_hpa(self, name: str, body: dict) -> None: ...
    def list_network_policies(self) -> list[NetworkPolicyInfo]: ...
    def create_network_policy(self, body: dict) -> None: ...
    def delete_network_policy(self, name: str) -> bool: ...
    def exec(self, pod: str, command: list[str], container: str | None = None,
             timeout: int = 30, namespace: str | None = None) -> ExecResult: ...
    def list_events(self, since: datetime) -> list[EventInfo]: ...
    def pod_logs(self, pod: str, since_seconds: int = 60, tail_lines: int = 500) -> str: ...


def pod_selector_matches(selector: dict[str, str], labels: dict[str, str]) -> bool:
    return all(labels.get(k) == v for k, v in selector.items())


# ── Real implementation ──────────────────────────────────────────────────────
class KubeCluster:
    """Cluster backed by the official kubernetes client and a kubeconfig context."""

    def __init__(self, context: str | None = None, namespace: str | None = None):
        from kubernetes import client, config as kconfig

        self.namespace = namespace or config.NAMESPACE
        context = context or config.KUBE_CONTEXT
        try:
            api_client = kconfig.new_client_from_config(context=context)
            exec_client = kconfig.new_client_from_config(context=context)
        except kconfig.ConfigException:
            # Running inside the cluster with a ServiceAccount.
            kconfig.load_incluster_config()
            api_client = client.ApiClient()
            exec_client = client.ApiClient()
        self._core = client.CoreV1Api(api_client)
        self._apps = client.AppsV1Api(api_client)
        self._net = client.NetworkingV1Api(api_client)
        self._hpa = client.AutoscalingV2Api(api_client)
        # `stream()` swaps the transport of the client it is given, so exec
        # gets its own ApiClient to stay thread-safe with regular calls.
        self._exec_core = client.CoreV1Api(exec_client)
        self._exec_lock = threading.Lock()
        self._client_mod = client

    # pods
    def list_pods(self, app: str | None = None, namespace: str | None = None) -> list[PodInfo]:
        selector = f"app={app}" if app else None
        items = self._core.list_namespaced_pod(namespace or self.namespace, label_selector=selector).items
        return [self._pod_info(p) for p in items]

    @staticmethod
    def _pod_info(p: Any) -> PodInfo:
        statuses = p.status.container_statuses or []
        ready = bool(statuses) and all(s.ready for s in statuses) and p.metadata.deletion_timestamp is None
        reason = None
        for s in statuses:
            term = s.last_state.terminated if s.last_state else None
            if term is not None:
                reason = term.reason
        resources = {}
        for c in p.spec.containers:
            applied = next((s.resources for s in statuses if s.name == c.name and s.resources), None)
            res = applied or c.resources
            resources[c.name] = {
                "requests": dict((res.requests or {}) if res else {}),
                "limits": dict((res.limits or {}) if res else {}),
            }
        return PodInfo(
            name=p.metadata.name,
            app=(p.metadata.labels or {}).get("app", ""),
            phase=p.status.phase or "Unknown",
            ready=ready,
            ip=p.status.pod_ip,
            created_at=p.metadata.creation_timestamp,
            restarts=sum(s.restart_count for s in statuses),
            deleting=p.metadata.deletion_timestamp is not None,
            labels=dict(p.metadata.labels or {}),
            last_termination_reason=reason,
            resources=resources,
            annotations=dict(p.metadata.annotations or {}),
        )

    def delete_pod(self, name: str, grace_seconds: int = 0) -> None:
        self._core.delete_namespaced_pod(
            name, self.namespace,
            body=self._client_mod.V1DeleteOptions(grace_period_seconds=grace_seconds),
        )

    def patch_pod_labels(self, name: str, labels: dict[str, str | None]) -> None:
        self._core.patch_namespaced_pod(name, self.namespace, {"metadata": {"labels": labels}})

    def annotate_pod(self, name: str, annotations: dict[str, str | None]) -> None:
        self._core.patch_namespaced_pod(name, self.namespace, {"metadata": {"annotations": annotations}})

    def resize_pod(self, name: str, container: str, resources: dict[str, dict[str, str]]) -> None:
        """In-place vertical resize via the pod `resize` subresource (no restart)."""
        body = {"spec": {"containers": [{"name": container, "resources": resources}]}}
        self._core.patch_namespaced_pod_resize(name, self.namespace, body)

    # deployments
    def get_deployment(self, name: str) -> DeploymentInfo:
        d = self._apps.read_namespaced_deployment(name, self.namespace)
        containers = [
            ContainerSpec(
                name=c.name,
                requests=dict((c.resources.requests or {}) if c.resources else {}),
                limits=dict((c.resources.limits or {}) if c.resources else {}),
            )
            for c in d.spec.template.spec.containers
        ]
        return DeploymentInfo(
            name=name,
            replicas=d.spec.replicas or 0,
            ready_replicas=d.status.ready_replicas or 0,
            available_replicas=d.status.available_replicas or 0,
            updated_replicas=d.status.updated_replicas or 0,
            containers=containers,
            annotations=dict(d.metadata.annotations or {}),
            generation=d.metadata.generation or 0,
            observed_generation=d.status.observed_generation or 0,
        )

    def patch_deployment(self, name: str, body: dict) -> None:
        self._apps.patch_namespaced_deployment(name, self.namespace, body)

    # autoscalers
    def get_hpa(self, name: str) -> HpaInfo:
        h = self._hpa.read_namespaced_horizontal_pod_autoscaler(name, self.namespace)
        return HpaInfo(
            name=name,
            min_replicas=h.spec.min_replicas or 1,
            max_replicas=h.spec.max_replicas,
            current_replicas=h.status.current_replicas or 0,
            desired_replicas=h.status.desired_replicas or 0,
            annotations=dict(h.metadata.annotations or {}),
        )

    def patch_hpa(self, name: str, body: dict) -> None:
        self._hpa.patch_namespaced_horizontal_pod_autoscaler(name, self.namespace, body)

    # network policies
    def list_network_policies(self) -> list[NetworkPolicyInfo]:
        out = []
        for np_ in self._net.list_namespaced_network_policy(self.namespace).items:
            spec = np_.spec
            out.append(NetworkPolicyInfo(
                name=np_.metadata.name,
                pod_selector=dict((spec.pod_selector.match_labels or {}) if spec.pod_selector else {}),
                policy_types=list(spec.policy_types or []),
                ingress_rules=len(spec.ingress or []),
                egress_rules=len(spec.egress or []),
                labels=dict(np_.metadata.labels or {}),
                created_at=np_.metadata.creation_timestamp,
            ))
        return out

    def create_network_policy(self, body: dict) -> None:
        self._net.create_namespaced_network_policy(self.namespace, body)

    def delete_network_policy(self, name: str) -> bool:
        from kubernetes.client.exceptions import ApiException
        try:
            self._net.delete_namespaced_network_policy(name, self.namespace)
            return True
        except ApiException as exc:
            if exc.status == 404:
                return False
            raise

    # exec
    def exec(self, pod: str, command: list[str], container: str | None = None,
             timeout: int = 30, namespace: str | None = None) -> ExecResult:
        from kubernetes.stream import stream

        with self._exec_lock:
            resp = stream(
                self._exec_core.connect_get_namespaced_pod_exec, pod, namespace or self.namespace,
                command=command, container=container,
                stderr=True, stdin=False, stdout=True, tty=False, _preload_content=False,
            )
            try:
                resp.run_forever(timeout=timeout)
                out, err = resp.read_stdout() or "", resp.read_stderr() or ""
                rc = resp.returncode
            finally:
                resp.close()
        return ExecResult(returncode=rc if rc is not None else -1, stdout=out, stderr=err)

    # events / logs
    def list_events(self, since: datetime) -> list[EventInfo]:
        out = []
        for e in self._core.list_namespaced_event(self.namespace).items:
            seen = e.last_timestamp or e.event_time or e.first_timestamp or e.metadata.creation_timestamp
            if seen is not None and seen.tzinfo is None:
                seen = seen.replace(tzinfo=timezone.utc)
            if seen is not None and seen < since:
                continue
            out.append(EventInfo(
                reason=e.reason or "",
                kind=e.involved_object.kind or "",
                name=e.involved_object.name or "",
                message=e.message or "",
                type=e.type or "",
                last_seen=seen,
            ))
        return out

    def pod_logs(self, pod: str, since_seconds: int = 60, tail_lines: int = 500) -> str:
        return self._core.read_namespaced_pod_log(
            pod, self.namespace, since_seconds=since_seconds, tail_lines=tail_lines,
        )


# ── Process-wide accessor ────────────────────────────────────────────────────
_cluster: Cluster | None = None
_lock = threading.Lock()


def get_cluster() -> Cluster:
    global _cluster
    with _lock:
        if _cluster is None:
            if config.SIMULATION:
                from novasurge.sim import get_simulated_cluster
                _cluster = get_simulated_cluster()
            else:
                _cluster = KubeCluster()
        return _cluster


def set_cluster(cluster: Cluster | None) -> None:
    """Install a specific backend (used by the simulator and tests)."""
    global _cluster
    with _lock:
        _cluster = cluster


def now() -> datetime:
    return datetime.now(timezone.utc)
