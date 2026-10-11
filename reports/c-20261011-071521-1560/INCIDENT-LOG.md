# Incident log — campaign `c-20261011-071521-1560`

**Resilience score 77.9/100** — GOOD — reliable recovery with minor SLA or diagnosis misses

| Component | Points |
|---|---|
| recovery sla | 23.33 |
| detection sla | 20.0 |
| remediation effectiveness | 13.33 |
| diagnosis accuracy | 12.5 |
| user protection | 8.7 |

| # | Fault | Target | Status | TTD | TTR | Users failed |
|---|---|---|---|---|---|---|
| 1 | latency_injection | order-service | RECOVERED | 14.83s | 49.99s | 0.3% |
| 2 | pod_deletion | payment-service | RECOVERED | 4.82s | 20.0s | 0.0% |
| 3 | network_partition | payment-service | MITIGATED | 9.84s | — | 19.2% |
| 4 | replica_reduction | api-gateway | SKIPPED_PREFLIGHT | — | — | — |
| 5 | cpu_throttle | product-service | SKIPPED_PREFLIGHT | — | — | — |

## Round 1 — latency_injection → order-service  ·  **RECOVERED**

TTD 14.83s (target 35s, met) · TTM 16.48s · TTR 49.99s (target 120s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: Long idle time, high business impact, and previous mitigated outcome reveals detection gaps in order-service latency injection.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | latency_injection | order-service | 0.602 | 408.7 | mitigated |
| 2 | replica_reduction | api-gateway | 0.52 | 376.2 | recovered_within_sla |
| 3 | latency_injection | api-gateway | 0.52 | 375.2 | recovered_within_sla |
| 4 | pod_deletion | payment-service | 0.47 | 377.2 | recovered_within_sla |
| 5 | network_partition | product-service | 0.453 | 391.6 | recovered_within_sla |
| 6 | cpu_throttle | product-service | 0.45 | 379.1 | recovered_within_sla |
| 7 | cpu_throttle | order-service | 0.448 | 393.4 | recovered_within_sla |
| 8 | network_partition | payment-service | 0.414 | 180.2 | recovered_within_sla |
| 9 | replica_reduction | payment-service | 0.413 | 176.6 | recovered_within_sla |
| 10 | network_partition | api-gateway | 0.403 | 64.6 | recovered_within_sla |

### 2. Safety check before injecting

Decision **GO** · risk MEDIUM · system health 100.0% · target ready 2/2 · load 0.88× baseline · dependents api-gateway · users possibly affected 100%

### 3. Failure injected

`latency_injection` on **order-service** at 07:15:45 UTC — succeeded

Details: `{"pod": "order-service-848895fdff-l8zbh", "delay": "200ms", "jitter": "50ms", "command": "tc qdisc replace dev eth0 root netem delay 200ms 50ms distribution normal", "replicas_ready": 2}`

### 4. Detection

Confirmed at 07:15:59 UTC on **order-service** as `high_latency` · severity 0.9271 · Isolation Forest score -0.0107 (threshold 0.1031) · flags: iforest, zscore:p99_latency_ms, zscore:caller_p99_ms

Evidence:
- p99_latency_ms=795.01ms vs baseline 246.95ms (z=+14.8)
- caller_p99_ms=1937.51ms vs baseline 246.99ms (z=+25.0)

LSTM 60 s forecast: score -0.0179 (still anomalous)

### 5. Root-cause analysis

Origin **order-service** · type `high_latency` · confidence 0.783 · call path api-gateway → order-service · affected api-gateway, product-service, order-service

> Root cause localised to order-service (high latency, confidence 78%). api-gateway also deviate as callers of order-service: its failure propagates to them. product-service deviate because requests from order-service stopped reaching them. Signal: p99_latency_ms=795.01ms vs baseline 246.95ms (z=+14.8); caller_p99_ms=1937.51ms vs baseline 246.99ms (z=+25.0).

Evidence:
- p99_latency_ms=795.01ms vs baseline 246.95ms (z=+14.8)
- caller_p99_ms=1937.51ms vs baseline 246.99ms (z=+25.0)

| Candidate | Score | Why |
|---|---|---|
| order-service | 2.895 | severity 0.92; its dependencies ['product-service'] are also anomalous (likely a victim); explains anomalies in callers ['api-gateway']; earliest onset; its calls to product-service take 187ms longer than product-service itself needs to serve them (caller-side or network problem) |
| product-service | 1.147 | severity 0.52; its own server-side latency/errors are normal; the degradation is only visible from callers (network or caller-side problem); no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service'] |
| api-gateway | 0.379 | severity 0.94; its dependencies ['product-service', 'order-service'] are also anomalous (likely a victim) |

### 6. Decision

Action **traffic_reroute** (fallback rolling_restart) · confidence 0.507 · priority 7.382

- order-service: high latency at severity 0.92; business impact 8/10 -> priority 7.38. Playbook: traffic_reroute, fallback rolling_restart.
- Confidence in traffic_reroute: 0.51 (prior 0.70 (no history yet) x RCA 0.78 x blast factor 0.93).
- Decision: traffic_reroute on order-service (fallback rolling_restart, confidence 0.51).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| traffic_reroute | order-service | success | yes | 11.1s | quarantined order-service-848895fdff-l8zbh (worst replica by live telemetry (p99=4600ms, next worst score 247 vs 4600)); traffic now on 2 healthy replica(s) |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"pod": "order-service-848895fdff-l8zbh", "note": "pod no longer exists (replaced)"}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 4 failed of 1284 requests (0.3%) · user p99 3118.7 ms over 64 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 07:15:28 | STRATEGY | order-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose latency_injection on order-service: Long idle time, high business impact, and previous mitigated outcome reveals detection gaps in order-service latency injection. |
| 07:15:45 | PREFLIGHT | order-service | GO: order-service at 2/2 Ready, system 100% healthy. Blast radius: 1 dependent service(s) ['api-gateway'], ~100% of users, risk MEDIUM. |
| 07:15:45 | INJECT | order-service | Injected latency_injection into order-service: tc netem egress delay on one replica (order-service-848895fdff-l8zbh). |
| 07:16:00 | DETECT | order-service | Anomaly confirmed on order-service 15s after injection: pattern matches high latency. Isolation Forest score -0.011 (threshold +0.103), severity 0.93. Evidence: p99_latency_ms=795.01ms vs baseline 246.95ms (z=+14.8); caller_p99_ms=1937.51ms vs baseline 246.99ms (z=+25.0). LSTM forecast for the next 60s: score -0.018 (still anomalous). |
| 07:16:05 | RCA | order-service | Root cause localised to order-service (high latency, confidence 78%). api-gateway also deviate as callers of order-service: its failure propagates to them. product-service deviate because requests from order-service stopped reaching them. Signal: p99_latency_ms=795.01ms vs baseline 246.95ms (z=+14.8); caller_p99_ms=1937.51ms vs baseline 246.99ms (z=+25.0). |
| 07:16:05 | DECIDE | order-service | Confidence in traffic_reroute: 0.51 (prior 0.70 (no history yet) x RCA 0.78 x blast factor 0.93). Decision: traffic_reroute on order-service (fallback rolling_restart, confidence 0.51). |
| 07:16:05 | REMEDIATE | order-service | Executing traffic_reroute on order-service. |
| 07:16:16 | REMEDIATE | order-service | traffic_reroute succeeded in 11.1s — quarantined order-service-848895fdff-l8zbh (worst replica by live telemetry (p99=4600ms, next worst score 247 vs 4600)); traffic now on 2 healthy replica(s). |
| 07:16:20 | VERIFY | order-service | order-service verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 6ms). |
| 07:17:00 | TEARDOWN | order-service | Round teardown for order-service: no residual fault found; autoscaler returned to declared bounds. |
| 07:17:10 | RECOVERED | order-service | order-service recovered: detected in 14.83s, mitigated in 16.48s, fully back to its normal operating band in 49.99s (target 120s — MET). Users saw 4 failed requests out of 1284 (0.3%) during the incident. |

## Round 2 — pod_deletion → payment-service  ·  **RECOVERED**

TTD 4.82s (target 25s, met) · TTM 15.6s · TTR 20.0s (target 90s, met) · healed by fallback · diagnosis correct, classification wrong

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: High‑impact pod_deletion on payment-service, long idle time, many dependents, and fault type not yet used in this campaign.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | replica_reduction | api-gateway | 0.52 | 378.1 | recovered_within_sla |
| 2 | pod_deletion | payment-service | 0.47 | 379.1 | recovered_within_sla |
| 3 | network_partition | product-service | 0.453 | 393.4 | recovered_within_sla |
| 4 | cpu_throttle | product-service | 0.451 | 380.9 | recovered_within_sla |
| 5 | network_partition | payment-service | 0.415 | 182.0 | recovered_within_sla |
| 6 | replica_reduction | payment-service | 0.414 | 178.4 | recovered_within_sla |
| 7 | network_partition | api-gateway | 0.404 | 66.4 | recovered_within_sla |
| 8 | cpu_throttle | notification-service | 0.38 | never | — |
| 9 | network_partition | notification-service | 0.38 | never | — |
| 10 | cpu_throttle | payment-service | 0.358 | 71.1 | recovered_within_sla |

### 2. Safety check before injecting

Decision **GO** · risk HIGH · system health 100.0% · target ready 2/2 · load 1.03× baseline · dependents api-gateway, order-service · users possibly affected 100%

### 3. Failure injected

`pod_deletion` on **payment-service** at 07:17:35 UTC — succeeded

Details: `{"pod": "payment-service-7745b65785-vpltn", "pod_ip": "10.244.0.29", "ready_pods_before": 2}`

### 4. Detection

Confirmed at 07:17:39 UTC on **payment-service** as `network_partition` · severity 0.76 · Isolation Forest score 0.1352 (threshold 0.1031) · flags: replicas_lost, metrics_unreachable

Evidence:
- replicas ready 2/2 (declared minimum 2)
- metrics endpoint unreachable on 67% of pods
- caller_error_rate=0.0% vs baseline 0.0% (z=+0.0)
- request_rate=6.19 req/s vs baseline 6.92 req/s (z=-1.1)
- pods are running (no container restarts) but cannot be reached over the pod network

LSTM 60 s forecast: score 0.1396 (returning to normal)

### 5. Root-cause analysis

Origin **payment-service** · type `network_partition` · confidence 0.953 · call path api-gateway → payment-service · affected payment-service

> Root cause localised to payment-service (network partition, confidence 95%). No other service deviates; the fault is contained to payment-service. Change evidence: Pod payment-service-7745b65785-vpltn: Killing — Stopping container payment-service; Pod payment-service-7745b65785-w8v4w: Unhealthy — Startup probe failed: Get "http://10.244.0.37:8003/health": dial tcp 10.244.0.37:8003: connect: connection refused.

Evidence:
- replicas ready 2/2 (declared minimum 2)
- metrics endpoint unreachable on 67% of pods
- caller_error_rate=0.0% vs baseline 0.0% (z=+0.0)
- request_rate=6.19 req/s vs baseline 6.92 req/s (z=-1.1)
- pods are running (no container restarts) but cannot be reached over the pod network
- Pod payment-service-7745b65785-vpltn: Killing — Stopping container payment-service
- Pod payment-service-7745b65785-w8v4w: Unhealthy — Startup probe failed: Get "http://10.244.0.37:8003/health": dial tcp 10.244.0.37:8003: connect: connection refused

| Candidate | Score | Why |
|---|---|---|
| payment-service | 4.412 | severity 0.46; no anomalous dependency explains it; earliest onset; structural fault on the service itself; Pod payment-service-7745b65785-vpltn: Killing — Stopping container payment-service; Pod payment-service-7745b65785-w8v4w: Unhealthy — Startup probe failed: Get "http://10.244.0.37:8003/health": dial tcp 10.244.0.37:8003: connect: connection refused |

### 6. Decision

Action **network_policy_rollback** (fallback rolling_restart) · confidence 0.689 · priority 4.56

- payment-service: network partition at severity 0.46; business impact 10/10 -> priority 4.56. Playbook: network_policy_rollback, fallback rolling_restart.
- Confidence in network_policy_rollback: 0.69 (history 0.85 over 2 attempt(s) x RCA 0.95 x blast factor 0.85).
- Decision: network_policy_rollback on payment-service (fallback rolling_restart, confidence 0.69).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| network_policy_rollback | payment-service | failed | no | 0.0s | no deny-all NetworkPolicy selects this service |
| rolling_restart | payment-service | success | yes | 10.1s | rolled 2 replica(s) onto the declared template |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"reversible": false, "note": "Kubernetes reschedules deleted pods by itself"}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 0 failed of 482 requests (0.0%) · user p99 243.7 ms over 24 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 07:17:16 | STRATEGY | payment-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose pod_deletion on payment-service: High‑impact pod_deletion on payment-service, long idle time, many dependents, and fault type not yet used in this campaign. |
| 07:17:35 | PREFLIGHT | payment-service | GO: payment-service at 2/2 Ready, system 100% healthy. Blast radius: 2 dependent service(s) ['api-gateway', 'order-service'], ~100% of users, risk HIGH. |
| 07:17:35 | INJECT | payment-service | Injected pod_deletion into payment-service: Force-delete one Ready pod (grace period 0) (payment-service-7745b65785-vpltn). |
| 07:17:40 | DETECT | payment-service | Anomaly confirmed on payment-service 5s after injection: pattern matches network partition. Isolation Forest score +0.135 (threshold +0.103), severity 0.76. Evidence: replicas ready 2/2 (declared minimum 2); metrics endpoint unreachable on 67% of pods; caller_error_rate=0.0% vs baseline 0.0% (z=+0.0). LSTM forecast for the next 60s: score +0.140 (returning to normal). |
| 07:17:45 | RCA | payment-service | Root cause localised to payment-service (network partition, confidence 95%). No other service deviates; the fault is contained to payment-service. Change evidence: Pod payment-service-7745b65785-vpltn: Killing — Stopping container payment-service; Pod payment-service-7745b65785-w8v4w: Unhealthy — Startup probe failed: Get "http://10.244.0.37:8003/health": dial tcp 10.244.0.37:8003: connect: connection refused. |
| 07:17:45 | DECIDE | payment-service | Confidence in network_policy_rollback: 0.69 (history 0.85 over 2 attempt(s) x RCA 0.95 x blast factor 0.85). Decision: network_policy_rollback on payment-service (fallback rolling_restart, confidence 0.69). |
| 07:17:45 | REMEDIATE | payment-service | Executing network_policy_rollback on payment-service. |
| 07:17:45 | REMEDIATE | payment-service | network_policy_rollback did not complete in 0.0s — no deny-all NetworkPolicy selects this service. |
| 07:17:45 | DECIDE | payment-service | network_policy_rollback did not restore payment-service; escalating to fallback rolling_restart. |
| 07:17:45 | REMEDIATE | payment-service | Executing rolling_restart on payment-service. |
| 07:17:55 | REMEDIATE | payment-service | rolling_restart succeeded in 10.1s — rolled 2 replica(s) onto the declared template. |
| 07:17:59 | VERIFY | payment-service | payment-service verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 6ms). |
| 07:18:10 | TEARDOWN | payment-service | Round teardown for payment-service: no residual fault found; autoscaler returned to declared bounds. |
| 07:18:20 | RECOVERED | payment-service | payment-service recovered: detected in 4.82s, mitigated in 15.6s, fully back to its normal operating band in 20.0s (target 90s — MET). Users saw 0 failed requests out of 482 (0.0%) during the incident. |

## Round 3 — network_partition → payment-service  ·  **MITIGATED**

TTD 9.84s (target 30s, met) · TTM 197.37s · TTR — (target 90s, missed) · healed by fallback · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: High-impact network partition on degraded payment-service, never tried this fault type in campaign, long since last attempt, maximizes insight into critical path resilience.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | replica_reduction | api-gateway | 0.521 | 379.2 | recovered_within_sla |
| 2 | network_partition | product-service | 0.454 | 394.6 | recovered_within_sla |
| 3 | cpu_throttle | product-service | 0.451 | 382.1 | recovered_within_sla |
| 4 | network_partition | api-gateway | 0.405 | 67.6 | recovered_within_sla |
| 5 | cpu_throttle | notification-service | 0.38 | never | — |
| 6 | network_partition | notification-service | 0.38 | never | — |
| 7 | cpu_throttle | api-gateway | 0.352 | 11.7 | recovered_within_sla |
| 8 | replica_reduction | product-service | 0.283 | 12.7 | recovered_within_sla |
| 9 | cpu_throttle | order-service | 0.199 | 396.4 | recovered_within_sla |
| 10 | network_partition | payment-service | 0.165 | 183.2 | recovered_within_sla |

### 2. Safety check before injecting

Decision **GO** · risk HIGH · system health 100.0% · target ready 2/2 · load 0.93× baseline · dependents api-gateway, order-service · users possibly affected 100%

### 3. Failure injected

`network_partition` on **payment-service** at 07:18:45 UTC — succeeded

Details: `{"policy": "chaos-isolate-payment-service", "effect": "deny all ingress + egress", "conntrack_flush": {"ok": true, "pod_ips": ["10.244.0.38", "10.244.0.39"], "agents": {"chaos-agent-l7fcx": true}}}`

### 4. Detection

Confirmed at 07:18:54 UTC on **payment-service** as `network_partition` · severity 0.9757 · Isolation Forest score -0.0475 (threshold 0.1031) · flags: iforest, zscore:caller_error_rate, zscore:caller_p99_ms, metrics_unreachable

Evidence:
- replicas ready 2/2 (declared minimum 2)
- metrics endpoint unreachable on 50% of pods
- caller_error_rate=0.6% vs baseline 0.0% (z=+0.3)
- request_rate=5.42 req/s vs baseline 6.92 req/s (z=-2.2)
- pods are running (no container restarts) but cannot be reached over the pod network

LSTM 60 s forecast: score -0.0482 (still anomalous)

### 5. Root-cause analysis

Origin **payment-service** · type `network_partition` · confidence 0.95 · call path api-gateway → payment-service · affected api-gateway, order-service, payment-service, notification-service

> Root cause localised to payment-service (network partition, confidence 95%). api-gateway, order-service also deviate as callers of payment-service: its failure propagates to them. notification-service also deviate without a dependency explaining it (lower-ranked candidates). Change evidence: NetworkPolicy 'chaos-isolate-payment-service' denies all Ingress/Egress traffic for pods of payment-service, created 15s ago; Pod payment-service-c89555bbc-jbdww: Unhealthy — Readiness probe failed: Get "http://10.244.0.38:8003/ready": context deadline exceeded (Client.Timeout exceeded while aw.

Evidence:
- replicas ready 2/2 (declared minimum 2)
- metrics endpoint unreachable on 50% of pods
- caller_error_rate=0.6% vs baseline 0.0% (z=+0.3)
- request_rate=5.42 req/s vs baseline 6.92 req/s (z=-2.2)
- pods are running (no container restarts) but cannot be reached over the pod network
- NetworkPolicy 'chaos-isolate-payment-service' denies all Ingress/Egress traffic for pods of payment-service, created 15s ago
- Pod payment-service-c89555bbc-jbdww: Unhealthy — Readiness probe failed: Get "http://10.244.0.38:8003/ready": context deadline exceeded (Client.Timeout exceeded while aw
- Pod payment-service-c89555bbc-s4krb: Unhealthy — Readiness probe failed: Get "http://10.244.0.39:8003/ready": context deadline exceeded (Client.Timeout exceeded while aw

| Candidate | Score | Why |
|---|---|---|
| payment-service | 9.098 | severity 1.00; no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service']; earliest onset; structural fault on the service itself; NetworkPolicy 'chaos-isolate-payment-service' denies all Ingress/Egress traffic for pods of payment-service, created 15s ago; Pod payment-service-c89555bbc-jbdww: Unhealthy — Readiness probe failed: Get "http://10.244.0.38:8003/… |
| order-service | 2.793 | severity 0.97; its dependencies ['payment-service'] are also anomalous (likely a victim); explains anomalies in callers ['api-gateway']; earliest onset; 162 ERROR log lines in the last 60s, e.g. 'dependency failure (payment-service)' |
| api-gateway | 2.362 | severity 0.97; its dependencies ['order-service', 'payment-service'] are also anomalous (likely a victim); earliest onset; 135 ERROR log lines in the last 60s, e.g. 'request failed' |
| notification-service | 0.751 | severity 0.23; only symptom is reduced traffic — consistent with an upstream failure; no anomalous dependency explains it; explains anomalies in callers ['api-gateway'] |

### 6. Decision

Action **rolling_restart** (fallback network_policy_rollback) · confidence 0.646 · priority 9.988

- payment-service: network partition at severity 1.00; business impact 10/10 -> priority 9.99. Playbook: network_policy_rollback, fallback rolling_restart.
- G3 SWITCHED: network_policy_rollback failed on payment-service within the last 5 minutes; trying rolling_restart first
- Confidence in rolling_restart: 0.65 (history 0.80 over 1 attempt(s) x RCA 0.95 x blast factor 0.85).
- Decision: rolling_restart on payment-service (fallback network_policy_rollback, confidence 0.65).

### Guardrails triggered

- {"id": "G3", "outcome": "SWITCHED", "detail": "network_policy_rollback failed on payment-service within the last 5 minutes; trying rolling_restart first"}

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| rolling_restart | payment-service | failed | no | 181.5s | rollout did not complete within 180s |
| network_policy_rollback | payment-service | success | yes | 10.1s | removed 1 isolating NetworkPolicy(ies): chaos-isolate-payment-service |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"policy": "chaos-isolate-payment-service", "deleted": false}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 1437 failed of 7501 requests (19.2%) · user p99 3789.5 ms over 375 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 07:18:26 | STRATEGY | payment-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose network_partition on payment-service: High-impact network partition on degraded payment-service, never tried this fault type in campaign, long since last attempt, maximizes insight into critical path resilience. |
| 07:18:45 | PREFLIGHT | payment-service | GO: payment-service at 2/2 Ready, system 100% healthy. Blast radius: 2 dependent service(s) ['api-gateway', 'order-service'], ~100% of users, risk HIGH. |
| 07:18:45 | INJECT | payment-service | Injected network_partition into payment-service: Deny-all NetworkPolicy selecting the service's pods (chaos-isolate-payment-service). |
| 07:18:55 | DETECT | payment-service | Anomaly confirmed on payment-service 10s after injection: pattern matches network partition. Isolation Forest score -0.048 (threshold +0.103), severity 0.98. Evidence: replicas ready 2/2 (declared minimum 2); metrics endpoint unreachable on 50% of pods; caller_error_rate=0.6% vs baseline 0.0% (z=+0.3). Also deviating: api-gateway, order-service. LSTM forecast for the next 60s: score -0.048 (still anomalous). |
| 07:19:00 | RCA | payment-service | Root cause localised to payment-service (network partition, confidence 95%). api-gateway, order-service also deviate as callers of payment-service: its failure propagates to them. notification-service also deviate without a dependency explaining it (lower-ranked candidates). Change evidence: NetworkPolicy 'chaos-isolate-payment-service' denies all Ingress/Egress traffic for pods of payment-service, created 15s ago; Pod payment-service-c89555bbc-jbdww: Unhealthy — Readiness probe failed: Get "http://10.244.0.38:8003/ready": context deadline exceeded (Client.Timeout exceeded while aw. |
| 07:19:00 | GUARDRAIL | payment-service | G3 SWITCHED: network_policy_rollback failed on payment-service within the last 5 minutes; trying rolling_restart first |
| 07:19:00 | DECIDE | payment-service | Confidence in rolling_restart: 0.65 (history 0.80 over 1 attempt(s) x RCA 0.95 x blast factor 0.85). Decision: rolling_restart on payment-service (fallback network_policy_rollback, confidence 0.65). |
| 07:19:00 | REMEDIATE | payment-service | Executing rolling_restart on payment-service. |
| 07:22:01 | REMEDIATE | payment-service | rolling_restart did not complete in 181.5s — rollout did not complete within 180s. |
| 07:22:02 | DECIDE | payment-service | rolling_restart did not restore payment-service; escalating to fallback network_policy_rollback. |
| 07:22:02 | REMEDIATE | payment-service | Executing network_policy_rollback on payment-service. |
| 07:22:12 | REMEDIATE | payment-service | network_policy_rollback succeeded in 10.1s — removed 1 isolating NetworkPolicy(ies): chaos-isolate-payment-service. |
| 07:22:16 | VERIFY | payment-service | payment-service verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 7ms). |
| 07:24:50 | TEARDOWN | payment-service | Round teardown for payment-service: no residual fault found; autoscaler returned to declared bounds. |

## Round 4 — replica_reduction → api-gateway  ·  **SKIPPED_PREFLIGHT**

TTD — (target —, missed) · TTM — · TTR — (target —, missed) · healed by — · diagnosis wrong, classification wrong

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: Replica reduction on api-gateway is high impact, long idle time, and a new fault/service pair for this campaign.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | replica_reduction | api-gateway | 0.522 | 385.9 | recovered_within_sla |
| 2 | cpu_throttle | product-service | 0.453 | 388.7 | recovered_within_sla |
| 3 | cpu_throttle | notification-service | 0.38 | never | — |
| 4 | cpu_throttle | api-gateway | 0.36 | 18.4 | recovered_within_sla |
| 5 | replica_reduction | product-service | 0.291 | 19.4 | recovered_within_sla |
| 6 | cpu_throttle | order-service | 0.2 | 403.1 | recovered_within_sla |
| 7 | replica_reduction | payment-service | 0.167 | 186.2 | recovered_within_sla |
| 8 | latency_injection | api-gateway | 0.122 | 384.9 | recovered_within_sla |
| 9 | cpu_throttle | payment-service | 0.113 | 78.9 | recovered_within_sla |
| 10 | replica_reduction | order-service | 0.087 | 77.1 | recovered_within_sla |

### 2. Safety check before injecting

Decision **NO-GO** · risk MEDIUM · system health 80.0% · target ready 2/2 · load 1.05× baseline · dependents none · users possibly affected 100%

- steady state not met: payment-service currently anomalous

### 4. Detection

Not detected within the detection window.

### 7. Remediation

No remediation was needed or attempted.

### 8. Teardown and user impact


### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 07:25:06 | STRATEGY | api-gateway | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose replica_reduction on api-gateway: Replica reduction on api-gateway is high impact, long idle time, and a new fault/service pair for this campaign. |
| 07:25:15 | PREFLIGHT | api-gateway | Waiting for steady state before injecting: steady state not met: payment-service currently anomalous. |
| 07:28:15 | PREFLIGHT | api-gateway | NO-GO for replica_reduction on api-gateway: steady state not met: payment-service currently anomalous. Round skipped. |

## Round 5 — cpu_throttle → product-service  ·  **SKIPPED_PREFLIGHT**

TTD — (target —, missed) · TTM — · TTR — (target —, missed) · healed by — · diagnosis wrong, classification wrong

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: CPU throttle on product-service hasn't been tried in a while, has high traffic and impact, and targets a service not yet used this campaign.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | cpu_throttle | product-service | 0.453 | 392.0 | recovered_within_sla |
| 2 | cpu_throttle | notification-service | 0.38 | never | — |
| 3 | cpu_throttle | order-service | 0.201 | 406.3 | recovered_within_sla |
| 4 | cpu_throttle | payment-service | 0.115 | 82.2 | recovered_within_sla |
| 5 | cpu_throttle | api-gateway | 0.114 | 21.7 | recovered_within_sla |
| 6 | network_partition | product-service | 0.056 | 404.5 | recovered_within_sla |
| 7 | latency_injection | product-service | -0.0 | 194.7 | recovered_within_sla |
| 8 | network_partition | notification-service | -0.02 | never | — |
| 9 | pod_deletion | product-service | -0.057 | 78.6 | recovered_within_sla |
| 10 | latency_injection | notification-service | -0.094 | 75.9 | undetected |

### 2. Safety check before injecting

Decision **NO-GO** · risk HIGH · system health 80.0% · target ready 2/2 · load 0.96× baseline · dependents api-gateway, order-service · users possibly affected 100%

- steady state not met: payment-service currently anomalous

### 4. Detection

Not detected within the detection window.

### 7. Remediation

No remediation was needed or attempted.

### 8. Teardown and user impact


### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 07:28:21 | STRATEGY | product-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose cpu_throttle on product-service: CPU throttle on product-service hasn't been tried in a while, has high traffic and impact, and targets a service not yet used this campaign. |
| 07:28:30 | PREFLIGHT | product-service | Waiting for steady state before injecting: steady state not met: payment-service currently anomalous. |
| 07:31:25 | PREFLIGHT | product-service | NO-GO for cpu_throttle on product-service: steady state not met: payment-service currently anomalous. Round skipped. |

## Campaign-level events

| Time (UTC) | Phase | Message |
|---|---|---|
| 07:15:21 | CAMPAIGN | Campaign c-20261011-071521-1560 starting: 5 rounds (auto, auto, auto, auto, auto). |
| 07:31:25 | SUMMARY | Campaign completed: resilience score 77.9/100 — GOOD — reliable recovery with minor SLA or diagnosis misses. |
