"""
SimulatedCluster — an in-memory, stateful model of the ShopFusion cluster that
implements the same `Cluster` contract as the real KubeCluster.

Modelled controllers (enough for every injector/remediator to behave as it
does on Kubernetes):
  * ReplicaSet    keeps the number of pods labelled app=<svc> at the desired count;
                  relabelled (quarantined) pods are orphaned and replaced
  * Deployment    template changes bump the generation and roll pods one at a
                  time (maxSurge 1, maxUnavailable 0)
  * HPA           clamps desired replicas into [minReplicas, maxReplicas]
  * kubelet       pods become Ready STARTUP_S after creation; pods isolated by a
                  deny-all NetworkPolicy fail readiness (their DB is unreachable)
Faults live in the same places they do for real: NetworkPolicies, live pod
resources (in-place resize), a per-pod netem flag set through `exec tc`.
"""

from __future__ import annotations

import copy
import itertools
import json
import random
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from novasurge import config, topology
from novasurge.cluster import (ContainerSpec, DeploymentInfo, EventInfo, ExecResult, HpaInfo, NetworkPolicyInfo,
                               PodInfo, pod_selector_matches)

STARTUP_S = 2.0
PARTITION_UNREADY_AFTER_S = 2.0

DECLARED = {
    "api-gateway": ({"cpu": "100m", "memory": "64Mi"}, {"cpu": "500m", "memory": "192Mi"}, 2, 4),
    "product-service": ({"cpu": "100m", "memory": "96Mi"}, {"cpu": "500m", "memory": "256Mi"}, 2, 4),
    "order-service": ({"cpu": "100m", "memory": "96Mi"}, {"cpu": "500m", "memory": "256Mi"}, 2, 4),
    "payment-service": ({"cpu": "100m", "memory": "96Mi"}, {"cpu": "500m", "memory": "256Mi"}, 2, 4),
    "notification-service": ({"cpu": "25m", "memory": "64Mi"}, {"cpu": "250m", "memory": "192Mi"}, 1, 3),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class SimPod:
    name: str
    labels: dict
    namespace: str
    created: float
    ready_at: float
    generation: int
    resources: dict
    ip: str
    annotations: dict = field(default_factory=dict)
    deleting_at: float | None = None
    netem: bool = False
    restarts: int = 0

    @property
    def app(self) -> str:
        return self.labels.get("app", "")


@dataclass
class SimDeployment:
    name: str
    replicas: int
    generation: int
    resources: dict           # template: container -> {requests, limits}
    annotations: dict
    template_annotations: dict = field(default_factory=dict)


@dataclass
class SimHpa:
    min_replicas: int
    max_replicas: int
    annotations: dict


class SimulatedCluster:
    def __init__(self, seed: int = 11):
        self.namespace = config.NAMESPACE
        self._lock = threading.RLock()
        self._rng = random.Random(seed)
        self._ip = itertools.count(10)
        self.pods: dict[str, SimPod] = {}
        self.deployments: dict[str, SimDeployment] = {}
        self.hpas: dict[str, SimHpa] = {}
        self.netpols: dict[str, dict] = {}
        self.events: list[EventInfo] = []
        self.redis_keys = 64
        now = time.monotonic()
        for svc, (req, lim, mn, mx) in DECLARED.items():
            res = {svc: {"requests": dict(req), "limits": dict(lim)}}
            self.deployments[svc] = SimDeployment(
                svc, mn, 1, copy.deepcopy(res),
                {"novasurge.io/baseline-resources": json.dumps(res)})
            self.hpas[svc] = SimHpa(mn, mx, {"novasurge.io/baseline": json.dumps(
                {"minReplicas": mn, "maxReplicas": mx})})
            for _ in range(mn):
                self._spawn(svc, now, ready_now=True)
        self._spawn_static("redis", self.namespace)
        self._spawn_static("chaos-agent", config.SYSTEM_NAMESPACE)

    # ── internals ────────────────────────────────────────────────────────────
    def _suffix(self) -> str:
        return "".join(self._rng.choice("bcdfghjklmnpqrstvwxz2456789") for _ in range(5))

    def _spawn(self, svc: str, now: float, ready_now: bool = False) -> SimPod:
        dep = self.deployments[svc]
        name = f"{svc}-{dep.generation:08x}-{self._suffix()}"
        pod = SimPod(name=name, labels={"app": svc}, namespace=self.namespace, created=now,
                     ready_at=now if ready_now else now + STARTUP_S, generation=dep.generation,
                     resources=copy.deepcopy(dep.resources), ip=f"10.244.0.{next(self._ip)}")
        self.pods[name] = pod
        return pod

    def _spawn_static(self, app: str, namespace: str) -> None:
        name = f"{app}-0000-{self._suffix()}"
        self.pods[name] = SimPod(name=name, labels={"app": app}, namespace=namespace, created=0.0, ready_at=0.0,
                                 generation=0, resources={}, ip=f"10.244.0.{next(self._ip)}")

    def isolated(self, pod: SimPod) -> bool:
        return any(np_["types"] and not np_["rules"] and pod_selector_matches(np_["selector"], pod.labels)
                   for np_ in self.netpols.values())

    def _is_ready(self, pod: SimPod, now: float) -> bool:
        if pod.deleting_at is not None or now < pod.ready_at:
            return False
        if self.isolated(pod):
            iso_since = min((np_["created_mono"] for np_ in self.netpols.values()
                             if pod_selector_matches(np_["selector"], pod.labels)), default=now)
            return now - iso_since < PARTITION_UNREADY_AFTER_S
        return True

    def _event(self, reason: str, name: str, message: str) -> None:
        self.events.append(EventInfo(reason=reason, kind="Pod", name=name, message=message, type="Normal",
                                     last_seen=_now()))
        self.events = self.events[-300:]

    def _reconcile(self) -> None:
        now = time.monotonic()
        for name in [n for n, p in self.pods.items() if p.deleting_at is not None and now >= p.deleting_at]:
            self.pods.pop(name)
        for svc, dep in self.deployments.items():
            hpa = self.hpas[svc]
            dep.replicas = max(hpa.min_replicas, min(hpa.max_replicas, dep.replicas))
            mine = [p for p in self.pods.values() if p.app == svc and p.deleting_at is None]
            ready = [p for p in mine if self._is_ready(p, now)]
            old = [p for p in mine if p.generation < dep.generation]
            if old:  # rolling update: surge one new pod, retire one old pod once it is Ready
                new = [p for p in mine if p.generation == dep.generation]
                if len(new) < dep.replicas and len(mine) <= dep.replicas:
                    self._spawn(svc, now)
                # maxUnavailable 0: retire an old pod only if Ready capacity stays >= replicas
                # (like the Deployment controller, unhealthy old pods are cleaned up first)
                victim = min(old, key=lambda p: self._is_ready(p, now))   # prefer a non-Ready old pod
                victim_ready = self._is_ready(victim, now)
                ready_after = len(ready) - (1 if victim_ready else 0)
                if not victim_ready or (any(self._is_ready(p, now) for p in new) and ready_after >= dep.replicas):
                    victim.deleting_at = now
                    self._event("Killing", victim.name, f"Stopping container {svc}")
                continue
            if len(mine) < dep.replicas:
                for _ in range(dep.replicas - len(mine)):
                    self._spawn(svc, now)
            elif len(mine) > dep.replicas:
                for p in sorted(mine, key=lambda p: -p.created)[: len(mine) - dep.replicas]:
                    p.deleting_at = now
                    self._event("Killing", p.name, f"Stopping container {svc}")

    def _pod_info(self, p: SimPod, now: float) -> PodInfo:
        return PodInfo(name=p.name, app=p.app, phase="Running", ready=self._is_ready(p, now), ip=p.ip,
                       created_at=_now() - timedelta(seconds=max(now - p.created, 0)), restarts=p.restarts,
                       deleting=p.deleting_at is not None, labels=dict(p.labels), resources=copy.deepcopy(p.resources),
                       annotations=dict(p.annotations))

    # ── Cluster contract ─────────────────────────────────────────────────────
    def list_pods(self, app: str | None = None, namespace: str | None = None) -> list[PodInfo]:
        with self._lock:
            self._reconcile()
            now = time.monotonic()
            ns = namespace or self.namespace
            return [self._pod_info(p, now) for p in self.pods.values()
                    if p.namespace == ns and (app is None or p.app == app)]

    def delete_pod(self, name: str, grace_seconds: int = 0) -> None:
        with self._lock:
            pod = self.pods[name]
            pod.deleting_at = time.monotonic() + min(grace_seconds, 1)
            self._event("Killing", name, f"Stopping container {pod.app}")
            self._reconcile()

    def patch_pod_labels(self, name: str, labels: dict) -> None:
        with self._lock:
            pod = self.pods[name]
            for k, v in labels.items():
                if v is None:
                    pod.labels.pop(k, None)
                else:
                    pod.labels[k] = v
            self._reconcile()

    def annotate_pod(self, name: str, annotations: dict) -> None:
        with self._lock:
            pod = self.pods[name]
            for k, v in annotations.items():
                if v is None:
                    pod.annotations.pop(k, None)
                else:
                    pod.annotations[k] = v

    def resize_pod(self, name: str, container: str, resources: dict) -> None:
        with self._lock:
            pod = self.pods[name]
            cur = pod.resources.setdefault(container, {"requests": {}, "limits": {}})
            for kind in ("requests", "limits"):
                cur[kind].update(resources.get(kind, {}))

    def get_deployment(self, name: str) -> DeploymentInfo:
        with self._lock:
            self._reconcile()
            dep = self.deployments[name]
            now = time.monotonic()
            mine = [p for p in self.pods.values() if p.app == name and p.deleting_at is None]
            ready = [p for p in mine if self._is_ready(p, now)]
            updated = [p for p in mine if p.generation == dep.generation]
            return DeploymentInfo(
                name=name, replicas=dep.replicas, ready_replicas=len(ready), available_replicas=len(ready),
                updated_replicas=len(updated),
                containers=[ContainerSpec(c, dict(r["requests"]), dict(r["limits"])) for c, r in dep.resources.items()],
                annotations=dict(dep.annotations), generation=dep.generation, observed_generation=dep.generation)

    def patch_deployment(self, name: str, body: dict) -> None:
        with self._lock:
            dep = self.deployments[name]
            tmpl = body.get("spec", {}).get("template", {})
            changed = False
            for k, v in tmpl.get("metadata", {}).get("annotations", {}).items():
                dep.template_annotations[k] = v
                changed = True
            for c in tmpl.get("spec", {}).get("containers", []):
                if "resources" in c:
                    dep.resources[c["name"]] = copy.deepcopy(c["resources"])
                    changed = True
            if changed:
                dep.generation += 1
            self._reconcile()

    def get_hpa(self, name: str) -> HpaInfo:
        with self._lock:
            self._reconcile()
            svc = name.removesuffix("-hpa")
            h, dep = self.hpas[svc], self.deployments[svc]
            return HpaInfo(name=name, min_replicas=h.min_replicas, max_replicas=h.max_replicas,
                           current_replicas=dep.replicas, desired_replicas=dep.replicas,
                           annotations=dict(h.annotations))

    def patch_hpa(self, name: str, body: dict) -> None:
        with self._lock:
            h = self.hpas[name.removesuffix("-hpa")]
            spec = body.get("spec", {})
            h.min_replicas = spec.get("minReplicas", h.min_replicas)
            h.max_replicas = spec.get("maxReplicas", h.max_replicas)
            self._reconcile()

    def list_network_policies(self) -> list[NetworkPolicyInfo]:
        with self._lock:
            return [NetworkPolicyInfo(name=n, pod_selector=dict(p["selector"]), policy_types=list(p["types"]),
                                      ingress_rules=0 if not p["rules"] else 1, egress_rules=0 if not p["rules"] else 1,
                                      labels=dict(p["labels"]), created_at=p["created"])
                    for n, p in self.netpols.items()]

    def create_network_policy(self, body: dict) -> None:
        with self._lock:
            name = body["metadata"]["name"]
            if name in self.netpols:
                raise RuntimeError(f'networkpolicies "{name}" already exists')
            spec = body["spec"]
            self.netpols[name] = {
                "selector": dict(spec.get("podSelector", {}).get("matchLabels", {})),
                "types": list(spec.get("policyTypes", [])),
                "rules": bool(spec.get("ingress") or spec.get("egress")),
                "labels": dict(body["metadata"].get("labels", {})),
                "created": _now(), "created_mono": time.monotonic(),
            }

    def delete_network_policy(self, name: str) -> bool:
        with self._lock:
            return self.netpols.pop(name, None) is not None

    def exec(self, pod: str, command: list[str], container: str | None = None, timeout: int = 30,
             namespace: str | None = None) -> ExecResult:
        with self._lock:
            p = self.pods.get(pod)
            if p is None:
                return ExecResult(1, "", f'pods "{pod}" not found')
            cmd = " ".join(command)
            if command[:2] == ["tc", "qdisc"]:
                if command[2] in ("add", "replace") and "netem" in command:
                    p.netem = True
                    return ExecResult(0, "", "")
                if command[2] == "del":
                    if not p.netem:
                        return ExecResult(2, "", "Error: Cannot delete qdisc with handle of zero.")
                    p.netem = False
                    return ExecResult(0, "", "")
                if command[2] == "show":
                    return ExecResult(0, "qdisc netem 8001: root delay 200ms 50ms\n" if p.netem
                                      else "qdisc noqueue 0: root refcnt 2\n", "")
            if "redis-cli" in cmd:
                n, self.redis_keys = self.redis_keys, 0
                return ExecResult(0, f"{n}\n", "")
            if "conntrack" in cmd:
                return ExecResult(0, "", "")
            return ExecResult(127, "", f"sim: unsupported command {cmd!r}")

    def list_events(self, since: datetime) -> list[EventInfo]:
        with self._lock:
            return [e for e in self.events if e.last_seen and e.last_seen >= since]

    def pod_logs(self, pod: str, since_seconds: int = 60, tail_lines: int = 500) -> str:
        with self._lock:
            p = self.pods.get(pod)
            if p is None:
                raise RuntimeError("pod not found")
            if self.isolated(p):
                return '{"level": "ERROR", "message": "dependency failure", "detail": "postgres unreachable"}\n' * 20
            return ""

    # ── helpers used by SimulatedTelemetry ───────────────────────────────────
    def serving_pods(self, svc: str) -> list[SimPod]:
        with self._lock:
            self._reconcile()
            now = time.monotonic()
            return [p for p in self.pods.values() if p.app == svc and self._is_ready(p, now)]

    def cpu_limit_millis_declared(self, svc: str) -> float:
        declared = json.loads(self.deployments[svc].annotations["novasurge.io/baseline-resources"])
        return _millis(next(iter(declared.values()))["limits"]["cpu"])

    def cpu_limit_millis(self, pod: SimPod) -> float:
        return _millis(next(iter(pod.resources.values()), {}).get("limits", {}).get("cpu", "500m"))


def _millis(value) -> float:
    m = re.match(r"(\d+)m$", str(value))
    return float(m.group(1)) if m else float(value) * 1000
