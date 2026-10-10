"""
network_partition — isolate a service with a deny-all NetworkPolicy
(no ingress or egress rules = all traffic dropped).

CNIs evaluate NetworkPolicy when a connection is *established*; flows that
already exist (pooled keep-alive connections, DB pools) would survive and the
partition would only be partial. After creating the policy the injector
therefore asks the node chaos-agent to flush the conntrack entries of the
isolated pods, so every subsequent packet is re-evaluated against the policy —
a true partition, as a real network split would be.
"""

from __future__ import annotations

from novasurge import config
from novasurge.chaos.injectors import Injection, now_iso

NAME = "network_partition"
DESCRIPTION = "Deny-all NetworkPolicy selecting the service's pods"
EXPECTED_SIGNATURE = "network_partition"


def policy_name(service: str) -> str:
    return f"chaos-isolate-{service}"


def compatible(cluster, service: str) -> tuple[bool, str]:
    if not cluster.list_pods(service):
        return False, "no pods"
    return True, "pods selectable by app label"


def inject(cluster, service: str) -> Injection:
    name = policy_name(service)
    body = {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "NetworkPolicy",
        "metadata": {"name": name, "labels": {"app.kubernetes.io/managed-by": "novasurge-chaos"}},
        "spec": {
            "podSelector": {"matchLabels": {"app": service}},
            "policyTypes": ["Ingress", "Egress"],
        },
    }
    at = now_iso()
    try:
        cluster.create_network_policy(body)
    except Exception as exc:  # noqa: BLE001
        if "already exists" not in str(exc).lower():
            return Injection(NAME, service, False, at, target=name, error=str(exc))
    flushed = sever_established_flows(cluster, service)
    return Injection(NAME, service, True, at, target=name,
                     details={"policy": name, "effect": "deny all ingress + egress",
                              "conntrack_flush": flushed})


def sever_established_flows(cluster, service: str) -> dict:
    """Flush conntrack for every pod IP of `service` on every node agent."""
    ips = [p.ip for p in cluster.list_pods(service) if p.ip and not p.deleting]
    agents = [p for p in cluster.list_pods("chaos-agent", namespace=config.SYSTEM_NAMESPACE) if p.ready]
    if not agents:
        return {"ok": False, "reason": "chaos-agent not running; established flows survive"}
    script = "; ".join(f"conntrack -D -s {ip} 2>/dev/null; conntrack -D -d {ip} 2>/dev/null" for ip in ips)
    results = {}
    for agent in agents:
        res = cluster.exec(agent.name, ["sh", "-c", script + "; true"], timeout=15,
                           namespace=config.SYSTEM_NAMESPACE)
        results[agent.name] = res.ok
    return {"ok": all(results.values()), "pod_ips": ips, "agents": results}


def still_active(cluster, injection: Injection) -> bool:
    return any(np_.name == injection.target for np_ in cluster.list_network_policies())


def reverse(cluster, injection: Injection) -> dict:
    deleted = cluster.delete_network_policy(injection.target)
    return {"policy": injection.target, "deleted": deleted}
