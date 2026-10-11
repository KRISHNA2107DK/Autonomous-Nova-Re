# Incident log — campaign `c-20261011-005421-d315`

**Resilience score 99.4/100** — EXCELLENT — every fault detected, diagnosed and healed within SLA

| Component | Points |
|---|---|
| recovery sla | 35.0 |
| detection sla | 20.0 |
| remediation effectiveness | 20.0 |
| diagnosis accuracy | 15.0 |
| user protection | 9.44 |

| # | Fault | Target | Status | TTD | TTR | Users failed |
|---|---|---|---|---|---|---|
| 1 | network_partition | order-service | RECOVERED | 9.83s | 40.0s | 10.3% |
| 2 | cpu_throttle | product-service | RECOVERED | 9.84s | 55.0s | 3.5% |
| 3 | pod_deletion | payment-service | RECOVERED | 4.82s | 20.01s | 0.0% |
| 4 | replica_reduction | api-gateway | RECOVERED | 4.82s | 15.0s | 0.0% |
| 5 | latency_injection | api-gateway | RECOVERED | 9.85s | 44.99s | 0.2% |

## Round 1 — network_partition → order-service  ·  **RECOVERED**

TTD 9.83s (target 30s, met) · TTM 10.59s · TTR 40.0s (target 90s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: First-time network partition on high‑impact order-service, affecting the critical api-gateway and exposing recovery paths for dependent services.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | cpu_throttle | product-service | 0.565 | never | — |
| 2 | latency_injection | product-service | 0.565 | never | — |
| 3 | pod_deletion | product-service | 0.565 | never | — |
| 4 | network_partition | order-service | 0.56 | never | — |
| 5 | pod_deletion | order-service | 0.56 | never | — |
| 6 | replica_reduction | order-service | 0.56 | never | — |
| 7 | latency_injection | order-service | 0.445 | 27.7 | mitigated |
| 8 | cpu_throttle | api-gateway | 0.413 | 78.0 | recovered_within_sla |
| 9 | latency_injection | api-gateway | 0.411 | 76.2 | recovered_within_sla |
| 10 | cpu_throttle | notification-service | 0.38 | never | — |

### 2. Safety check before injecting

Decision **GO** · risk MEDIUM · system health 100.0% · target ready 2/2 · load 0.91× baseline · dependents api-gateway · users possibly affected 100%

### 3. Failure injected

`network_partition` on **order-service** at 00:54:45 UTC — succeeded

Details: `{"policy": "chaos-isolate-order-service", "effect": "deny all ingress + egress", "conntrack_flush": {"ok": true, "pod_ips": ["10.244.0.12", "10.244.0.7"], "agents": {"chaos-agent-zm457": true}}}`

### 4. Detection

Confirmed at 00:54:55 UTC on **api-gateway** as `high_latency` · severity 0.9194 · Isolation Forest score 0.0125 (threshold 0.1031) · flags: iforest, zscore:p99_latency_ms, zscore:inflight

Evidence:
- p99_latency_ms=8797.37ms vs baseline 242.46ms (z=+25.0)
- caller_p99_ms=243.30ms vs baseline 242.66ms (z=+0.0)

LSTM 60 s forecast: score 0.0085 (still anomalous)

### 5. Root-cause analysis

Origin **order-service** · type `network_partition` · confidence 0.95 · call path api-gateway → order-service · affected api-gateway, order-service, notification-service

> Root cause localised to order-service (network partition, confidence 95%). api-gateway also deviate as callers of order-service: its failure propagates to them. notification-service also deviate without a dependency explaining it (lower-ranked candidates). Change evidence: NetworkPolicy 'chaos-isolate-order-service' denies all Ingress/Egress traffic for pods of order-service, created 16s ago; 2 ERROR log lines in the last 60s, e.g. 'dependency failure (product-service)'.

Evidence:
- replicas ready 2/2 (declared minimum 2)
- metrics endpoint unreachable on 100% of pods
- caller_error_rate=0.0% vs baseline 0.0% (z=+0.0)
- request_rate=5.06 req/s vs baseline 8.08 req/s (z=-3.7)
- pods are running (no container restarts) but cannot be reached over the pod network
- NetworkPolicy 'chaos-isolate-order-service' denies all Ingress/Egress traffic for pods of order-service, created 16s ago
- Pod order-service-6d874b5f49-84lmr: Unhealthy — Readiness probe failed: Get "http://10.244.0.12:8002/ready": context deadline exceeded (Client.Timeout exceeded while aw
- Pod order-service-6d874b5f49-dtwm6: Unhealthy — Readiness probe failed: Get "http://10.244.0.7:8002/ready": context deadline exceeded (Client.Timeout exceeded while awa
- 2 ERROR log lines in the last 60s, e.g. 'dependency failure (product-service)'

| Candidate | Score | Why |
|---|---|---|
| order-service | 8.557 | severity 1.00; no anomalous dependency explains it; explains anomalies in callers ['api-gateway']; structural fault on the service itself; NetworkPolicy 'chaos-isolate-order-service' denies all Ingress/Egress traffic for pods of order-service, created 16s ago; Pod order-service-6d874b5f49-84lmr: Unhealthy — Readiness probe failed: Get "http://10.244.0.12:8002/ready": context deadline exceeded (Cli… |
| api-gateway | 2.492 | severity 0.97; its dependencies ['order-service'] are also anomalous (likely a victim); earliest onset; 161 ERROR log lines in the last 60s, e.g. 'request failed' |
| notification-service | 0.955 | severity 0.33; only symptom is reduced traffic — consistent with an upstream failure; no anomalous dependency explains it; explains anomalies in callers ['api-gateway'] |

### 6. Decision

Action **network_policy_rollback** (fallback rolling_restart) · confidence 0.615 · priority 7.99

- order-service: network partition at severity 1.00; business impact 8/10 -> priority 7.99. Playbook: network_policy_rollback, fallback rolling_restart.
- Confidence in network_policy_rollback: 0.61 (prior 0.70 (no history yet) x RCA 0.95 x blast factor 0.93).
- Decision: network_policy_rollback on order-service (fallback rolling_restart, confidence 0.61).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| network_policy_rollback | order-service | success | yes | 2.0s | removed 1 isolating NetworkPolicy(ies): chaos-isolate-order-service |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"policy": "chaos-isolate-order-service", "deleted": false}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 102 failed of 992 requests (10.3%) · user p99 9497.6 ms over 49 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 00:54:27 | STRATEGY | order-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose network_partition on order-service: First-time network partition on high‑impact order-service, affecting the critical api-gateway and exposing recovery paths for dependent services. |
| 00:54:45 | PREFLIGHT | order-service | GO: order-service at 2/2 Ready, system 100% healthy. Blast radius: 1 dependent service(s) ['api-gateway'], ~100% of users, risk MEDIUM. |
| 00:54:46 | INJECT | order-service | Injected network_partition into order-service: Deny-all NetworkPolicy selecting the service's pods (chaos-isolate-order-service). |
| 00:54:55 | DETECT | api-gateway | Anomaly confirmed on api-gateway 10s after injection: pattern matches high latency. Isolation Forest score +0.013 (threshold +0.103), severity 0.92. Evidence: p99_latency_ms=8797.37ms vs baseline 242.46ms (z=+25.0); caller_p99_ms=243.30ms vs baseline 242.66ms (z=+0.0). LSTM forecast for the next 60s: score +0.009 (still anomalous). |
| 00:55:01 | RCA | order-service | Root cause localised to order-service (network partition, confidence 95%). api-gateway also deviate as callers of order-service: its failure propagates to them. notification-service also deviate without a dependency explaining it (lower-ranked candidates). Change evidence: NetworkPolicy 'chaos-isolate-order-service' denies all Ingress/Egress traffic for pods of order-service, created 16s ago; 2 ERROR log lines in the last 60s, e.g. 'dependency failure (product-service)'. |
| 00:55:01 | DECIDE | order-service | Confidence in network_policy_rollback: 0.61 (prior 0.70 (no history yet) x RCA 0.95 x blast factor 0.93). Decision: network_policy_rollback on order-service (fallback rolling_restart, confidence 0.61). |
| 00:55:01 | REMEDIATE | order-service | Executing network_policy_rollback on order-service. |
| 00:55:03 | REMEDIATE | order-service | network_policy_rollback succeeded in 2.0s — removed 1 isolating NetworkPolicy(ies): chaos-isolate-order-service. |
| 00:55:10 | VERIFY | order-service | order-service verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 7ms). |
| 00:55:45 | TEARDOWN | order-service | Round teardown for order-service: no residual fault found; autoscaler returned to declared bounds. |
| 00:55:55 | RECOVERED | order-service | order-service recovered: detected in 9.83s, mitigated in 10.59s, fully back to its normal operating band in 40.0s (target 90s — MET). Users saw 102 failed requests out of 992 (10.3%) during the incident. |

## Round 2 — cpu_throttle → product-service  ·  **RECOVERED**

TTD 9.84s (target 35s, met) · TTM 7.67s · TTR 55.0s (target 90s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: First-time CPU throttle on high‑traffic product-service, maximizing new fault/service coverage and business impact

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | cpu_throttle | product-service | 0.565 | never | — |
| 2 | latency_injection | product-service | 0.565 | never | — |
| 3 | pod_deletion | product-service | 0.565 | never | — |
| 4 | cpu_throttle | api-gateway | 0.414 | 79.6 | recovered_within_sla |
| 5 | latency_injection | api-gateway | 0.412 | 77.8 | recovered_within_sla |
| 6 | cpu_throttle | notification-service | 0.38 | never | — |
| 7 | latency_injection | notification-service | 0.38 | never | — |
| 8 | pod_deletion | api-gateway | 0.373 | 30.2 | recovered_within_sla |
| 9 | pod_deletion | payment-service | 0.361 | 76.1 | recovered_within_sla |
| 10 | replica_reduction | payment-service | 0.361 | 75.1 | recovered_within_sla |

### 2. Safety check before injecting

Decision **GO** · risk HIGH · system health 100.0% · target ready 2/2 · load 0.97× baseline · dependents api-gateway, order-service · users possibly affected 100%

### 3. Failure injected

`cpu_throttle` on **product-service** at 00:56:20 UTC — succeeded

Details: `{"pods": ["product-service-84848bf994-7gtnp", "product-service-84848bf994-nxvlh"], "cpu_limit": "25m", "original": {"product-service-84848bf994-7gtnp": {"product-service": {"requests": {"cpu": "100m", "memory": "96Mi"}, "limits": {"cpu": "500m", "memory": "256Mi"}}}, "product-service-84848bf994-nxvlh": {"product-service": {"requests": {"cpu": "100m", "memory": "96Mi"}, "limits": {"cpu": "500m", "memory": "256Mi"}}}}}`

### 4. Detection

Confirmed at 00:56:30 UTC on **order-service** as `high_latency` · severity 0.9549 · Isolation Forest score -0.0944 (threshold 0.1031) · flags: iforest, zscore:p99_latency_ms, zscore:inflight, zscore:caller_p99_ms

Evidence:
- p99_latency_ms=861.67ms vs baseline 246.95ms (z=+16.6)
- caller_p99_ms=1127.50ms vs baseline 246.99ms (z=+23.8)

LSTM 60 s forecast: score -0.0828 (still anomalous)

### 5. Root-cause analysis

Origin **product-service** · type `cpu_throttle` · confidence 0.95 · call path api-gateway → product-service · affected api-gateway, product-service, order-service

> Root cause localised to product-service (cpu throttle, confidence 95%). api-gateway, order-service also deviate as callers of product-service: its failure propagates to them. Change evidence: pod product-service-84848bf994-7gtnp CPU limit is 25m vs declared 500m; pod product-service-84848bf994-nxvlh CPU limit is 25m vs declared 500m.

Evidence:
- p99_latency_ms=730.56ms vs baseline 16.09ms (z=+25.0)
- caller_p99_ms=860.72ms vs baseline 16.56ms (z=+25.0)
- pod product-service-84848bf994-7gtnp CPU limit is 25m vs declared 500m
- pod product-service-84848bf994-nxvlh CPU limit is 25m vs declared 500m

| Candidate | Score | Why |
|---|---|---|
| product-service | 9.265 | severity 0.96; no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service']; earliest onset; pod product-service-84848bf994-7gtnp CPU limit is 25m vs declared 500m; pod product-service-84848bf994-nxvlh CPU limit is 25m vs declared 500m |
| order-service | 2.19 | severity 0.97; its dependencies ['product-service'] are also anomalous (likely a victim); explains anomalies in callers ['api-gateway']; earliest onset; 40 ERROR log lines in the last 60s, e.g. 'dependency failure (product-service)' |
| api-gateway | 2.029 | severity 0.97; its dependencies ['product-service', 'order-service'] are also anomalous (likely a victim); earliest onset; 68 ERROR log lines in the last 60s, e.g. 'upstream error (order-service)' |

### 6. Decision

Action **resource_restore** (fallback rolling_restart) · confidence 0.565 · priority 5.744

- product-service: cpu throttle at severity 0.96; business impact 6/10 -> priority 5.74. Playbook: resource_restore, fallback rolling_restart.
- Confidence in resource_restore: 0.56 (prior 0.70 (no history yet) x RCA 0.95 x blast factor 0.85).
- Decision: resource_restore on product-service (fallback rolling_restart, confidence 0.56).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| resource_restore | product-service | success | yes | 2.1s | resized 2 container(s) in place to {'product-service': {'requests': {'cpu': '100m', 'memory': '96Mi'}, 'limits': {'cpu': '500m', 'memory': '256Mi'}}} |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"restored_pods": []}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 45 failed of 1312 requests (3.5%) · user p99 8339.7 ms over 64 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 00:56:02 | STRATEGY | product-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose cpu_throttle on product-service: First-time CPU throttle on high‑traffic product-service, maximizing new fault/service coverage and business impact |
| 00:56:20 | PREFLIGHT | product-service | GO: product-service at 2/2 Ready, system 100% healthy. Blast radius: 2 dependent service(s) ['api-gateway', 'order-service'], ~100% of users, risk HIGH. |
| 00:56:21 | INJECT | product-service | Injected cpu_throttle into product-service: In-place resize of every replica's CPU limit to a starvation value (product-service-84848bf994-7gtnp,product-service-84848bf994-nxvlh). |
| 00:56:30 | DETECT | order-service | Anomaly confirmed on order-service 10s after injection: pattern matches high latency. Isolation Forest score -0.094 (threshold +0.103), severity 0.95. Evidence: p99_latency_ms=861.67ms vs baseline 246.95ms (z=+16.6); caller_p99_ms=1127.50ms vs baseline 246.99ms (z=+23.8). Also deviating: api-gateway, product-service. LSTM forecast for the next 60s: score -0.083 (still anomalous). |
| 00:56:36 | RCA | product-service | Root cause localised to product-service (cpu throttle, confidence 95%). api-gateway, order-service also deviate as callers of product-service: its failure propagates to them. Change evidence: pod product-service-84848bf994-7gtnp CPU limit is 25m vs declared 500m; pod product-service-84848bf994-nxvlh CPU limit is 25m vs declared 500m. |
| 00:56:36 | DECIDE | product-service | Confidence in resource_restore: 0.56 (prior 0.70 (no history yet) x RCA 0.95 x blast factor 0.85). Decision: resource_restore on product-service (fallback rolling_restart, confidence 0.56). |
| 00:56:36 | REMEDIATE | product-service | Executing resource_restore on product-service. |
| 00:56:38 | REMEDIATE | product-service | resource_restore succeeded in 2.1s — resized 2 container(s) in place to {'product-service': {'requests': {'cpu': '100m', 'memory': '96Mi'}, 'limits': {'cpu': '500m', 'memory': '256Mi'}}}. |
| 00:56:42 | VERIFY | product-service | product-service verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 5ms). |
| 00:57:35 | TEARDOWN | product-service | Round teardown for product-service: no residual fault found; autoscaler returned to declared bounds. |
| 00:57:45 | RECOVERED | product-service | product-service recovered: detected in 9.84s, mitigated in 7.67s, fully back to its normal operating band in 55.0s (target 90s — MET). Users saw 45 failed requests out of 1312 (3.5%) during the incident. |

## Round 3 — pod_deletion → payment-service  ·  **RECOVERED**

TTD 4.82s (target 25s, met) · TTM 11.53s · TTR 20.01s (target 90s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: Inject pod_deletion into high‑impact payment-service, unused this campaign and long since last try, to test recovery of a critical downstream service.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | latency_injection | api-gateway | 0.414 | 79.6 | recovered_within_sla |
| 2 | latency_injection | notification-service | 0.38 | never | — |
| 3 | pod_deletion | api-gateway | 0.375 | 32.1 | recovered_within_sla |
| 4 | pod_deletion | payment-service | 0.363 | 77.9 | recovered_within_sla |
| 5 | replica_reduction | payment-service | 0.362 | 76.9 | recovered_within_sla |
| 6 | replica_reduction | api-gateway | 0.358 | 16.8 | recovered_within_sla |
| 7 | latency_injection | product-service | 0.315 | never | — |
| 8 | pod_deletion | product-service | 0.315 | never | — |
| 9 | latency_injection | payment-service | 0.31 | 18.7 | recovered_within_sla |
| 10 | pod_deletion | order-service | 0.31 | never | — |

### 2. Safety check before injecting

Decision **GO** · risk HIGH · system health 100.0% · target ready 2/2 · load 0.99× baseline · dependents api-gateway, order-service · users possibly affected 100%

### 3. Failure injected

`pod_deletion` on **payment-service** at 00:58:10 UTC — succeeded

Details: `{"pod": "payment-service-b6f875b8d-6jctr", "pod_ip": "10.244.0.11", "ready_pods_before": 2}`

### 4. Detection

Confirmed at 00:58:15 UTC on **payment-service** as `pod_crash` · severity 0.4072 · Isolation Forest score 0.0991 (threshold 0.1031) · flags: replicas_lost

Evidence:
- replicas ready 2/2 (declared minimum 2)
- Ready pod(s) payment-service-b6f875b8d-6jctr disappeared without a scale-down or rollout
- caller_error_rate=0.0% vs baseline 0.0% (z=+0.0)

LSTM 60 s forecast: score 0.0738 (returning to normal)

### 5. Root-cause analysis

Origin **payment-service** · type `pod_crash` · confidence 0.919 · call path api-gateway → payment-service · affected payment-service

> Root cause localised to payment-service (pod crash, confidence 92%). No other service deviates; the fault is contained to payment-service. Change evidence: Pod payment-service-b6f875b8d-6jctr: Killing — Stopping container payment-service; Pod payment-service-b6f875b8d-6wtrx: Unhealthy — Startup probe failed: Get "http://10.244.0.22:8003/health": dial tcp 10.244.0.22:8003: connect: connection refused.

Evidence:
- replicas ready 2/2 (declared minimum 2)
- Ready pod(s) payment-service-b6f875b8d-6jctr disappeared without a scale-down or rollout
- caller_error_rate=0.0% vs baseline 0.0% (z=+0.0)
- Pod payment-service-b6f875b8d-6jctr: Killing — Stopping container payment-service
- Pod payment-service-b6f875b8d-6wtrx: Unhealthy — Startup probe failed: Get "http://10.244.0.22:8003/health": dial tcp 10.244.0.22:8003: connect: connection refused

| Candidate | Score | Why |
|---|---|---|
| payment-service | 3.989 | severity 0.24; no anomalous dependency explains it; earliest onset; structural fault on the service itself; Pod payment-service-b6f875b8d-6jctr: Killing — Stopping container payment-service; Pod payment-service-b6f875b8d-6wtrx: Unhealthy — Startup probe failed: Get "http://10.244.0.22:8003/health": dial tcp 10.244.0.22:8003: connect: connection refused |

### 6. Decision

Action **hpa_scaleout** (fallback rolling_restart) · confidence 0.625 · priority 2.443

- payment-service: pod crash at severity 0.24; business impact 10/10 -> priority 2.44. Playbook: hpa_scaleout, fallback rolling_restart.
- Confidence in hpa_scaleout: 0.62 (history 0.80 over 1 attempt(s) x RCA 0.92 x blast factor 0.85).
- Decision: hpa_scaleout on payment-service (fallback rolling_restart, confidence 0.62).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| hpa_scaleout | payment-service | success | yes | 6.1s | autoscaler 2-4 -> 3-4; 2 -> 3 Ready replicas |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"reversible": false, "note": "Kubernetes reschedules deleted pods by itself"}` · autoscaler `{"from": {"minReplicas": 3, "maxReplicas": 4}, "to": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 0 failed of 480 requests (0.0%) · user p99 241.0 ms over 24 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 00:57:52 | STRATEGY | payment-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose pod_deletion on payment-service: Inject pod_deletion into high‑impact payment-service, unused this campaign and long since last try, to test recovery of a critical downstream service. |
| 00:58:10 | PREFLIGHT | payment-service | GO: payment-service at 2/2 Ready, system 100% healthy. Blast radius: 2 dependent service(s) ['api-gateway', 'order-service'], ~100% of users, risk HIGH. |
| 00:58:10 | INJECT | payment-service | Injected pod_deletion into payment-service: Force-delete one Ready pod (grace period 0) (payment-service-b6f875b8d-6jctr). |
| 00:58:15 | DETECT | payment-service | Anomaly confirmed on payment-service 5s after injection: pattern matches pod crash. Isolation Forest score +0.099 (threshold +0.103), severity 0.41. Evidence: replicas ready 2/2 (declared minimum 2); Ready pod(s) payment-service-b6f875b8d-6jctr disappeared without a scale-down or rollout; caller_error_rate=0.0% vs baseline 0.0% (z=+0.0). LSTM forecast for the next 60s: score +0.074 (returning to normal). |
| 00:58:21 | RCA | payment-service | Root cause localised to payment-service (pod crash, confidence 92%). No other service deviates; the fault is contained to payment-service. Change evidence: Pod payment-service-b6f875b8d-6jctr: Killing — Stopping container payment-service; Pod payment-service-b6f875b8d-6wtrx: Unhealthy — Startup probe failed: Get "http://10.244.0.22:8003/health": dial tcp 10.244.0.22:8003: connect: connection refused. |
| 00:58:21 | DECIDE | payment-service | Confidence in hpa_scaleout: 0.62 (history 0.80 over 1 attempt(s) x RCA 0.92 x blast factor 0.85). Decision: hpa_scaleout on payment-service (fallback rolling_restart, confidence 0.62). |
| 00:58:21 | REMEDIATE | payment-service | Executing hpa_scaleout on payment-service. |
| 00:58:27 | REMEDIATE | payment-service | hpa_scaleout succeeded in 6.1s — autoscaler 2-4 -> 3-4; 2 -> 3 Ready replicas. |
| 00:58:31 | VERIFY | payment-service | payment-service verified functional: 3/3 replicas Ready and 5 consecutive user-path probes OK (last 7ms). |
| 00:58:35 | TEARDOWN | payment-service | Round teardown for payment-service: no residual fault found; autoscaler returned to declared bounds. |
| 00:58:45 | RECOVERED | payment-service | payment-service recovered: detected in 4.82s, mitigated in 11.53s, fully back to its normal operating band in 20.01s (target 90s — MET). Users saw 0 failed requests out of 480 (0.0%) during the incident. |

## Round 4 — replica_reduction → api-gateway  ·  **RECOVERED**

TTD 4.82s (target 35s, met) · TTM 10.33s · TTR 15.0s (target 120s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: First use of replica_reduction on high‑impact api‑gateway, a service not yet tested this campaign, maximizing insight into core traffic resilience.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | latency_injection | api-gateway | 0.414 | 80.6 | recovered_within_sla |
| 2 | latency_injection | notification-service | 0.38 | never | — |
| 3 | replica_reduction | api-gateway | 0.359 | 17.8 | recovered_within_sla |
| 4 | latency_injection | product-service | 0.315 | never | — |
| 5 | replica_reduction | order-service | 0.31 | never | — |
| 6 | latency_injection | order-service | 0.2 | 32.2 | mitigated |
| 7 | replica_reduction | payment-service | 0.113 | 77.9 | recovered_within_sla |
| 8 | latency_injection | payment-service | 0.061 | 19.7 | recovered_within_sla |
| 9 | replica_reduction | product-service | 0.051 | 28.2 | recovered_within_sla |
| 10 | cpu_throttle | api-gateway | 0.016 | 82.4 | recovered_within_sla |

### 2. Safety check before injecting

Decision **GO** · risk MEDIUM · system health 100.0% · target ready 2/2 · load 1.0× baseline · dependents none · users possibly affected 100%

### 3. Failure injected

`replica_reduction` on **api-gateway** at 00:59:10 UTC — succeeded

Details: `{"hpa": "api-gateway-hpa", "original": {"minReplicas": 2, "maxReplicas": 4}, "patched_to": {"minReplicas": 1, "maxReplicas": 1}}`

### 4. Detection

Confirmed at 00:59:15 UTC on **api-gateway** as `replica_exhaustion` · severity 0.5 · Isolation Forest score 0.1399 (threshold 0.1031) · flags: capacity_below_baseline

Evidence:
- replicas ready 1/1 (declared minimum 2)
- autoscaler bounds min=1 max=1 below declared minimum 2

LSTM 60 s forecast: score 0.1427 (returning to normal)

### 5. Root-cause analysis

Origin **api-gateway** · type `replica_exhaustion` · confidence 0.96 · call path api-gateway · affected api-gateway

> Root cause localised to api-gateway (replica exhaustion, confidence 96%). No other service deviates; the fault is contained to api-gateway. Change evidence: HPA bounds 1-1 are below the declared 2-4; Pod api-gateway-6f5c8cf68b-cv44x: Killing — Stopping container api-gateway.

Evidence:
- replicas ready 1/1 (declared minimum 2)
- autoscaler bounds min=1 max=1 below declared minimum 2
- HPA bounds 1-1 are below the declared 2-4
- Pod api-gateway-6f5c8cf68b-cv44x: Killing — Stopping container api-gateway

| Candidate | Score | Why |
|---|---|---|
| api-gateway | 7.6 | severity 0.80; no anomalous dependency explains it; earliest onset; structural fault on the service itself; HPA bounds 1-1 are below the declared 2-4; Pod api-gateway-6f5c8cf68b-cv44x: Killing — Stopping container api-gateway |

### 6. Decision

Action **hpa_scaleout** (fallback resource_restore) · confidence 0.768 · priority 7.2

- api-gateway: replica exhaustion at severity 0.80; business impact 9/10 -> priority 7.20. Playbook: hpa_scaleout, fallback resource_restore.
- Confidence in hpa_scaleout: 0.77 (history 0.80 over 1 attempt(s) x RCA 0.96 x blast factor 1.00).
- Decision: hpa_scaleout on api-gateway (fallback resource_restore, confidence 0.77).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| hpa_scaleout | api-gateway | success | yes | 4.1s | autoscaler 1-1 -> 3-4; 1 -> 3 Ready replicas |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"restored": false, "note": "autoscaler already at or above declared bounds"}` · autoscaler `{"from": {"minReplicas": 3, "maxReplicas": 4}, "to": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 0 failed of 384 requests (0.0%) · user p99 243.6 ms over 19 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 00:58:52 | STRATEGY | api-gateway | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose replica_reduction on api-gateway: First use of replica_reduction on high‑impact api‑gateway, a service not yet tested this campaign, maximizing insight into core traffic resilience. |
| 00:59:10 | PREFLIGHT | api-gateway | GO: api-gateway at 2/2 Ready, system 100% healthy. Blast radius: 0 dependent service(s) , ~100% of users, risk MEDIUM. |
| 00:59:10 | INJECT | api-gateway | Injected replica_reduction into api-gateway: Clamp HPA to min=max=1 (api-gateway-hpa). |
| 00:59:15 | DETECT | api-gateway | Anomaly confirmed on api-gateway 5s after injection: pattern matches replica exhaustion. Isolation Forest score +0.140 (threshold +0.103), severity 0.50. Evidence: replicas ready 1/1 (declared minimum 2); autoscaler bounds min=1 max=1 below declared minimum 2. LSTM forecast for the next 60s: score +0.143 (returning to normal). |
| 00:59:20 | RCA | api-gateway | Root cause localised to api-gateway (replica exhaustion, confidence 96%). No other service deviates; the fault is contained to api-gateway. Change evidence: HPA bounds 1-1 are below the declared 2-4; Pod api-gateway-6f5c8cf68b-cv44x: Killing — Stopping container api-gateway. |
| 00:59:20 | DECIDE | api-gateway | Confidence in hpa_scaleout: 0.77 (history 0.80 over 1 attempt(s) x RCA 0.96 x blast factor 1.00). Decision: hpa_scaleout on api-gateway (fallback resource_restore, confidence 0.77). |
| 00:59:21 | REMEDIATE | api-gateway | Executing hpa_scaleout on api-gateway. |
| 00:59:25 | REMEDIATE | api-gateway | hpa_scaleout succeeded in 4.1s — autoscaler 1-1 -> 3-4; 1 -> 3 Ready replicas. |
| 00:59:30 | VERIFY | api-gateway | api-gateway verified functional: 3/3 replicas Ready and 5 consecutive user-path probes OK (last 10ms). |
| 00:59:35 | TEARDOWN | api-gateway | Round teardown for api-gateway: no residual fault found; autoscaler returned to declared bounds. |
| 00:59:46 | RECOVERED | api-gateway | api-gateway recovered: detected in 4.82s, mitigated in 10.33s, fully back to its normal operating band in 15.0s (target 120s — MET). Users saw 0 failed requests out of 384 (0.0%) during the incident. |

## Round 5 — latency_injection → api-gateway  ·  **RECOVERED**

TTD 9.85s (target 35s, met) · TTM 14.75s · TTR 44.99s (target 120s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: Latency injection on api-gateway (high impact 9, 100% traffic, many dependents) hasn’t been tried recently and introduces a new fault type for this service, maximizing resilience insight.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | latency_injection | notification-service | 0.38 | never | — |
| 2 | latency_injection | product-service | 0.315 | never | — |
| 3 | latency_injection | order-service | 0.201 | 33.2 | mitigated |
| 4 | latency_injection | api-gateway | 0.165 | 81.6 | recovered_within_sla |
| 5 | latency_injection | payment-service | 0.063 | 20.7 | recovered_within_sla |
| 6 | cpu_throttle | notification-service | -0.02 | never | — |
| 7 | network_partition | notification-service | -0.02 | never | — |
| 8 | pod_deletion | product-service | -0.085 | never | — |
| 9 | pod_deletion | order-service | -0.09 | never | — |
| 10 | replica_reduction | order-service | -0.09 | never | — |

### 2. Safety check before injecting

Decision **GO** · risk MEDIUM · system health 100.0% · target ready 2/2 · load 1.02× baseline · dependents none · users possibly affected 100%

### 3. Failure injected

`latency_injection` on **api-gateway** at 01:00:10 UTC — succeeded

Details: `{"pod": "api-gateway-6f5c8cf68b-t6rbp", "delay": "200ms", "jitter": "50ms", "command": "tc qdisc replace dev eth0 root netem delay 200ms 50ms distribution normal", "replicas_ready": 2}`

### 4. Detection

Confirmed at 01:00:20 UTC on **api-gateway** as `high_latency` · severity 0.8134 · Isolation Forest score 0.0213 (threshold 0.1031) · flags: iforest, zscore:p99_latency_ms, zscore:caller_p99_ms

Evidence:
- p99_latency_ms=412.19ms vs baseline 242.46ms (z=+4.7)
- caller_p99_ms=690.00ms vs baseline 242.66ms (z=+12.3)

LSTM 60 s forecast: score -0.0188 (still anomalous)

### 5. Root-cause analysis

Origin **api-gateway** · type `high_latency` · confidence 0.935 · call path api-gateway · affected api-gateway, product-service, order-service, payment-service

> Root cause localised to api-gateway (high latency, confidence 94%). product-service, order-service, payment-service deviate because requests from api-gateway stopped reaching them. Signal: p99_latency_ms=412.19ms vs baseline 242.46ms (z=+4.7); caller_p99_ms=690.00ms vs baseline 242.66ms (z=+12.3).

Evidence:
- p99_latency_ms=412.19ms vs baseline 242.46ms (z=+4.7)
- caller_p99_ms=690.00ms vs baseline 242.66ms (z=+12.3)

| Candidate | Score | Why |
|---|---|---|
| api-gateway | 5.534 | severity 0.89; its dependencies ['product-service', 'order-service', 'payment-service'] are also anomalous (likely a victim); earliest onset; its calls to product-service take 754ms longer than product-service itself needs to serve them (caller-side or network problem); its calls to order-service take 489ms longer than order-service itself needs to serve them (caller-side or network problem); its … |
| product-service | 2.646 | severity 0.90; its own server-side latency/errors are normal; the degradation is only visible from callers (network or caller-side problem); no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service']; earliest onset |
| payment-service | 1.199 | severity 0.55; its own server-side latency/errors are normal; the degradation is only visible from callers (network or caller-side problem); no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service'] |
| order-service | -0.499 | severity 0.73; its own server-side latency/errors are normal; the degradation is only visible from callers (network or caller-side problem); its dependencies ['product-service', 'payment-service'] are also anomalous (likely a victim); explains anomalies in callers ['api-gateway']; earliest onset |

### 6. Decision

Action **traffic_reroute** (fallback rolling_restart) · confidence 0.748 · priority 8.026

- api-gateway: high latency at severity 0.89; business impact 9/10 -> priority 8.03. Playbook: traffic_reroute, fallback rolling_restart.
- Confidence in traffic_reroute: 0.75 (history 0.80 over 1 attempt(s) x RCA 0.94 x blast factor 1.00).
- Decision: traffic_reroute on api-gateway (fallback rolling_restart, confidence 0.75).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| traffic_reroute | api-gateway | success | yes | 9.1s | quarantined api-gateway-6f5c8cf68b-t6rbp (worst replica by live telemetry (p99=882ms, next worst score 244 vs 882)); traffic now on 2 healthy replica(s) |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"pod": "api-gateway-6f5c8cf68b-t6rbp", "note": "pod no longer exists (replaced)"}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 2 failed of 1085 requests (0.2%) · user p99 962.6 ms over 54 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 00:59:52 | STRATEGY | api-gateway | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose latency_injection on api-gateway: Latency injection on api-gateway (high impact 9, 100% traffic, many dependents) hasn’t been tried recently and introduces a new fault type for this service, maximizing resilience insight. |
| 01:00:10 | PREFLIGHT | api-gateway | GO: api-gateway at 2/2 Ready, system 100% healthy. Blast radius: 0 dependent service(s) , ~100% of users, risk MEDIUM. |
| 01:00:10 | INJECT | api-gateway | Injected latency_injection into api-gateway: tc netem egress delay on one replica (api-gateway-6f5c8cf68b-t6rbp). |
| 01:00:20 | DETECT | api-gateway | Anomaly confirmed on api-gateway 10s after injection: pattern matches high latency. Isolation Forest score +0.021 (threshold +0.103), severity 0.81. Evidence: p99_latency_ms=412.19ms vs baseline 242.46ms (z=+4.7); caller_p99_ms=690.00ms vs baseline 242.66ms (z=+12.3). Also deviating: product-service, order-service. LSTM forecast for the next 60s: score -0.019 (still anomalous). |
| 01:00:26 | RCA | api-gateway | Root cause localised to api-gateway (high latency, confidence 94%). product-service, order-service, payment-service deviate because requests from api-gateway stopped reaching them. Signal: p99_latency_ms=412.19ms vs baseline 242.46ms (z=+4.7); caller_p99_ms=690.00ms vs baseline 242.66ms (z=+12.3). |
| 01:00:26 | DECIDE | api-gateway | Confidence in traffic_reroute: 0.75 (history 0.80 over 1 attempt(s) x RCA 0.94 x blast factor 1.00). Decision: traffic_reroute on api-gateway (fallback rolling_restart, confidence 0.75). |
| 01:00:26 | REMEDIATE | api-gateway | Executing traffic_reroute on api-gateway. |
| 01:00:35 | REMEDIATE | api-gateway | traffic_reroute succeeded in 9.1s — quarantined api-gateway-6f5c8cf68b-t6rbp (worst replica by live telemetry (p99=882ms, next worst score 244 vs 882)); traffic now on 2 healthy replica(s). |
| 01:00:40 | VERIFY | api-gateway | api-gateway verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 8ms). |
| 01:01:15 | TEARDOWN | api-gateway | Round teardown for api-gateway: no residual fault found; autoscaler returned to declared bounds. |
| 01:01:25 | RECOVERED | api-gateway | api-gateway recovered: detected in 9.85s, mitigated in 14.75s, fully back to its normal operating band in 44.99s (target 120s — MET). Users saw 2 failed requests out of 1085 (0.2%) during the incident. |

## Campaign-level events

| Time (UTC) | Phase | Message |
|---|---|---|
| 00:54:21 | CAMPAIGN | Campaign c-20261011-005421-d315 starting: 5 rounds (auto, auto, auto, auto, auto). |
| 01:01:26 | SUMMARY | Campaign completed: resilience score 99.4/100 — EXCELLENT — every fault detected, diagnosed and healed within SLA. |
