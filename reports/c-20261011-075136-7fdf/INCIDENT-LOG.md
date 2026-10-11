# Incident log — campaign `c-20261011-075136-7fdf`

**Resilience score 98.8/100** — EXCELLENT — every fault detected, diagnosed and healed within SLA

| Component | Points |
|---|---|
| recovery sla | 35.0 |
| detection sla | 20.0 |
| remediation effectiveness | 20.0 |
| diagnosis accuracy | 15.0 |
| user protection | 8.84 |

| # | Fault | Target | Status | TTD | TTR | Users failed |
|---|---|---|---|---|---|---|
| 1 | replica_reduction | api-gateway | RECOVERED | 4.86s | 20.0s | 0.0% |
| 2 | cpu_throttle | order-service | RECOVERED | 9.85s | 55.0s | 6.0% |
| 3 | latency_injection | api-gateway | RECOVERED | 14.85s | 45.0s | 0.0% |
| 4 | network_partition | product-service | RECOVERED | 9.86s | 40.0s | 23.0% |
| 5 | pod_deletion | payment-service | RECOVERED | 4.86s | 19.99s | 0.0% |

## Round 1 — replica_reduction → api-gateway  ·  **RECOVERED**

TTD 4.86s (target 35s, met) · TTM 11.35s · TTR 20.0s (target 120s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: High‑impact api‑gateway replica reduction not tried for 412 min, new fault type this campaign, affects many dependents, maximizing resilience insight.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | replica_reduction | api-gateway | 0.527 | 412.5 | recovered_within_sla |
| 2 | latency_injection | api-gateway | 0.527 | 411.5 | recovered_within_sla |
| 3 | network_partition | payment-service | 0.476 | 32.9 | mitigated |
| 4 | network_partition | product-service | 0.46 | 427.8 | recovered_within_sla |
| 5 | cpu_throttle | product-service | 0.458 | 415.3 | recovered_within_sla |
| 6 | cpu_throttle | order-service | 0.456 | 429.6 | recovered_within_sla |
| 7 | network_partition | api-gateway | 0.427 | 100.8 | recovered_within_sla |
| 8 | replica_reduction | payment-service | 0.426 | 212.8 | recovered_within_sla |
| 9 | latency_injection | product-service | 0.408 | 218.0 | recovered_within_sla |
| 10 | pod_deletion | order-service | 0.403 | 219.0 | recovered_within_sla |

### 2. Safety check before injecting

Decision **GO** · risk MEDIUM · system health 100.0% · target ready 2/2 · load 1.04× baseline · dependents none · users possibly affected 100%

### 3. Failure injected

`replica_reduction` on **api-gateway** at 07:51:58 UTC — succeeded

Details: `{"hpa": "api-gateway-hpa", "original": {"minReplicas": 2, "maxReplicas": 4}, "patched_to": {"minReplicas": 1, "maxReplicas": 1}}`

### 4. Detection

Confirmed at 07:52:03 UTC on **api-gateway** as `replica_exhaustion` · severity 0.5 · Isolation Forest score 0.1281 (threshold 0.1031) · flags: capacity_below_baseline

Evidence:
- replicas ready 1/1 (declared minimum 2)
- autoscaler bounds min=1 max=1 below declared minimum 2

### 5. Root-cause analysis

Origin **api-gateway** · type `replica_exhaustion` · confidence 0.96 · call path api-gateway · affected api-gateway

> Root cause localised to api-gateway (replica exhaustion, confidence 96%). No other service deviates; the fault is contained to api-gateway. Change evidence: HPA bounds 1-1 are below the declared 2-4; Pod api-gateway-6488bc94fb-zzt9d: Killing — Stopping container api-gateway.

Evidence:
- replicas ready 1/1 (declared minimum 2)
- autoscaler bounds min=1 max=1 below declared minimum 2
- HPA bounds 1-1 are below the declared 2-4
- Pod api-gateway-6488bc94fb-zzt9d: Killing — Stopping container api-gateway

| Candidate | Score | Why |
|---|---|---|
| api-gateway | 7.0 | severity 0.50; no anomalous dependency explains it; earliest onset; structural fault on the service itself; HPA bounds 1-1 are below the declared 2-4; Pod api-gateway-6488bc94fb-zzt9d: Killing — Stopping container api-gateway |

### 6. Decision

Action **hpa_scaleout** (fallback resource_restore) · confidence 0.816 · priority 4.5

- api-gateway: replica exhaustion at severity 0.50; business impact 9/10 -> priority 4.50. Playbook: hpa_scaleout, fallback resource_restore.
- Confidence in hpa_scaleout: 0.82 (history 0.85 over 2 attempt(s) x RCA 0.96 x blast factor 1.00).
- Decision: hpa_scaleout on api-gateway (fallback resource_restore, confidence 0.82).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| hpa_scaleout | api-gateway | success | yes | 6.1s | autoscaler 1-1 -> 3-4; 1 -> 3 Ready replicas |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"restored": false, "note": "autoscaler already at or above declared bounds"}` · autoscaler `{"from": {"minReplicas": 3, "maxReplicas": 4}, "to": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 0 failed of 479 requests (0.0%) · user p99 243.0 ms over 24 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 07:51:39 | STRATEGY | api-gateway | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose replica_reduction on api-gateway: High‑impact api‑gateway replica reduction not tried for 412 min, new fault type this campaign, affects many dependents, maximizing resilience insight. |
| 07:51:58 | PREFLIGHT | api-gateway | GO: api-gateway at 2/2 Ready, system 100% healthy. Blast radius: 0 dependent service(s) , ~100% of users, risk MEDIUM. |
| 07:51:58 | INJECT | api-gateway | Injected replica_reduction into api-gateway: Clamp HPA to min=max=1 (api-gateway-hpa). |
| 07:52:03 | DETECT | api-gateway | Anomaly confirmed on api-gateway 5s after injection: pattern matches replica exhaustion. Isolation Forest score +0.128 (threshold +0.103), severity 0.50. Evidence: replicas ready 1/1 (declared minimum 2); autoscaler bounds min=1 max=1 below declared minimum 2. |
| 07:52:08 | RCA | api-gateway | Root cause localised to api-gateway (replica exhaustion, confidence 96%). No other service deviates; the fault is contained to api-gateway. Change evidence: HPA bounds 1-1 are below the declared 2-4; Pod api-gateway-6488bc94fb-zzt9d: Killing — Stopping container api-gateway. |
| 07:52:08 | DECIDE | api-gateway | Confidence in hpa_scaleout: 0.82 (history 0.85 over 2 attempt(s) x RCA 0.96 x blast factor 1.00). Decision: hpa_scaleout on api-gateway (fallback resource_restore, confidence 0.82). |
| 07:52:08 | REMEDIATE | api-gateway | Executing hpa_scaleout on api-gateway. |
| 07:52:14 | REMEDIATE | api-gateway | hpa_scaleout succeeded in 6.1s — autoscaler 1-1 -> 3-4; 1 -> 3 Ready replicas. |
| 07:52:18 | VERIFY | api-gateway | api-gateway verified functional: 3/3 replicas Ready and 5 consecutive user-path probes OK (last 6ms). |
| 07:52:23 | TEARDOWN | api-gateway | Round teardown for api-gateway: no residual fault found; autoscaler returned to declared bounds. |
| 07:52:33 | RECOVERED | api-gateway | api-gateway recovered: detected in 4.86s, mitigated in 11.35s, fully back to its normal operating band in 20.0s (target 120s — MET). Users saw 0 failed requests out of 479 (0.0%) during the incident. |

## Round 2 — cpu_throttle → order-service  ·  **RECOVERED**

TTD 9.85s (target 35s, met) · TTM 10.63s · TTR 55.0s (target 90s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: High‑impact order-service CPU throttle, long idle time, few tries, and critical dependent api-gateway maximize resilience insight.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | network_partition | payment-service | 0.477 | 33.9 | mitigated |
| 2 | network_partition | product-service | 0.46 | 428.8 | recovered_within_sla |
| 3 | cpu_throttle | product-service | 0.458 | 416.3 | recovered_within_sla |
| 4 | cpu_throttle | order-service | 0.456 | 430.6 | recovered_within_sla |
| 5 | latency_injection | product-service | 0.408 | 219.0 | recovered_within_sla |
| 6 | pod_deletion | order-service | 0.404 | 220.0 | recovered_within_sla |
| 7 | cpu_throttle | payment-service | 0.38 | 106.5 | recovered_within_sla |
| 8 | cpu_throttle | notification-service | 0.38 | never | — |
| 9 | network_partition | notification-service | 0.38 | never | — |
| 10 | pod_deletion | product-service | 0.358 | 102.9 | recovered_within_sla |

### 2. Safety check before injecting

Decision **GO** · risk MEDIUM · system health 100.0% · target ready 2/2 · load 1.01× baseline · dependents api-gateway · users possibly affected 100%

### 3. Failure injected

`cpu_throttle` on **order-service** at 07:52:58 UTC — succeeded

Details: `{"pods": ["order-service-848895fdff-9xflx", "order-service-848895fdff-nkgrs"], "cpu_limit": "25m", "original": {"order-service-848895fdff-9xflx": {"order-service": {"requests": {"cpu": "100m", "memory": "96Mi"}, "limits": {"cpu": "500m", "memory": "256Mi"}}}, "order-service-848895fdff-nkgrs": {"order-service": {"requests": {"cpu": "100m", "memory": "96Mi"}, "limits": {"cpu": "500m", "memory": "256Mi"}}}}}`

### 4. Detection

Confirmed at 07:53:08 UTC on **order-service** as `high_latency` · severity 0.9556 · Isolation Forest score -0.0965 (threshold 0.1031) · flags: iforest, zscore:p99_latency_ms, zscore:inflight, zscore:caller_p99_ms

Evidence:
- p99_latency_ms=1935.00ms vs baseline 246.95ms (z=+25.0)
- caller_p99_ms=248.27ms vs baseline 246.99ms (z=+0.0)

LSTM 60 s forecast: score -0.0826 (still anomalous)

### 5. Root-cause analysis

Origin **order-service** · type `cpu_throttle` · confidence 0.95 · call path api-gateway → order-service · affected api-gateway, product-service, order-service, payment-service

> Root cause localised to order-service (cpu throttle, confidence 95%). api-gateway also deviate as callers of order-service: its failure propagates to them. product-service, payment-service deviate because requests from order-service stopped reaching them. Change evidence: pod order-service-848895fdff-9xflx CPU limit is 25m vs declared 500m; pod order-service-848895fdff-nkgrs CPU limit is 25m vs declared 500m.

Evidence:
- p99_latency_ms=1935.00ms vs baseline 246.95ms (z=+25.0)
- caller_p99_ms=248.27ms vs baseline 246.99ms (z=+0.0)
- pod order-service-848895fdff-9xflx CPU limit is 25m vs declared 500m
- pod order-service-848895fdff-nkgrs CPU limit is 25m vs declared 500m
- Pod order-service-848895fdff-9xflx: Unhealthy — Readiness probe failed: Get "http://10.244.0.36:8002/ready": context deadline exceeded (Client.Timeout exceeded while aw
- Pod order-service-848895fdff-9xflx: Unhealthy — Liveness probe failed: Get "http://10.244.0.36:8002/health": context deadline exceeded (Client.Timeout exceeded while aw
- Pod order-service-848895fdff-nkgrs: Unhealthy — Readiness probe failed: Get "http://10.244.0.25:8002/ready": context deadline exceeded (Client.Timeout exceeded while aw

| Candidate | Score | Why |
|---|---|---|
| order-service | 8.298 | severity 1.00; its dependencies ['product-service', 'payment-service'] are also anomalous (likely a victim); explains anomalies in callers ['api-gateway']; earliest onset; structural fault on the service itself; pod order-service-848895fdff-9xflx CPU limit is 25m vs declared 500m; pod order-service-848895fdff-nkgrs CPU limit is 25m vs declared 500m; Pod order-service-848895fdff-9xflx: Unhealthy — … |
| payment-service | 4.198 | severity 0.92; no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service']; earliest onset |
| product-service | 4.192 | severity 0.92; no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service']; earliest onset |
| api-gateway | 2.306 | severity 0.97; its dependencies ['product-service', 'order-service', 'payment-service'] are also anomalous (likely a victim); earliest onset; 124 ERROR log lines in the last 60s, e.g. 'upstream error (order-service)' |

### 6. Decision

Action **resource_restore** (fallback rolling_restart) · confidence 0.703 · priority 7.99

- order-service: cpu throttle at severity 1.00; business impact 8/10 -> priority 7.99. Playbook: resource_restore, fallback rolling_restart.
- Confidence in resource_restore: 0.70 (history 0.80 over 1 attempt(s) x RCA 0.95 x blast factor 0.93).
- Decision: resource_restore on order-service (fallback rolling_restart, confidence 0.70).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| resource_restore | order-service | success | yes | 2.1s | resized 2 container(s) in place to {'order-service': {'requests': {'cpu': '100m', 'memory': '96Mi'}, 'limits': {'cpu': '500m', 'memory': '256Mi'}}} |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"restored_pods": []}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 77 failed of 1289 requests (6.0%) · user p99 9056.2 ms over 64 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 07:52:40 | STRATEGY | order-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose cpu_throttle on order-service: High‑impact order-service CPU throttle, long idle time, few tries, and critical dependent api-gateway maximize resilience insight. |
| 07:52:58 | PREFLIGHT | order-service | GO: order-service at 2/2 Ready, system 100% healthy. Blast radius: 1 dependent service(s) ['api-gateway'], ~100% of users, risk MEDIUM. |
| 07:52:58 | INJECT | order-service | Injected cpu_throttle into order-service: In-place resize of every replica's CPU limit to a starvation value (order-service-848895fdff-9xflx,order-service-848895fdff-nkgrs). |
| 07:53:08 | DETECT | order-service | Anomaly confirmed on order-service 10s after injection: pattern matches high latency. Isolation Forest score -0.097 (threshold +0.103), severity 0.96. Evidence: p99_latency_ms=1935.00ms vs baseline 246.95ms (z=+25.0); caller_p99_ms=248.27ms vs baseline 246.99ms (z=+0.0). Also deviating: api-gateway, product-service, payment-service. LSTM forecast for the next 60s: score -0.083 (still anomalous). |
| 07:53:13 | RCA | order-service | Root cause localised to order-service (cpu throttle, confidence 95%). api-gateway also deviate as callers of order-service: its failure propagates to them. product-service, payment-service deviate because requests from order-service stopped reaching them. Change evidence: pod order-service-848895fdff-9xflx CPU limit is 25m vs declared 500m; pod order-service-848895fdff-nkgrs CPU limit is 25m vs declared 500m. |
| 07:53:13 | DECIDE | order-service | Confidence in resource_restore: 0.70 (history 0.80 over 1 attempt(s) x RCA 0.95 x blast factor 0.93). Decision: resource_restore on order-service (fallback rolling_restart, confidence 0.70). |
| 07:53:13 | REMEDIATE | order-service | Executing resource_restore on order-service. |
| 07:53:15 | REMEDIATE | order-service | resource_restore succeeded in 2.1s — resized 2 container(s) in place to {'order-service': {'requests': {'cpu': '100m', 'memory': '96Mi'}, 'limits': {'cpu': '500m', 'memory': '256Mi'}}}. |
| 07:53:23 | VERIFY | order-service | order-service verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 8ms). |
| 07:54:13 | TEARDOWN | order-service | Round teardown for order-service: no residual fault found; autoscaler returned to declared bounds. |
| 07:54:23 | RECOVERED | order-service | order-service recovered: detected in 9.85s, mitigated in 10.63s, fully back to its normal operating band in 55.0s (target 90s — MET). Users saw 77 failed requests out of 1289 (6.0%) during the incident. |

## Round 3 — latency_injection → api-gateway  ·  **RECOVERED**

TTD 14.85s (target 35s, met) · TTM 14.49s · TTR 45.0s (target 120s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: High‑impact latency injection on api‑gateway, central with many dependents, not tried recently (414 min) and introduces a new fault type for this campaign.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | network_partition | payment-service | 0.479 | 35.7 | mitigated |
| 2 | network_partition | product-service | 0.461 | 430.6 | recovered_within_sla |
| 3 | latency_injection | product-service | 0.409 | 220.9 | recovered_within_sla |
| 4 | network_partition | notification-service | 0.38 | never | — |
| 5 | pod_deletion | product-service | 0.359 | 104.7 | recovered_within_sla |
| 6 | latency_injection | payment-service | 0.344 | 53.3 | recovered_within_sla |
| 7 | pod_deletion | payment-service | 0.33 | 36.9 | recovered_within_sla |
| 8 | latency_injection | notification-service | 0.323 | 102.0 | undetected |
| 9 | latency_injection | api-gateway | 0.278 | 414.3 | recovered_within_sla |
| 10 | pod_deletion | notification-service | 0.276 | 429.0 | recovered_within_sla |

### 2. Safety check before injecting

Decision **GO** · risk MEDIUM · system health 100.0% · target ready 2/2 · load 0.99× baseline · dependents none · users possibly affected 100%

### 3. Failure injected

`latency_injection` on **api-gateway** at 07:54:48 UTC — succeeded

Details: `{"pod": "api-gateway-6488bc94fb-ln2vs", "delay": "200ms", "jitter": "50ms", "command": "tc qdisc replace dev eth0 root netem delay 200ms 50ms distribution normal", "replicas_ready": 2}`

### 4. Detection

Confirmed at 07:55:03 UTC on **product-service** as `high_latency` · severity 0.8973 · Isolation Forest score 0.0791 (threshold 0.1031) · flags: iforest, zscore:caller_p99_ms

Evidence:
- p99_latency_ms=19.21ms vs baseline 16.09ms (z=+0.2)
- caller_p99_ms=373.33ms vs baseline 16.56ms (z=+23.8)

LSTM 60 s forecast: score 0.0609 (still anomalous)

### 5. Root-cause analysis

Origin **api-gateway** · type `high_latency` · confidence 0.934 · call path api-gateway · affected api-gateway, product-service, order-service, payment-service

> Root cause localised to api-gateway (high latency, confidence 93%). product-service, order-service, payment-service deviate because requests from api-gateway stopped reaching them. Signal: p99_latency_ms=499.17ms vs baseline 242.46ms (z=+7.1); caller_p99_ms=917.50ms vs baseline 242.66ms (z=+18.5).

Evidence:
- p99_latency_ms=499.17ms vs baseline 242.46ms (z=+7.1)
- caller_p99_ms=917.50ms vs baseline 242.66ms (z=+18.5)

| Candidate | Score | Why |
|---|---|---|
| api-gateway | 5.525 | severity 0.89; its dependencies ['product-service', 'order-service', 'payment-service'] are also anomalous (likely a victim); earliest onset; its calls to product-service take 742ms longer than product-service itself needs to serve them (caller-side or network problem); its calls to order-service take 550ms longer than order-service itself needs to serve them (caller-side or network problem); its … |
| product-service | 2.645 | severity 0.90; its own server-side latency/errors are normal; the degradation is only visible from callers (network or caller-side problem); no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service']; earliest onset |
| payment-service | 0.72 | severity 0.31; its own server-side latency/errors are normal; the degradation is only visible from callers (network or caller-side problem); no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service'] |
| order-service | -0.445 | severity 0.75; its own server-side latency/errors are normal; the degradation is only visible from callers (network or caller-side problem); its dependencies ['product-service', 'payment-service'] are also anomalous (likely a victim); explains anomalies in callers ['api-gateway']; earliest onset |

### 6. Decision

Action **traffic_reroute** (fallback rolling_restart) · confidence 0.794 · priority 7.988

- api-gateway: high latency at severity 0.89; business impact 9/10 -> priority 7.99. Playbook: traffic_reroute, fallback rolling_restart.
- Confidence in traffic_reroute: 0.79 (history 0.85 over 2 attempt(s) x RCA 0.93 x blast factor 1.00).
- Decision: traffic_reroute on api-gateway (fallback rolling_restart, confidence 0.79).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| traffic_reroute | api-gateway | success | yes | 9.1s | quarantined api-gateway-6488bc94fb-ln2vs (worst replica by live telemetry (p99=915ms, next worst score 243 vs 915)); traffic now on 2 healthy replica(s) |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"pod": "api-gateway-6488bc94fb-ln2vs", "note": "pod no longer exists (replaced)"}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 0 failed of 1185 requests (0.0%) · user p99 959.7 ms over 59 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 07:54:30 | STRATEGY | api-gateway | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose latency_injection on api-gateway: High‑impact latency injection on api‑gateway, central with many dependents, not tried recently (414 min) and introduces a new fault type for this campaign. |
| 07:54:48 | PREFLIGHT | api-gateway | GO: api-gateway at 2/2 Ready, system 100% healthy. Blast radius: 0 dependent service(s) , ~100% of users, risk MEDIUM. |
| 07:54:48 | INJECT | api-gateway | Injected latency_injection into api-gateway: tc netem egress delay on one replica (api-gateway-6488bc94fb-ln2vs). |
| 07:55:03 | DETECT | product-service | Anomaly confirmed on product-service 15s after injection: pattern matches high latency. Isolation Forest score +0.079 (threshold +0.103), severity 0.90. Evidence: p99_latency_ms=19.21ms vs baseline 16.09ms (z=+0.2); caller_p99_ms=373.33ms vs baseline 16.56ms (z=+23.8). Also deviating: api-gateway, order-service. LSTM forecast for the next 60s: score +0.061 (still anomalous). |
| 07:55:08 | RCA | api-gateway | Root cause localised to api-gateway (high latency, confidence 93%). product-service, order-service, payment-service deviate because requests from api-gateway stopped reaching them. Signal: p99_latency_ms=499.17ms vs baseline 242.46ms (z=+7.1); caller_p99_ms=917.50ms vs baseline 242.66ms (z=+18.5). |
| 07:55:08 | DECIDE | api-gateway | Confidence in traffic_reroute: 0.79 (history 0.85 over 2 attempt(s) x RCA 0.93 x blast factor 1.00). Decision: traffic_reroute on api-gateway (fallback rolling_restart, confidence 0.79). |
| 07:55:08 | REMEDIATE | api-gateway | Executing traffic_reroute on api-gateway. |
| 07:55:17 | REMEDIATE | api-gateway | traffic_reroute succeeded in 9.1s — quarantined api-gateway-6488bc94fb-ln2vs (worst replica by live telemetry (p99=915ms, next worst score 243 vs 915)); traffic now on 2 healthy replica(s). |
| 07:55:21 | VERIFY | api-gateway | api-gateway verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 5ms). |
| 07:55:58 | TEARDOWN | api-gateway | Round teardown for api-gateway: no residual fault found; autoscaler returned to declared bounds. |
| 07:56:08 | RECOVERED | api-gateway | api-gateway recovered: detected in 14.85s, mitigated in 14.49s, fully back to its normal operating band in 45.0s (target 120s — MET). Users saw 0 failed requests out of 1185 (0.0%) during the incident. |

## Round 4 — network_partition → product-service  ·  **RECOVERED**

TTD 9.86s (target 30s, met) · TTM 10.46s · TTR 40.0s (target 90s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-20b)**: Product-service network partition never tried for 432 minutes, high traffic impact, and not used this campaign.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | network_partition | payment-service | 0.48 | 37.5 | mitigated |
| 2 | network_partition | product-service | 0.461 | 432.4 | recovered_within_sla |
| 3 | network_partition | notification-service | 0.38 | never | — |
| 4 | pod_deletion | product-service | 0.36 | 106.5 | recovered_within_sla |
| 5 | pod_deletion | payment-service | 0.331 | 38.6 | recovered_within_sla |
| 6 | pod_deletion | notification-service | 0.276 | 430.8 | recovered_within_sla |
| 7 | network_partition | api-gateway | 0.18 | 105.4 | recovered_within_sla |
| 8 | pod_deletion | order-service | 0.155 | 223.6 | recovered_within_sla |
| 9 | pod_deletion | api-gateway | 0.144 | 53.2 | recovered_within_sla |
| 10 | network_partition | order-service | 0.068 | 52.3 | recovered_within_sla |

### 2. Safety check before injecting

Decision **GO** · risk HIGH · system health 100.0% · target ready 2/2 · load 0.97× baseline · dependents api-gateway, order-service · users possibly affected 100%

### 3. Failure injected

`network_partition` on **product-service** at 07:56:33 UTC — succeeded

Details: `{"policy": "chaos-isolate-product-service", "effect": "deny all ingress + egress", "conntrack_flush": {"ok": true, "pod_ips": ["10.244.0.34", "10.244.0.4"], "agents": {"chaos-agent-l7fcx": true}}}`

### 4. Detection

Confirmed at 07:56:43 UTC on **product-service** as `high_latency` · severity 0.9987 · Isolation Forest score -0.039 (threshold 0.1031) · flags: iforest, zscore:caller_p99_ms, all_replicas_down, metrics_unreachable

Evidence:
- p99_latency_ms=9.94ms vs baseline 16.09ms (z=-0.4)
- caller_p99_ms=1274.98ms vs baseline 16.56ms (z=+25.0)

LSTM 60 s forecast: score -0.0437 (still anomalous)

### 5. Root-cause analysis

Origin **product-service** · type `network_partition` · confidence 0.95 · call path api-gateway → product-service · affected api-gateway, product-service, order-service

> Root cause localised to product-service (network partition, confidence 95%). api-gateway, order-service also deviate as callers of product-service: its failure propagates to them. Change evidence: NetworkPolicy 'chaos-isolate-product-service' denies all Ingress/Egress traffic for pods of product-service, created 15s ago; Pod product-service-78f8dcb767-6dvbl: Unhealthy — Readiness probe failed: Get "http://10.244.0.34:8001/ready": context deadline exceeded (Client.Timeout exceeded while aw.

Evidence:
- p99_latency_ms=9.94ms vs baseline 16.09ms (z=-0.4)
- caller_p99_ms=1274.98ms vs baseline 16.56ms (z=+25.0)
- NetworkPolicy 'chaos-isolate-product-service' denies all Ingress/Egress traffic for pods of product-service, created 15s ago
- Pod product-service-78f8dcb767-6dvbl: Unhealthy — Readiness probe failed: Get "http://10.244.0.34:8001/ready": context deadline exceeded (Client.Timeout exceeded while aw
- Pod product-service-78f8dcb767-94ww2: Unhealthy — Readiness probe failed: Get "http://10.244.0.4:8001/ready": context deadline exceeded (Client.Timeout exceeded while awa

| Candidate | Score | Why |
|---|---|---|
| product-service | 9.098 | severity 1.00; no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service']; earliest onset; structural fault on the service itself; NetworkPolicy 'chaos-isolate-product-service' denies all Ingress/Egress traffic for pods of product-service, created 15s ago; Pod product-service-78f8dcb767-6dvbl: Unhealthy — Readiness probe failed: Get "http://10.244.0.34:8001… |
| order-service | 2.685 | severity 0.96; its dependencies ['product-service'] are also anomalous (likely a victim); explains anomalies in callers ['api-gateway']; earliest onset; 142 ERROR log lines in the last 60s, e.g. 'dependency failure (product-service)' |
| api-gateway | 2.682 | severity 0.97; its dependencies ['product-service', 'order-service'] are also anomalous (likely a victim); earliest onset; 269 ERROR log lines in the last 60s, e.g. 'request failed' |

### 6. Decision

Action **network_policy_rollback** (fallback rolling_restart) · confidence 0.646 · priority 5.993

- product-service: network partition at severity 1.00; business impact 6/10 -> priority 5.99. Playbook: network_policy_rollback, fallback rolling_restart.
- Confidence in network_policy_rollback: 0.65 (history 0.80 over 1 attempt(s) x RCA 0.95 x blast factor 0.85).
- Decision: network_policy_rollback on product-service (fallback rolling_restart, confidence 0.65).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| network_policy_rollback | product-service | success | yes | 4.1s | removed 1 isolating NetworkPolicy(ies): chaos-isolate-product-service |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"policy": "chaos-isolate-product-service", "deleted": false}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 230 failed of 1001 requests (23.0%) · user p99 9562.4 ms over 49 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 07:56:15 | STRATEGY | product-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-20b) chose network_partition on product-service: Product-service network partition never tried for 432 minutes, high traffic impact, and not used this campaign. |
| 07:56:33 | PREFLIGHT | product-service | GO: product-service at 2/2 Ready, system 100% healthy. Blast radius: 2 dependent service(s) ['api-gateway', 'order-service'], ~100% of users, risk HIGH. |
| 07:56:33 | INJECT | product-service | Injected network_partition into product-service: Deny-all NetworkPolicy selecting the service's pods (chaos-isolate-product-service). |
| 07:56:43 | DETECT | product-service | Anomaly confirmed on product-service 10s after injection: pattern matches high latency. Isolation Forest score -0.039 (threshold +0.103), severity 1.00. Evidence: p99_latency_ms=9.94ms vs baseline 16.09ms (z=-0.4); caller_p99_ms=1274.98ms vs baseline 16.56ms (z=+25.0). Also deviating: api-gateway, order-service. LSTM forecast for the next 60s: score -0.044 (still anomalous). |
| 07:56:48 | RCA | product-service | Root cause localised to product-service (network partition, confidence 95%). api-gateway, order-service also deviate as callers of product-service: its failure propagates to them. Change evidence: NetworkPolicy 'chaos-isolate-product-service' denies all Ingress/Egress traffic for pods of product-service, created 15s ago; Pod product-service-78f8dcb767-6dvbl: Unhealthy — Readiness probe failed: Get "http://10.244.0.34:8001/ready": context deadline exceeded (Client.Timeout exceeded while aw. |
| 07:56:48 | DECIDE | product-service | Confidence in network_policy_rollback: 0.65 (history 0.80 over 1 attempt(s) x RCA 0.95 x blast factor 0.85). Decision: network_policy_rollback on product-service (fallback rolling_restart, confidence 0.65). |
| 07:56:48 | REMEDIATE | product-service | Executing network_policy_rollback on product-service. |
| 07:56:52 | REMEDIATE | product-service | network_policy_rollback succeeded in 4.1s — removed 1 isolating NetworkPolicy(ies): chaos-isolate-product-service. |
| 07:56:57 | VERIFY | product-service | product-service verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 5ms). |
| 07:57:33 | TEARDOWN | product-service | Round teardown for product-service: no residual fault found; autoscaler returned to declared bounds. |
| 07:57:43 | RECOVERED | product-service | product-service recovered: detected in 9.86s, mitigated in 10.46s, fully back to its normal operating band in 40.0s (target 90s — MET). Users saw 230 failed requests out of 1001 (23.0%) during the incident. |

## Round 5 — pod_deletion → payment-service  ·  **RECOVERED**

TTD 4.86s (target 25s, met) · TTM 11.33s · TTR 19.99s (target 90s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-20b)**: High impact, high traffic, recent try, and fault type not yet used this campaign.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | pod_deletion | payment-service | 0.333 | 40.2 | recovered_within_sla |
| 2 | pod_deletion | notification-service | 0.276 | 432.4 | recovered_within_sla |
| 3 | pod_deletion | order-service | 0.155 | 225.2 | recovered_within_sla |
| 4 | pod_deletion | api-gateway | 0.145 | 54.8 | recovered_within_sla |
| 5 | pod_deletion | product-service | 0.111 | 108.1 | recovered_within_sla |
| 6 | network_partition | payment-service | 0.082 | 39.1 | mitigated |
| 7 | replica_reduction | payment-service | 0.028 | 219.0 | recovered_within_sla |
| 8 | cpu_throttle | payment-service | -0.017 | 111.7 | recovered_within_sla |
| 9 | cpu_throttle | notification-service | -0.02 | never | — |
| 10 | network_partition | notification-service | -0.02 | never | — |

### 2. Safety check before injecting

Decision **GO** · risk HIGH · system health 100.0% · target ready 2/2 · load 1.1× baseline · dependents api-gateway, order-service · users possibly affected 100%

### 3. Failure injected

`pod_deletion` on **payment-service** at 07:58:08 UTC — succeeded

Details: `{"pod": "payment-service-9cd4c489d-6jdp9", "pod_ip": "10.244.0.43", "ready_pods_before": 2}`

### 4. Detection

Confirmed at 07:58:13 UTC on **payment-service** as `pod_crash` · severity 0.4 · Isolation Forest score 0.1466 (threshold 0.1031) · flags: replicas_lost

Evidence:
- replicas ready 2/2 (declared minimum 2)
- Ready pod(s) payment-service-9cd4c489d-6jdp9 disappeared without a scale-down or rollout
- caller_error_rate=0.0% vs baseline 0.0% (z=+0.0)

LSTM 60 s forecast: score 0.1495 (returning to normal)

### 5. Root-cause analysis

Origin **payment-service** · type `pod_crash` · confidence 0.918 · call path api-gateway → payment-service · affected payment-service

> Root cause localised to payment-service (pod crash, confidence 92%). No other service deviates; the fault is contained to payment-service. Change evidence: Pod payment-service-9cd4c489d-6jdp9: Killing — Stopping container payment-service; Pod payment-service-9cd4c489d-frfw5: Unhealthy — Startup probe failed: Get "http://10.244.0.47:8003/health": dial tcp 10.244.0.47:8003: connect: connection refused.

Evidence:
- replicas ready 2/2 (declared minimum 2)
- Ready pod(s) payment-service-9cd4c489d-6jdp9 disappeared without a scale-down or rollout
- caller_error_rate=0.0% vs baseline 0.0% (z=+0.0)
- Pod payment-service-9cd4c489d-6jdp9: Killing — Stopping container payment-service
- Pod payment-service-9cd4c489d-frfw5: Unhealthy — Startup probe failed: Get "http://10.244.0.47:8003/health": dial tcp 10.244.0.47:8003: connect: connection refused

| Candidate | Score | Why |
|---|---|---|
| payment-service | 3.98 | severity 0.24; no anomalous dependency explains it; earliest onset; structural fault on the service itself; Pod payment-service-9cd4c489d-6jdp9: Killing — Stopping container payment-service; Pod payment-service-9cd4c489d-frfw5: Unhealthy — Startup probe failed: Get "http://10.244.0.47:8003/health": dial tcp 10.244.0.47:8003: connect: connection refused |

### 6. Decision

Action **hpa_scaleout** (fallback rolling_restart) · confidence 0.663 · priority 2.4

- payment-service: pod crash at severity 0.24; business impact 10/10 -> priority 2.40. Playbook: hpa_scaleout, fallback rolling_restart.
- Confidence in hpa_scaleout: 0.66 (history 0.85 over 2 attempt(s) x RCA 0.92 x blast factor 0.85).
- Decision: hpa_scaleout on payment-service (fallback rolling_restart, confidence 0.66).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| hpa_scaleout | payment-service | success | yes | 6.1s | autoscaler 2-4 -> 3-4; 2 -> 3 Ready replicas |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"reversible": false, "note": "Kubernetes reschedules deleted pods by itself"}` · autoscaler `{"from": {"minReplicas": 3, "maxReplicas": 4}, "to": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 0 failed of 479 requests (0.0%) · user p99 243.4 ms over 24 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 07:57:50 | STRATEGY | payment-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-20b) chose pod_deletion on payment-service: High impact, high traffic, recent try, and fault type not yet used this campaign. |
| 07:58:08 | PREFLIGHT | payment-service | GO: payment-service at 2/2 Ready, system 100% healthy. Blast radius: 2 dependent service(s) ['api-gateway', 'order-service'], ~100% of users, risk HIGH. |
| 07:58:08 | INJECT | payment-service | Injected pod_deletion into payment-service: Force-delete one Ready pod (grace period 0) (payment-service-9cd4c489d-6jdp9). |
| 07:58:13 | DETECT | payment-service | Anomaly confirmed on payment-service 5s after injection: pattern matches pod crash. Isolation Forest score +0.147 (threshold +0.103), severity 0.40. Evidence: replicas ready 2/2 (declared minimum 2); Ready pod(s) payment-service-9cd4c489d-6jdp9 disappeared without a scale-down or rollout; caller_error_rate=0.0% vs baseline 0.0% (z=+0.0). LSTM forecast for the next 60s: score +0.149 (returning to normal). |
| 07:58:18 | RCA | payment-service | Root cause localised to payment-service (pod crash, confidence 92%). No other service deviates; the fault is contained to payment-service. Change evidence: Pod payment-service-9cd4c489d-6jdp9: Killing — Stopping container payment-service; Pod payment-service-9cd4c489d-frfw5: Unhealthy — Startup probe failed: Get "http://10.244.0.47:8003/health": dial tcp 10.244.0.47:8003: connect: connection refused. |
| 07:58:18 | DECIDE | payment-service | Confidence in hpa_scaleout: 0.66 (history 0.85 over 2 attempt(s) x RCA 0.92 x blast factor 0.85). Decision: hpa_scaleout on payment-service (fallback rolling_restart, confidence 0.66). |
| 07:58:18 | REMEDIATE | payment-service | Executing hpa_scaleout on payment-service. |
| 07:58:24 | REMEDIATE | payment-service | hpa_scaleout succeeded in 6.1s — autoscaler 2-4 -> 3-4; 2 -> 3 Ready replicas. |
| 07:58:28 | VERIFY | payment-service | payment-service verified functional: 3/3 replicas Ready and 5 consecutive user-path probes OK (last 7ms). |
| 07:58:33 | TEARDOWN | payment-service | Round teardown for payment-service: no residual fault found; autoscaler returned to declared bounds. |
| 07:58:43 | RECOVERED | payment-service | payment-service recovered: detected in 4.86s, mitigated in 11.33s, fully back to its normal operating band in 19.99s (target 90s — MET). Users saw 0 failed requests out of 479 (0.0%) during the incident. |

## Campaign-level events

| Time (UTC) | Phase | Message |
|---|---|---|
| 07:51:36 | CAMPAIGN | Campaign c-20261011-075136-7fdf starting: 5 rounds (auto, auto, auto, auto, auto). |
| 07:58:43 | SUMMARY | Campaign completed: resilience score 98.8/100 — EXCELLENT — every fault detected, diagnosed and healed within SLA. |
