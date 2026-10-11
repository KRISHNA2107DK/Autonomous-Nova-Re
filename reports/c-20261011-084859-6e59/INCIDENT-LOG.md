# Incident log — campaign `c-20261011-084859-6e59`

**Resilience score 95.0/100** — EXCELLENT — every fault detected, diagnosed and healed within SLA

| Component | Points |
|---|---|
| recovery sla | 35.0 |
| detection sla | 16.0 |
| remediation effectiveness | 20.0 |
| diagnosis accuracy | 15.0 |
| user protection | 9.02 |

| # | Fault | Target | Status | TTD | TTR | Users failed |
|---|---|---|---|---|---|---|
| 1 | cpu_throttle | product-service | RECOVERED | 9.75s | 50.0s | 14.3% |
| 2 | network_partition | payment-service | RECOVERED | 9.78s | 50.01s | 9.9% |
| 3 | latency_injection | notification-service | RECOVERED | 64.75s | 30.0s | 0.0% |
| 4 | pod_deletion | api-gateway | RECOVERED | 4.76s | 15.0s | 0.3% |
| 5 | pod_deletion | order-service | RECOVERED | 4.75s | 19.99s | 0.0% |

## Round 1 — cpu_throttle → product-service  ·  **RECOVERED**

TTD 9.75s (target 35s, met) · TTM 10.88s · TTR 50.0s (target 90s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: Product-service CPU throttling hasn't been tried in ~8 hours, targets a degraded high‑traffic service, offering fresh insight into recovery under load.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | network_partition | payment-service | 0.521 | 90.3 | mitigated |
| 2 | cpu_throttle | product-service | 0.469 | 472.7 | recovered_within_sla |
| 3 | network_partition | api-gateway | 0.455 | 158.2 | recovered_within_sla |
| 4 | replica_reduction | payment-service | 0.444 | 270.2 | recovered_within_sla |
| 5 | pod_deletion | api-gateway | 0.43 | 106.1 | recovered_within_sla |
| 6 | cpu_throttle | api-gateway | 0.428 | 102.4 | recovered_within_sla |
| 7 | latency_injection | product-service | 0.425 | 275.5 | recovered_within_sla |
| 8 | pod_deletion | order-service | 0.421 | 276.5 | recovered_within_sla |
| 9 | cpu_throttle | payment-service | 0.407 | 162.9 | recovered_within_sla |
| 10 | replica_reduction | api-gateway | 0.397 | 57.1 | recovered_within_sla |

### 2. Safety check before injecting

Decision **GO** · risk HIGH · system health 100.0% · target ready 2/2 · load 0.95× baseline · dependents api-gateway, order-service · users possibly affected 100%

### 3. Failure injected

`cpu_throttle` on **product-service** at 08:49:23 UTC — succeeded

Details: `{"pods": ["product-service-78f8dcb767-6dvbl", "product-service-78f8dcb767-b475x"], "cpu_limit": "25m", "original": {"product-service-78f8dcb767-6dvbl": {"product-service": {"requests": {"cpu": "100m", "memory": "96Mi"}, "limits": {"cpu": "500m", "memory": "256Mi"}}}, "product-service-78f8dcb767-b475x": {"product-service": {"requests": {"cpu": "100m", "memory": "96Mi"}, "limits": {"cpu": "500m", "memory": "256Mi"}}}}}`

### 4. Detection

Confirmed at 08:49:33 UTC on **product-service** as `high_latency` · severity 0.9787 · Isolation Forest score -0.0696 (threshold 0.1031) · flags: iforest, zscore:p99_latency_ms, zscore:inflight, zscore:caller_p99_ms, replicas_lost

Evidence:
- p99_latency_ms=23.79ms vs baseline 16.09ms (z=+0.5)
- caller_p99_ms=781.67ms vs baseline 16.56ms (z=+25.0)

LSTM 60 s forecast: score -0.0883 (still anomalous)

### 5. Root-cause analysis

Origin **product-service** · type `cpu_throttle` · confidence 0.95 · call path api-gateway → product-service · affected api-gateway, product-service, order-service, payment-service, notification-service

> Root cause localised to product-service (cpu throttle, confidence 95%). api-gateway, order-service also deviate as callers of product-service: its failure propagates to them. payment-service, notification-service also deviate without a dependency explaining it (lower-ranked candidates). Change evidence: pod product-service-78f8dcb767-6dvbl CPU limit is 25m vs declared 500m; pod product-service-78f8dcb767-b475x CPU limit is 25m vs declared 500m.

Evidence:
- p99_latency_ms=23.79ms vs baseline 16.09ms (z=+0.5)
- caller_p99_ms=781.67ms vs baseline 16.56ms (z=+25.0)
- pod product-service-78f8dcb767-6dvbl CPU limit is 25m vs declared 500m
- pod product-service-78f8dcb767-b475x CPU limit is 25m vs declared 500m
- Pod product-service-78f8dcb767-6dvbl: Unhealthy — Readiness probe failed: Get "http://10.244.0.34:8001/ready": context deadline exceeded (Client.Timeout exceeded while aw
- Pod product-service-78f8dcb767-6dvbl: Unhealthy — Liveness probe failed: Get "http://10.244.0.34:8001/health": context deadline exceeded (Client.Timeout exceeded while aw
- Pod product-service-78f8dcb767-b475x: Unhealthy — Readiness probe failed: Get "http://10.244.0.52:8001/ready": context deadline exceeded (Client.Timeout exceeded while aw

| Candidate | Score | Why |
|---|---|---|
| product-service | 11.097 | severity 1.00; no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service']; earliest onset; structural fault on the service itself; pod product-service-78f8dcb767-6dvbl CPU limit is 25m vs declared 500m; pod product-service-78f8dcb767-b475x CPU limit is 25m vs declared 500m; Pod product-service-78f8dcb767-6dvbl: Unhealthy — Readiness probe failed: Get "http:… |
| api-gateway | 2.696 | severity 0.97; its dependencies ['product-service', 'order-service'] are also anomalous (likely a victim); earliest onset; 228 ERROR log lines in the last 60s, e.g. 'upstream error (order-service)' |
| order-service | 2.653 | severity 0.97; its dependencies ['product-service'] are also anomalous (likely a victim); explains anomalies in callers ['api-gateway']; earliest onset; 132 ERROR log lines in the last 60s, e.g. 'dependency failure (product-service)' |
| payment-service | 0.781 | severity 0.09; only symptom is reduced traffic — consistent with an upstream failure; no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service'] |
| notification-service | 0.665 | severity 0.18; only symptom is reduced traffic — consistent with an upstream failure; no anomalous dependency explains it; explains anomalies in callers ['api-gateway'] |

### 6. Decision

Action **resource_restore** (fallback rolling_restart) · confidence 0.646 · priority 5.99

- product-service: cpu throttle at severity 1.00; business impact 6/10 -> priority 5.99. Playbook: resource_restore, fallback rolling_restart.
- Confidence in resource_restore: 0.65 (history 0.80 over 1 attempt(s) x RCA 0.95 x blast factor 0.85).
- Decision: resource_restore on product-service (fallback rolling_restart, confidence 0.65).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| resource_restore | product-service | success | yes | 2.2s | resized 2 container(s) in place to {'product-service': {'requests': {'cpu': '100m', 'memory': '96Mi'}, 'limits': {'cpu': '500m', 'memory': '256Mi'}}} |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"restored_pods": []}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 170 failed of 1189 requests (14.3%) · user p99 9332.5 ms over 59 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 08:49:05 | STRATEGY | product-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose cpu_throttle on product-service: Product-service CPU throttling hasn't been tried in ~8 hours, targets a degraded high‑traffic service, offering fresh insight into recovery under load. |
| 08:49:23 | PREFLIGHT | product-service | GO: product-service at 2/2 Ready, system 100% healthy. Blast radius: 2 dependent service(s) ['api-gateway', 'order-service'], ~100% of users, risk HIGH. |
| 08:49:23 | INJECT | product-service | Injected cpu_throttle into product-service: In-place resize of every replica's CPU limit to a starvation value (product-service-78f8dcb767-6dvbl,product-service-78f8dcb767-b475x). |
| 08:49:33 | DETECT | product-service | Anomaly confirmed on product-service 10s after injection: pattern matches high latency. Isolation Forest score -0.070 (threshold +0.103), severity 0.98. Evidence: p99_latency_ms=23.79ms vs baseline 16.09ms (z=+0.5); caller_p99_ms=781.67ms vs baseline 16.56ms (z=+25.0). Also deviating: api-gateway, order-service. LSTM forecast for the next 60s: score -0.088 (still anomalous). |
| 08:49:38 | RCA | product-service | Root cause localised to product-service (cpu throttle, confidence 95%). api-gateway, order-service also deviate as callers of product-service: its failure propagates to them. payment-service, notification-service also deviate without a dependency explaining it (lower-ranked candidates). Change evidence: pod product-service-78f8dcb767-6dvbl CPU limit is 25m vs declared 500m; pod product-service-78f8dcb767-b475x CPU limit is 25m vs declared 500m. |
| 08:49:38 | DECIDE | product-service | Confidence in resource_restore: 0.65 (history 0.80 over 1 attempt(s) x RCA 0.95 x blast factor 0.85). Decision: resource_restore on product-service (fallback rolling_restart, confidence 0.65). |
| 08:49:38 | REMEDIATE | product-service | Executing resource_restore on product-service (step 1, primary). |
| 08:49:41 | REMEDIATE | product-service | resource_restore succeeded in 2.2s — resized 2 container(s) in place to {'product-service': {'requests': {'cpu': '100m', 'memory': '96Mi'}, 'limits': {'cpu': '500m', 'memory': '256Mi'}}}. |
| 08:49:48 | VERIFY | product-service | product-service verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 10ms). |
| 08:50:33 | TEARDOWN | product-service | Round teardown for product-service: no residual fault found; autoscaler returned to declared bounds. |
| 08:50:43 | RECOVERED | product-service | product-service recovered: detected in 9.75s, mitigated in 10.88s, fully back to its normal operating band in 50.0s (target 90s — MET). Users saw 170 failed requests out of 1189 (14.3%) during the incident. |

## Round 2 — network_partition → payment-service  ·  **RECOVERED**

TTD 9.78s (target 30s, met) · TTM 10.8s · TTR 50.01s (target 90s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: High‑impact network partition on payment-service, long idle time and previous mitigated outcome offers fresh insight into critical path resilience.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | network_partition | payment-service | 0.522 | 92.1 | mitigated |
| 2 | network_partition | api-gateway | 0.456 | 160.0 | recovered_within_sla |
| 3 | replica_reduction | payment-service | 0.444 | 272.0 | recovered_within_sla |
| 4 | pod_deletion | api-gateway | 0.431 | 107.8 | recovered_within_sla |
| 5 | pod_deletion | order-service | 0.421 | 278.2 | recovered_within_sla |
| 6 | replica_reduction | api-gateway | 0.399 | 58.8 | recovered_within_sla |
| 7 | latency_injection | api-gateway | 0.396 | 56.0 | recovered_within_sla |
| 8 | replica_reduction | order-service | 0.382 | 162.8 | recovered_within_sla |
| 9 | latency_injection | payment-service | 0.382 | 109.6 | recovered_within_sla |
| 10 | network_partition | notification-service | 0.38 | never | — |

### 2. Safety check before injecting

Decision **GO** · risk HIGH · system health 100.0% · target ready 2/2 · load 0.91× baseline · dependents api-gateway, order-service · users possibly affected 100%

### 3. Failure injected

`network_partition` on **payment-service** at 08:51:08 UTC — succeeded

Details: `{"policy": "chaos-isolate-payment-service", "effect": "deny all ingress + egress", "conntrack_flush": {"ok": true, "pod_ips": ["10.244.0.49", "10.244.0.50"], "agents": {"chaos-agent-l7fcx": true}}}`

### 4. Detection

Confirmed at 08:51:18 UTC on **payment-service** as `high_latency` · severity 0.9739 · Isolation Forest score -0.0334 (threshold 0.1031) · flags: iforest, zscore:caller_error_rate, zscore:caller_p99_ms, metrics_unreachable

Evidence:
- p99_latency_ms=246.30ms vs baseline 246.49ms (z=-0.0)
- caller_p99_ms=2420.51ms vs baseline 246.52ms (z=+25.0)

LSTM 60 s forecast: score -0.0521 (still anomalous)

### 5. Root-cause analysis

Origin **payment-service** · type `network_partition` · confidence 0.95 · call path api-gateway → payment-service · affected api-gateway, order-service, payment-service, notification-service

> Root cause localised to payment-service (network partition, confidence 95%). api-gateway, order-service also deviate as callers of payment-service: its failure propagates to them. notification-service also deviate without a dependency explaining it (lower-ranked candidates). Change evidence: NetworkPolicy 'chaos-isolate-payment-service' denies all Ingress/Egress traffic for pods of payment-service, created 15s ago; Pod payment-service-64d79d469d-2hzcm: Unhealthy — Readiness probe failed: Get "http://10.244.0.49:8003/ready": context deadline exceeded (Client.Timeout exceeded while aw.

Evidence:
- p99_latency_ms=246.30ms vs baseline 246.49ms (z=-0.0)
- caller_p99_ms=2420.51ms vs baseline 246.52ms (z=+25.0)
- NetworkPolicy 'chaos-isolate-payment-service' denies all Ingress/Egress traffic for pods of payment-service, created 15s ago
- Pod payment-service-64d79d469d-2hzcm: Unhealthy — Readiness probe failed: Get "http://10.244.0.49:8003/ready": context deadline exceeded (Client.Timeout exceeded while aw
- Pod payment-service-64d79d469d-2mbsp: Unhealthy — Readiness probe failed: Get "http://10.244.0.50:8003/ready": context deadline exceeded (Client.Timeout exceeded while aw

| Candidate | Score | Why |
|---|---|---|
| payment-service | 9.097 | severity 1.00; no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service']; earliest onset; structural fault on the service itself; NetworkPolicy 'chaos-isolate-payment-service' denies all Ingress/Egress traffic for pods of payment-service, created 15s ago; Pod payment-service-64d79d469d-2hzcm: Unhealthy — Readiness probe failed: Get "http://10.244.0.49:8003… |
| order-service | 2.774 | severity 0.96; its dependencies ['payment-service'] are also anomalous (likely a victim); explains anomalies in callers ['api-gateway']; earliest onset; 162 ERROR log lines in the last 60s, e.g. 'dependency failure (payment-service)' |
| api-gateway | 2.296 | severity 0.97; its dependencies ['order-service', 'payment-service'] are also anomalous (likely a victim); earliest onset; 121 ERROR log lines in the last 60s, e.g. 'request failed' |
| notification-service | 0.767 | severity 0.23; only symptom is reduced traffic — consistent with an upstream failure; no anomalous dependency explains it; explains anomalies in callers ['api-gateway'] |

### 6. Decision

Action **network_policy_rollback** (fallback rolling_restart) · confidence 0.508 · priority 9.987

- payment-service: network partition at severity 1.00; business impact 10/10 -> priority 9.99. Playbook: network_policy_rollback, fallback rolling_restart.
- Confidence in network_policy_rollback: 0.51 (history 0.63 over 5 attempt(s) x RCA 0.95 x blast factor 0.85).
- Decision: network_policy_rollback on payment-service (fallback rolling_restart, confidence 0.51).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| network_policy_rollback | payment-service | success | yes | 2.1s | removed 1 isolating NetworkPolicy(ies): chaos-isolate-payment-service |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"policy": "chaos-isolate-payment-service", "deleted": false}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 117 failed of 1186 requests (9.9%) · user p99 5391.7 ms over 59 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 08:50:50 | STRATEGY | payment-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose network_partition on payment-service: High‑impact network partition on payment-service, long idle time and previous mitigated outcome offers fresh insight into critical path resilience. |
| 08:51:08 | PREFLIGHT | payment-service | GO: payment-service at 2/2 Ready, system 100% healthy. Blast radius: 2 dependent service(s) ['api-gateway', 'order-service'], ~100% of users, risk HIGH. |
| 08:51:09 | INJECT | payment-service | Injected network_partition into payment-service: Deny-all NetworkPolicy selecting the service's pods (chaos-isolate-payment-service). |
| 08:51:18 | DETECT | payment-service | Anomaly confirmed on payment-service 10s after injection: pattern matches high latency. Isolation Forest score -0.033 (threshold +0.103), severity 0.97. Evidence: p99_latency_ms=246.30ms vs baseline 246.49ms (z=-0.0); caller_p99_ms=2420.51ms vs baseline 246.52ms (z=+25.0). Also deviating: api-gateway, order-service. LSTM forecast for the next 60s: score -0.052 (still anomalous). |
| 08:51:23 | RCA | payment-service | Root cause localised to payment-service (network partition, confidence 95%). api-gateway, order-service also deviate as callers of payment-service: its failure propagates to them. notification-service also deviate without a dependency explaining it (lower-ranked candidates). Change evidence: NetworkPolicy 'chaos-isolate-payment-service' denies all Ingress/Egress traffic for pods of payment-service, created 15s ago; Pod payment-service-64d79d469d-2hzcm: Unhealthy — Readiness probe failed: Get "http://10.244.0.49:8003/ready": context deadline exceeded (Client.Timeout exceeded while aw. |
| 08:51:23 | DECIDE | payment-service | Confidence in network_policy_rollback: 0.51 (history 0.63 over 5 attempt(s) x RCA 0.95 x blast factor 0.85). Decision: network_policy_rollback on payment-service (fallback rolling_restart, confidence 0.51). |
| 08:51:23 | REMEDIATE | payment-service | Executing network_policy_rollback on payment-service (step 1, primary). |
| 08:51:26 | REMEDIATE | payment-service | network_policy_rollback succeeded in 2.1s — removed 1 isolating NetworkPolicy(ies): chaos-isolate-payment-service. |
| 08:51:33 | VERIFY | payment-service | payment-service verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 7ms). |
| 08:52:18 | TEARDOWN | payment-service | Round teardown for payment-service: no residual fault found; autoscaler returned to declared bounds. |
| 08:52:28 | RECOVERED | payment-service | payment-service recovered: detected in 9.78s, mitigated in 10.8s, fully back to its normal operating band in 50.01s (target 90s — MET). Users saw 117 failed requests out of 1186 (9.9%) during the incident. |

## Round 3 — latency_injection → notification-service  ·  **RECOVERED**

TTD 64.75s (target 35s, missed) · TTM 13.6s · TTR 30.0s (target 120s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: Latency injection on notification-service was undetected previously, offering new fault type insight despite low impact.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | pod_deletion | api-gateway | 0.432 | 109.6 | recovered_within_sla |
| 2 | pod_deletion | order-service | 0.422 | 280.0 | recovered_within_sla |
| 3 | replica_reduction | api-gateway | 0.4 | 60.6 | recovered_within_sla |
| 4 | latency_injection | api-gateway | 0.398 | 57.8 | recovered_within_sla |
| 5 | replica_reduction | order-service | 0.383 | 164.6 | recovered_within_sla |
| 6 | latency_injection | notification-service | 0.351 | 160.1 | undetected |
| 7 | latency_injection | order-service | 0.35 | 96.8 | recovered_within_sla |
| 8 | pod_deletion | notification-service | 0.286 | 487.1 | recovered_within_sla |
| 9 | replica_reduction | payment-service | 0.195 | 273.7 | recovered_within_sla |
| 10 | latency_injection | product-service | 0.176 | 279.0 | recovered_within_sla |

### 2. Safety check before injecting

Decision **GO** · risk MEDIUM · system health 100.0% · target ready 1/1 · load 1.08× baseline · dependents api-gateway · users possibly affected 100%

### 3. Failure injected

`latency_injection` on **notification-service** at 08:52:53 UTC — succeeded

Details: `{"pod": "notification-service-85dc68594-thpcd", "delay": "200ms", "jitter": "50ms", "command": "tc qdisc replace dev eth0 root netem delay 200ms 50ms distribution normal", "replicas_ready": 1}`

### 4. Detection

Confirmed at 08:53:58 UTC on **notification-service** as `high_latency` · severity 0.9025 · Isolation Forest score 0.0632 (threshold 0.1031) · flags: iforest, zscore:caller_p99_ms

Evidence:
- p99_latency_ms=0.50ms vs baseline 0.49ms (z=+0.0)
- caller_p99_ms=497.50ms vs baseline 0.00ms (z=+25.0)

LSTM 60 s forecast: score 0.063 (still anomalous)

### 5. Root-cause analysis

Origin **notification-service** · type `high_latency` · confidence 0.623 · call path api-gateway → notification-service · affected notification-service

> Root cause localised to notification-service (high latency, confidence 62%). No other service deviates; the fault is contained to notification-service. Signal: p99_latency_ms=0.50ms vs baseline 0.49ms (z=+0.0); caller_p99_ms=497.50ms vs baseline 0.00ms (z=+25.0).

Evidence:
- p99_latency_ms=0.50ms vs baseline 0.49ms (z=+0.0)
- caller_p99_ms=497.50ms vs baseline 0.00ms (z=+25.0)

| Candidate | Score | Why |
|---|---|---|
| notification-service | 2.048 | severity 0.90; its own server-side latency/errors are normal; the degradation is only visible from callers (network or caller-side problem); no anomalous dependency explains it; earliest onset |
| api-gateway | 1.5 | its calls to notification-service take 497ms longer than notification-service itself needs to serve them (caller-side or network problem) |

### 6. Decision

Action **rolling_restart** (fallback traffic_reroute) · confidence 0.403 · priority 1.798

- notification-service: high latency at severity 0.90; business impact 2/10 -> priority 1.80. Playbook: traffic_reroute, fallback rolling_restart.
- G2 SWITCHED: traffic_reroute would remove the only Ready replica (1 Ready); using a surge rollout instead
- Confidence in rolling_restart: 0.40 (prior 0.70 (no history yet) x RCA 0.62 x blast factor 0.93).
- Decision: rolling_restart on notification-service (fallback traffic_reroute, confidence 0.40).

### Guardrails triggered

- {"id": "G2", "outcome": "SWITCHED", "detail": "traffic_reroute would remove the only Ready replica (1 Ready); using a surge rollout instead"}

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| rolling_restart | notification-service | success | yes | 8.1s | rolled 1 replica(s) onto the declared template |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"pod": "notification-service-85dc68594-thpcd", "note": "pod no longer exists (replaced)"}` · autoscaler `{"unchanged": {"minReplicas": 1, "maxReplicas": 3}}`

Users: 0 failed of 1880 requests (0.0%) · user p99 243.8 ms over 94 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 08:52:35 | STRATEGY | notification-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose latency_injection on notification-service: Latency injection on notification-service was undetected previously, offering new fault type insight despite low impact. |
| 08:52:53 | PREFLIGHT | notification-service | GO: notification-service at 1/1 Ready, system 100% healthy. Blast radius: 1 dependent service(s) ['api-gateway'], ~100% of users, risk MEDIUM. |
| 08:52:53 | INJECT | notification-service | Injected latency_injection into notification-service: tc netem egress delay on one replica (notification-service-85dc68594-thpcd). |
| 08:53:58 | DETECT | notification-service | Anomaly confirmed on notification-service 65s after injection: pattern matches high latency. Isolation Forest score +0.063 (threshold +0.103), severity 0.90. Evidence: p99_latency_ms=0.50ms vs baseline 0.49ms (z=+0.0); caller_p99_ms=497.50ms vs baseline 0.00ms (z=+25.0). LSTM forecast for the next 60s: score +0.063 (still anomalous). |
| 08:54:03 | RCA | notification-service | Root cause localised to notification-service (high latency, confidence 62%). No other service deviates; the fault is contained to notification-service. Signal: p99_latency_ms=0.50ms vs baseline 0.49ms (z=+0.0); caller_p99_ms=497.50ms vs baseline 0.00ms (z=+25.0). |
| 08:54:03 | GUARDRAIL | notification-service | G2 SWITCHED: traffic_reroute would remove the only Ready replica (1 Ready); using a surge rollout instead |
| 08:54:03 | DECIDE | notification-service | Confidence in rolling_restart: 0.40 (prior 0.70 (no history yet) x RCA 0.62 x blast factor 0.93). Decision: rolling_restart on notification-service (fallback traffic_reroute, confidence 0.40). |
| 08:54:03 | REMEDIATE | notification-service | Executing rolling_restart on notification-service (step 1, primary). |
| 08:54:11 | REMEDIATE | notification-service | rolling_restart succeeded in 8.1s — rolled 1 replica(s) onto the declared template. |
| 08:54:15 | VERIFY | notification-service | notification-service verified functional: 1/1 replicas Ready and 5 consecutive user-path probes OK (last 6ms). |
| 08:54:38 | TEARDOWN | notification-service | Round teardown for notification-service: no residual fault found; autoscaler returned to declared bounds. |
| 08:54:48 | RECOVERED | notification-service | notification-service recovered: detected in 64.75s, mitigated in 13.6s, fully back to its normal operating band in 30.0s (target 120s — MET). Users saw 0 failed requests out of 1880 (0.0%) during the incident. |

## Round 4 — pod_deletion → api-gateway  ·  **RECOVERED**

TTD 4.76s (target 25s, met) · TTM 9.53s · TTR 15.0s (target 90s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: Pod deletion on api-gateway is a high‑impact, unused fault/service pair with long time since last test, maximizing learning about core traffic handling.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | pod_deletion | api-gateway | 0.433 | 111.9 | recovered_within_sla |
| 2 | pod_deletion | order-service | 0.422 | 282.3 | recovered_within_sla |
| 3 | replica_reduction | api-gateway | 0.402 | 62.9 | recovered_within_sla |
| 4 | replica_reduction | order-service | 0.384 | 166.9 | recovered_within_sla |
| 5 | replica_reduction | payment-service | 0.196 | 276.0 | recovered_within_sla |
| 6 | pod_deletion | product-service | 0.138 | 165.2 | recovered_within_sla |
| 7 | replica_reduction | product-service | 0.112 | 109.2 | recovered_within_sla |
| 8 | pod_deletion | payment-service | 0.097 | 56.8 | recovered_within_sla |
| 9 | network_partition | api-gateway | 0.058 | 164.1 | recovered_within_sla |
| 10 | pod_deletion | notification-service | 0.036 | 489.5 | recovered_within_sla |

### 2. Safety check before injecting

Decision **GO** · risk MEDIUM · system health 100.0% · target ready 2/2 · load 0.99× baseline · dependents none · users possibly affected 100%

### 3. Failure injected

`pod_deletion` on **api-gateway** at 08:55:13 UTC — succeeded

Details: `{"pod": "api-gateway-6488bc94fb-k5b2k", "pod_ip": "10.244.0.46", "ready_pods_before": 2}`

### 4. Detection

Confirmed at 08:55:18 UTC on **api-gateway** as `pod_crash` · severity 0.4 · Isolation Forest score 0.1132 (threshold 0.1031) · flags: replicas_lost

Evidence:
- replicas ready 2/2 (declared minimum 2)
- Ready pod(s) api-gateway-6488bc94fb-k5b2k disappeared without a scale-down or rollout
- caller_error_rate=0.0% vs baseline 0.0% (z=+0.0)

LSTM 60 s forecast: score 0.1206 (returning to normal)

### 5. Root-cause analysis

Origin **api-gateway** · type `pod_crash` · confidence 0.918 · call path api-gateway · affected api-gateway

> Root cause localised to api-gateway (pod crash, confidence 92%). No other service deviates; the fault is contained to api-gateway. Change evidence: Pod api-gateway-6488bc94fb-k5b2k: Killing — Stopping container api-gateway.

Evidence:
- replicas ready 2/2 (declared minimum 2)
- Ready pod(s) api-gateway-6488bc94fb-k5b2k disappeared without a scale-down or rollout
- caller_error_rate=0.0% vs baseline 0.0% (z=+0.0)
- Pod api-gateway-6488bc94fb-k5b2k: Killing — Stopping container api-gateway

| Candidate | Score | Why |
|---|---|---|
| api-gateway | 3.98 | severity 0.24; no anomalous dependency explains it; earliest onset; structural fault on the service itself; Pod api-gateway-6488bc94fb-k5b2k: Killing — Stopping container api-gateway |

### 6. Decision

Action **hpa_scaleout** (fallback rolling_restart) · confidence 0.78 · priority 2.16

- api-gateway: pod crash at severity 0.24; business impact 9/10 -> priority 2.16. Playbook: hpa_scaleout, fallback rolling_restart.
- Confidence in hpa_scaleout: 0.78 (history 0.85 over 2 attempt(s) x RCA 0.92 x blast factor 1.00).
- Decision: hpa_scaleout on api-gateway (fallback rolling_restart, confidence 0.78).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| hpa_scaleout | api-gateway | success | yes | 4.1s | autoscaler 2-4 -> 3-4; 2 -> 3 Ready replicas |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"reversible": false, "note": "Kubernetes reschedules deleted pods by itself"}` · autoscaler `{"from": {"minReplicas": 3, "maxReplicas": 4}, "to": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 1 failed of 379 requests (0.3%) · user p99 246.5 ms over 19 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 08:54:55 | STRATEGY | api-gateway | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose pod_deletion on api-gateway: Pod deletion on api-gateway is a high‑impact, unused fault/service pair with long time since last test, maximizing learning about core traffic handling. |
| 08:55:13 | PREFLIGHT | api-gateway | GO: api-gateway at 2/2 Ready, system 100% healthy. Blast radius: 0 dependent service(s) , ~100% of users, risk MEDIUM. |
| 08:55:13 | INJECT | api-gateway | Injected pod_deletion into api-gateway: Force-delete one Ready pod (grace period 0) (api-gateway-6488bc94fb-k5b2k). |
| 08:55:18 | DETECT | api-gateway | Anomaly confirmed on api-gateway 5s after injection: pattern matches pod crash. Isolation Forest score +0.113 (threshold +0.103), severity 0.40. Evidence: replicas ready 2/2 (declared minimum 2); Ready pod(s) api-gateway-6488bc94fb-k5b2k disappeared without a scale-down or rollout; caller_error_rate=0.0% vs baseline 0.0% (z=+0.0). LSTM forecast for the next 60s: score +0.121 (returning to normal). |
| 08:55:23 | RCA | api-gateway | Root cause localised to api-gateway (pod crash, confidence 92%). No other service deviates; the fault is contained to api-gateway. Change evidence: Pod api-gateway-6488bc94fb-k5b2k: Killing — Stopping container api-gateway. |
| 08:55:23 | DECIDE | api-gateway | Confidence in hpa_scaleout: 0.78 (history 0.85 over 2 attempt(s) x RCA 0.92 x blast factor 1.00). Decision: hpa_scaleout on api-gateway (fallback rolling_restart, confidence 0.78). |
| 08:55:23 | REMEDIATE | api-gateway | Executing hpa_scaleout on api-gateway (step 1, primary). |
| 08:55:27 | REMEDIATE | api-gateway | hpa_scaleout succeeded in 4.1s — autoscaler 2-4 -> 3-4; 2 -> 3 Ready replicas. |
| 08:55:31 | VERIFY | api-gateway | api-gateway verified functional: 3/3 replicas Ready and 5 consecutive user-path probes OK (last 11ms). |
| 08:55:33 | TEARDOWN | api-gateway | Round teardown for api-gateway: no residual fault found; autoscaler returned to declared bounds. |
| 08:55:43 | RECOVERED | api-gateway | api-gateway recovered: detected in 4.76s, mitigated in 9.53s, fully back to its normal operating band in 15.0s (target 90s — MET). Users saw 1 failed requests out of 379 (0.3%) during the incident. |

## Round 5 — pod_deletion → order-service  ·  **RECOVERED**

TTD 4.75s (target 25s, met) · TTM 15.54s · TTR 19.99s (target 90s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-20b)**: Order-service pod deletion is high impact, long since last tried, and has only been attempted once, offering fresh insight into resilience.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | replica_reduction | order-service | 0.384 | 167.8 | recovered_within_sla |
| 2 | replica_reduction | payment-service | 0.196 | 277.0 | recovered_within_sla |
| 3 | replica_reduction | api-gateway | 0.153 | 63.8 | recovered_within_sla |
| 4 | replica_reduction | product-service | 0.112 | 110.1 | recovered_within_sla |
| 5 | pod_deletion | order-service | 0.023 | 283.2 | recovered_within_sla |
| 6 | network_partition | order-service | -0.042 | 111.9 | recovered_within_sla |
| 7 | latency_injection | order-service | -0.049 | 100.1 | recovered_within_sla |
| 8 | cpu_throttle | order-service | -0.073 | 62.8 | recovered_within_sla |
| 9 | network_partition | api-gateway | -0.192 | 165.0 | recovered_within_sla |
| 10 | cpu_throttle | api-gateway | -0.218 | 109.1 | recovered_within_sla |

### 2. Safety check before injecting

Decision **GO** · risk MEDIUM · system health 100.0% · target ready 2/2 · load 1.02× baseline · dependents api-gateway · users possibly affected 100%

### 3. Failure injected

`pod_deletion` on **order-service** at 08:56:08 UTC — succeeded

Details: `{"pod": "order-service-b95945cc9-v58dk", "pod_ip": "10.244.0.54", "ready_pods_before": 2}`

### 4. Detection

Confirmed at 08:56:13 UTC on **order-service** as `pod_crash` · severity 0.6491 · Isolation Forest score 0.0622 (threshold 0.1031) · flags: replicas_lost

Evidence:
- replicas ready 1/2 (declared minimum 2)
- Ready pod(s) order-service-b95945cc9-v58dk disappeared without a scale-down or rollout
- caller_error_rate=0.0% vs baseline 0.0% (z=+0.0)

LSTM 60 s forecast: score 0.1052 (returning to normal)

### 5. Root-cause analysis

Origin **order-service** · type `pod_crash` · confidence 0.942 · call path api-gateway → order-service · affected order-service

> Root cause localised to order-service (pod crash, confidence 94%). No other service deviates; the fault is contained to order-service. Change evidence: Pod order-service-b95945cc9-q9796: Unhealthy — Startup probe failed: Get "http://10.244.0.58:8002/health": dial tcp 10.244.0.58:8002: connect: connection refused; Pod order-service-b95945cc9-v58dk: Killing — Stopping container order-service.

Evidence:
- replicas ready 1/2 (declared minimum 2)
- Ready pod(s) order-service-b95945cc9-v58dk disappeared without a scale-down or rollout
- caller_error_rate=0.0% vs baseline 0.0% (z=+0.0)
- Pod order-service-b95945cc9-q9796: Unhealthy — Startup probe failed: Get "http://10.244.0.58:8002/health": dial tcp 10.244.0.58:8002: connect: connection refused
- Pod order-service-b95945cc9-v58dk: Killing — Stopping container order-service

| Candidate | Score | Why |
|---|---|---|
| order-service | 4.279 | severity 0.39; no anomalous dependency explains it; earliest onset; structural fault on the service itself; Pod order-service-b95945cc9-q9796: Unhealthy — Startup probe failed: Get "http://10.244.0.58:8002/health": dial tcp 10.244.0.58:8002: connect: connection refused; Pod order-service-b95945cc9-v58dk: Killing — Stopping container order-service |

### 6. Decision

Action **hpa_scaleout** (fallback rolling_restart) · confidence 0.697 · priority 3.116

- order-service: pod crash at severity 0.39; business impact 8/10 -> priority 3.12. Playbook: hpa_scaleout, fallback rolling_restart.
- Confidence in hpa_scaleout: 0.70 (history 0.80 over 1 attempt(s) x RCA 0.94 x blast factor 0.93).
- Decision: hpa_scaleout on order-service (fallback rolling_restart, confidence 0.70).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| hpa_scaleout | order-service | success | yes | 8.2s | autoscaler 2-4 -> 3-4; 2 -> 3 Ready replicas |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"reversible": false, "note": "Kubernetes reschedules deleted pods by itself"}` · autoscaler `{"from": {"minReplicas": 3, "maxReplicas": 4}, "to": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 0 failed of 479 requests (0.0%) · user p99 244.1 ms over 24 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 08:55:51 | STRATEGY | order-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-20b) chose pod_deletion on order-service: Order-service pod deletion is high impact, long since last tried, and has only been attempted once, offering fresh insight into resilience. |
| 08:56:08 | PREFLIGHT | order-service | GO: order-service at 2/2 Ready, system 100% healthy. Blast radius: 1 dependent service(s) ['api-gateway'], ~100% of users, risk MEDIUM. |
| 08:56:08 | INJECT | order-service | Injected pod_deletion into order-service: Force-delete one Ready pod (grace period 0) (order-service-b95945cc9-v58dk). |
| 08:56:13 | DETECT | order-service | Anomaly confirmed on order-service 5s after injection: pattern matches pod crash. Isolation Forest score +0.062 (threshold +0.103), severity 0.65. Evidence: replicas ready 1/2 (declared minimum 2); Ready pod(s) order-service-b95945cc9-v58dk disappeared without a scale-down or rollout; caller_error_rate=0.0% vs baseline 0.0% (z=+0.0). LSTM forecast for the next 60s: score +0.105 (returning to normal). |
| 08:56:18 | RCA | order-service | Root cause localised to order-service (pod crash, confidence 94%). No other service deviates; the fault is contained to order-service. Change evidence: Pod order-service-b95945cc9-q9796: Unhealthy — Startup probe failed: Get "http://10.244.0.58:8002/health": dial tcp 10.244.0.58:8002: connect: connection refused; Pod order-service-b95945cc9-v58dk: Killing — Stopping container order-service. |
| 08:56:18 | DECIDE | order-service | Confidence in hpa_scaleout: 0.70 (history 0.80 over 1 attempt(s) x RCA 0.94 x blast factor 0.93). Decision: hpa_scaleout on order-service (fallback rolling_restart, confidence 0.70). |
| 08:56:18 | REMEDIATE | order-service | Executing hpa_scaleout on order-service (step 1, primary). |
| 08:56:26 | REMEDIATE | order-service | hpa_scaleout succeeded in 8.2s — autoscaler 2-4 -> 3-4; 2 -> 3 Ready replicas. |
| 08:56:32 | VERIFY | order-service | order-service verified functional: 3/3 replicas Ready and 5 consecutive user-path probes OK (last 9ms). |
| 08:56:33 | TEARDOWN | order-service | Round teardown for order-service: no residual fault found; autoscaler returned to declared bounds. |
| 08:56:43 | RECOVERED | order-service | order-service recovered: detected in 4.75s, mitigated in 15.54s, fully back to its normal operating band in 19.99s (target 90s — MET). Users saw 0 failed requests out of 479 (0.0%) during the incident. |

## Campaign-level events

| Time (UTC) | Phase | Message |
|---|---|---|
| 08:48:59 | CAMPAIGN | Campaign c-20261011-084859-6e59 starting: 5 rounds (auto, auto, auto, auto, auto). |
| 08:56:43 | SUMMARY | Campaign completed: resilience score 95.0/100 — EXCELLENT — every fault detected, diagnosed and healed within SLA. |
