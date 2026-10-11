# Incident log — campaign `c-20261010-233424-3b77`

**Resilience score 99.6/100** — EXCELLENT — every fault detected, diagnosed and healed within SLA

| Component | Points |
|---|---|
| recovery sla | 35.0 |
| detection sla | 20.0 |
| remediation effectiveness | 20.0 |
| diagnosis accuracy | 15.0 |
| user protection | 9.58 |

| # | Fault | Target | Status | TTD | TTR | Users failed |
|---|---|---|---|---|---|---|
| 1 | network_partition | payment-service | RECOVERED | 9.85s | 44.99s | 10.4% |
| 2 | cpu_throttle | api-gateway | RECOVERED | 14.82s | 50.01s | 0.0% |
| 3 | latency_injection | api-gateway | RECOVERED | 9.85s | 44.99s | 0.2% |
| 4 | pod_deletion | payment-service | RECOVERED | 4.84s | 20.0s | 0.0% |
| 5 | replica_reduction | payment-service | RECOVERED | 4.84s | 20.01s | 0.0% |

## Round 1 — network_partition → payment-service  ·  **RECOVERED**

TTD 9.85s (target 30s, met) · TTM 11.58s · TTR 44.99s (target 90s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: Inject network partition into payment-service, the highest‑impact service with critical dependents, never tried before, to assess cascade failures and recovery across the most valuable transaction path.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | cpu_throttle | api-gateway | 0.635 | never | — |
| 2 | latency_injection | api-gateway | 0.635 | never | — |
| 3 | network_partition | api-gateway | 0.635 | never | — |
| 4 | pod_deletion | api-gateway | 0.635 | never | — |
| 5 | replica_reduction | api-gateway | 0.635 | never | — |
| 6 | cpu_throttle | payment-service | 0.585 | never | — |
| 7 | latency_injection | payment-service | 0.585 | never | — |
| 8 | network_partition | payment-service | 0.585 | never | — |
| 9 | pod_deletion | payment-service | 0.585 | never | — |
| 10 | replica_reduction | payment-service | 0.585 | never | — |

### 2. Safety check before injecting

Decision **GO** · risk HIGH · system health 100.0% · target ready 2/2 · load 0.9× baseline · dependents api-gateway, order-service · users possibly affected 100%

### 3. Failure injected

`network_partition` on **payment-service** at 23:34:45 UTC — succeeded

Details: `{"policy": "chaos-isolate-payment-service", "effect": "deny all ingress + egress", "conntrack_flush": {"ok": true, "pod_ips": ["10.244.0.12", "10.244.0.14"], "agents": {"chaos-agent-45wxr": true}}}`

### 4. Detection

Confirmed at 23:34:55 UTC on **payment-service** as `high_latency` · severity 0.9893 · Isolation Forest score -0.0297 (threshold 0.1031) · flags: iforest, zscore:caller_error_rate, zscore:caller_p99_ms, replicas_lost, metrics_unreachable

Evidence:
- p99_latency_ms=246.41ms vs baseline 246.49ms (z=-0.0)
- caller_p99_ms=2305.00ms vs baseline 246.52ms (z=+25.0)

LSTM 60 s forecast: score -0.0389 (still anomalous)

### 5. Root-cause analysis

Origin **payment-service** · type `network_partition` · confidence 0.95 · call path api-gateway → payment-service · affected api-gateway, order-service, payment-service, notification-service

> Root cause localised to payment-service (network partition, confidence 95%). api-gateway, order-service also deviate as callers of payment-service: its failure propagates to them. notification-service also deviate without a dependency explaining it (lower-ranked candidates). Change evidence: NetworkPolicy 'chaos-isolate-payment-service' denies all Ingress/Egress traffic for pods of payment-service, created 15s ago; Pod payment-service-575ff5bc6d-5ck2l: Unhealthy — Readiness probe failed: Get "http://10.244.0.12:8003/ready": context deadline exceeded (Client.Timeout exceeded while aw.

Evidence:
- p99_latency_ms=246.41ms vs baseline 246.49ms (z=-0.0)
- caller_p99_ms=2305.00ms vs baseline 246.52ms (z=+25.0)
- NetworkPolicy 'chaos-isolate-payment-service' denies all Ingress/Egress traffic for pods of payment-service, created 15s ago
- Pod payment-service-575ff5bc6d-5ck2l: Unhealthy — Readiness probe failed: Get "http://10.244.0.12:8003/ready": context deadline exceeded (Client.Timeout exceeded while aw
- Pod payment-service-575ff5bc6d-xp2qh: Unhealthy — Readiness probe failed: Get "http://10.244.0.14:8003/ready": context deadline exceeded (Client.Timeout exceeded while aw

| Candidate | Score | Why |
|---|---|---|
| payment-service | 9.097 | severity 1.00; no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service']; earliest onset; structural fault on the service itself; NetworkPolicy 'chaos-isolate-payment-service' denies all Ingress/Egress traffic for pods of payment-service, created 15s ago; Pod payment-service-575ff5bc6d-5ck2l: Unhealthy — Readiness probe failed: Get "http://10.244.0.12:8003… |
| order-service | 2.885 | severity 0.96; its dependencies ['payment-service'] are also anomalous (likely a victim); explains anomalies in callers ['api-gateway']; earliest onset; 184 ERROR log lines in the last 60s, e.g. 'dependency failure (payment-service)' |
| api-gateway | 2.367 | severity 0.97; its dependencies ['order-service', 'payment-service'] are also anomalous (likely a victim); earliest onset; 136 ERROR log lines in the last 60s, e.g. 'request failed' |
| notification-service | 0.741 | severity 0.22; only symptom is reduced traffic — consistent with an upstream failure; no anomalous dependency explains it; explains anomalies in callers ['api-gateway'] |

### 6. Decision

Action **network_policy_rollback** (fallback rolling_restart) · confidence 0.565 · priority 9.987

- payment-service: network partition at severity 1.00; business impact 10/10 -> priority 9.99. Playbook: network_policy_rollback, fallback rolling_restart.
- Confidence in network_policy_rollback: 0.56 (prior 0.70 (no history yet) x RCA 0.95 x blast factor 0.85).
- Decision: network_policy_rollback on payment-service (fallback rolling_restart, confidence 0.56).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| network_policy_rollback | payment-service | success | yes | 6.1s | removed 1 isolating NetworkPolicy(ies): chaos-isolate-payment-service |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"policy": "chaos-isolate-payment-service", "deleted": false}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 110 failed of 1052 requests (10.4%) · user p99 5440.9 ms over 54 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 23:34:26 | STRATEGY | payment-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose network_partition on payment-service: Inject network partition into payment-service, the highest‑impact service with critical dependents, never tried before, to assess cascade failures and recovery across the most valuable transaction path. |
| 23:34:45 | PREFLIGHT | payment-service | GO: payment-service at 2/2 Ready, system 100% healthy. Blast radius: 2 dependent service(s) ['api-gateway', 'order-service'], ~100% of users, risk HIGH. |
| 23:34:45 | INJECT | payment-service | Injected network_partition into payment-service: Deny-all NetworkPolicy selecting the service's pods (chaos-isolate-payment-service). |
| 23:34:55 | DETECT | payment-service | Anomaly confirmed on payment-service 10s after injection: pattern matches high latency. Isolation Forest score -0.030 (threshold +0.103), severity 0.99. Evidence: p99_latency_ms=246.41ms vs baseline 246.49ms (z=-0.0); caller_p99_ms=2305.00ms vs baseline 246.52ms (z=+25.0). Also deviating: api-gateway, order-service. LSTM forecast for the next 60s: score -0.039 (still anomalous). |
| 23:35:00 | RCA | payment-service | Root cause localised to payment-service (network partition, confidence 95%). api-gateway, order-service also deviate as callers of payment-service: its failure propagates to them. notification-service also deviate without a dependency explaining it (lower-ranked candidates). Change evidence: NetworkPolicy 'chaos-isolate-payment-service' denies all Ingress/Egress traffic for pods of payment-service, created 15s ago; Pod payment-service-575ff5bc6d-5ck2l: Unhealthy — Readiness probe failed: Get "http://10.244.0.12:8003/ready": context deadline exceeded (Client.Timeout exceeded while aw. |
| 23:35:00 | DECIDE | payment-service | Confidence in network_policy_rollback: 0.56 (prior 0.70 (no history yet) x RCA 0.95 x blast factor 0.85). Decision: network_policy_rollback on payment-service (fallback rolling_restart, confidence 0.56). |
| 23:35:00 | REMEDIATE | payment-service | Executing network_policy_rollback on payment-service. |
| 23:35:06 | REMEDIATE | payment-service | network_policy_rollback succeeded in 6.1s — removed 1 isolating NetworkPolicy(ies): chaos-isolate-payment-service. |
| 23:35:10 | VERIFY | payment-service | payment-service verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 7ms). |
| 23:35:50 | TEARDOWN | payment-service | Round teardown for payment-service: no residual fault found; autoscaler returned to declared bounds. |
| 23:36:00 | RECOVERED | payment-service | payment-service recovered: detected in 9.85s, mitigated in 11.58s, fully back to its normal operating band in 44.99s (target 90s — MET). Users saw 110 failed requests out of 1052 (10.4%) during the incident. |

## Round 2 — cpu_throttle → api-gateway  ·  **RECOVERED**

TTD 14.82s (target 35s, met) · TTM 7.56s · TTR 50.01s (target 90s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: First-time CPU throttling on high‑impact api‑gateway, which routes all traffic and has many downstream services, maximizes learning about core request handling resilience.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | cpu_throttle | api-gateway | 0.635 | never | — |
| 2 | latency_injection | api-gateway | 0.635 | never | — |
| 3 | pod_deletion | api-gateway | 0.635 | never | — |
| 4 | replica_reduction | api-gateway | 0.635 | never | — |
| 5 | cpu_throttle | product-service | 0.565 | never | — |
| 6 | latency_injection | product-service | 0.565 | never | — |
| 7 | pod_deletion | product-service | 0.565 | never | — |
| 8 | replica_reduction | product-service | 0.565 | never | — |
| 9 | cpu_throttle | order-service | 0.56 | never | — |
| 10 | latency_injection | order-service | 0.56 | never | — |

### 2. Safety check before injecting

Decision **GO** · risk MEDIUM · system health 100.0% · target ready 2/2 · load 0.95× baseline · dependents none · users possibly affected 100%

### 3. Failure injected

`cpu_throttle` on **api-gateway** at 23:36:25 UTC — succeeded

Details: `{"pods": ["api-gateway-f65f9d7f5-5hl5f", "api-gateway-f65f9d7f5-mxdkk"], "cpu_limit": "25m", "original": {"api-gateway-f65f9d7f5-5hl5f": {"api-gateway": {"requests": {"cpu": "100m", "memory": "64Mi"}, "limits": {"cpu": "500m", "memory": "192Mi"}}}, "api-gateway-f65f9d7f5-mxdkk": {"api-gateway": {"requests": {"cpu": "100m", "memory": "64Mi"}, "limits": {"cpu": "500m", "memory": "192Mi"}}}}}`

### 4. Detection

Confirmed at 23:36:40 UTC on **product-service** as `high_latency` · severity 0.7238 · Isolation Forest score 0.0636 (threshold 0.1031) · flags: iforest, zscore:caller_p99_ms

Evidence:
- p99_latency_ms=11.74ms vs baseline 16.09ms (z=-0.3)
- caller_p99_ms=99.19ms vs baseline 16.56ms (z=+5.5)

LSTM 60 s forecast: score 0.042 (still anomalous)

### 5. Root-cause analysis

Origin **api-gateway** · type `cpu_throttle` · confidence 0.95 · call path api-gateway · affected api-gateway, product-service, order-service

> Root cause localised to api-gateway (cpu throttle, confidence 95%). product-service, order-service deviate because requests from api-gateway stopped reaching them. Change evidence: pod api-gateway-f65f9d7f5-5hl5f CPU limit is 25m vs declared 500m; pod api-gateway-f65f9d7f5-mxdkk CPU limit is 25m vs declared 500m.

Evidence:
- p99_latency_ms=496.00ms vs baseline 242.46ms (z=+7.0)
- caller_p99_ms=505.00ms vs baseline 242.66ms (z=+7.2)
- pod api-gateway-f65f9d7f5-5hl5f CPU limit is 25m vs declared 500m
- pod api-gateway-f65f9d7f5-mxdkk CPU limit is 25m vs declared 500m

| Candidate | Score | Why |
|---|---|---|
| api-gateway | 8.595 | severity 0.67; its dependencies ['product-service', 'order-service'] are also anomalous (likely a victim); earliest onset; pod api-gateway-f65f9d7f5-5hl5f CPU limit is 25m vs declared 500m; pod api-gateway-f65f9d7f5-mxdkk CPU limit is 25m vs declared 500m; its calls to product-service take 607ms longer than product-service itself needs to serve them (caller-side or network problem); its calls to o… |
| product-service | 2.388 | severity 0.77; its own server-side latency/errors are normal; the degradation is only visible from callers (network or caller-side problem); no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service']; earliest onset |
| order-service | -1.192 | severity 0.38; its own server-side latency/errors are normal; the degradation is only visible from callers (network or caller-side problem); its dependencies ['product-service'] are also anomalous (likely a victim); explains anomalies in callers ['api-gateway']; earliest onset |

### 6. Decision

Action **resource_restore** (fallback rolling_restart) · confidence 0.665 · priority 6.051

- api-gateway: cpu throttle at severity 0.67; business impact 9/10 -> priority 6.05. Playbook: resource_restore, fallback rolling_restart.
- Confidence in resource_restore: 0.67 (prior 0.70 (no history yet) x RCA 0.95 x blast factor 1.00).
- Decision: resource_restore on api-gateway (fallback rolling_restart, confidence 0.67).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| resource_restore | api-gateway | success | yes | 2.1s | resized 2 container(s) in place to {'api-gateway': {'requests': {'cpu': '100m', 'memory': '64Mi'}, 'limits': {'cpu': '500m', 'memory': '192Mi'}}} |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"restored_pods": []}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 0 failed of 1281 requests (0.0%) · user p99 460.4 ms over 64 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 23:36:06 | STRATEGY | api-gateway | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose cpu_throttle on api-gateway: First-time CPU throttling on high‑impact api‑gateway, which routes all traffic and has many downstream services, maximizes learning about core request handling resilience. |
| 23:36:25 | PREFLIGHT | api-gateway | GO: api-gateway at 2/2 Ready, system 100% healthy. Blast radius: 0 dependent service(s) , ~100% of users, risk MEDIUM. |
| 23:36:25 | INJECT | api-gateway | Injected cpu_throttle into api-gateway: In-place resize of every replica's CPU limit to a starvation value (api-gateway-f65f9d7f5-5hl5f,api-gateway-f65f9d7f5-mxdkk). |
| 23:36:40 | DETECT | product-service | Anomaly confirmed on product-service 15s after injection: pattern matches high latency. Isolation Forest score +0.064 (threshold +0.103), severity 0.72. Evidence: p99_latency_ms=11.74ms vs baseline 16.09ms (z=-0.3); caller_p99_ms=99.19ms vs baseline 16.56ms (z=+5.5). LSTM forecast for the next 60s: score +0.042 (still anomalous). |
| 23:36:45 | RCA | api-gateway | Root cause localised to api-gateway (cpu throttle, confidence 95%). product-service, order-service deviate because requests from api-gateway stopped reaching them. Change evidence: pod api-gateway-f65f9d7f5-5hl5f CPU limit is 25m vs declared 500m; pod api-gateway-f65f9d7f5-mxdkk CPU limit is 25m vs declared 500m. |
| 23:36:45 | DECIDE | api-gateway | Confidence in resource_restore: 0.67 (prior 0.70 (no history yet) x RCA 0.95 x blast factor 1.00). Decision: resource_restore on api-gateway (fallback rolling_restart, confidence 0.67). |
| 23:36:45 | REMEDIATE | api-gateway | Executing resource_restore on api-gateway. |
| 23:36:47 | REMEDIATE | api-gateway | resource_restore succeeded in 2.1s — resized 2 container(s) in place to {'api-gateway': {'requests': {'cpu': '100m', 'memory': '64Mi'}, 'limits': {'cpu': '500m', 'memory': '192Mi'}}}. |
| 23:36:51 | VERIFY | api-gateway | api-gateway verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 6ms). |
| 23:37:40 | TEARDOWN | api-gateway | Round teardown for api-gateway: no residual fault found; autoscaler returned to declared bounds. |
| 23:37:50 | RECOVERED | api-gateway | api-gateway recovered: detected in 14.82s, mitigated in 7.56s, fully back to its normal operating band in 50.01s (target 90s — MET). Users saw 0 failed requests out of 1281 (0.0%) during the incident. |

## Round 3 — latency_injection → api-gateway  ·  **RECOVERED**

TTD 9.85s (target 35s, met) · TTM 17.58s · TTR 44.99s (target 120s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: High‑impact latency injection on api‑gateway, never tried, adds new fault type and stresses the critical entry point.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | latency_injection | product-service | 0.565 | never | — |
| 2 | pod_deletion | product-service | 0.565 | never | — |
| 3 | replica_reduction | product-service | 0.565 | never | — |
| 4 | latency_injection | order-service | 0.56 | never | — |
| 5 | pod_deletion | order-service | 0.56 | never | — |
| 6 | replica_reduction | order-service | 0.56 | never | — |
| 7 | latency_injection | api-gateway | 0.385 | never | — |
| 8 | pod_deletion | api-gateway | 0.385 | never | — |
| 9 | replica_reduction | api-gateway | 0.385 | never | — |
| 10 | latency_injection | notification-service | 0.38 | never | — |

### 2. Safety check before injecting

Decision **GO** · risk MEDIUM · system health 100.0% · target ready 2/2 · load 1.03× baseline · dependents none · users possibly affected 100%

### 3. Failure injected

`latency_injection` on **api-gateway** at 23:38:15 UTC — succeeded

Details: `{"pod": "api-gateway-f65f9d7f5-5hl5f", "delay": "200ms", "jitter": "50ms", "command": "tc qdisc replace dev eth0 root netem delay 200ms 50ms distribution normal", "replicas_ready": 2}`

### 4. Detection

Confirmed at 23:38:25 UTC on **order-service** as `high_latency` · severity 0.4775 · Isolation Forest score 0.0714 (threshold 0.1031) · flags: iforest, zscore:caller_p99_ms

Evidence:
- p99_latency_ms=246.60ms vs baseline 246.95ms (z=-0.0)
- caller_p99_ms=435.00ms vs baseline 246.99ms (z=+5.1)

LSTM 60 s forecast: score 0.0502 (still anomalous)

### 5. Root-cause analysis

Origin **api-gateway** · type `high_latency` · confidence 0.762 · call path api-gateway · affected api-gateway, product-service, order-service

> Root cause localised to api-gateway (high latency, confidence 76%). product-service, order-service deviate because requests from api-gateway stopped reaching them. Signal: p99_latency_ms=441.08ms vs baseline 242.46ms (z=+5.5); caller_p99_ms=715.71ms vs baseline 242.66ms (z=+13.0).

Evidence:
- p99_latency_ms=441.08ms vs baseline 242.46ms (z=+5.5)
- caller_p99_ms=715.71ms vs baseline 242.66ms (z=+13.0)

| Candidate | Score | Why |
|---|---|---|
| api-gateway | 3.23 | severity 0.86; its dependencies ['product-service', 'order-service'] are also anomalous (likely a victim); its calls to product-service take 564ms longer than product-service itself needs to serve them (caller-side or network problem); its calls to order-service take 430ms longer than order-service itself needs to serve them (caller-side or network problem) |
| product-service | 1.64 | severity 0.77; its own server-side latency/errors are normal; the degradation is only visible from callers (network or caller-side problem); no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service'] |
| order-service | -0.625 | severity 0.66; its own server-side latency/errors are normal; the degradation is only visible from callers (network or caller-side problem); its dependencies ['product-service'] are also anomalous (likely a victim); explains anomalies in callers ['api-gateway']; earliest onset |

### 6. Decision

Action **traffic_reroute** (fallback rolling_restart) · confidence 0.533 · priority 7.784

- api-gateway: high latency at severity 0.86; business impact 9/10 -> priority 7.78. Playbook: traffic_reroute, fallback rolling_restart.
- Confidence in traffic_reroute: 0.53 (prior 0.70 (no history yet) x RCA 0.76 x blast factor 1.00).
- Decision: traffic_reroute on api-gateway (fallback rolling_restart, confidence 0.53).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| traffic_reroute | api-gateway | success | yes | 9.1s | quarantined api-gateway-f65f9d7f5-5hl5f (worst replica by live telemetry (p99=916ms, next worst score 241 vs 916)); traffic now on 2 healthy replica(s) |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"pod": "api-gateway-f65f9d7f5-5hl5f", "note": "pod no longer exists (replaced)"}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 2 failed of 1081 requests (0.2%) · user p99 930.1 ms over 54 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 23:37:56 | STRATEGY | api-gateway | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose latency_injection on api-gateway: High‑impact latency injection on api‑gateway, never tried, adds new fault type and stresses the critical entry point. |
| 23:38:15 | PREFLIGHT | api-gateway | GO: api-gateway at 2/2 Ready, system 100% healthy. Blast radius: 0 dependent service(s) , ~100% of users, risk MEDIUM. |
| 23:38:15 | INJECT | api-gateway | Injected latency_injection into api-gateway: tc netem egress delay on one replica (api-gateway-f65f9d7f5-5hl5f). |
| 23:38:25 | DETECT | order-service | Anomaly confirmed on order-service 10s after injection: pattern matches high latency. Isolation Forest score +0.071 (threshold +0.103), severity 0.48. Evidence: p99_latency_ms=246.60ms vs baseline 246.95ms (z=-0.0); caller_p99_ms=435.00ms vs baseline 246.99ms (z=+5.1). LSTM forecast for the next 60s: score +0.050 (still anomalous). |
| 23:38:30 | RCA | api-gateway | Root cause localised to api-gateway (high latency, confidence 76%). product-service, order-service deviate because requests from api-gateway stopped reaching them. Signal: p99_latency_ms=441.08ms vs baseline 242.46ms (z=+5.5); caller_p99_ms=715.71ms vs baseline 242.66ms (z=+13.0). |
| 23:38:30 | DECIDE | api-gateway | Confidence in traffic_reroute: 0.53 (prior 0.70 (no history yet) x RCA 0.76 x blast factor 1.00). Decision: traffic_reroute on api-gateway (fallback rolling_restart, confidence 0.53). |
| 23:38:30 | REMEDIATE | api-gateway | Executing traffic_reroute on api-gateway. |
| 23:38:39 | REMEDIATE | api-gateway | traffic_reroute succeeded in 9.1s — quarantined api-gateway-f65f9d7f5-5hl5f (worst replica by live telemetry (p99=916ms, next worst score 241 vs 916)); traffic now on 2 healthy replica(s). |
| 23:38:46 | VERIFY | api-gateway | api-gateway verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 5ms). |
| 23:39:20 | TEARDOWN | api-gateway | Round teardown for api-gateway: no residual fault found; autoscaler returned to declared bounds. |
| 23:39:30 | RECOVERED | api-gateway | api-gateway recovered: detected in 9.85s, mitigated in 17.58s, fully back to its normal operating band in 44.99s (target 120s — MET). Users saw 2 failed requests out of 1081 (0.2%) during the incident. |

## Round 4 — pod_deletion → payment-service  ·  **RECOVERED**

TTD 4.84s (target 25s, met) · TTM 11.4s · TTR 20.0s (target 90s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: High business impact payment-service pod deletion, never tried, many dependents, and distinct fault/service from prior rounds.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | pod_deletion | product-service | 0.565 | never | — |
| 2 | replica_reduction | product-service | 0.565 | never | — |
| 3 | pod_deletion | order-service | 0.56 | never | — |
| 4 | replica_reduction | order-service | 0.56 | never | — |
| 5 | pod_deletion | api-gateway | 0.385 | never | — |
| 6 | replica_reduction | api-gateway | 0.385 | never | — |
| 7 | pod_deletion | notification-service | 0.38 | never | — |
| 8 | pod_deletion | payment-service | 0.335 | never | — |
| 9 | replica_reduction | payment-service | 0.335 | never | — |
| 10 | cpu_throttle | product-service | 0.165 | never | — |

### 2. Safety check before injecting

Decision **GO** · risk HIGH · system health 100.0% · target ready 2/2 · load 1.01× baseline · dependents api-gateway, order-service · users possibly affected 100%

### 3. Failure injected

`pod_deletion` on **payment-service** at 23:39:55 UTC — succeeded

Details: `{"pod": "payment-service-575ff5bc6d-5ck2l", "pod_ip": "10.244.0.12", "ready_pods_before": 2}`

### 4. Detection

Confirmed at 23:40:00 UTC on **payment-service** as `pod_crash` · severity 0.4 · Isolation Forest score 0.1543 (threshold 0.1031) · flags: replicas_lost

Evidence:
- replicas ready 2/2 (declared minimum 2)
- Ready pod(s) payment-service-575ff5bc6d-5ck2l disappeared without a scale-down or rollout
- caller_error_rate=0.0% vs baseline 0.0% (z=+0.0)

LSTM 60 s forecast: score 0.1529 (returning to normal)

### 5. Root-cause analysis

Origin **payment-service** · type `pod_crash` · confidence 0.918 · call path api-gateway → payment-service · affected payment-service

> Root cause localised to payment-service (pod crash, confidence 92%). No other service deviates; the fault is contained to payment-service. Change evidence: Pod payment-service-575ff5bc6d-54kkl: Unhealthy — Startup probe failed: Get "http://10.244.0.21:8003/health": dial tcp 10.244.0.21:8003: connect: connection refused; Pod payment-service-575ff5bc6d-5ck2l: Killing — Stopping container payment-service.

Evidence:
- replicas ready 2/2 (declared minimum 2)
- Ready pod(s) payment-service-575ff5bc6d-5ck2l disappeared without a scale-down or rollout
- caller_error_rate=0.0% vs baseline 0.0% (z=+0.0)
- Pod payment-service-575ff5bc6d-54kkl: Unhealthy — Startup probe failed: Get "http://10.244.0.21:8003/health": dial tcp 10.244.0.21:8003: connect: connection refused
- Pod payment-service-575ff5bc6d-5ck2l: Killing — Stopping container payment-service

| Candidate | Score | Why |
|---|---|---|
| payment-service | 3.98 | severity 0.24; no anomalous dependency explains it; earliest onset; structural fault on the service itself; Pod payment-service-575ff5bc6d-54kkl: Unhealthy — Startup probe failed: Get "http://10.244.0.21:8003/health": dial tcp 10.244.0.21:8003: connect: connection refused; Pod payment-service-575ff5bc6d-5ck2l: Killing — Stopping container payment-service |

### 6. Decision

Action **hpa_scaleout** (fallback rolling_restart) · confidence 0.546 · priority 2.4

- payment-service: pod crash at severity 0.24; business impact 10/10 -> priority 2.40. Playbook: hpa_scaleout, fallback rolling_restart.
- Confidence in hpa_scaleout: 0.55 (prior 0.70 (no history yet) x RCA 0.92 x blast factor 0.85).
- Decision: hpa_scaleout on payment-service (fallback rolling_restart, confidence 0.55).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| hpa_scaleout | payment-service | success | yes | 6.1s | autoscaler 2-4 -> 3-4; 2 -> 3 Ready replicas |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"reversible": false, "note": "Kubernetes reschedules deleted pods by itself"}` · autoscaler `{"from": {"minReplicas": 3, "maxReplicas": 4}, "to": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 0 failed of 480 requests (0.0%) · user p99 243.3 ms over 24 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 23:39:36 | STRATEGY | payment-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose pod_deletion on payment-service: High business impact payment-service pod deletion, never tried, many dependents, and distinct fault/service from prior rounds. |
| 23:39:55 | PREFLIGHT | payment-service | GO: payment-service at 2/2 Ready, system 100% healthy. Blast radius: 2 dependent service(s) ['api-gateway', 'order-service'], ~100% of users, risk HIGH. |
| 23:39:55 | INJECT | payment-service | Injected pod_deletion into payment-service: Force-delete one Ready pod (grace period 0) (payment-service-575ff5bc6d-5ck2l). |
| 23:40:00 | DETECT | payment-service | Anomaly confirmed on payment-service 5s after injection: pattern matches pod crash. Isolation Forest score +0.154 (threshold +0.103), severity 0.40. Evidence: replicas ready 2/2 (declared minimum 2); Ready pod(s) payment-service-575ff5bc6d-5ck2l disappeared without a scale-down or rollout; caller_error_rate=0.0% vs baseline 0.0% (z=+0.0). LSTM forecast for the next 60s: score +0.153 (returning to normal). |
| 23:40:05 | RCA | payment-service | Root cause localised to payment-service (pod crash, confidence 92%). No other service deviates; the fault is contained to payment-service. Change evidence: Pod payment-service-575ff5bc6d-54kkl: Unhealthy — Startup probe failed: Get "http://10.244.0.21:8003/health": dial tcp 10.244.0.21:8003: connect: connection refused; Pod payment-service-575ff5bc6d-5ck2l: Killing — Stopping container payment-service. |
| 23:40:05 | DECIDE | payment-service | Confidence in hpa_scaleout: 0.55 (prior 0.70 (no history yet) x RCA 0.92 x blast factor 0.85). Decision: hpa_scaleout on payment-service (fallback rolling_restart, confidence 0.55). |
| 23:40:05 | REMEDIATE | payment-service | Executing hpa_scaleout on payment-service. |
| 23:40:11 | REMEDIATE | payment-service | hpa_scaleout succeeded in 6.1s — autoscaler 2-4 -> 3-4; 2 -> 3 Ready replicas. |
| 23:40:15 | VERIFY | payment-service | payment-service verified functional: 3/3 replicas Ready and 5 consecutive user-path probes OK (last 6ms). |
| 23:40:20 | TEARDOWN | payment-service | Round teardown for payment-service: no residual fault found; autoscaler returned to declared bounds. |
| 23:40:30 | RECOVERED | payment-service | payment-service recovered: detected in 4.84s, mitigated in 11.4s, fully back to its normal operating band in 20.0s (target 90s — MET). Users saw 0 failed requests out of 480 (0.0%) during the incident. |

## Round 5 — replica_reduction → payment-service  ·  **RECOVERED**

TTD 4.84s (target 35s, met) · TTM 11.4s · TTR 20.01s (target 120s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: Highest business impact (10) on payment-service, a critical node with multiple dependents, never tried before and introduces a new fault type for this service.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | replica_reduction | product-service | 0.565 | never | — |
| 2 | replica_reduction | order-service | 0.56 | never | — |
| 3 | replica_reduction | api-gateway | 0.385 | never | — |
| 4 | replica_reduction | payment-service | 0.335 | never | — |
| 5 | cpu_throttle | product-service | 0.165 | never | — |
| 6 | latency_injection | product-service | 0.165 | never | — |
| 7 | network_partition | product-service | 0.165 | never | — |
| 8 | pod_deletion | product-service | 0.165 | never | — |
| 9 | cpu_throttle | order-service | 0.16 | never | — |
| 10 | latency_injection | order-service | 0.16 | never | — |

### 2. Safety check before injecting

Decision **GO** · risk HIGH · system health 100.0% · target ready 3/3 · load 0.97× baseline · dependents api-gateway, order-service · users possibly affected 100%

### 3. Failure injected

`replica_reduction` on **payment-service** at 23:40:55 UTC — succeeded

Details: `{"hpa": "payment-service-hpa", "original": {"minReplicas": 2, "maxReplicas": 4}, "patched_to": {"minReplicas": 1, "maxReplicas": 1}}`

### 4. Detection

Confirmed at 23:41:00 UTC on **payment-service** as `replica_exhaustion` · severity 0.5 · Isolation Forest score 0.1181 (threshold 0.1031) · flags: capacity_below_baseline

Evidence:
- replicas ready 1/1 (declared minimum 2)
- autoscaler bounds min=1 max=1 below declared minimum 2

LSTM 60 s forecast: score 0.1136 (returning to normal)

### 5. Root-cause analysis

Origin **payment-service** · type `replica_exhaustion` · confidence 0.96 · call path api-gateway → payment-service · affected payment-service

> Root cause localised to payment-service (replica exhaustion, confidence 96%). No other service deviates; the fault is contained to payment-service. Change evidence: HPA bounds 1-1 are below the declared 2-4; Pod payment-service-575ff5bc6d-54kkl: Killing — Stopping container payment-service.

Evidence:
- replicas ready 1/1 (declared minimum 2)
- autoscaler bounds min=1 max=1 below declared minimum 2
- HPA bounds 1-1 are below the declared 2-4
- Pod payment-service-575ff5bc6d-54kkl: Killing — Stopping container payment-service
- Pod payment-service-575ff5bc6d-pcdrl: Killing — Stopping container payment-service

| Candidate | Score | Why |
|---|---|---|
| payment-service | 7.0 | severity 0.50; no anomalous dependency explains it; earliest onset; structural fault on the service itself; HPA bounds 1-1 are below the declared 2-4; Pod payment-service-575ff5bc6d-54kkl: Killing — Stopping container payment-service; Pod payment-service-575ff5bc6d-pcdrl: Killing — Stopping container payment-service |

### 6. Decision

Action **hpa_scaleout** (fallback resource_restore) · confidence 0.571 · priority 5.0

- payment-service: replica exhaustion at severity 0.50; business impact 10/10 -> priority 5.00. Playbook: hpa_scaleout, fallback resource_restore.
- Confidence in hpa_scaleout: 0.57 (prior 0.70 (no history yet) x RCA 0.96 x blast factor 0.85).
- Decision: hpa_scaleout on payment-service (fallback resource_restore, confidence 0.57).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| hpa_scaleout | payment-service | success | yes | 6.1s | autoscaler 1-1 -> 3-4; 1 -> 3 Ready replicas |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"restored": false, "note": "autoscaler already at or above declared bounds"}` · autoscaler `{"from": {"minReplicas": 3, "maxReplicas": 4}, "to": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 0 failed of 482 requests (0.0%) · user p99 242.8 ms over 24 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 23:40:36 | STRATEGY | payment-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose replica_reduction on payment-service: Highest business impact (10) on payment-service, a critical node with multiple dependents, never tried before and introduces a new fault type for this service. |
| 23:40:55 | PREFLIGHT | payment-service | GO: payment-service at 3/3 Ready, system 100% healthy. Blast radius: 2 dependent service(s) ['api-gateway', 'order-service'], ~100% of users, risk HIGH. |
| 23:40:55 | INJECT | payment-service | Injected replica_reduction into payment-service: Clamp HPA to min=max=1 (payment-service-hpa). |
| 23:41:00 | DETECT | payment-service | Anomaly confirmed on payment-service 5s after injection: pattern matches replica exhaustion. Isolation Forest score +0.118 (threshold +0.103), severity 0.50. Evidence: replicas ready 1/1 (declared minimum 2); autoscaler bounds min=1 max=1 below declared minimum 2. LSTM forecast for the next 60s: score +0.114 (returning to normal). |
| 23:41:05 | RCA | payment-service | Root cause localised to payment-service (replica exhaustion, confidence 96%). No other service deviates; the fault is contained to payment-service. Change evidence: HPA bounds 1-1 are below the declared 2-4; Pod payment-service-575ff5bc6d-54kkl: Killing — Stopping container payment-service. |
| 23:41:05 | DECIDE | payment-service | Confidence in hpa_scaleout: 0.57 (prior 0.70 (no history yet) x RCA 0.96 x blast factor 0.85). Decision: hpa_scaleout on payment-service (fallback resource_restore, confidence 0.57). |
| 23:41:05 | REMEDIATE | payment-service | Executing hpa_scaleout on payment-service. |
| 23:41:11 | REMEDIATE | payment-service | hpa_scaleout succeeded in 6.1s — autoscaler 1-1 -> 3-4; 1 -> 3 Ready replicas. |
| 23:41:15 | VERIFY | payment-service | payment-service verified functional: 3/3 replicas Ready and 5 consecutive user-path probes OK (last 7ms). |
| 23:41:20 | TEARDOWN | payment-service | Round teardown for payment-service: no residual fault found; autoscaler returned to declared bounds. |
| 23:41:30 | RECOVERED | payment-service | payment-service recovered: detected in 4.84s, mitigated in 11.4s, fully back to its normal operating band in 20.01s (target 120s — MET). Users saw 0 failed requests out of 482 (0.0%) during the incident. |

## Campaign-level events

| Time (UTC) | Phase | Message |
|---|---|---|
| 23:34:24 | CAMPAIGN | Campaign c-20261010-233424-3b77 starting: 5 rounds (auto, auto, auto, auto, auto). |
| 23:41:30 | SUMMARY | Campaign completed: resilience score 99.6/100 — EXCELLENT — every fault detected, diagnosed and healed within SLA. |
