# Incident log — campaign `c-20261011-095621-cefd`

**Resilience score 99.5/100** — EXCELLENT — every fault detected, diagnosed and healed within SLA

| Component | Points |
|---|---|
| recovery sla | 35.0 |
| detection sla | 20.0 |
| remediation effectiveness | 20.0 |
| diagnosis accuracy | 15.0 |
| user protection | 9.52 |

| # | Fault | Target | Status | TTD | TTR | Users failed |
|---|---|---|---|---|---|---|
| 1 | cpu_throttle | payment-service | RECOVERED | 9.85s | 54.99s | 0.0% |
| 2 | replica_reduction | api-gateway | RECOVERED | 4.85s | 14.99s | 0.0% |
| 3 | latency_injection | product-service | RECOVERED | 14.84s | 50.0s | 0.0% |
| 4 | network_partition | order-service | RECOVERED | 9.86s | 40.0s | 12.0% |
| 5 | pod_deletion | product-service | RECOVERED | 4.85s | 20.0s | 0.0% |

## Round 1 — cpu_throttle → payment-service  ·  **RECOVERED**

TTD 9.85s (target 35s, met) · TTM 7.52s · TTR 54.99s (target 90s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-20b)**: High impact payment-service CPU throttle, long since last tried, many dependents, not yet used this campaign.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | cpu_throttle | api-gateway | 0.46 | 169.7 | recovered_within_sla |
| 2 | latency_injection | product-service | 0.442 | 342.8 | recovered_within_sla |
| 3 | replica_reduction | api-gateway | 0.44 | 124.4 | recovered_within_sla |
| 4 | latency_injection | api-gateway | 0.438 | 121.6 | recovered_within_sla |
| 5 | cpu_throttle | payment-service | 0.432 | 230.2 | recovered_within_sla |
| 6 | replica_reduction | order-service | 0.406 | 228.4 | recovered_within_sla |
| 7 | pod_deletion | api-gateway | 0.401 | 61.2 | recovered_within_sla |
| 8 | replica_reduction | product-service | 0.391 | 170.7 | recovered_within_sla |
| 9 | pod_deletion | payment-service | 0.386 | 118.2 | recovered_within_sla |
| 10 | network_partition | order-service | 0.386 | 172.5 | recovered_within_sla |

### 2. Safety check before injecting

Decision **GO** · risk HIGH · system health 100.0% · target ready 2/2 · load 1.1× baseline · dependents api-gateway, order-service · users possibly affected 100%

### 3. Failure injected

`cpu_throttle` on **payment-service** at 09:56:43 UTC — succeeded

Details: `{"pods": ["payment-service-64d79d469d-pj7cf", "payment-service-64d79d469d-rd2rr"], "cpu_limit": "25m", "original": {"payment-service-64d79d469d-pj7cf": {"payment-service": {"requests": {"cpu": "100m", "memory": "96Mi"}, "limits": {"cpu": "500m", "memory": "256Mi"}}}, "payment-service-64d79d469d-rd2rr": {"payment-service": {"requests": {"cpu": "100m", "memory": "96Mi"}, "limits": {"cpu": "500m", "memory": "256Mi"}}}}}`

### 4. Detection

Confirmed at 09:56:53 UTC on **payment-service** as `high_latency` · severity 0.868 · Isolation Forest score 0.0083 (threshold 0.1031) · flags: iforest, zscore:p99_latency_ms, zscore:caller_p99_ms

Evidence:
- p99_latency_ms=811.00ms vs baseline 246.49ms (z=+15.3)
- caller_p99_ms=921.67ms vs baseline 246.52ms (z=+18.3)

LSTM 60 s forecast: score -0.0171 (still anomalous)

### 5. Root-cause analysis

Origin **payment-service** · type `cpu_throttle` · confidence 0.95 · call path api-gateway → payment-service · affected api-gateway, order-service, payment-service

> Root cause localised to payment-service (cpu throttle, confidence 95%). api-gateway, order-service also deviate as callers of payment-service: its failure propagates to them. Change evidence: pod payment-service-64d79d469d-pj7cf CPU limit is 25m vs declared 500m; pod payment-service-64d79d469d-rd2rr CPU limit is 25m vs declared 500m.

Evidence:
- p99_latency_ms=811.00ms vs baseline 246.49ms (z=+15.3)
- caller_p99_ms=921.67ms vs baseline 246.52ms (z=+18.3)
- pod payment-service-64d79d469d-pj7cf CPU limit is 25m vs declared 500m
- pod payment-service-64d79d469d-rd2rr CPU limit is 25m vs declared 500m

| Candidate | Score | Why |
|---|---|---|
| payment-service | 9.117 | severity 0.88; no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service']; earliest onset; pod payment-service-64d79d469d-pj7cf CPU limit is 25m vs declared 500m; pod payment-service-64d79d469d-rd2rr CPU limit is 25m vs declared 500m |
| order-service | 1.286 | severity 0.87; its dependencies ['payment-service'] are also anomalous (likely a victim); explains anomalies in callers ['api-gateway']; earliest onset |
| api-gateway | 0.199 | severity 0.85; its dependencies ['order-service', 'payment-service'] are also anomalous (likely a victim) |

### 6. Decision

Action **resource_restore** (fallback rolling_restart) · confidence 0.686 · priority 8.834

- payment-service: cpu throttle at severity 0.88; business impact 10/10 -> priority 8.83. Playbook: resource_restore, fallback rolling_restart.
- Confidence in resource_restore: 0.69 (history 0.85 over 2 attempt(s) x RCA 0.95 x blast factor 0.85).
- Decision: resource_restore on payment-service (fallback rolling_restart, confidence 0.69).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| resource_restore | payment-service | success | yes | 2.1s | resized 2 container(s) in place to {'payment-service': {'requests': {'cpu': '100m', 'memory': '96Mi'}, 'limits': {'cpu': '500m', 'memory': '256Mi'}}} |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"restored_pods": []}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 0 failed of 1284 requests (0.0%) · user p99 665.6 ms over 64 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 09:56:25 | STRATEGY | payment-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-20b) chose cpu_throttle on payment-service: High impact payment-service CPU throttle, long since last tried, many dependents, not yet used this campaign. |
| 09:56:43 | PREFLIGHT | payment-service | GO: payment-service at 2/2 Ready, system 100% healthy. Blast radius: 2 dependent service(s) ['api-gateway', 'order-service'], ~100% of users, risk HIGH. |
| 09:56:43 | INJECT | payment-service | Injected cpu_throttle into payment-service: In-place resize of every replica's CPU limit to a starvation value (payment-service-64d79d469d-pj7cf,payment-service-64d79d469d-rd2rr). |
| 09:56:53 | DETECT | payment-service | Anomaly confirmed on payment-service 10s after injection: pattern matches high latency. Isolation Forest score +0.008 (threshold +0.103), severity 0.87. Evidence: p99_latency_ms=811.00ms vs baseline 246.49ms (z=+15.3); caller_p99_ms=921.67ms vs baseline 246.52ms (z=+18.3). Also deviating: order-service. LSTM forecast for the next 60s: score -0.017 (still anomalous). |
| 09:56:58 | RCA | payment-service | Root cause localised to payment-service (cpu throttle, confidence 95%). api-gateway, order-service also deviate as callers of payment-service: its failure propagates to them. Change evidence: pod payment-service-64d79d469d-pj7cf CPU limit is 25m vs declared 500m; pod payment-service-64d79d469d-rd2rr CPU limit is 25m vs declared 500m. |
| 09:56:58 | DECIDE | payment-service | Confidence in resource_restore: 0.69 (history 0.85 over 2 attempt(s) x RCA 0.95 x blast factor 0.85). Decision: resource_restore on payment-service (fallback rolling_restart, confidence 0.69). |
| 09:56:58 | REMEDIATE | payment-service | Executing resource_restore on payment-service (step 1, primary). |
| 09:57:00 | REMEDIATE | payment-service | resource_restore succeeded in 2.1s — resized 2 container(s) in place to {'payment-service': {'requests': {'cpu': '100m', 'memory': '96Mi'}, 'limits': {'cpu': '500m', 'memory': '256Mi'}}}. |
| 09:57:04 | VERIFY | payment-service | payment-service verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 7ms). |
| 09:57:58 | TEARDOWN | payment-service | Round teardown for payment-service: no residual fault found; autoscaler returned to declared bounds. |
| 09:58:08 | RECOVERED | payment-service | payment-service recovered: detected in 9.85s, mitigated in 7.52s, fully back to its normal operating band in 54.99s (target 90s — MET). Users saw 0 failed requests out of 1284 (0.0%) during the incident. |

## Round 2 — replica_reduction → api-gateway  ·  **RECOVERED**

TTD 4.85s (target 35s, met) · TTM 10.31s · TTR 14.99s (target 120s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-20b)**: High impact, full traffic, long idle time, and service not yet tested this campaign.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | latency_injection | product-service | 0.443 | 344.6 | recovered_within_sla |
| 2 | replica_reduction | api-gateway | 0.441 | 126.2 | recovered_within_sla |
| 3 | latency_injection | api-gateway | 0.439 | 123.4 | recovered_within_sla |
| 4 | replica_reduction | order-service | 0.407 | 230.2 | recovered_within_sla |
| 5 | pod_deletion | api-gateway | 0.402 | 63.0 | recovered_within_sla |
| 6 | replica_reduction | product-service | 0.391 | 172.6 | recovered_within_sla |
| 7 | network_partition | order-service | 0.387 | 174.3 | recovered_within_sla |
| 8 | latency_injection | order-service | 0.382 | 162.5 | recovered_within_sla |
| 9 | network_partition | notification-service | 0.38 | never | — |
| 10 | network_partition | product-service | 0.368 | 121.7 | recovered_within_sla |

### 2. Safety check before injecting

Decision **GO** · risk MEDIUM · system health 100.0% · target ready 2/2 · load 1.0× baseline · dependents none · users possibly affected 100%

### 3. Failure injected

`replica_reduction` on **api-gateway** at 09:58:33 UTC — succeeded

Details: `{"hpa": "api-gateway-hpa", "original": {"minReplicas": 2, "maxReplicas": 4}, "patched_to": {"minReplicas": 1, "maxReplicas": 1}}`

### 4. Detection

Confirmed at 09:58:38 UTC on **api-gateway** as `replica_exhaustion` · severity 0.8077 · Isolation Forest score 0.0904 (threshold 0.1031) · flags: capacity_below_baseline, metrics_unreachable

Evidence:
- replicas ready 1/1 (declared minimum 2)
- metrics endpoint unreachable on 50% of pods
- autoscaler bounds min=1 max=1 below declared minimum 2

LSTM 60 s forecast: score 0.0785 (returning to normal)

### 5. Root-cause analysis

Origin **api-gateway** · type `replica_exhaustion` · confidence 0.96 · call path api-gateway · affected api-gateway

> Root cause localised to api-gateway (replica exhaustion, confidence 96%). No other service deviates; the fault is contained to api-gateway. Change evidence: HPA bounds 1-1 are below the declared 2-4; Pod api-gateway-6488bc94fb-sm6r5: Killing — Stopping container api-gateway.

Evidence:
- replicas ready 1/1 (declared minimum 2)
- metrics endpoint unreachable on 50% of pods
- autoscaler bounds min=1 max=1 below declared minimum 2
- HPA bounds 1-1 are below the declared 2-4
- Pod api-gateway-6488bc94fb-sm6r5: Killing — Stopping container api-gateway
- Pod api-gateway-6488bc94fb-sm6r5: Unhealthy — Readiness probe failed: Get "http://10.244.0.56:3000/ready": dial tcp 10.244.0.56:3000: connect: connection refused

| Candidate | Score | Why |
|---|---|---|
| api-gateway | 7.628 | severity 0.81; no anomalous dependency explains it; earliest onset; structural fault on the service itself; HPA bounds 1-1 are below the declared 2-4; Pod api-gateway-6488bc94fb-sm6r5: Killing — Stopping container api-gateway; Pod api-gateway-6488bc94fb-sm6r5: Unhealthy — Readiness probe failed: Get "http://10.244.0.56:3000/ready": dial tcp 10.244.0.56:3000: connect: connection refused |

### 6. Decision

Action **hpa_scaleout** (fallback resource_restore) · confidence 0.845 · priority 7.324

- api-gateway: replica exhaustion at severity 0.81; business impact 9/10 -> priority 7.32. Playbook: hpa_scaleout, fallback resource_restore.
- Confidence in hpa_scaleout: 0.84 (history 0.88 over 3 attempt(s) x RCA 0.96 x blast factor 1.00).
- Decision: hpa_scaleout on api-gateway (fallback resource_restore, confidence 0.84).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| hpa_scaleout | api-gateway | success | yes | 4.1s | autoscaler 1-1 -> 3-4; 1 -> 3 Ready replicas |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"restored": false, "note": "autoscaler already at or above declared bounds"}` · autoscaler `{"from": {"minReplicas": 3, "maxReplicas": 4}, "to": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 0 failed of 379 requests (0.0%) · user p99 243.0 ms over 19 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 09:58:15 | STRATEGY | api-gateway | Chaos Planner — LLM agent (groq/openai/gpt-oss-20b) chose replica_reduction on api-gateway: High impact, full traffic, long idle time, and service not yet tested this campaign. |
| 09:58:33 | PREFLIGHT | api-gateway | GO: api-gateway at 2/2 Ready, system 100% healthy. Blast radius: 0 dependent service(s) , ~100% of users, risk MEDIUM. |
| 09:58:33 | INJECT | api-gateway | Injected replica_reduction into api-gateway: Clamp HPA to min=max=1 (api-gateway-hpa). |
| 09:58:38 | DETECT | api-gateway | Anomaly confirmed on api-gateway 5s after injection: pattern matches replica exhaustion. Isolation Forest score +0.090 (threshold +0.103), severity 0.81. Evidence: replicas ready 1/1 (declared minimum 2); metrics endpoint unreachable on 50% of pods; autoscaler bounds min=1 max=1 below declared minimum 2. LSTM forecast for the next 60s: score +0.079 (returning to normal). |
| 09:58:43 | RCA | api-gateway | Root cause localised to api-gateway (replica exhaustion, confidence 96%). No other service deviates; the fault is contained to api-gateway. Change evidence: HPA bounds 1-1 are below the declared 2-4; Pod api-gateway-6488bc94fb-sm6r5: Killing — Stopping container api-gateway. |
| 09:58:43 | DECIDE | api-gateway | Confidence in hpa_scaleout: 0.84 (history 0.88 over 3 attempt(s) x RCA 0.96 x blast factor 1.00). Decision: hpa_scaleout on api-gateway (fallback resource_restore, confidence 0.84). |
| 09:58:43 | REMEDIATE | api-gateway | Executing hpa_scaleout on api-gateway (step 1, primary). |
| 09:58:47 | REMEDIATE | api-gateway | hpa_scaleout succeeded in 4.1s — autoscaler 1-1 -> 3-4; 1 -> 3 Ready replicas. |
| 09:58:52 | VERIFY | api-gateway | api-gateway verified functional: 3/3 replicas Ready and 5 consecutive user-path probes OK (last 6ms). |
| 09:59:03 | TEARDOWN | api-gateway | Round teardown for api-gateway: no residual fault found; autoscaler returned to declared bounds. |
| 09:59:13 | RECOVERED | api-gateway | api-gateway recovered: detected in 4.85s, mitigated in 10.31s, fully back to its normal operating band in 14.99s (target 120s — MET). Users saw 0 failed requests out of 379 (0.0%) during the incident. |

## Round 3 — latency_injection → product-service  ·  **RECOVERED**

TTD 14.84s (target 35s, met) · TTM 17.56s · TTR 50.0s (target 120s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-20b)**: Long-untried latency on high-traffic product-service, many dependents, high impact, maximises learning.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | latency_injection | product-service | 0.443 | 345.7 | recovered_within_sla |
| 2 | network_partition | order-service | 0.387 | 175.4 | recovered_within_sla |
| 3 | latency_injection | order-service | 0.383 | 163.6 | recovered_within_sla |
| 4 | network_partition | notification-service | 0.38 | never | — |
| 5 | network_partition | product-service | 0.369 | 122.7 | recovered_within_sla |
| 6 | pod_deletion | order-service | 0.327 | 63.2 | recovered_within_sla |
| 7 | pod_deletion | notification-service | 0.297 | 553.9 | recovered_within_sla |
| 8 | pod_deletion | product-service | 0.274 | 5.7 | recovered_within_sla |
| 9 | latency_injection | api-gateway | 0.19 | 124.5 | recovered_within_sla |
| 10 | pod_deletion | api-gateway | 0.153 | 64.1 | recovered_within_sla |

### 2. Safety check before injecting

Decision **GO** · risk HIGH · system health 100.0% · target ready 2/2 · load 0.94× baseline · dependents api-gateway, order-service · users possibly affected 100%

### 3. Failure injected

`latency_injection` on **product-service** at 09:59:38 UTC — succeeded

Details: `{"pod": "product-service-78f8dcb767-6dvbl", "delay": "200ms", "jitter": "50ms", "command": "tc qdisc replace dev eth0 root netem delay 200ms 50ms distribution normal", "replicas_ready": 2}`

### 4. Detection

Confirmed at 09:59:53 UTC on **product-service** as `high_latency` · severity 0.935 · Isolation Forest score -0.0345 (threshold 0.1031) · flags: iforest, zscore:p99_latency_ms, zscore:caller_p99_ms

Evidence:
- p99_latency_ms=642.48ms vs baseline 16.09ms (z=+25.0)
- caller_p99_ms=23.77ms vs baseline 16.56ms (z=+0.5)

LSTM 60 s forecast: score -0.0429 (still anomalous)

### 5. Root-cause analysis

Origin **product-service** · type `high_latency` · confidence 0.923 · call path api-gateway → product-service · affected api-gateway, product-service

> Root cause localised to product-service (high latency, confidence 92%). api-gateway also deviate as callers of product-service: its failure propagates to them. Signal: p99_latency_ms=642.48ms vs baseline 16.09ms (z=+25.0); caller_p99_ms=23.77ms vs baseline 16.56ms (z=+0.5).

Evidence:
- p99_latency_ms=642.48ms vs baseline 16.09ms (z=+25.0)
- caller_p99_ms=23.77ms vs baseline 16.56ms (z=+0.5)

| Candidate | Score | Why |
|---|---|---|
| product-service | 3.919 | severity 0.93; no anomalous dependency explains it; explains anomalies in callers ['api-gateway']; earliest onset |
| api-gateway | 1.117 | severity 0.93; its dependencies ['product-service'] are also anomalous (likely a victim); earliest onset |

### 6. Decision

Action **traffic_reroute** (fallback rolling_restart) · confidence 0.69 · priority 5.606

- product-service: high latency at severity 0.93; business impact 6/10 -> priority 5.61. Playbook: traffic_reroute, fallback rolling_restart.
- Confidence in traffic_reroute: 0.69 (history 0.88 over 3 attempt(s) x RCA 0.92 x blast factor 0.85).
- Decision: traffic_reroute on product-service (fallback rolling_restart, confidence 0.69).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| traffic_reroute | product-service | success | yes | 11.2s | quarantined product-service-78f8dcb767-6dvbl (worst replica by live telemetry (p99=2405ms, next worst score 15 vs 2405)); traffic now on 2 healthy replica(s) |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"pod": "product-service-78f8dcb767-6dvbl", "note": "pod no longer exists (replaced)"}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 0 failed of 1281 requests (0.0%) · user p99 2049.6 ms over 64 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 09:59:21 | STRATEGY | product-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-20b) chose latency_injection on product-service: Long-untried latency on high-traffic product-service, many dependents, high impact, maximises learning. |
| 09:59:38 | PREFLIGHT | product-service | GO: product-service at 2/2 Ready, system 100% healthy. Blast radius: 2 dependent service(s) ['api-gateway', 'order-service'], ~100% of users, risk HIGH. |
| 09:59:38 | INJECT | product-service | Injected latency_injection into product-service: tc netem egress delay on one replica (product-service-78f8dcb767-6dvbl). |
| 09:59:53 | DETECT | product-service | Anomaly confirmed on product-service 15s after injection: pattern matches high latency. Isolation Forest score -0.035 (threshold +0.103), severity 0.94. Evidence: p99_latency_ms=642.48ms vs baseline 16.09ms (z=+25.0); caller_p99_ms=23.77ms vs baseline 16.56ms (z=+0.5). LSTM forecast for the next 60s: score -0.043 (still anomalous). |
| 09:59:58 | RCA | product-service | Root cause localised to product-service (high latency, confidence 92%). api-gateway also deviate as callers of product-service: its failure propagates to them. Signal: p99_latency_ms=642.48ms vs baseline 16.09ms (z=+25.0); caller_p99_ms=23.77ms vs baseline 16.56ms (z=+0.5). |
| 09:59:58 | DECIDE | product-service | Confidence in traffic_reroute: 0.69 (history 0.88 over 3 attempt(s) x RCA 0.92 x blast factor 0.85). Decision: traffic_reroute on product-service (fallback rolling_restart, confidence 0.69). |
| 09:59:58 | REMEDIATE | product-service | Executing traffic_reroute on product-service (step 1, primary). |
| 10:00:09 | REMEDIATE | product-service | traffic_reroute succeeded in 11.2s — quarantined product-service-78f8dcb767-6dvbl (worst replica by live telemetry (p99=2405ms, next worst score 15 vs 2405)); traffic now on 2 healthy replica(s). |
| 10:00:14 | VERIFY | product-service | product-service verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 4ms). |
| 10:00:53 | TEARDOWN | product-service | Round teardown for product-service: no residual fault found; autoscaler returned to declared bounds. |
| 10:01:03 | RECOVERED | product-service | product-service recovered: detected in 14.84s, mitigated in 17.56s, fully back to its normal operating band in 50.0s (target 120s — MET). Users saw 0 failed requests out of 1281 (0.0%) during the incident. |

## Round 4 — network_partition → order-service  ·  **RECOVERED**

TTD 9.86s (target 30s, met) · TTM 10.46s · TTR 40.0s (target 90s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-20b)**: Order-service network partition is high impact, high traffic, and hasn't been tried for 177 minutes, providing fresh insight into resilience.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | network_partition | order-service | 0.388 | 177.2 | recovered_within_sla |
| 2 | network_partition | notification-service | 0.38 | never | — |
| 3 | pod_deletion | order-service | 0.328 | 65.0 | recovered_within_sla |
| 4 | pod_deletion | notification-service | 0.297 | 555.7 | recovered_within_sla |
| 5 | pod_deletion | api-gateway | 0.154 | 65.9 | recovered_within_sla |
| 6 | pod_deletion | payment-service | 0.139 | 123.0 | recovered_within_sla |
| 7 | network_partition | product-service | 0.12 | 124.6 | recovered_within_sla |
| 8 | network_partition | payment-service | 0.107 | 70.0 | recovered_within_sla |
| 9 | network_partition | api-gateway | 0.104 | 13.3 | recovered_within_sla |
| 10 | pod_deletion | product-service | 0.026 | 7.6 | recovered_within_sla |

### 2. Safety check before injecting

Decision **GO** · risk MEDIUM · system health 100.0% · target ready 2/2 · load 1.01× baseline · dependents api-gateway · users possibly affected 100%

### 3. Failure injected

`network_partition` on **order-service** at 10:01:28 UTC — succeeded

Details: `{"policy": "chaos-isolate-order-service", "effect": "deny all ingress + egress", "conntrack_flush": {"ok": true, "pod_ips": ["10.244.0.61", "10.244.0.60"], "agents": {"chaos-agent-l7fcx": true}}}`

### 4. Detection

Confirmed at 10:01:38 UTC on **order-service** as `network_partition` · severity 0.9864 · Isolation Forest score 0.026 (threshold 0.1031) · flags: iforest, zscore:caller_p99_ms, replicas_lost, metrics_unreachable

Evidence:
- replicas ready 1/2 (declared minimum 2)
- metrics endpoint unreachable on 100% of pods
- caller_error_rate=1.7% vs baseline 0.0% (z=+0.9)
- request_rate=6.28 req/s vs baseline 8.08 req/s (z=-2.2)
- pods are running (no container restarts) but cannot be reached over the pod network

LSTM 60 s forecast: score 0.0331 (still anomalous)

### 5. Root-cause analysis

Origin **order-service** · type `network_partition` · confidence 0.95 · call path api-gateway → order-service · affected api-gateway, order-service, notification-service, payment-service

> Root cause localised to order-service (network partition, confidence 95%). api-gateway also deviate as callers of order-service: its failure propagates to them. payment-service deviate because requests from order-service stopped reaching them. notification-service also deviate without a dependency explaining it (lower-ranked candidates). Change evidence: NetworkPolicy 'chaos-isolate-order-service' denies all Ingress/Egress traffic for pods of order-service, created 15s ago; 4 ERROR log lines in the last 60s, e.g. 'dependency failure (product-service)'.

Evidence:
- replicas ready 1/2 (declared minimum 2)
- metrics endpoint unreachable on 100% of pods
- caller_error_rate=1.7% vs baseline 0.0% (z=+0.9)
- request_rate=6.28 req/s vs baseline 8.08 req/s (z=-2.2)
- pods are running (no container restarts) but cannot be reached over the pod network
- NetworkPolicy 'chaos-isolate-order-service' denies all Ingress/Egress traffic for pods of order-service, created 15s ago
- Pod order-service-6c97d984dc-8c2p8: Unhealthy — Readiness probe failed: Get "http://10.244.0.61:8002/ready": context deadline exceeded (Client.Timeout exceeded while aw
- Pod order-service-6c97d984dc-lx58g: Unhealthy — Readiness probe failed: Get "http://10.244.0.60:8002/ready": context deadline exceeded (Client.Timeout exceeded while aw
- 4 ERROR log lines in the last 60s, e.g. 'dependency failure (product-service)'

| Candidate | Score | Why |
|---|---|---|
| order-service | 9.317 | severity 1.00; no anomalous dependency explains it; explains anomalies in callers ['api-gateway']; earliest onset; structural fault on the service itself; NetworkPolicy 'chaos-isolate-order-service' denies all Ingress/Egress traffic for pods of order-service, created 15s ago; Pod order-service-6c97d984dc-8c2p8: Unhealthy — Readiness probe failed: Get "http://10.244.0.61:8002/ready": context deadli… |
| api-gateway | 2.653 | severity 0.97; its dependencies ['order-service'] are also anomalous (likely a victim); earliest onset; 192 ERROR log lines in the last 60s, e.g. 'request failed' |
| notification-service | 1.935 | severity 0.44; only symptom is reduced traffic — consistent with an upstream failure; no anomalous dependency explains it; explains anomalies in callers ['api-gateway']; earliest onset |
| payment-service | 0.798 | severity 0.10; only symptom is reduced traffic — consistent with an upstream failure; no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service'] |

### 6. Decision

Action **network_policy_rollback** (fallback rolling_restart) · confidence 0.747 · priority 7.99

- order-service: network partition at severity 1.00; business impact 8/10 -> priority 7.99. Playbook: network_policy_rollback, fallback rolling_restart.
- Confidence in network_policy_rollback: 0.75 (history 0.85 over 2 attempt(s) x RCA 0.95 x blast factor 0.93).
- Decision: network_policy_rollback on order-service (fallback rolling_restart, confidence 0.75).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| network_policy_rollback | order-service | success | yes | 4.1s | removed 1 isolating NetworkPolicy(ies): chaos-isolate-order-service |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"policy": "chaos-isolate-order-service", "deleted": false}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 119 failed of 990 requests (12.0%) · user p99 9489.3 ms over 49 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 10:01:10 | STRATEGY | order-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-20b) chose network_partition on order-service: Order-service network partition is high impact, high traffic, and hasn't been tried for 177 minutes, providing fresh insight into resilience. |
| 10:01:28 | PREFLIGHT | order-service | GO: order-service at 2/2 Ready, system 100% healthy. Blast radius: 1 dependent service(s) ['api-gateway'], ~100% of users, risk MEDIUM. |
| 10:01:28 | INJECT | order-service | Injected network_partition into order-service: Deny-all NetworkPolicy selecting the service's pods (chaos-isolate-order-service). |
| 10:01:38 | DETECT | order-service | Anomaly confirmed on order-service 10s after injection: pattern matches network partition. Isolation Forest score +0.026 (threshold +0.103), severity 0.99. Evidence: replicas ready 1/2 (declared minimum 2); metrics endpoint unreachable on 100% of pods; caller_error_rate=1.7% vs baseline 0.0% (z=+0.9). LSTM forecast for the next 60s: score +0.033 (still anomalous). |
| 10:01:43 | RCA | order-service | Root cause localised to order-service (network partition, confidence 95%). api-gateway also deviate as callers of order-service: its failure propagates to them. payment-service deviate because requests from order-service stopped reaching them. notification-service also deviate without a dependency explaining it (lower-ranked candidates). Change evidence: NetworkPolicy 'chaos-isolate-order-service' denies all Ingress/Egress traffic for pods of order-service, created 15s ago; 4 ERROR log lines in the last 60s, e.g. 'dependency failure (product-service)'. |
| 10:01:43 | DECIDE | order-service | Confidence in network_policy_rollback: 0.75 (history 0.85 over 2 attempt(s) x RCA 0.95 x blast factor 0.93). Decision: network_policy_rollback on order-service (fallback rolling_restart, confidence 0.75). |
| 10:01:43 | REMEDIATE | order-service | Executing network_policy_rollback on order-service (step 1, primary). |
| 10:01:47 | REMEDIATE | order-service | network_policy_rollback succeeded in 4.1s — removed 1 isolating NetworkPolicy(ies): chaos-isolate-order-service. |
| 10:01:52 | VERIFY | order-service | order-service verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 6ms). |
| 10:02:28 | TEARDOWN | order-service | Round teardown for order-service: no residual fault found; autoscaler returned to declared bounds. |
| 10:02:38 | RECOVERED | order-service | order-service recovered: detected in 9.86s, mitigated in 10.46s, fully back to its normal operating band in 40.0s (target 90s — MET). Users saw 119 failed requests out of 990 (12.0%) during the incident. |

## Round 5 — pod_deletion → product-service  ·  **RECOVERED**

TTD 4.85s (target 25s, met) · TTM 11.33s · TTR 20.0s (target 90s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-20b)**: High traffic product-service, recently tried, offers fresh insight into pod deletion resilience.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | pod_deletion | notification-service | 0.297 | 557.3 | recovered_within_sla |
| 2 | pod_deletion | api-gateway | 0.155 | 67.5 | recovered_within_sla |
| 3 | pod_deletion | payment-service | 0.14 | 124.6 | recovered_within_sla |
| 4 | pod_deletion | order-service | 0.08 | 66.6 | recovered_within_sla |
| 5 | pod_deletion | product-service | 0.028 | 9.2 | recovered_within_sla |
| 6 | network_partition | notification-service | -0.02 | never | — |
| 7 | cpu_throttle | notification-service | -0.152 | 13.2 | undetected |
| 8 | cpu_throttle | api-gateway | -0.187 | 176.1 | recovered_within_sla |
| 9 | latency_injection | api-gateway | -0.209 | 127.9 | recovered_within_sla |
| 10 | replica_reduction | order-service | -0.242 | 234.7 | recovered_within_sla |

### 2. Safety check before injecting

Decision **GO** · risk HIGH · system health 100.0% · target ready 2/2 · load 1.02× baseline · dependents api-gateway, order-service · users possibly affected 100%

### 3. Failure injected

`pod_deletion` on **product-service** at 10:03:03 UTC — succeeded

Details: `{"pod": "product-service-78f8dcb767-g7zks", "pod_ip": "10.244.0.69", "ready_pods_before": 2}`

### 4. Detection

Confirmed at 10:03:08 UTC on **product-service** as `pod_crash` · severity 0.4171 · Isolation Forest score 0.0936 (threshold 0.1031) · flags: replicas_lost

Evidence:
- replicas ready 2/2 (declared minimum 2)
- Ready pod(s) product-service-78f8dcb767-g7zks disappeared without a scale-down or rollout
- caller_error_rate=0.0% vs baseline 0.0% (z=+0.0)

LSTM 60 s forecast: score 0.0793 (returning to normal)

### 5. Root-cause analysis

Origin **product-service** · type `pod_crash` · confidence 0.92 · call path api-gateway → product-service · affected product-service

> Root cause localised to product-service (pod crash, confidence 92%). No other service deviates; the fault is contained to product-service. Change evidence: Pod product-service-78f8dcb767-g7zks: Killing — Stopping container product-service; Pod product-service-78f8dcb767-zl555: Unhealthy — Startup probe failed: Get "http://10.244.0.70:8001/health": dial tcp 10.244.0.70:8001: connect: connection refused.

Evidence:
- replicas ready 2/2 (declared minimum 2)
- Ready pod(s) product-service-78f8dcb767-g7zks disappeared without a scale-down or rollout
- caller_error_rate=0.0% vs baseline 0.0% (z=+0.0)
- Pod product-service-78f8dcb767-g7zks: Killing — Stopping container product-service
- Pod product-service-78f8dcb767-zl555: Unhealthy — Startup probe failed: Get "http://10.244.0.70:8001/health": dial tcp 10.244.0.70:8001: connect: connection refused

| Candidate | Score | Why |
|---|---|---|
| product-service | 4.001 | severity 0.25; no anomalous dependency explains it; earliest onset; structural fault on the service itself; Pod product-service-78f8dcb767-g7zks: Killing — Stopping container product-service; Pod product-service-78f8dcb767-zl555: Unhealthy — Startup probe failed: Get "http://10.244.0.70:8001/health": dial tcp 10.244.0.70:8001: connect: connection refused |

### 6. Decision

Action **hpa_scaleout** (fallback rolling_restart) · confidence 0.665 · priority 1.502

- product-service: pod crash at severity 0.25; business impact 6/10 -> priority 1.50. Playbook: hpa_scaleout, fallback rolling_restart.
- Confidence in hpa_scaleout: 0.67 (history 0.85 over 2 attempt(s) x RCA 0.92 x blast factor 0.85).
- Decision: hpa_scaleout on product-service (fallback rolling_restart, confidence 0.67).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| hpa_scaleout | product-service | success | yes | 6.1s | autoscaler 2-4 -> 3-4; 2 -> 3 Ready replicas |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"reversible": false, "note": "Kubernetes reschedules deleted pods by itself"}` · autoscaler `{"from": {"minReplicas": 3, "maxReplicas": 4}, "to": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 0 failed of 480 requests (0.0%) · user p99 242.1 ms over 24 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 10:02:47 | STRATEGY | product-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-20b) chose pod_deletion on product-service: High traffic product-service, recently tried, offers fresh insight into pod deletion resilience. |
| 10:03:03 | PREFLIGHT | product-service | GO: product-service at 2/2 Ready, system 100% healthy. Blast radius: 2 dependent service(s) ['api-gateway', 'order-service'], ~100% of users, risk HIGH. |
| 10:03:03 | INJECT | product-service | Injected pod_deletion into product-service: Force-delete one Ready pod (grace period 0) (product-service-78f8dcb767-g7zks). |
| 10:03:08 | DETECT | product-service | Anomaly confirmed on product-service 5s after injection: pattern matches pod crash. Isolation Forest score +0.094 (threshold +0.103), severity 0.42. Evidence: replicas ready 2/2 (declared minimum 2); Ready pod(s) product-service-78f8dcb767-g7zks disappeared without a scale-down or rollout; caller_error_rate=0.0% vs baseline 0.0% (z=+0.0). LSTM forecast for the next 60s: score +0.079 (returning to normal). |
| 10:03:13 | RCA | product-service | Root cause localised to product-service (pod crash, confidence 92%). No other service deviates; the fault is contained to product-service. Change evidence: Pod product-service-78f8dcb767-g7zks: Killing — Stopping container product-service; Pod product-service-78f8dcb767-zl555: Unhealthy — Startup probe failed: Get "http://10.244.0.70:8001/health": dial tcp 10.244.0.70:8001: connect: connection refused. |
| 10:03:13 | DECIDE | product-service | Confidence in hpa_scaleout: 0.67 (history 0.85 over 2 attempt(s) x RCA 0.92 x blast factor 0.85). Decision: hpa_scaleout on product-service (fallback rolling_restart, confidence 0.67). |
| 10:03:13 | REMEDIATE | product-service | Executing hpa_scaleout on product-service (step 1, primary). |
| 10:03:19 | REMEDIATE | product-service | hpa_scaleout succeeded in 6.1s — autoscaler 2-4 -> 3-4; 2 -> 3 Ready replicas. |
| 10:03:23 | VERIFY | product-service | product-service verified functional: 3/3 replicas Ready and 5 consecutive user-path probes OK (last 7ms). |
| 10:03:28 | TEARDOWN | product-service | Round teardown for product-service: no residual fault found; autoscaler returned to declared bounds. |
| 10:03:38 | RECOVERED | product-service | product-service recovered: detected in 4.85s, mitigated in 11.33s, fully back to its normal operating band in 20.0s (target 90s — MET). Users saw 0 failed requests out of 480 (0.0%) during the incident. |

## Campaign-level events

| Time (UTC) | Phase | Message |
|---|---|---|
| 09:56:21 | CAMPAIGN | Campaign c-20261011-095621-cefd starting: 5 rounds (auto, auto, auto, auto, auto). |
| 10:03:38 | SUMMARY | Campaign completed: resilience score 99.5/100 — EXCELLENT — every fault detected, diagnosed and healed within SLA. |
