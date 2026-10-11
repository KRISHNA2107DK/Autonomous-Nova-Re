# Incident log — campaign `c-20261011-003847-4377`

**Resilience score 98.9/100** — EXCELLENT — every fault detected, diagnosed and healed within SLA

| Component | Points |
|---|---|
| recovery sla | 35.0 |
| detection sla | 20.0 |
| remediation effectiveness | 20.0 |
| diagnosis accuracy | 15.0 |
| user protection | 8.94 |

| # | Fault | Target | Status | TTD | TTR | Users failed |
|---|---|---|---|---|---|---|
| 1 | latency_injection | payment-service | RECOVERED | 14.81s | 50.0s | 0.1% |
| 2 | replica_reduction | api-gateway | RECOVERED | 4.82s | 15.0s | 0.0% |
| 3 | cpu_throttle | order-service | RECOVERED | 9.82s | 55.0s | 5.9% |
| 4 | network_partition | product-service | RECOVERED | 9.8s | 40.0s | 20.5% |
| 5 | pod_deletion | notification-service | RECOVERED | 4.81s | 15.0s | 0.0% |

## Round 1 — latency_injection → payment-service  ·  **RECOVERED**

TTD 14.81s (target 35s, met) · TTM 16.68s · TTR 50.0s (target 120s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: Highest business impact (10) on payment-service with many dependents, never tried before, maximizing insight into critical transaction path.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | replica_reduction | api-gateway | 0.635 | never | — |
| 2 | latency_injection | payment-service | 0.585 | never | — |
| 3 | cpu_throttle | product-service | 0.565 | never | — |
| 4 | latency_injection | product-service | 0.565 | never | — |
| 5 | network_partition | product-service | 0.565 | never | — |
| 6 | pod_deletion | product-service | 0.565 | never | — |
| 7 | cpu_throttle | order-service | 0.56 | never | — |
| 8 | network_partition | order-service | 0.56 | never | — |
| 9 | pod_deletion | order-service | 0.56 | never | — |
| 10 | replica_reduction | order-service | 0.56 | never | — |

### 2. Safety check before injecting

Decision **GO** · risk HIGH · system health 100.0% · target ready 2/2 · load 0.98× baseline · dependents api-gateway, order-service · users possibly affected 100%

### 3. Failure injected

`latency_injection` on **payment-service** at 00:39:11 UTC — succeeded

Details: `{"pod": "payment-service-b6f875b8d-njmg9", "delay": "200ms", "jitter": "50ms", "command": "tc qdisc replace dev eth0 root netem delay 200ms 50ms distribution normal", "replicas_ready": 2}`

### 4. Detection

Confirmed at 00:39:26 UTC on **order-service** as `high_latency` · severity 0.9183 · Isolation Forest score 0.0157 (threshold 0.1031) · flags: iforest, zscore:p99_latency_ms, zscore:caller_p99_ms

Evidence:
- p99_latency_ms=2550.08ms vs baseline 246.95ms (z=+25.0)
- caller_p99_ms=2500.04ms vs baseline 246.99ms (z=+25.0)

LSTM 60 s forecast: score -0.0113 (still anomalous)

### 5. Root-cause analysis

Origin **payment-service** · type `high_latency` · confidence 0.922 · call path api-gateway → payment-service · affected order-service, payment-service, api-gateway

> Root cause localised to payment-service (high latency, confidence 92%). order-service, api-gateway also deviate as callers of payment-service: its failure propagates to them. Signal: p99_latency_ms=248.58ms vs baseline 246.49ms (z=+0.1); caller_p99_ms=2912.56ms vs baseline 246.52ms (z=+25.0).

Evidence:
- p99_latency_ms=248.58ms vs baseline 246.49ms (z=+0.1)
- caller_p99_ms=2912.56ms vs baseline 246.52ms (z=+25.0)

| Candidate | Score | Why |
|---|---|---|
| payment-service | 4.182 | severity 0.92; no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service']; earliest onset |
| order-service | 1.389 | severity 0.92; its dependencies ['payment-service'] are also anomalous (likely a victim); explains anomalies in callers ['api-gateway']; earliest onset |
| api-gateway | 0.356 | severity 0.93; its dependencies ['order-service', 'payment-service'] are also anomalous (likely a victim) |

### 6. Decision

Action **traffic_reroute** (fallback rolling_restart) · confidence 0.549 · priority 9.16

- payment-service: high latency at severity 0.92; business impact 10/10 -> priority 9.16. Playbook: traffic_reroute, fallback rolling_restart.
- Confidence in traffic_reroute: 0.55 (prior 0.70 (no history yet) x RCA 0.92 x blast factor 0.85).
- Decision: traffic_reroute on payment-service (fallback rolling_restart, confidence 0.55).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| traffic_reroute | payment-service | success | yes | 11.2s | quarantined payment-service-b6f875b8d-njmg9 (worst replica by live telemetry (p99=4931ms, next worst score 246 vs 4931)); traffic now on 2 healthy replica(s) |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"pod": "payment-service-b6f875b8d-njmg9", "note": "pod no longer exists (replaced)"}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 1 failed of 1281 requests (0.1%) · user p99 2362.3 ms over 64 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 00:38:52 | STRATEGY | payment-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose latency_injection on payment-service: Highest business impact (10) on payment-service with many dependents, never tried before, maximizing insight into critical transaction path. |
| 00:39:11 | PREFLIGHT | payment-service | GO: payment-service at 2/2 Ready, system 100% healthy. Blast radius: 2 dependent service(s) ['api-gateway', 'order-service'], ~100% of users, risk HIGH. |
| 00:39:11 | INJECT | payment-service | Injected latency_injection into payment-service: tc netem egress delay on one replica (payment-service-b6f875b8d-njmg9). |
| 00:39:26 | DETECT | order-service | Anomaly confirmed on order-service 15s after injection: pattern matches high latency. Isolation Forest score +0.016 (threshold +0.103), severity 0.92. Evidence: p99_latency_ms=2550.08ms vs baseline 246.95ms (z=+25.0); caller_p99_ms=2500.04ms vs baseline 246.99ms (z=+25.0). Also deviating: payment-service. LSTM forecast for the next 60s: score -0.011 (still anomalous). |
| 00:39:31 | RCA | payment-service | Root cause localised to payment-service (high latency, confidence 92%). order-service, api-gateway also deviate as callers of payment-service: its failure propagates to them. Signal: p99_latency_ms=248.58ms vs baseline 246.49ms (z=+0.1); caller_p99_ms=2912.56ms vs baseline 246.52ms (z=+25.0). |
| 00:39:31 | DECIDE | payment-service | Confidence in traffic_reroute: 0.55 (prior 0.70 (no history yet) x RCA 0.92 x blast factor 0.85). Decision: traffic_reroute on payment-service (fallback rolling_restart, confidence 0.55). |
| 00:39:31 | REMEDIATE | payment-service | Executing traffic_reroute on payment-service. |
| 00:39:42 | REMEDIATE | payment-service | traffic_reroute succeeded in 11.2s — quarantined payment-service-b6f875b8d-njmg9 (worst replica by live telemetry (p99=4931ms, next worst score 246 vs 4931)); traffic now on 2 healthy replica(s). |
| 00:39:47 | VERIFY | payment-service | payment-service verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 8ms). |
| 00:40:26 | TEARDOWN | payment-service | Round teardown for payment-service: no residual fault found; autoscaler returned to declared bounds. |
| 00:40:36 | RECOVERED | payment-service | payment-service recovered: detected in 14.81s, mitigated in 16.68s, fully back to its normal operating band in 50.0s (target 120s — MET). Users saw 1 failed requests out of 1281 (0.1%) during the incident. |

## Round 2 — replica_reduction → api-gateway  ·  **RECOVERED**

TTD 4.82s (target 35s, met) · TTM 10.46s · TTR 15.0s (target 120s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: Never tried replica reduction on the critical api-gateway, highest business impact and traffic, maximizing insight into core routing resilience.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | replica_reduction | api-gateway | 0.635 | never | — |
| 2 | cpu_throttle | product-service | 0.565 | never | — |
| 3 | network_partition | product-service | 0.565 | never | — |
| 4 | pod_deletion | product-service | 0.565 | never | — |
| 5 | cpu_throttle | order-service | 0.56 | never | — |
| 6 | network_partition | order-service | 0.56 | never | — |
| 7 | pod_deletion | order-service | 0.56 | never | — |
| 8 | replica_reduction | order-service | 0.56 | never | — |
| 9 | cpu_throttle | api-gateway | 0.403 | 64.3 | recovered_within_sla |
| 10 | cpu_throttle | notification-service | 0.38 | never | — |

### 2. Safety check before injecting

Decision **GO** · risk MEDIUM · system health 100.0% · target ready 2/2 · load 1.03× baseline · dependents none · users possibly affected 100%

### 3. Failure injected

`replica_reduction` on **api-gateway** at 00:41:01 UTC — succeeded

Details: `{"hpa": "api-gateway-hpa", "original": {"minReplicas": 2, "maxReplicas": 4}, "patched_to": {"minReplicas": 1, "maxReplicas": 1}}`

### 4. Detection

Confirmed at 00:41:06 UTC on **api-gateway** as `replica_exhaustion` · severity 0.8 · Isolation Forest score 0.1133 (threshold 0.1031) · flags: capacity_below_baseline, metrics_unreachable

Evidence:
- replicas ready 1/1 (declared minimum 2)
- metrics endpoint unreachable on 50% of pods
- autoscaler bounds min=1 max=1 below declared minimum 2

LSTM 60 s forecast: score 0.0982 (returning to normal)

### 5. Root-cause analysis

Origin **api-gateway** · type `replica_exhaustion` · confidence 0.96 · call path api-gateway · affected api-gateway

> Root cause localised to api-gateway (replica exhaustion, confidence 96%). No other service deviates; the fault is contained to api-gateway. Change evidence: HPA bounds 1-1 are below the declared 2-4; Pod api-gateway-6f5c8cf68b-pc477: Killing — Stopping container api-gateway.

Evidence:
- replicas ready 1/1 (declared minimum 2)
- metrics endpoint unreachable on 50% of pods
- autoscaler bounds min=1 max=1 below declared minimum 2
- HPA bounds 1-1 are below the declared 2-4
- Pod api-gateway-6f5c8cf68b-pc477: Killing — Stopping container api-gateway

| Candidate | Score | Why |
|---|---|---|
| api-gateway | 7.6 | severity 0.80; no anomalous dependency explains it; earliest onset; structural fault on the service itself; HPA bounds 1-1 are below the declared 2-4; Pod api-gateway-6f5c8cf68b-pc477: Killing — Stopping container api-gateway |

### 6. Decision

Action **hpa_scaleout** (fallback resource_restore) · confidence 0.672 · priority 7.2

- api-gateway: replica exhaustion at severity 0.80; business impact 9/10 -> priority 7.20. Playbook: hpa_scaleout, fallback resource_restore.
- Confidence in hpa_scaleout: 0.67 (prior 0.70 (no history yet) x RCA 0.96 x blast factor 1.00).
- Decision: hpa_scaleout on api-gateway (fallback resource_restore, confidence 0.67).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| hpa_scaleout | api-gateway | success | yes | 4.1s | autoscaler 1-1 -> 3-4; 1 -> 3 Ready replicas |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"restored": false, "note": "autoscaler already at or above declared bounds"}` · autoscaler `{"from": {"minReplicas": 3, "maxReplicas": 4}, "to": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 0 failed of 379 requests (0.0%) · user p99 242.3 ms over 19 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 00:40:43 | STRATEGY | api-gateway | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose replica_reduction on api-gateway: Never tried replica reduction on the critical api-gateway, highest business impact and traffic, maximizing insight into core routing resilience. |
| 00:41:01 | PREFLIGHT | api-gateway | GO: api-gateway at 2/2 Ready, system 100% healthy. Blast radius: 0 dependent service(s) , ~100% of users, risk MEDIUM. |
| 00:41:01 | INJECT | api-gateway | Injected replica_reduction into api-gateway: Clamp HPA to min=max=1 (api-gateway-hpa). |
| 00:41:06 | DETECT | api-gateway | Anomaly confirmed on api-gateway 5s after injection: pattern matches replica exhaustion. Isolation Forest score +0.113 (threshold +0.103), severity 0.80. Evidence: replicas ready 1/1 (declared minimum 2); metrics endpoint unreachable on 50% of pods; autoscaler bounds min=1 max=1 below declared minimum 2. LSTM forecast for the next 60s: score +0.098 (returning to normal). |
| 00:41:11 | RCA | api-gateway | Root cause localised to api-gateway (replica exhaustion, confidence 96%). No other service deviates; the fault is contained to api-gateway. Change evidence: HPA bounds 1-1 are below the declared 2-4; Pod api-gateway-6f5c8cf68b-pc477: Killing — Stopping container api-gateway. |
| 00:41:11 | DECIDE | api-gateway | Confidence in hpa_scaleout: 0.67 (prior 0.70 (no history yet) x RCA 0.96 x blast factor 1.00). Decision: hpa_scaleout on api-gateway (fallback resource_restore, confidence 0.67). |
| 00:41:11 | REMEDIATE | api-gateway | Executing hpa_scaleout on api-gateway. |
| 00:41:15 | REMEDIATE | api-gateway | hpa_scaleout succeeded in 4.1s — autoscaler 1-1 -> 3-4; 1 -> 3 Ready replicas. |
| 00:41:20 | VERIFY | api-gateway | api-gateway verified functional: 3/3 replicas Ready and 5 consecutive user-path probes OK (last 12ms). |
| 00:41:26 | TEARDOWN | api-gateway | Round teardown for api-gateway: no residual fault found; autoscaler returned to declared bounds. |
| 00:41:36 | RECOVERED | api-gateway | api-gateway recovered: detected in 4.82s, mitigated in 10.46s, fully back to its normal operating band in 15.0s (target 120s — MET). Users saw 0 failed requests out of 379 (0.0%) during the incident. |

## Round 3 — cpu_throttle → order-service  ·  **RECOVERED**

TTD 9.82s (target 35s, met) · TTM 10.82s · TTR 55.0s (target 90s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: Highest business impact (8) on a core service with dependents, using a fresh fault type and service for this campaign.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | cpu_throttle | product-service | 0.565 | never | — |
| 2 | network_partition | product-service | 0.565 | never | — |
| 3 | pod_deletion | product-service | 0.565 | never | — |
| 4 | cpu_throttle | order-service | 0.56 | never | — |
| 5 | network_partition | order-service | 0.56 | never | — |
| 6 | pod_deletion | order-service | 0.56 | never | — |
| 7 | cpu_throttle | notification-service | 0.38 | never | — |
| 8 | network_partition | notification-service | 0.38 | never | — |
| 9 | pod_deletion | notification-service | 0.38 | never | — |
| 10 | latency_injection | product-service | 0.165 | never | — |

### 2. Safety check before injecting

Decision **GO** · risk MEDIUM · system health 100.0% · target ready 2/2 · load 1.03× baseline · dependents api-gateway · users possibly affected 100%

### 3. Failure injected

`cpu_throttle` on **order-service** at 00:42:01 UTC — succeeded

Details: `{"pods": ["order-service-6d874b5f49-84lmr", "order-service-6d874b5f49-dtwm6"], "cpu_limit": "25m", "original": {"order-service-6d874b5f49-84lmr": {"order-service": {"requests": {"cpu": "100m", "memory": "96Mi"}, "limits": {"cpu": "500m", "memory": "256Mi"}}}, "order-service-6d874b5f49-dtwm6": {"order-service": {"requests": {"cpu": "100m", "memory": "96Mi"}, "limits": {"cpu": "500m", "memory": "256Mi"}}}}}`

### 4. Detection

Confirmed at 00:42:11 UTC on **api-gateway** as `high_latency` · severity 0.9386 · Isolation Forest score -0.0453 (threshold 0.1031) · flags: iforest, zscore:p99_latency_ms, zscore:inflight, zscore:caller_p99_ms

Evidence:
- p99_latency_ms=248.69ms vs baseline 242.46ms (z=+0.2)
- caller_p99_ms=520.00ms vs baseline 242.66ms (z=+7.6)

LSTM 60 s forecast: score -0.0513 (still anomalous)

### 5. Root-cause analysis

Origin **order-service** · type `cpu_throttle` · confidence 0.95 · call path api-gateway → order-service · affected api-gateway, product-service, order-service, payment-service

> Root cause localised to order-service (cpu throttle, confidence 95%). api-gateway also deviate as callers of order-service: its failure propagates to them. product-service, payment-service deviate because requests from order-service stopped reaching them. Change evidence: pod order-service-6d874b5f49-84lmr CPU limit is 25m vs declared 500m; pod order-service-6d874b5f49-dtwm6 CPU limit is 25m vs declared 500m.

Evidence:
- p99_latency_ms=646.67ms vs baseline 246.95ms (z=+10.8)
- caller_p99_ms=730.00ms vs baseline 246.99ms (z=+13.0)
- pod order-service-6d874b5f49-84lmr CPU limit is 25m vs declared 500m
- pod order-service-6d874b5f49-dtwm6 CPU limit is 25m vs declared 500m
- Pod order-service-6d874b5f49-84lmr: Unhealthy — Readiness probe failed: Get "http://10.244.0.27:8002/ready": context deadline exceeded (Client.Timeout exceeded while aw
- Pod order-service-6d874b5f49-dtwm6: Unhealthy — Readiness probe failed: Get "http://10.244.0.21:8002/ready": context deadline exceeded (Client.Timeout exceeded while aw
- Pod order-service-6d874b5f49-dtwm6: Unhealthy — Liveness probe failed: Get "http://10.244.0.21:8002/health": context deadline exceeded (Client.Timeout exceeded while aw

| Candidate | Score | Why |
|---|---|---|
| order-service | 9.799 | severity 1.00; its dependencies ['product-service', 'payment-service'] are also anomalous (likely a victim); explains anomalies in callers ['api-gateway']; earliest onset; structural fault on the service itself; pod order-service-6d874b5f49-84lmr CPU limit is 25m vs declared 500m; pod order-service-6d874b5f49-dtwm6 CPU limit is 25m vs declared 500m; Pod order-service-6d874b5f49-84lmr: Unhealthy — … |
| payment-service | 3.448 | severity 0.92; no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service'] |
| api-gateway | 2.348 | severity 0.95; its dependencies ['product-service', 'order-service', 'payment-service'] are also anomalous (likely a victim); earliest onset; 138 ERROR log lines in the last 60s, e.g. 'upstream error (order-service)' |
| product-service | 1.925 | severity 0.91; its own server-side latency/errors are normal; the degradation is only visible from callers (network or caller-side problem); no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service'] |

### 6. Decision

Action **resource_restore** (fallback rolling_restart) · confidence 0.615 · priority 7.996

- order-service: cpu throttle at severity 1.00; business impact 8/10 -> priority 8.00. Playbook: resource_restore, fallback rolling_restart.
- Confidence in resource_restore: 0.61 (prior 0.70 (no history yet) x RCA 0.95 x blast factor 0.93).
- Decision: resource_restore on order-service (fallback rolling_restart, confidence 0.61).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| resource_restore | order-service | success | yes | 2.1s | resized 2 container(s) in place to {'order-service': {'requests': {'cpu': '100m', 'memory': '96Mi'}, 'limits': {'cpu': '500m', 'memory': '256Mi'}}} |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"restored_pods": []}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 77 failed of 1297 requests (5.9%) · user p99 9078.8 ms over 64 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 00:41:43 | STRATEGY | order-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose cpu_throttle on order-service: Highest business impact (8) on a core service with dependents, using a fresh fault type and service for this campaign. |
| 00:42:01 | PREFLIGHT | order-service | GO: order-service at 2/2 Ready, system 100% healthy. Blast radius: 1 dependent service(s) ['api-gateway'], ~100% of users, risk MEDIUM. |
| 00:42:01 | INJECT | order-service | Injected cpu_throttle into order-service: In-place resize of every replica's CPU limit to a starvation value (order-service-6d874b5f49-84lmr,order-service-6d874b5f49-dtwm6). |
| 00:42:11 | DETECT | api-gateway | Anomaly confirmed on api-gateway 10s after injection: pattern matches high latency. Isolation Forest score -0.045 (threshold +0.103), severity 0.94. Evidence: p99_latency_ms=248.69ms vs baseline 242.46ms (z=+0.2); caller_p99_ms=520.00ms vs baseline 242.66ms (z=+7.6). Also deviating: order-service. LSTM forecast for the next 60s: score -0.051 (still anomalous). |
| 00:42:16 | RCA | order-service | Root cause localised to order-service (cpu throttle, confidence 95%). api-gateway also deviate as callers of order-service: its failure propagates to them. product-service, payment-service deviate because requests from order-service stopped reaching them. Change evidence: pod order-service-6d874b5f49-84lmr CPU limit is 25m vs declared 500m; pod order-service-6d874b5f49-dtwm6 CPU limit is 25m vs declared 500m. |
| 00:42:16 | DECIDE | order-service | Confidence in resource_restore: 0.61 (prior 0.70 (no history yet) x RCA 0.95 x blast factor 0.93). Decision: resource_restore on order-service (fallback rolling_restart, confidence 0.61). |
| 00:42:16 | REMEDIATE | order-service | Executing resource_restore on order-service. |
| 00:42:19 | REMEDIATE | order-service | resource_restore succeeded in 2.1s — resized 2 container(s) in place to {'order-service': {'requests': {'cpu': '100m', 'memory': '96Mi'}, 'limits': {'cpu': '500m', 'memory': '256Mi'}}}. |
| 00:42:26 | VERIFY | order-service | order-service verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 7ms). |
| 00:43:16 | TEARDOWN | order-service | Round teardown for order-service: no residual fault found; autoscaler returned to declared bounds. |
| 00:43:26 | RECOVERED | order-service | order-service recovered: detected in 9.82s, mitigated in 10.82s, fully back to its normal operating band in 55.0s (target 90s — MET). Users saw 77 failed requests out of 1297 (5.9%) during the incident. |

## Round 4 — network_partition → product-service  ·  **RECOVERED**

TTD 9.8s (target 30s, met) · TTM 10.76s · TTR 40.0s (target 90s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: Network partition on product-service is untried, impacts high traffic (75%) and multiple dependents, and introduces a new fault type for this campaign.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | network_partition | product-service | 0.565 | never | — |
| 2 | pod_deletion | product-service | 0.565 | never | — |
| 3 | network_partition | notification-service | 0.38 | never | — |
| 4 | pod_deletion | notification-service | 0.38 | never | — |
| 5 | network_partition | order-service | 0.31 | never | — |
| 6 | pod_deletion | order-service | 0.31 | never | — |
| 7 | cpu_throttle | product-service | 0.165 | never | — |
| 8 | latency_injection | product-service | 0.165 | never | — |
| 9 | network_partition | api-gateway | 0.111 | 19.4 | recovered_within_sla |
| 10 | pod_deletion | api-gateway | 0.109 | 17.7 | recovered_within_sla |

### 2. Safety check before injecting

Decision **GO** · risk HIGH · system health 100.0% · target ready 2/2 · load 1.0× baseline · dependents api-gateway, order-service · users possibly affected 100%

### 3. Failure injected

`network_partition` on **product-service** at 00:43:51 UTC — succeeded

Details: `{"policy": "chaos-isolate-product-service", "effect": "deny all ingress + egress", "conntrack_flush": {"ok": true, "pod_ips": ["10.244.0.34", "10.244.0.35"], "agents": {"chaos-agent-zm457": true}}}`

### 4. Detection

Confirmed at 00:44:01 UTC on **api-gateway** as `high_latency` · severity 0.9614 · Isolation Forest score -0.114 (threshold 0.1031) · flags: iforest, zscore:p99_latency_ms, zscore:inflight, zscore:caller_p99_ms

Evidence:
- p99_latency_ms=242.93ms vs baseline 242.46ms (z=+0.0)
- caller_p99_ms=1075.00ms vs baseline 242.66ms (z=+22.9)

LSTM 60 s forecast: score -0.1161 (still anomalous)

### 5. Root-cause analysis

Origin **product-service** · type `network_partition` · confidence 0.95 · call path api-gateway → product-service · affected api-gateway, product-service, order-service, notification-service, payment-service

> Root cause localised to product-service (network partition, confidence 95%). api-gateway, order-service also deviate as callers of product-service: its failure propagates to them. notification-service, payment-service also deviate without a dependency explaining it (lower-ranked candidates). Change evidence: NetworkPolicy 'chaos-isolate-product-service' denies all Ingress/Egress traffic for pods of product-service, created 15s ago; Pod product-service-84848bf994-7gtnp: Unhealthy — Readiness probe failed: Get "http://10.244.0.34:8001/ready": context deadline exceeded (Client.Timeout exceeded while aw.

Evidence:
- replicas ready 2/2 (declared minimum 2)
- metrics endpoint unreachable on 100% of pods
- caller_error_rate=3.9% vs baseline 0.0% (z=+2.0)
- request_rate=13.92 req/s vs baseline 20.32 req/s (z=-3.1)
- pods are running (no container restarts) but cannot be reached over the pod network
- NetworkPolicy 'chaos-isolate-product-service' denies all Ingress/Egress traffic for pods of product-service, created 15s ago
- Pod product-service-84848bf994-7gtnp: Unhealthy — Readiness probe failed: Get "http://10.244.0.34:8001/ready": context deadline exceeded (Client.Timeout exceeded while aw
- Pod product-service-84848bf994-nxvlh: Unhealthy — Readiness probe failed: Get "http://10.244.0.35:8001/ready": context deadline exceeded (Client.Timeout exceeded while aw

| Candidate | Score | Why |
|---|---|---|
| product-service | 8.347 | severity 1.00; no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service']; structural fault on the service itself; NetworkPolicy 'chaos-isolate-product-service' denies all Ingress/Egress traffic for pods of product-service, created 15s ago; Pod product-service-84848bf994-7gtnp: Unhealthy — Readiness probe failed: Get "http://10.244.0.34:8001/ready": context… |
| api-gateway | 3.687 | severity 0.97; its dependencies ['product-service', 'order-service'] are also anomalous (likely a victim); earliest onset; Pod api-gateway-6f5c8cf68b-4nsdr: Killing — Stopping container api-gateway; 278 ERROR log lines in the last 60s, e.g. 'request failed' |
| order-service | 2.547 | severity 0.96; its dependencies ['product-service'] are also anomalous (likely a victim); explains anomalies in callers ['api-gateway']; earliest onset; 114 ERROR log lines in the last 60s, e.g. 'dependency failure (product-service)' |
| payment-service | 0.898 | severity 0.15; only symptom is reduced traffic — consistent with an upstream failure; no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service'] |
| notification-service | 0.775 | severity 0.24; only symptom is reduced traffic — consistent with an upstream failure; no anomalous dependency explains it; explains anomalies in callers ['api-gateway'] |

### 6. Decision

Action **network_policy_rollback** (fallback rolling_restart) · confidence 0.565 · priority 5.992

- product-service: network partition at severity 1.00; business impact 6/10 -> priority 5.99. Playbook: network_policy_rollback, fallback rolling_restart.
- Confidence in network_policy_rollback: 0.56 (prior 0.70 (no history yet) x RCA 0.95 x blast factor 0.85).
- Decision: network_policy_rollback on product-service (fallback rolling_restart, confidence 0.56).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| network_policy_rollback | product-service | success | yes | 2.0s | removed 1 isolating NetworkPolicy(ies): chaos-isolate-product-service |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"policy": "chaos-isolate-product-service", "deleted": false}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 206 failed of 1005 requests (20.5%) · user p99 9572.7 ms over 49 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 00:43:33 | STRATEGY | product-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose network_partition on product-service: Network partition on product-service is untried, impacts high traffic (75%) and multiple dependents, and introduces a new fault type for this campaign. |
| 00:43:51 | PREFLIGHT | product-service | GO: product-service at 2/2 Ready, system 100% healthy. Blast radius: 2 dependent service(s) ['api-gateway', 'order-service'], ~100% of users, risk HIGH. |
| 00:43:51 | INJECT | product-service | Injected network_partition into product-service: Deny-all NetworkPolicy selecting the service's pods (chaos-isolate-product-service). |
| 00:44:01 | DETECT | api-gateway | Anomaly confirmed on api-gateway 10s after injection: pattern matches high latency. Isolation Forest score -0.114 (threshold +0.103), severity 0.96. Evidence: p99_latency_ms=242.93ms vs baseline 242.46ms (z=+0.0); caller_p99_ms=1075.00ms vs baseline 242.66ms (z=+22.9). Also deviating: order-service. LSTM forecast for the next 60s: score -0.116 (still anomalous). |
| 00:44:06 | RCA | product-service | Root cause localised to product-service (network partition, confidence 95%). api-gateway, order-service also deviate as callers of product-service: its failure propagates to them. notification-service, payment-service also deviate without a dependency explaining it (lower-ranked candidates). Change evidence: NetworkPolicy 'chaos-isolate-product-service' denies all Ingress/Egress traffic for pods of product-service, created 15s ago; Pod product-service-84848bf994-7gtnp: Unhealthy — Readiness probe failed: Get "http://10.244.0.34:8001/ready": context deadline exceeded (Client.Timeout exceeded while aw. |
| 00:44:06 | DECIDE | product-service | Confidence in network_policy_rollback: 0.56 (prior 0.70 (no history yet) x RCA 0.95 x blast factor 0.85). Decision: network_policy_rollback on product-service (fallback rolling_restart, confidence 0.56). |
| 00:44:06 | REMEDIATE | product-service | Executing network_policy_rollback on product-service. |
| 00:44:08 | REMEDIATE | product-service | network_policy_rollback succeeded in 2.0s — removed 1 isolating NetworkPolicy(ies): chaos-isolate-product-service. |
| 00:44:16 | VERIFY | product-service | product-service verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 5ms). |
| 00:44:51 | TEARDOWN | product-service | Round teardown for product-service: no residual fault found; autoscaler returned to declared bounds. |
| 00:45:01 | RECOVERED | product-service | product-service recovered: detected in 9.8s, mitigated in 10.76s, fully back to its normal operating band in 40.0s (target 90s — MET). Users saw 206 failed requests out of 1005 (20.5%) during the incident. |

## Round 5 — pod_deletion → notification-service  ·  **RECOVERED**

TTD 4.81s (target 25s, met) · TTM 9.43s · TTR 15.0s (target 90s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: First use of pod_deletion on notification-service, a fresh service with no recent trials, adding fault variety and testing low‑impact path.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | pod_deletion | notification-service | 0.38 | never | — |
| 2 | pod_deletion | product-service | 0.315 | never | — |
| 3 | pod_deletion | order-service | 0.31 | never | — |
| 4 | pod_deletion | api-gateway | 0.111 | 19.3 | recovered_within_sla |
| 5 | pod_deletion | payment-service | 0.104 | 65.2 | recovered_within_sla |
| 6 | cpu_throttle | notification-service | -0.02 | never | — |
| 7 | latency_injection | notification-service | -0.02 | never | — |
| 8 | network_partition | notification-service | -0.02 | never | — |
| 9 | cpu_throttle | product-service | -0.085 | never | — |
| 10 | latency_injection | product-service | -0.085 | never | — |

### 2. Safety check before injecting

Decision **GO** · risk MEDIUM · system health 100.0% · target ready 1/1 · load 1.07× baseline · dependents api-gateway · users possibly affected 100%

### 3. Failure injected

`pod_deletion` on **notification-service** at 00:45:26 UTC — succeeded

Details: `{"pod": "notification-service-6bd7c9776b-hsvzz", "pod_ip": "10.244.0.15", "ready_pods_before": 1}`

### 4. Detection

Confirmed at 00:45:31 UTC on **notification-service** as `pod_crash` · severity 0.4 · Isolation Forest score 0.1424 (threshold 0.1031) · flags: replicas_lost

Evidence:
- replicas ready 1/1 (declared minimum 1)
- Ready pod(s) notification-service-6bd7c9776b-hsvzz disappeared without a scale-down or rollout
- caller_error_rate=0.0% vs baseline 0.0% (z=+0.0)

LSTM 60 s forecast: score 0.1345 (returning to normal)

### 5. Root-cause analysis

Origin **notification-service** · type `pod_crash` · confidence 0.96 · call path api-gateway → notification-service · affected notification-service

> Root cause localised to notification-service (pod crash, confidence 96%). No other service deviates; the fault is contained to notification-service. Change evidence: Pod notification-service-6bd7c9776b-hsvzz: Killing — Stopping container notification-service.

Evidence:
- replicas ready 1/1 (declared minimum 1)
- Ready pod(s) notification-service-6bd7c9776b-hsvzz disappeared without a scale-down or rollout
- caller_error_rate=0.0% vs baseline 0.0% (z=+0.0)
- Pod notification-service-6bd7c9776b-hsvzz: Killing — Stopping container notification-service

| Candidate | Score | Why |
|---|---|---|
| notification-service | 4.808 | severity 0.65; no anomalous dependency explains it; earliest onset; structural fault on the service itself; Pod notification-service-6bd7c9776b-hsvzz: Killing — Stopping container notification-service |

### 6. Decision

Action **hpa_scaleout** (fallback rolling_restart) · confidence 0.622 · priority 1.308

- notification-service: pod crash at severity 0.65; business impact 2/10 -> priority 1.31. Playbook: hpa_scaleout, fallback rolling_restart.
- Confidence in hpa_scaleout: 0.62 (prior 0.70 (no history yet) x RCA 0.96 x blast factor 0.93).
- Decision: hpa_scaleout on notification-service (fallback rolling_restart, confidence 0.62).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| hpa_scaleout | notification-service | success | yes | 4.1s | autoscaler 1-3 -> 2-3; 1 -> 2 Ready replicas |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"reversible": false, "note": "Kubernetes reschedules deleted pods by itself"}` · autoscaler `{"from": {"minReplicas": 2, "maxReplicas": 3}, "to": {"minReplicas": 1, "maxReplicas": 3}}`

Users: 0 failed of 380 requests (0.0%) · user p99 243.5 ms over 19 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 00:45:07 | STRATEGY | notification-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose pod_deletion on notification-service: First use of pod_deletion on notification-service, a fresh service with no recent trials, adding fault variety and testing low‑impact path. |
| 00:45:26 | PREFLIGHT | notification-service | GO: notification-service at 1/1 Ready, system 100% healthy. Blast radius: 1 dependent service(s) ['api-gateway'], ~100% of users, risk MEDIUM. |
| 00:45:26 | INJECT | notification-service | Injected pod_deletion into notification-service: Force-delete one Ready pod (grace period 0) (notification-service-6bd7c9776b-hsvzz). |
| 00:45:31 | DETECT | notification-service | Anomaly confirmed on notification-service 5s after injection: pattern matches pod crash. Isolation Forest score +0.142 (threshold +0.103), severity 0.40. Evidence: replicas ready 1/1 (declared minimum 1); Ready pod(s) notification-service-6bd7c9776b-hsvzz disappeared without a scale-down or rollout; caller_error_rate=0.0% vs baseline 0.0% (z=+0.0). LSTM forecast for the next 60s: score +0.135 (returning to normal). |
| 00:45:36 | RCA | notification-service | Root cause localised to notification-service (pod crash, confidence 96%). No other service deviates; the fault is contained to notification-service. Change evidence: Pod notification-service-6bd7c9776b-hsvzz: Killing — Stopping container notification-service. |
| 00:45:36 | DECIDE | notification-service | Confidence in hpa_scaleout: 0.62 (prior 0.70 (no history yet) x RCA 0.96 x blast factor 0.93). Decision: hpa_scaleout on notification-service (fallback rolling_restart, confidence 0.62). |
| 00:45:36 | REMEDIATE | notification-service | Executing hpa_scaleout on notification-service. |
| 00:45:40 | REMEDIATE | notification-service | hpa_scaleout succeeded in 4.1s — autoscaler 1-3 -> 2-3; 1 -> 2 Ready replicas. |
| 00:45:44 | VERIFY | notification-service | notification-service verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 4ms). |
| 00:45:51 | TEARDOWN | notification-service | Round teardown for notification-service: no residual fault found; autoscaler returned to declared bounds. |
| 00:46:01 | RECOVERED | notification-service | notification-service recovered: detected in 4.81s, mitigated in 9.43s, fully back to its normal operating band in 15.0s (target 90s — MET). Users saw 0 failed requests out of 380 (0.0%) during the incident. |

## Campaign-level events

| Time (UTC) | Phase | Message |
|---|---|---|
| 00:38:47 | CAMPAIGN | Campaign c-20261011-003847-4377 starting: 5 rounds (auto, auto, auto, auto, auto). |
| 00:46:01 | SUMMARY | Campaign completed: resilience score 98.9/100 — EXCELLENT — every fault detected, diagnosed and healed within SLA. |
