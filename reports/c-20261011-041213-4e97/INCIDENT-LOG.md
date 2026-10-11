# Incident log — campaign `c-20261011-041213-4e97`

**Resilience score 99.6/100** — EXCELLENT — every fault detected, diagnosed and healed within SLA

| Component | Points |
|---|---|
| recovery sla | 35.0 |
| detection sla | 20.0 |
| remediation effectiveness | 20.0 |
| diagnosis accuracy | 15.0 |
| user protection | 9.64 |

| # | Fault | Target | Status | TTD | TTR | Users failed |
|---|---|---|---|---|---|---|
| 1 | pod_deletion | order-service | RECOVERED | 4.82s | 20.0s | 0.0% |
| 2 | latency_injection | product-service | RECOVERED | 9.82s | 45.0s | 0.0% |
| 3 | network_partition | payment-service | RECOVERED | 9.81s | 50.0s | 8.9% |
| 4 | cpu_throttle | api-gateway | RECOVERED | 14.78s | 45.0s | 0.0% |
| 5 | replica_reduction | payment-service | RECOVERED | 4.82s | 20.0s | 0.0% |

## Round 1 — pod_deletion → order-service  ·  **RECOVERED**

TTD 4.82s (target 25s, met) · TTM 11.48s · TTR 20.0s (target 90s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: First-time pod deletion on order-service has high business impact and multiple dependents, maximizing insight into critical path resilience.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | latency_injection | product-service | 0.565 | never | — |
| 2 | pod_deletion | product-service | 0.565 | never | — |
| 3 | pod_deletion | order-service | 0.56 | never | — |
| 4 | replica_reduction | order-service | 0.56 | never | — |
| 5 | latency_injection | order-service | 0.555 | 225.6 | mitigated |
| 6 | cpu_throttle | api-gateway | 0.496 | 275.8 | recovered_within_sla |
| 7 | network_partition | api-gateway | 0.481 | 228.2 | recovered_within_sla |
| 8 | pod_deletion | api-gateway | 0.481 | 226.5 | recovered_within_sla |
| 9 | replica_reduction | api-gateway | 0.469 | 193.1 | recovered_within_sla |
| 10 | latency_injection | api-gateway | 0.469 | 192.1 | recovered_within_sla |

### 2. Safety check before injecting

Decision **GO** · risk MEDIUM · system health 100.0% · target ready 2/2 · load 1.11× baseline · dependents api-gateway · users possibly affected 100%

### 3. Failure injected

`pod_deletion` on **order-service** at 04:12:35 UTC — succeeded

Details: `{"pod": "order-service-6bdd796ccd-vwlhl", "pod_ip": "10.244.0.21", "ready_pods_before": 2}`

### 4. Detection

Confirmed at 04:12:40 UTC on **order-service** as `pod_crash` · severity 0.4 · Isolation Forest score 0.1253 (threshold 0.1031) · flags: replicas_lost

Evidence:
- replicas ready 2/2 (declared minimum 2)
- Ready pod(s) order-service-6bdd796ccd-vwlhl disappeared without a scale-down or rollout
- caller_error_rate=0.0% vs baseline 0.0% (z=+0.0)

### 5. Root-cause analysis

Origin **order-service** · type `pod_crash` · confidence 0.918 · call path api-gateway → order-service · affected order-service

> Root cause localised to order-service (pod crash, confidence 92%). No other service deviates; the fault is contained to order-service. Change evidence: Pod order-service-6bdd796ccd-flmcw: Unhealthy — Startup probe failed: Get "http://10.244.0.31:8002/health": dial tcp 10.244.0.31:8002: connect: connection refused; Pod order-service-6bdd796ccd-vwlhl: Killing — Stopping container order-service.

Evidence:
- replicas ready 2/2 (declared minimum 2)
- Ready pod(s) order-service-6bdd796ccd-vwlhl disappeared without a scale-down or rollout
- caller_error_rate=0.0% vs baseline 0.0% (z=+0.0)
- Pod order-service-6bdd796ccd-flmcw: Unhealthy — Startup probe failed: Get "http://10.244.0.31:8002/health": dial tcp 10.244.0.31:8002: connect: connection refused
- Pod order-service-6bdd796ccd-vwlhl: Killing — Stopping container order-service

| Candidate | Score | Why |
|---|---|---|
| order-service | 3.98 | severity 0.24; no anomalous dependency explains it; earliest onset; structural fault on the service itself; Pod order-service-6bdd796ccd-flmcw: Unhealthy — Startup probe failed: Get "http://10.244.0.31:8002/health": dial tcp 10.244.0.31:8002: connect: connection refused; Pod order-service-6bdd796ccd-vwlhl: Killing — Stopping container order-service |

### 6. Decision

Action **hpa_scaleout** (fallback rolling_restart) · confidence 0.594 · priority 1.92

- order-service: pod crash at severity 0.24; business impact 8/10 -> priority 1.92. Playbook: hpa_scaleout, fallback rolling_restart.
- Confidence in hpa_scaleout: 0.59 (prior 0.70 (no history yet) x RCA 0.92 x blast factor 0.93).
- Decision: hpa_scaleout on order-service (fallback rolling_restart, confidence 0.59).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| hpa_scaleout | order-service | success | yes | 6.1s | autoscaler 2-4 -> 3-4; 2 -> 3 Ready replicas |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"reversible": false, "note": "Kubernetes reschedules deleted pods by itself"}` · autoscaler `{"from": {"minReplicas": 3, "maxReplicas": 4}, "to": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 0 failed of 480 requests (0.0%) · user p99 243.5 ms over 24 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 04:12:17 | STRATEGY | order-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose pod_deletion on order-service: First-time pod deletion on order-service has high business impact and multiple dependents, maximizing insight into critical path resilience. |
| 04:12:35 | PREFLIGHT | order-service | GO: order-service at 2/2 Ready, system 100% healthy. Blast radius: 1 dependent service(s) ['api-gateway'], ~100% of users, risk MEDIUM. |
| 04:12:35 | INJECT | order-service | Injected pod_deletion into order-service: Force-delete one Ready pod (grace period 0) (order-service-6bdd796ccd-vwlhl). |
| 04:12:40 | DETECT | order-service | Anomaly confirmed on order-service 5s after injection: pattern matches pod crash. Isolation Forest score +0.125 (threshold +0.103), severity 0.40. Evidence: replicas ready 2/2 (declared minimum 2); Ready pod(s) order-service-6bdd796ccd-vwlhl disappeared without a scale-down or rollout; caller_error_rate=0.0% vs baseline 0.0% (z=+0.0). |
| 04:12:45 | RCA | order-service | Root cause localised to order-service (pod crash, confidence 92%). No other service deviates; the fault is contained to order-service. Change evidence: Pod order-service-6bdd796ccd-flmcw: Unhealthy — Startup probe failed: Get "http://10.244.0.31:8002/health": dial tcp 10.244.0.31:8002: connect: connection refused; Pod order-service-6bdd796ccd-vwlhl: Killing — Stopping container order-service. |
| 04:12:45 | DECIDE | order-service | Confidence in hpa_scaleout: 0.59 (prior 0.70 (no history yet) x RCA 0.92 x blast factor 0.93). Decision: hpa_scaleout on order-service (fallback rolling_restart, confidence 0.59). |
| 04:12:45 | REMEDIATE | order-service | Executing hpa_scaleout on order-service. |
| 04:12:51 | REMEDIATE | order-service | hpa_scaleout succeeded in 6.1s — autoscaler 2-4 -> 3-4; 2 -> 3 Ready replicas. |
| 04:12:55 | VERIFY | order-service | order-service verified functional: 3/3 replicas Ready and 5 consecutive user-path probes OK (last 7ms). |
| 04:13:00 | TEARDOWN | order-service | Round teardown for order-service: no residual fault found; autoscaler returned to declared bounds. |
| 04:13:10 | RECOVERED | order-service | order-service recovered: detected in 4.82s, mitigated in 11.48s, fully back to its normal operating band in 20.0s (target 90s — MET). Users saw 0 failed requests out of 480 (0.0%) during the incident. |

## Round 2 — latency_injection → product-service  ·  **RECOVERED**

TTD 9.82s (target 35s, met) · TTM 17.05s · TTR 45.0s (target 120s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: First-time latency injection on product-service, a high‑traffic, degraded service with multiple dependents, maximizing new insight into resilience.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | latency_injection | product-service | 0.565 | never | — |
| 2 | cpu_throttle | api-gateway | 0.496 | 276.8 | recovered_within_sla |
| 3 | network_partition | api-gateway | 0.482 | 229.2 | recovered_within_sla |
| 4 | replica_reduction | api-gateway | 0.47 | 194.1 | recovered_within_sla |
| 5 | latency_injection | api-gateway | 0.469 | 193.1 | recovered_within_sla |
| 6 | network_partition | payment-service | 0.446 | 278.5 | recovered_within_sla |
| 7 | replica_reduction | payment-service | 0.445 | 272.3 | recovered_within_sla |
| 8 | cpu_throttle | payment-service | 0.432 | 231.0 | recovered_within_sla |
| 9 | latency_injection | payment-service | 0.427 | 214.1 | recovered_within_sla |
| 10 | replica_reduction | product-service | 0.409 | 222.6 | recovered_within_sla |

### 2. Safety check before injecting

Decision **GO** · risk HIGH · system health 100.0% · target ready 2/2 · load 0.99× baseline · dependents api-gateway, order-service · users possibly affected 100%

### 3. Failure injected

`latency_injection` on **product-service** at 04:13:35 UTC — succeeded

Details: `{"pod": "product-service-78f8dcb767-nlmw8", "delay": "200ms", "jitter": "50ms", "command": "tc qdisc replace dev eth0 root netem delay 200ms 50ms distribution normal", "replicas_ready": 2}`

### 4. Detection

Confirmed at 04:13:45 UTC on **product-service** as `high_latency` · severity 0.9299 · Isolation Forest score -0.0192 (threshold 0.1031) · flags: iforest, zscore:p99_latency_ms, zscore:caller_p99_ms

Evidence:
- p99_latency_ms=119.52ms vs baseline 16.09ms (z=+6.9)
- caller_p99_ms=24.93ms vs baseline 16.56ms (z=+0.6)

LSTM 60 s forecast: score -0.0353 (still anomalous)

### 5. Root-cause analysis

Origin **product-service** · type `high_latency` · confidence 0.95 · call path api-gateway → product-service · affected api-gateway, product-service, order-service

> Root cause localised to product-service (high latency, confidence 95%). api-gateway, order-service also deviate as callers of product-service: its failure propagates to them. Change evidence: Pod product-service-78f8dcb767-nlmw8: Unhealthy — Readiness probe failed: Get "http://10.244.0.25:8001/ready": context deadline exceeded (Client.Timeout exceeded while aw.

Evidence:
- p99_latency_ms=119.52ms vs baseline 16.09ms (z=+6.9)
- caller_p99_ms=24.93ms vs baseline 16.56ms (z=+0.6)
- Pod product-service-78f8dcb767-nlmw8: Unhealthy — Readiness probe failed: Get "http://10.244.0.25:8001/ready": context deadline exceeded (Client.Timeout exceeded while aw

| Candidate | Score | Why |
|---|---|---|
| product-service | 5.215 | severity 0.93; no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service']; earliest onset; Pod product-service-78f8dcb767-nlmw8: Unhealthy — Readiness probe failed: Get "http://10.244.0.25:8001/ready": context deadline exceeded (Client.Timeout exceeded while aw |
| order-service | 0.654 | severity 0.93; its dependencies ['product-service'] are also anomalous (likely a victim); explains anomalies in callers ['api-gateway'] |
| api-gateway | 0.371 | severity 0.94; its dependencies ['product-service', 'order-service'] are also anomalous (likely a victim) |

### 6. Decision

Action **traffic_reroute** (fallback rolling_restart) · confidence 0.646 · priority 5.596

- product-service: high latency at severity 0.93; business impact 6/10 -> priority 5.60. Playbook: traffic_reroute, fallback rolling_restart.
- Confidence in traffic_reroute: 0.65 (history 0.80 over 1 attempt(s) x RCA 0.95 x blast factor 0.85).
- Decision: traffic_reroute on product-service (fallback rolling_restart, confidence 0.65).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| traffic_reroute | product-service | success | yes | 11.1s | quarantined product-service-78f8dcb767-nlmw8 (worst replica by live telemetry (p99=2563ms, next worst score 14 vs 2563)); traffic now on 2 healthy replica(s) |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"pod": "product-service-78f8dcb767-nlmw8", "note": "pod no longer exists (replaced)"}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 0 failed of 1080 requests (0.0%) · user p99 2396.3 ms over 54 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 04:13:17 | STRATEGY | product-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose latency_injection on product-service: First-time latency injection on product-service, a high‑traffic, degraded service with multiple dependents, maximizing new insight into resilience. |
| 04:13:35 | PREFLIGHT | product-service | GO: product-service at 2/2 Ready, system 100% healthy. Blast radius: 2 dependent service(s) ['api-gateway', 'order-service'], ~100% of users, risk HIGH. |
| 04:13:35 | INJECT | product-service | Injected latency_injection into product-service: tc netem egress delay on one replica (product-service-78f8dcb767-nlmw8). |
| 04:13:45 | DETECT | product-service | Anomaly confirmed on product-service 10s after injection: pattern matches high latency. Isolation Forest score -0.019 (threshold +0.103), severity 0.93. Evidence: p99_latency_ms=119.52ms vs baseline 16.09ms (z=+6.9); caller_p99_ms=24.93ms vs baseline 16.56ms (z=+0.6). LSTM forecast for the next 60s: score -0.035 (still anomalous). |
| 04:13:50 | RCA | product-service | Root cause localised to product-service (high latency, confidence 95%). api-gateway, order-service also deviate as callers of product-service: its failure propagates to them. Change evidence: Pod product-service-78f8dcb767-nlmw8: Unhealthy — Readiness probe failed: Get "http://10.244.0.25:8001/ready": context deadline exceeded (Client.Timeout exceeded while aw. |
| 04:13:50 | DECIDE | product-service | Confidence in traffic_reroute: 0.65 (history 0.80 over 1 attempt(s) x RCA 0.95 x blast factor 0.85). Decision: traffic_reroute on product-service (fallback rolling_restart, confidence 0.65). |
| 04:13:50 | REMEDIATE | product-service | Executing traffic_reroute on product-service. |
| 04:14:01 | REMEDIATE | product-service | traffic_reroute succeeded in 11.1s — quarantined product-service-78f8dcb767-nlmw8 (worst replica by live telemetry (p99=2563ms, next worst score 14 vs 2563)); traffic now on 2 healthy replica(s). |
| 04:14:06 | VERIFY | product-service | product-service verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 15ms). |
| 04:14:40 | TEARDOWN | product-service | Round teardown for product-service: no residual fault found; autoscaler returned to declared bounds. |
| 04:14:50 | RECOVERED | product-service | product-service recovered: detected in 9.82s, mitigated in 17.05s, fully back to its normal operating band in 45.0s (target 120s — MET). Users saw 0 failed requests out of 1080 (0.0%) during the incident. |

## Round 3 — network_partition → payment-service  ·  **RECOVERED**

TTD 9.81s (target 30s, met) · TTM 10.59s · TTR 50.0s (target 90s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: High‑impact payment-service network partition, long idle time, many dependents, and not yet used in this campaign, maximizing resilience insight.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | cpu_throttle | api-gateway | 0.496 | 278.5 | recovered_within_sla |
| 2 | network_partition | api-gateway | 0.482 | 230.8 | recovered_within_sla |
| 3 | replica_reduction | api-gateway | 0.47 | 195.7 | recovered_within_sla |
| 4 | network_partition | payment-service | 0.447 | 280.2 | recovered_within_sla |
| 5 | replica_reduction | payment-service | 0.445 | 274.0 | recovered_within_sla |
| 6 | cpu_throttle | payment-service | 0.433 | 232.7 | recovered_within_sla |
| 7 | cpu_throttle | notification-service | 0.38 | never | — |
| 8 | network_partition | notification-service | 0.38 | never | — |
| 9 | replica_reduction | order-service | 0.31 | never | — |
| 10 | replica_reduction | product-service | 0.16 | 224.2 | recovered_within_sla |

### 2. Safety check before injecting

Decision **GO** · risk HIGH · system health 100.0% · target ready 2/2 · load 0.92× baseline · dependents api-gateway, order-service · users possibly affected 100%

### 3. Failure injected

`network_partition` on **payment-service** at 04:15:15 UTC — succeeded

Details: `{"policy": "chaos-isolate-payment-service", "effect": "deny all ingress + egress", "conntrack_flush": {"ok": true, "pod_ips": ["10.244.0.22", "10.244.0.27"], "agents": {"chaos-agent-l7fcx": true}}}`

### 4. Detection

Confirmed at 04:15:25 UTC on **payment-service** as `network_partition` · severity 0.9987 · Isolation Forest score -0.0378 (threshold 0.1031) · flags: iforest, zscore:caller_error_rate, zscore:caller_p99_ms, all_replicas_down, metrics_unreachable

Evidence:
- replicas ready 2/2 (declared minimum 2)
- metrics endpoint unreachable on 50% of pods
- caller_error_rate=0.0% vs baseline 0.0% (z=+0.0)
- request_rate=5.46 req/s vs baseline 6.92 req/s (z=-2.1)
- pods are running (no container restarts) but cannot be reached over the pod network

LSTM 60 s forecast: score -0.037 (still anomalous)

### 5. Root-cause analysis

Origin **payment-service** · type `network_partition` · confidence 0.95 · call path api-gateway → payment-service · affected api-gateway, order-service, payment-service, notification-service

> Root cause localised to payment-service (network partition, confidence 95%). api-gateway, order-service also deviate as callers of payment-service: its failure propagates to them. notification-service also deviate without a dependency explaining it (lower-ranked candidates). Change evidence: NetworkPolicy 'chaos-isolate-payment-service' denies all Ingress/Egress traffic for pods of payment-service, created 15s ago; Pod payment-service-7d546fc794-6v2rq: Unhealthy — Readiness probe failed: Get "http://10.244.0.22:8003/ready": context deadline exceeded (Client.Timeout exceeded while aw.

Evidence:
- replicas ready 2/2 (declared minimum 2)
- metrics endpoint unreachable on 50% of pods
- caller_error_rate=0.0% vs baseline 0.0% (z=+0.0)
- request_rate=5.46 req/s vs baseline 6.92 req/s (z=-2.1)
- pods are running (no container restarts) but cannot be reached over the pod network
- NetworkPolicy 'chaos-isolate-payment-service' denies all Ingress/Egress traffic for pods of payment-service, created 15s ago
- Pod payment-service-7d546fc794-6v2rq: Unhealthy — Readiness probe failed: Get "http://10.244.0.22:8003/ready": context deadline exceeded (Client.Timeout exceeded while aw
- Pod payment-service-7d546fc794-wh4kn: Unhealthy — Readiness probe failed: Get "http://10.244.0.27:8003/ready": context deadline exceeded (Client.Timeout exceeded while aw

| Candidate | Score | Why |
|---|---|---|
| payment-service | 9.097 | severity 1.00; no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service']; earliest onset; structural fault on the service itself; NetworkPolicy 'chaos-isolate-payment-service' denies all Ingress/Egress traffic for pods of payment-service, created 15s ago; Pod payment-service-7d546fc794-6v2rq: Unhealthy — Readiness probe failed: Get "http://10.244.0.22:8003… |
| order-service | 3.561 | severity 0.98; its dependencies ['payment-service'] are also anomalous (likely a victim); explains anomalies in callers ['api-gateway']; earliest onset; Pod order-service-6bdd796ccd-zk9m6: Killing — Stopping container order-service; 112 ERROR log lines in the last 60s, e.g. 'dependency failure (payment-service)' |
| api-gateway | 2.286 | severity 0.97; its dependencies ['order-service', 'payment-service'] are also anomalous (likely a victim); earliest onset; 118 ERROR log lines in the last 60s, e.g. 'request failed' |
| notification-service | 1.097 | severity 0.40; only symptom is reduced traffic — consistent with an upstream failure; no anomalous dependency explains it; explains anomalies in callers ['api-gateway'] |

### 6. Decision

Action **network_policy_rollback** (fallback rolling_restart) · confidence 0.646 · priority 9.987

- payment-service: network partition at severity 1.00; business impact 10/10 -> priority 9.99. Playbook: network_policy_rollback, fallback rolling_restart.
- Confidence in network_policy_rollback: 0.65 (history 0.80 over 1 attempt(s) x RCA 0.95 x blast factor 0.85).
- Decision: network_policy_rollback on payment-service (fallback rolling_restart, confidence 0.65).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| network_policy_rollback | payment-service | success | yes | 4.1s | removed 1 isolating NetworkPolicy(ies): chaos-isolate-payment-service |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"policy": "chaos-isolate-payment-service", "deleted": false}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 104 failed of 1172 requests (8.9%) · user p99 5746.2 ms over 59 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 04:14:57 | STRATEGY | payment-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose network_partition on payment-service: High‑impact payment-service network partition, long idle time, many dependents, and not yet used in this campaign, maximizing resilience insight. |
| 04:15:15 | PREFLIGHT | payment-service | GO: payment-service at 2/2 Ready, system 100% healthy. Blast radius: 2 dependent service(s) ['api-gateway', 'order-service'], ~100% of users, risk HIGH. |
| 04:15:15 | INJECT | payment-service | Injected network_partition into payment-service: Deny-all NetworkPolicy selecting the service's pods (chaos-isolate-payment-service). |
| 04:15:25 | DETECT | payment-service | Anomaly confirmed on payment-service 10s after injection: pattern matches network partition. Isolation Forest score -0.038 (threshold +0.103), severity 1.00. Evidence: replicas ready 2/2 (declared minimum 2); metrics endpoint unreachable on 50% of pods; caller_error_rate=0.0% vs baseline 0.0% (z=+0.0). Also deviating: api-gateway, order-service. LSTM forecast for the next 60s: score -0.037 (still anomalous). |
| 04:15:30 | RCA | payment-service | Root cause localised to payment-service (network partition, confidence 95%). api-gateway, order-service also deviate as callers of payment-service: its failure propagates to them. notification-service also deviate without a dependency explaining it (lower-ranked candidates). Change evidence: NetworkPolicy 'chaos-isolate-payment-service' denies all Ingress/Egress traffic for pods of payment-service, created 15s ago; Pod payment-service-7d546fc794-6v2rq: Unhealthy — Readiness probe failed: Get "http://10.244.0.22:8003/ready": context deadline exceeded (Client.Timeout exceeded while aw. |
| 04:15:30 | DECIDE | payment-service | Confidence in network_policy_rollback: 0.65 (history 0.80 over 1 attempt(s) x RCA 0.95 x blast factor 0.85). Decision: network_policy_rollback on payment-service (fallback rolling_restart, confidence 0.65). |
| 04:15:30 | REMEDIATE | payment-service | Executing network_policy_rollback on payment-service. |
| 04:15:34 | REMEDIATE | payment-service | network_policy_rollback succeeded in 4.1s — removed 1 isolating NetworkPolicy(ies): chaos-isolate-payment-service. |
| 04:15:40 | VERIFY | payment-service | payment-service verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 7ms). |
| 04:16:25 | TEARDOWN | payment-service | Round teardown for payment-service: no residual fault found; autoscaler returned to declared bounds. |
| 04:16:35 | RECOVERED | payment-service | payment-service recovered: detected in 9.81s, mitigated in 10.59s, fully back to its normal operating band in 50.0s (target 90s — MET). Users saw 104 failed requests out of 1172 (8.9%) during the incident. |

## Round 4 — cpu_throttle → api-gateway  ·  **RECOVERED**

TTD 14.78s (target 35s, met) · TTM 7.54s · TTR 45.0s (target 90s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: Introduces a new fault type (cpu_throttle) on the high‑impact api‑gateway, a service not yet tested in this campaign, maximizing learning about core traffic resilience.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | cpu_throttle | api-gateway | 0.497 | 280.3 | recovered_within_sla |
| 2 | replica_reduction | api-gateway | 0.471 | 197.5 | recovered_within_sla |
| 3 | cpu_throttle | notification-service | 0.38 | never | — |
| 4 | replica_reduction | order-service | 0.31 | never | — |
| 5 | replica_reduction | payment-service | 0.195 | 275.8 | recovered_within_sla |
| 6 | cpu_throttle | payment-service | 0.183 | 234.4 | recovered_within_sla |
| 7 | replica_reduction | product-service | 0.161 | 226.0 | recovered_within_sla |
| 8 | cpu_throttle | product-service | 0.152 | 200.3 | recovered_within_sla |
| 9 | cpu_throttle | order-service | 0.152 | 214.7 | recovered_within_sla |
| 10 | network_partition | api-gateway | 0.083 | 232.6 | recovered_within_sla |

### 2. Safety check before injecting

Decision **GO** · risk MEDIUM · system health 100.0% · target ready 2/2 · load 1.01× baseline · dependents none · users possibly affected 100%

### 3. Failure injected

`cpu_throttle` on **api-gateway** at 04:17:00 UTC — succeeded

Details: `{"pods": ["api-gateway-6488bc94fb-2jrp7", "api-gateway-6488bc94fb-f9qqs"], "cpu_limit": "25m", "original": {"api-gateway-6488bc94fb-2jrp7": {"api-gateway": {"requests": {"cpu": "100m", "memory": "64Mi"}, "limits": {"cpu": "500m", "memory": "192Mi"}}}, "api-gateway-6488bc94fb-f9qqs": {"api-gateway": {"requests": {"cpu": "100m", "memory": "64Mi"}, "limits": {"cpu": "500m", "memory": "192Mi"}}}}}`

### 4. Detection

Confirmed at 04:17:15 UTC on **product-service** as `high_latency` · severity 0.706 · Isolation Forest score 0.0696 (threshold 0.1031) · flags: iforest, zscore:caller_p99_ms

Evidence:
- p99_latency_ms=11.93ms vs baseline 16.09ms (z=-0.3)
- caller_p99_ms=209.50ms vs baseline 16.56ms (z=+12.9)

LSTM 60 s forecast: score 0.0456 (still anomalous)

### 5. Root-cause analysis

Origin **api-gateway** · type `cpu_throttle` · confidence 0.95 · call path api-gateway · affected api-gateway, product-service, order-service

> Root cause localised to api-gateway (cpu throttle, confidence 95%). product-service, order-service deviate because requests from api-gateway stopped reaching them. Change evidence: pod api-gateway-6488bc94fb-2jrp7 CPU limit is 25m vs declared 500m; pod api-gateway-6488bc94fb-f9qqs CPU limit is 25m vs declared 500m.

Evidence:
- p99_latency_ms=362.49ms vs baseline 242.46ms (z=+3.3)
- caller_p99_ms=469.37ms vs baseline 242.66ms (z=+6.2)
- pod api-gateway-6488bc94fb-2jrp7 CPU limit is 25m vs declared 500m
- pod api-gateway-6488bc94fb-f9qqs CPU limit is 25m vs declared 500m

| Candidate | Score | Why |
|---|---|---|
| api-gateway | 8.807 | severity 0.78; its dependencies ['product-service', 'order-service'] are also anomalous (likely a victim); earliest onset; pod api-gateway-6488bc94fb-2jrp7 CPU limit is 25m vs declared 500m; pod api-gateway-6488bc94fb-f9qqs CPU limit is 25m vs declared 500m; its calls to product-service take 345ms longer than product-service itself needs to serve them (caller-side or network problem); its calls to… |
| product-service | 2.28 | severity 0.71; its own server-side latency/errors are normal; the degradation is only visible from callers (network or caller-side problem); no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service']; earliest onset |
| order-service | -1.176 | severity 0.39; its own server-side latency/errors are normal; the degradation is only visible from callers (network or caller-side problem); its dependencies ['product-service'] are also anomalous (likely a victim); explains anomalies in callers ['api-gateway']; earliest onset |

### 6. Decision

Action **resource_restore** (fallback rolling_restart) · confidence 0.76 · priority 7.006

- api-gateway: cpu throttle at severity 0.78; business impact 9/10 -> priority 7.01. Playbook: resource_restore, fallback rolling_restart.
- Confidence in resource_restore: 0.76 (history 0.80 over 1 attempt(s) x RCA 0.95 x blast factor 1.00).
- Decision: resource_restore on api-gateway (fallback rolling_restart, confidence 0.76).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| resource_restore | api-gateway | success | yes | 2.1s | resized 2 container(s) in place to {'api-gateway': {'requests': {'cpu': '100m', 'memory': '64Mi'}, 'limits': {'cpu': '500m', 'memory': '192Mi'}}} |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"restored_pods": []}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 0 failed of 1181 requests (0.0%) · user p99 455.7 ms over 59 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 04:16:43 | STRATEGY | api-gateway | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose cpu_throttle on api-gateway: Introduces a new fault type (cpu_throttle) on the high‑impact api‑gateway, a service not yet tested in this campaign, maximizing learning about core traffic resilience. |
| 04:17:00 | PREFLIGHT | api-gateway | GO: api-gateway at 2/2 Ready, system 100% healthy. Blast radius: 0 dependent service(s) , ~100% of users, risk MEDIUM. |
| 04:17:00 | INJECT | api-gateway | Injected cpu_throttle into api-gateway: In-place resize of every replica's CPU limit to a starvation value (api-gateway-6488bc94fb-2jrp7,api-gateway-6488bc94fb-f9qqs). |
| 04:17:15 | DETECT | product-service | Anomaly confirmed on product-service 15s after injection: pattern matches high latency. Isolation Forest score +0.070 (threshold +0.103), severity 0.71. Evidence: p99_latency_ms=11.93ms vs baseline 16.09ms (z=-0.3); caller_p99_ms=209.50ms vs baseline 16.56ms (z=+12.9). Also deviating: api-gateway, order-service. LSTM forecast for the next 60s: score +0.046 (still anomalous). |
| 04:17:20 | RCA | api-gateway | Root cause localised to api-gateway (cpu throttle, confidence 95%). product-service, order-service deviate because requests from api-gateway stopped reaching them. Change evidence: pod api-gateway-6488bc94fb-2jrp7 CPU limit is 25m vs declared 500m; pod api-gateway-6488bc94fb-f9qqs CPU limit is 25m vs declared 500m. |
| 04:17:20 | DECIDE | api-gateway | Confidence in resource_restore: 0.76 (history 0.80 over 1 attempt(s) x RCA 0.95 x blast factor 1.00). Decision: resource_restore on api-gateway (fallback rolling_restart, confidence 0.76). |
| 04:17:20 | REMEDIATE | api-gateway | Executing resource_restore on api-gateway. |
| 04:17:22 | REMEDIATE | api-gateway | resource_restore succeeded in 2.1s — resized 2 container(s) in place to {'api-gateway': {'requests': {'cpu': '100m', 'memory': '64Mi'}, 'limits': {'cpu': '500m', 'memory': '192Mi'}}}. |
| 04:17:27 | VERIFY | api-gateway | api-gateway verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 8ms). |
| 04:18:10 | TEARDOWN | api-gateway | Round teardown for api-gateway: no residual fault found; autoscaler returned to declared bounds. |
| 04:18:20 | RECOVERED | api-gateway | api-gateway recovered: detected in 14.78s, mitigated in 7.54s, fully back to its normal operating band in 45.0s (target 90s — MET). Users saw 0 failed requests out of 1181 (0.0%) during the incident. |

## Round 5 — replica_reduction → payment-service  ·  **RECOVERED**

TTD 4.82s (target 35s, met) · TTM 11.4s · TTR 20.0s (target 120s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: Highest business impact (10) replica reduction on payment-service, never tried, many dependents, and introduces a new fault type for this campaign.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | replica_reduction | order-service | 0.31 | never | — |
| 2 | replica_reduction | api-gateway | 0.221 | 199.2 | recovered_within_sla |
| 3 | replica_reduction | payment-service | 0.196 | 277.5 | recovered_within_sla |
| 4 | replica_reduction | product-service | 0.161 | 227.7 | recovered_within_sla |
| 5 | cpu_throttle | notification-service | -0.02 | never | — |
| 6 | latency_injection | notification-service | -0.02 | never | — |
| 7 | network_partition | notification-service | -0.02 | never | — |
| 8 | pod_deletion | product-service | -0.085 | never | — |
| 9 | latency_injection | order-service | -0.093 | 231.7 | mitigated |
| 10 | network_partition | api-gateway | -0.167 | 234.3 | recovered_within_sla |

### 2. Safety check before injecting

Decision **GO** · risk HIGH · system health 100.0% · target ready 2/2 · load 0.93× baseline · dependents api-gateway, order-service · users possibly affected 100%

### 3. Failure injected

`replica_reduction` on **payment-service** at 04:18:50 UTC — succeeded

Details: `{"hpa": "payment-service-hpa", "original": {"minReplicas": 2, "maxReplicas": 4}, "patched_to": {"minReplicas": 1, "maxReplicas": 1}}`

### 4. Detection

Confirmed at 04:18:55 UTC on **payment-service** as `replica_exhaustion` · severity 0.8 · Isolation Forest score 0.1279 (threshold 0.1031) · flags: capacity_below_baseline, metrics_unreachable

Evidence:
- replicas ready 1/1 (declared minimum 2)
- metrics endpoint unreachable on 50% of pods
- autoscaler bounds min=1 max=1 below declared minimum 2

LSTM 60 s forecast: score 0.1519 (returning to normal)

### 5. Root-cause analysis

Origin **payment-service** · type `replica_exhaustion` · confidence 0.96 · call path api-gateway → payment-service · affected payment-service

> Root cause localised to payment-service (replica exhaustion, confidence 96%). No other service deviates; the fault is contained to payment-service. Change evidence: HPA bounds 1-1 are below the declared 2-4; Pod payment-service-7d546fc794-wh4kn: Killing — Stopping container payment-service.

Evidence:
- replicas ready 1/1 (declared minimum 2)
- metrics endpoint unreachable on 50% of pods
- autoscaler bounds min=1 max=1 below declared minimum 2
- HPA bounds 1-1 are below the declared 2-4
- Pod payment-service-7d546fc794-wh4kn: Killing — Stopping container payment-service

| Candidate | Score | Why |
|---|---|---|
| payment-service | 7.6 | severity 0.80; no anomalous dependency explains it; earliest onset; structural fault on the service itself; HPA bounds 1-1 are below the declared 2-4; Pod payment-service-7d546fc794-wh4kn: Killing — Stopping container payment-service |

### 6. Decision

Action **hpa_scaleout** (fallback resource_restore) · confidence 0.653 · priority 8.0

- payment-service: replica exhaustion at severity 0.80; business impact 10/10 -> priority 8.00. Playbook: hpa_scaleout, fallback resource_restore.
- Confidence in hpa_scaleout: 0.65 (history 0.80 over 1 attempt(s) x RCA 0.96 x blast factor 0.85).
- Decision: hpa_scaleout on payment-service (fallback resource_restore, confidence 0.65).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| hpa_scaleout | payment-service | success | yes | 6.1s | autoscaler 1-1 -> 3-4; 1 -> 3 Ready replicas |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"restored": false, "note": "autoscaler already at or above declared bounds"}` · autoscaler `{"from": {"minReplicas": 3, "maxReplicas": 4}, "to": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 0 failed of 480 requests (0.0%) · user p99 243.5 ms over 24 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 04:18:31 | STRATEGY | payment-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose replica_reduction on payment-service: Highest business impact (10) replica reduction on payment-service, never tried, many dependents, and introduces a new fault type for this campaign. |
| 04:18:50 | PREFLIGHT | payment-service | GO: payment-service at 2/2 Ready, system 100% healthy. Blast radius: 2 dependent service(s) ['api-gateway', 'order-service'], ~100% of users, risk HIGH. |
| 04:18:50 | INJECT | payment-service | Injected replica_reduction into payment-service: Clamp HPA to min=max=1 (payment-service-hpa). |
| 04:18:55 | DETECT | payment-service | Anomaly confirmed on payment-service 5s after injection: pattern matches replica exhaustion. Isolation Forest score +0.128 (threshold +0.103), severity 0.80. Evidence: replicas ready 1/1 (declared minimum 2); metrics endpoint unreachable on 50% of pods; autoscaler bounds min=1 max=1 below declared minimum 2. LSTM forecast for the next 60s: score +0.152 (returning to normal). |
| 04:19:00 | RCA | payment-service | Root cause localised to payment-service (replica exhaustion, confidence 96%). No other service deviates; the fault is contained to payment-service. Change evidence: HPA bounds 1-1 are below the declared 2-4; Pod payment-service-7d546fc794-wh4kn: Killing — Stopping container payment-service. |
| 04:19:00 | DECIDE | payment-service | Confidence in hpa_scaleout: 0.65 (history 0.80 over 1 attempt(s) x RCA 0.96 x blast factor 0.85). Decision: hpa_scaleout on payment-service (fallback resource_restore, confidence 0.65). |
| 04:19:00 | REMEDIATE | payment-service | Executing hpa_scaleout on payment-service. |
| 04:19:06 | REMEDIATE | payment-service | hpa_scaleout succeeded in 6.1s — autoscaler 1-1 -> 3-4; 1 -> 3 Ready replicas. |
| 04:19:10 | VERIFY | payment-service | payment-service verified functional: 3/3 replicas Ready and 5 consecutive user-path probes OK (last 6ms). |
| 04:19:15 | TEARDOWN | payment-service | Round teardown for payment-service: no residual fault found; autoscaler returned to declared bounds. |
| 04:19:25 | RECOVERED | payment-service | payment-service recovered: detected in 4.82s, mitigated in 11.4s, fully back to its normal operating band in 20.0s (target 120s — MET). Users saw 0 failed requests out of 480 (0.0%) during the incident. |

## Campaign-level events

| Time (UTC) | Phase | Message |
|---|---|---|
| 04:12:13 | CAMPAIGN | Campaign c-20261011-041213-4e97 starting: 5 rounds (auto, auto, auto, auto, auto). |
| 04:19:25 | SUMMARY | Campaign completed: resilience score 99.6/100 — EXCELLENT — every fault detected, diagnosed and healed within SLA. |
