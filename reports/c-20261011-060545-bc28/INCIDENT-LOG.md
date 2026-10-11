# Incident log — campaign `c-20261011-060545-bc28`

**Resilience score 80.6/100** — GOOD — reliable recovery with minor SLA or diagnosis misses

| Component | Points |
|---|---|
| recovery sla | 28.0 |
| detection sla | 16.0 |
| remediation effectiveness | 16.0 |
| diagnosis accuracy | 12.0 |
| user protection | 8.62 |

| # | Fault | Target | Status | TTD | TTR | Users failed |
|---|---|---|---|---|---|---|
| 1 | cpu_throttle | payment-service | RECOVERED | 9.84s | 54.99s | 0.4% |
| 2 | replica_reduction | order-service | RECOVERED | 4.81s | 55.0s | 0.0% |
| 3 | pod_deletion | product-service | RECOVERED | 4.8s | 19.99s | 0.0% |
| 4 | network_partition | api-gateway | RECOVERED | 14.83s | 39.99s | 34.2% |
| 5 | latency_injection | notification-service | UNDETECTED | — | — | 0.0% |

## Round 1 — cpu_throttle → payment-service  ·  **RECOVERED**

TTD 9.84s (target 35s, met) · TTM 7.63s · TTR 54.99s (target 90s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: High‑impact CPU throttling on payment-service, never tried recently and only once before, maximises learning about critical service resilience while adding fault type variety.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | latency_injection | order-service | 0.587 | 339.1 | mitigated |
| 2 | pod_deletion | product-service | 0.565 | never | — |
| 3 | replica_reduction | order-service | 0.56 | never | — |
| 4 | network_partition | api-gateway | 0.512 | 341.7 | recovered_within_sla |
| 5 | pod_deletion | api-gateway | 0.512 | 340.0 | recovered_within_sla |
| 6 | replica_reduction | api-gateway | 0.504 | 306.6 | recovered_within_sla |
| 7 | latency_injection | api-gateway | 0.503 | 305.6 | recovered_within_sla |
| 8 | cpu_throttle | payment-service | 0.463 | 343.5 | recovered_within_sla |
| 9 | latency_injection | payment-service | 0.459 | 326.6 | recovered_within_sla |
| 10 | pod_deletion | payment-service | 0.454 | 307.6 | recovered_within_sla |

### 2. Safety check before injecting

Decision **GO** · risk HIGH · system health 100.0% · target ready 2/2 · load 0.95× baseline · dependents api-gateway, order-service · users possibly affected 100%

### 3. Failure injected

`cpu_throttle` on **payment-service** at 06:06:08 UTC — succeeded

Details: `{"pods": ["payment-service-7745b65785-hmgd7", "payment-service-7745b65785-kt8nc"], "cpu_limit": "25m", "original": {"payment-service-7745b65785-hmgd7": {"payment-service": {"requests": {"cpu": "100m", "memory": "96Mi"}, "limits": {"cpu": "500m", "memory": "256Mi"}}}, "payment-service-7745b65785-kt8nc": {"payment-service": {"requests": {"cpu": "100m", "memory": "96Mi"}, "limits": {"cpu": "500m", "memory": "256Mi"}}}}}`

### 4. Detection

Confirmed at 06:06:18 UTC on **payment-service** as `high_latency` · severity 0.9462 · Isolation Forest score -0.0681 (threshold 0.1031) · flags: iforest, zscore:p99_latency_ms, zscore:inflight, zscore:caller_p99_ms

Evidence:
- p99_latency_ms=392.70ms vs baseline 246.49ms (z=+4.0)
- caller_p99_ms=933.75ms vs baseline 246.52ms (z=+18.6)

LSTM 60 s forecast: score -0.063 (still anomalous)

### 5. Root-cause analysis

Origin **payment-service** · type `cpu_throttle` · confidence 0.95 · call path api-gateway → payment-service · affected api-gateway, order-service, payment-service

> Root cause localised to payment-service (cpu throttle, confidence 95%). api-gateway, order-service also deviate as callers of payment-service: its failure propagates to them. Change evidence: pod payment-service-7745b65785-hmgd7 CPU limit is 25m vs declared 500m; pod payment-service-7745b65785-kt8nc CPU limit is 25m vs declared 500m.

Evidence:
- p99_latency_ms=392.70ms vs baseline 246.49ms (z=+4.0)
- caller_p99_ms=933.75ms vs baseline 246.52ms (z=+18.6)
- pod payment-service-7745b65785-hmgd7 CPU limit is 25m vs declared 500m
- pod payment-service-7745b65785-kt8nc CPU limit is 25m vs declared 500m

| Candidate | Score | Why |
|---|---|---|
| payment-service | 9.268 | severity 0.96; no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service']; earliest onset; pod payment-service-7745b65785-hmgd7 CPU limit is 25m vs declared 500m; pod payment-service-7745b65785-kt8nc CPU limit is 25m vs declared 500m |
| order-service | 2.059 | severity 0.95; its dependencies ['payment-service'] are also anomalous (likely a victim); explains anomalies in callers ['api-gateway']; earliest onset; 22 ERROR log lines in the last 60s, e.g. 'dependency failure (payment-service)' |
| api-gateway | 1.682 | severity 0.94; its dependencies ['order-service', 'payment-service'] are also anomalous (likely a victim); earliest onset; 11 ERROR log lines in the last 60s, e.g. 'request failed' |

### 6. Decision

Action **resource_restore** (fallback rolling_restart) · confidence 0.646 · priority 9.59

- payment-service: cpu throttle at severity 0.96; business impact 10/10 -> priority 9.59. Playbook: resource_restore, fallback rolling_restart.
- Confidence in resource_restore: 0.65 (history 0.80 over 1 attempt(s) x RCA 0.95 x blast factor 0.85).
- Decision: resource_restore on payment-service (fallback rolling_restart, confidence 0.65).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| resource_restore | payment-service | success | yes | 2.1s | resized 2 container(s) in place to {'payment-service': {'requests': {'cpu': '100m', 'memory': '96Mi'}, 'limits': {'cpu': '500m', 'memory': '256Mi'}}} |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"restored_pods": []}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 5 failed of 1289 requests (0.4%) · user p99 4303.1 ms over 64 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 06:05:50 | STRATEGY | payment-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose cpu_throttle on payment-service: High‑impact CPU throttling on payment-service, never tried recently and only once before, maximises learning about critical service resilience while adding fault type variety. |
| 06:06:08 | PREFLIGHT | payment-service | GO: payment-service at 2/2 Ready, system 100% healthy. Blast radius: 2 dependent service(s) ['api-gateway', 'order-service'], ~100% of users, risk HIGH. |
| 06:06:08 | INJECT | payment-service | Injected cpu_throttle into payment-service: In-place resize of every replica's CPU limit to a starvation value (payment-service-7745b65785-hmgd7,payment-service-7745b65785-kt8nc). |
| 06:06:18 | DETECT | payment-service | Anomaly confirmed on payment-service 10s after injection: pattern matches high latency. Isolation Forest score -0.068 (threshold +0.103), severity 0.95. Evidence: p99_latency_ms=392.70ms vs baseline 246.49ms (z=+4.0); caller_p99_ms=933.75ms vs baseline 246.52ms (z=+18.6). Also deviating: api-gateway, order-service. LSTM forecast for the next 60s: score -0.063 (still anomalous). |
| 06:06:23 | RCA | payment-service | Root cause localised to payment-service (cpu throttle, confidence 95%). api-gateway, order-service also deviate as callers of payment-service: its failure propagates to them. Change evidence: pod payment-service-7745b65785-hmgd7 CPU limit is 25m vs declared 500m; pod payment-service-7745b65785-kt8nc CPU limit is 25m vs declared 500m. |
| 06:06:23 | DECIDE | payment-service | Confidence in resource_restore: 0.65 (history 0.80 over 1 attempt(s) x RCA 0.95 x blast factor 0.85). Decision: resource_restore on payment-service (fallback rolling_restart, confidence 0.65). |
| 06:06:23 | REMEDIATE | payment-service | Executing resource_restore on payment-service. |
| 06:06:25 | REMEDIATE | payment-service | resource_restore succeeded in 2.1s — resized 2 container(s) in place to {'payment-service': {'requests': {'cpu': '100m', 'memory': '96Mi'}, 'limits': {'cpu': '500m', 'memory': '256Mi'}}}. |
| 06:06:30 | VERIFY | payment-service | payment-service verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 6ms). |
| 06:07:23 | TEARDOWN | payment-service | Round teardown for payment-service: no residual fault found; autoscaler returned to declared bounds. |
| 06:07:33 | RECOVERED | payment-service | payment-service recovered: detected in 9.84s, mitigated in 7.63s, fully back to its normal operating band in 54.99s (target 90s — MET). Users saw 5 failed requests out of 1289 (0.4%) during the incident. |

## Round 2 — replica_reduction → order-service  ·  **RECOVERED**

TTD 4.81s (target 35s, met) · TTM 15.44s · TTR 55.0s (target 120s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: New fault on high‑impact order-service with no prior trials, affecting critical dependents and maximizing insight into resilience.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | latency_injection | order-service | 0.587 | 341.0 | mitigated |
| 2 | pod_deletion | product-service | 0.565 | never | — |
| 3 | replica_reduction | order-service | 0.56 | never | — |
| 4 | network_partition | api-gateway | 0.513 | 343.5 | recovered_within_sla |
| 5 | pod_deletion | api-gateway | 0.512 | 341.9 | recovered_within_sla |
| 6 | replica_reduction | api-gateway | 0.504 | 308.5 | recovered_within_sla |
| 7 | latency_injection | api-gateway | 0.504 | 307.5 | recovered_within_sla |
| 8 | replica_reduction | product-service | 0.441 | 337.0 | recovered_within_sla |
| 9 | network_partition | product-service | 0.438 | 323.8 | recovered_within_sla |
| 10 | network_partition | order-service | 0.43 | 312.9 | recovered_within_sla |

### 2. Safety check before injecting

Decision **GO** · risk MEDIUM · system health 100.0% · target ready 2/2 · load 0.99× baseline · dependents api-gateway · users possibly affected 100%

### 3. Failure injected

`replica_reduction` on **order-service** at 06:07:58 UTC — succeeded

Details: `{"hpa": "order-service-hpa", "original": {"minReplicas": 2, "maxReplicas": 4}, "patched_to": {"minReplicas": 1, "maxReplicas": 1}}`

### 4. Detection

Confirmed at 06:08:03 UTC on **order-service** as `replica_exhaustion` · severity 0.5 · Isolation Forest score 0.1308 (threshold 0.1031) · flags: capacity_below_baseline

Evidence:
- replicas ready 1/1 (declared minimum 2)
- autoscaler bounds min=1 max=1 below declared minimum 2

LSTM 60 s forecast: score 0.1061 (returning to normal)

### 5. Root-cause analysis

Origin **order-service** · type `replica_exhaustion` · confidence 0.96 · call path api-gateway → order-service · affected order-service

> Root cause localised to order-service (replica exhaustion, confidence 96%). No other service deviates; the fault is contained to order-service. Change evidence: HPA bounds 1-1 are below the declared 2-4; Pod order-service-848895fdff-gcnmb: Killing — Stopping container order-service.

Evidence:
- replicas ready 1/1 (declared minimum 2)
- autoscaler bounds min=1 max=1 below declared minimum 2
- HPA bounds 1-1 are below the declared 2-4
- Pod order-service-848895fdff-gcnmb: Killing — Stopping container order-service

| Candidate | Score | Why |
|---|---|---|
| order-service | 7.6 | severity 0.80; no anomalous dependency explains it; earliest onset; structural fault on the service itself; HPA bounds 1-1 are below the declared 2-4; Pod order-service-848895fdff-gcnmb: Killing — Stopping container order-service |

### 6. Decision

Action **hpa_scaleout** (fallback resource_restore) · confidence 0.622 · priority 6.4

- order-service: replica exhaustion at severity 0.80; business impact 8/10 -> priority 6.40. Playbook: hpa_scaleout, fallback resource_restore.
- Confidence in hpa_scaleout: 0.62 (prior 0.70 (no history yet) x RCA 0.96 x blast factor 0.93).
- Decision: hpa_scaleout on order-service (fallback resource_restore, confidence 0.62).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| hpa_scaleout | order-service | success | yes | 8.1s | autoscaler 1-1 -> 3-4; 1 -> 3 Ready replicas |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"restored": false, "note": "autoscaler already at or above declared bounds"}` · autoscaler `{"from": {"minReplicas": 3, "maxReplicas": 4}, "to": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 0 failed of 1180 requests (0.0%) · user p99 241.9 ms over 59 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 06:07:40 | STRATEGY | order-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose replica_reduction on order-service: New fault on high‑impact order-service with no prior trials, affecting critical dependents and maximizing insight into resilience. |
| 06:07:58 | PREFLIGHT | order-service | GO: order-service at 2/2 Ready, system 100% healthy. Blast radius: 1 dependent service(s) ['api-gateway'], ~100% of users, risk MEDIUM. |
| 06:07:58 | INJECT | order-service | Injected replica_reduction into order-service: Clamp HPA to min=max=1 (order-service-hpa). |
| 06:08:03 | DETECT | order-service | Anomaly confirmed on order-service 5s after injection: pattern matches replica exhaustion. Isolation Forest score +0.131 (threshold +0.103), severity 0.50. Evidence: replicas ready 1/1 (declared minimum 2); autoscaler bounds min=1 max=1 below declared minimum 2. LSTM forecast for the next 60s: score +0.106 (returning to normal). |
| 06:08:08 | RCA | order-service | Root cause localised to order-service (replica exhaustion, confidence 96%). No other service deviates; the fault is contained to order-service. Change evidence: HPA bounds 1-1 are below the declared 2-4; Pod order-service-848895fdff-gcnmb: Killing — Stopping container order-service. |
| 06:08:08 | DECIDE | order-service | Confidence in hpa_scaleout: 0.62 (prior 0.70 (no history yet) x RCA 0.96 x blast factor 0.93). Decision: hpa_scaleout on order-service (fallback resource_restore, confidence 0.62). |
| 06:08:08 | REMEDIATE | order-service | Executing hpa_scaleout on order-service. |
| 06:08:16 | REMEDIATE | order-service | hpa_scaleout succeeded in 8.1s — autoscaler 1-1 -> 3-4; 1 -> 3 Ready replicas. |
| 06:08:22 | VERIFY | order-service | order-service verified functional: 3/3 replicas Ready and 5 consecutive user-path probes OK (last 6ms). |
| 06:09:08 | TEARDOWN | order-service | Round teardown for order-service: no residual fault found; autoscaler returned to declared bounds. |
| 06:09:18 | RECOVERED | order-service | order-service recovered: detected in 4.81s, mitigated in 15.44s, fully back to its normal operating band in 55.0s (target 120s — MET). Users saw 0 failed requests out of 1180 (0.0%) during the incident. |

## Round 3 — pod_deletion → product-service  ·  **RECOVERED**

TTD 4.8s (target 25s, met) · TTM 11.44s · TTR 19.99s (target 90s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: Never‑tried pod deletion on product‑service, high traffic impact and multiple dependents, maximizing new insight for this campaign

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | pod_deletion | product-service | 0.565 | never | — |
| 2 | network_partition | api-gateway | 0.513 | 345.3 | recovered_within_sla |
| 3 | pod_deletion | api-gateway | 0.513 | 343.6 | recovered_within_sla |
| 4 | latency_injection | api-gateway | 0.504 | 309.2 | recovered_within_sla |
| 5 | network_partition | product-service | 0.438 | 325.5 | recovered_within_sla |
| 6 | latency_injection | notification-service | 0.38 | never | — |
| 7 | network_partition | notification-service | 0.38 | never | — |
| 8 | latency_injection | product-service | 0.365 | 115.8 | recovered_within_sla |
| 9 | latency_injection | order-service | 0.337 | 342.7 | mitigated |
| 10 | pod_deletion | notification-service | 0.253 | 324.0 | recovered_within_sla |

### 2. Safety check before injecting

Decision **GO** · risk HIGH · system health 100.0% · target ready 2/2 · load 0.97× baseline · dependents api-gateway, order-service · users possibly affected 100%

### 3. Failure injected

`pod_deletion` on **product-service** at 06:09:43 UTC — succeeded

Details: `{"pod": "product-service-78f8dcb767-qbbxb", "pod_ip": "10.244.0.14", "ready_pods_before": 2}`

### 4. Detection

Confirmed at 06:09:48 UTC on **product-service** as `pod_crash` · severity 0.4 · Isolation Forest score 0.1301 (threshold 0.1031) · flags: replicas_lost

Evidence:
- replicas ready 2/2 (declared minimum 2)
- Ready pod(s) product-service-78f8dcb767-qbbxb disappeared without a scale-down or rollout
- caller_error_rate=0.0% vs baseline 0.0% (z=+0.0)

LSTM 60 s forecast: score 0.1441 (returning to normal)

### 5. Root-cause analysis

Origin **product-service** · type `pod_crash` · confidence 0.918 · call path api-gateway → product-service · affected product-service

> Root cause localised to product-service (pod crash, confidence 92%). No other service deviates; the fault is contained to product-service. Change evidence: Pod product-service-78f8dcb767-qbbxb: Killing — Stopping container product-service; Pod product-service-78f8dcb767-xcrwf: Unhealthy — Startup probe failed: Get "http://10.244.0.26:8001/health": dial tcp 10.244.0.26:8001: connect: connection refused.

Evidence:
- replicas ready 2/2 (declared minimum 2)
- Ready pod(s) product-service-78f8dcb767-qbbxb disappeared without a scale-down or rollout
- caller_error_rate=0.0% vs baseline 0.0% (z=+0.0)
- Pod product-service-78f8dcb767-qbbxb: Killing — Stopping container product-service
- Pod product-service-78f8dcb767-xcrwf: Unhealthy — Startup probe failed: Get "http://10.244.0.26:8001/health": dial tcp 10.244.0.26:8001: connect: connection refused

| Candidate | Score | Why |
|---|---|---|
| product-service | 3.98 | severity 0.24; no anomalous dependency explains it; earliest onset; structural fault on the service itself; Pod product-service-78f8dcb767-qbbxb: Killing — Stopping container product-service; Pod product-service-78f8dcb767-xcrwf: Unhealthy — Startup probe failed: Get "http://10.244.0.26:8001/health": dial tcp 10.244.0.26:8001: connect: connection refused |

### 6. Decision

Action **hpa_scaleout** (fallback rolling_restart) · confidence 0.546 · priority 1.44

- product-service: pod crash at severity 0.24; business impact 6/10 -> priority 1.44. Playbook: hpa_scaleout, fallback rolling_restart.
- Confidence in hpa_scaleout: 0.55 (prior 0.70 (no history yet) x RCA 0.92 x blast factor 0.85).
- Decision: hpa_scaleout on product-service (fallback rolling_restart, confidence 0.55).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| hpa_scaleout | product-service | success | yes | 6.1s | autoscaler 2-4 -> 3-4; 2 -> 3 Ready replicas |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"reversible": false, "note": "Kubernetes reschedules deleted pods by itself"}` · autoscaler `{"from": {"minReplicas": 3, "maxReplicas": 4}, "to": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 0 failed of 482 requests (0.0%) · user p99 244.7 ms over 24 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 06:09:25 | STRATEGY | product-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose pod_deletion on product-service: Never‑tried pod deletion on product‑service, high traffic impact and multiple dependents, maximizing new insight for this campaign |
| 06:09:43 | PREFLIGHT | product-service | GO: product-service at 2/2 Ready, system 100% healthy. Blast radius: 2 dependent service(s) ['api-gateway', 'order-service'], ~100% of users, risk HIGH. |
| 06:09:43 | INJECT | product-service | Injected pod_deletion into product-service: Force-delete one Ready pod (grace period 0) (product-service-78f8dcb767-qbbxb). |
| 06:09:48 | DETECT | product-service | Anomaly confirmed on product-service 5s after injection: pattern matches pod crash. Isolation Forest score +0.130 (threshold +0.103), severity 0.40. Evidence: replicas ready 2/2 (declared minimum 2); Ready pod(s) product-service-78f8dcb767-qbbxb disappeared without a scale-down or rollout; caller_error_rate=0.0% vs baseline 0.0% (z=+0.0). LSTM forecast for the next 60s: score +0.144 (returning to normal). |
| 06:09:53 | RCA | product-service | Root cause localised to product-service (pod crash, confidence 92%). No other service deviates; the fault is contained to product-service. Change evidence: Pod product-service-78f8dcb767-qbbxb: Killing — Stopping container product-service; Pod product-service-78f8dcb767-xcrwf: Unhealthy — Startup probe failed: Get "http://10.244.0.26:8001/health": dial tcp 10.244.0.26:8001: connect: connection refused. |
| 06:09:53 | DECIDE | product-service | Confidence in hpa_scaleout: 0.55 (prior 0.70 (no history yet) x RCA 0.92 x blast factor 0.85). Decision: hpa_scaleout on product-service (fallback rolling_restart, confidence 0.55). |
| 06:09:53 | REMEDIATE | product-service | Executing hpa_scaleout on product-service. |
| 06:09:59 | REMEDIATE | product-service | hpa_scaleout succeeded in 6.1s — autoscaler 2-4 -> 3-4; 2 -> 3 Ready replicas. |
| 06:10:03 | VERIFY | product-service | product-service verified functional: 3/3 replicas Ready and 5 consecutive user-path probes OK (last 5ms). |
| 06:10:08 | TEARDOWN | product-service | Round teardown for product-service: no residual fault found; autoscaler returned to declared bounds. |
| 06:10:18 | RECOVERED | product-service | product-service recovered: detected in 4.8s, mitigated in 11.44s, fully back to its normal operating band in 19.99s (target 90s — MET). Users saw 0 failed requests out of 482 (0.0%) during the incident. |

## Round 4 — network_partition → api-gateway  ·  **RECOVERED**

TTD 14.83s (target 30s, met) · TTM 5.62s · TTR 39.99s (target 90s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: High‑impact api‑gateway network partition, long idle time, never used in this campaign, and critical downstream dependencies.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | network_partition | api-gateway | 0.513 | 346.3 | recovered_within_sla |
| 2 | latency_injection | api-gateway | 0.505 | 310.2 | recovered_within_sla |
| 3 | latency_injection | notification-service | 0.38 | never | — |
| 4 | network_partition | notification-service | 0.38 | never | — |
| 5 | latency_injection | order-service | 0.338 | 343.7 | mitigated |
| 6 | latency_injection | payment-service | 0.21 | 331.2 | recovered_within_sla |
| 7 | network_partition | product-service | 0.189 | 326.5 | recovered_within_sla |
| 8 | network_partition | order-service | 0.181 | 315.6 | recovered_within_sla |
| 9 | network_partition | payment-service | 0.135 | 115.1 | recovered_within_sla |
| 10 | latency_injection | product-service | 0.116 | 116.8 | recovered_within_sla |

### 2. Safety check before injecting

Decision **GO** · risk MEDIUM · system health 100.0% · target ready 2/2 · load 1.0× baseline · dependents none · users possibly affected 100%

### 3. Failure injected

`network_partition` on **api-gateway** at 06:10:48 UTC — succeeded

Details: `{"policy": "chaos-isolate-api-gateway", "effect": "deny all ingress + egress", "conntrack_flush": {"ok": true, "pod_ips": ["10.244.0.5", "10.244.0.18"], "agents": {"chaos-agent-l7fcx": true}}}`

### 4. Detection

Confirmed at 06:11:03 UTC on **api-gateway** as `network_partition` · severity 0.9746 · Isolation Forest score -0.0393 (threshold 0.1031) · flags: iforest, zscore:caller_error_rate, zscore:caller_p99_ms, metrics_unreachable

Evidence:
- replicas ready 2/2 (declared minimum 2)
- metrics endpoint unreachable on 100% of pods
- caller_error_rate=6.1% vs baseline 0.0% (z=+3.1)
- request_rate=13.93 req/s vs baseline 20.00 req/s (z=-3.0)
- pods are running (no container restarts) but cannot be reached over the pod network

LSTM 60 s forecast: score -0.0449 (still anomalous)

### 5. Root-cause analysis

Origin **api-gateway** · type `network_partition` · confidence 0.95 · call path api-gateway · affected api-gateway, product-service, order-service, payment-service, notification-service

> Root cause localised to api-gateway (network partition, confidence 95%). product-service, order-service, payment-service, notification-service deviate because requests from api-gateway stopped reaching them. Change evidence: NetworkPolicy 'chaos-isolate-api-gateway' denies all Ingress/Egress traffic for pods of api-gateway, created 20s ago; 12 ERROR log lines in the last 60s, e.g. 'upstream error (product-service)'.

Evidence:
- replicas ready 2/2 (declared minimum 2)
- metrics endpoint unreachable on 100% of pods
- caller_error_rate=6.1% vs baseline 0.0% (z=+3.1)
- request_rate=13.93 req/s vs baseline 20.00 req/s (z=-3.0)
- pods are running (no container restarts) but cannot be reached over the pod network
- NetworkPolicy 'chaos-isolate-api-gateway' denies all Ingress/Egress traffic for pods of api-gateway, created 20s ago
- 12 ERROR log lines in the last 60s, e.g. 'upstream error (product-service)'

| Candidate | Score | Why |
|---|---|---|
| api-gateway | 8.011 | severity 0.98; no anomalous dependency explains it; earliest onset; structural fault on the service itself; NetworkPolicy 'chaos-isolate-api-gateway' denies all Ingress/Egress traffic for pods of api-gateway, created 20s ago; 12 ERROR log lines in the last 60s, e.g. 'upstream error (product-service)' |
| product-service | 2.328 | severity 0.49; only symptom is reduced traffic — consistent with an upstream failure; no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service']; earliest onset |
| payment-service | 2.185 | severity 0.42; only symptom is reduced traffic — consistent with an upstream failure; no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service']; earliest onset |
| notification-service | 1.934 | severity 0.44; only symptom is reduced traffic — consistent with an upstream failure; no anomalous dependency explains it; explains anomalies in callers ['api-gateway']; earliest onset |
| order-service | 1.835 | severity 0.39; only symptom is reduced traffic — consistent with an upstream failure; no anomalous dependency explains it; explains anomalies in callers ['api-gateway']; earliest onset |

### 6. Decision

Action **network_policy_rollback** (fallback rolling_restart) · confidence 0.76 · priority 8.778

- api-gateway: network partition at severity 0.98; business impact 9/10 -> priority 8.78. Playbook: network_policy_rollback, fallback rolling_restart.
- Confidence in network_policy_rollback: 0.76 (history 0.80 over 1 attempt(s) x RCA 0.95 x blast factor 1.00).
- Decision: network_policy_rollback on api-gateway (fallback rolling_restart, confidence 0.76).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| network_policy_rollback | api-gateway | success | yes | 0.0s | removed 1 isolating NetworkPolicy(ies): chaos-isolate-api-gateway |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"policy": "chaos-isolate-api-gateway", "deleted": false}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 385 failed of 1128 requests (34.2%) · user p99 2489.3 ms over 54 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 06:10:25 | STRATEGY | api-gateway | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose network_partition on api-gateway: High‑impact api‑gateway network partition, long idle time, never used in this campaign, and critical downstream dependencies. |
| 06:10:33 | PREFLIGHT | api-gateway | Waiting for steady state before injecting: steady state not met: product-service currently anomalous. |
| 06:10:48 | PREFLIGHT | api-gateway | GO: api-gateway at 2/2 Ready, system 100% healthy. Blast radius: 0 dependent service(s) , ~100% of users, risk MEDIUM. |
| 06:10:48 | INJECT | api-gateway | Injected network_partition into api-gateway: Deny-all NetworkPolicy selecting the service's pods (chaos-isolate-api-gateway). |
| 06:11:03 | DETECT | api-gateway | Anomaly confirmed on api-gateway 15s after injection: pattern matches network partition. Isolation Forest score -0.039 (threshold +0.103), severity 0.97. Evidence: replicas ready 2/2 (declared minimum 2); metrics endpoint unreachable on 100% of pods; caller_error_rate=6.1% vs baseline 0.0% (z=+3.1). Also deviating: product-service, payment-service, notification-service. LSTM forecast for the next 60s: score -0.045 (still anomalous). |
| 06:11:08 | RCA | api-gateway | Root cause localised to api-gateway (network partition, confidence 95%). product-service, order-service, payment-service, notification-service deviate because requests from api-gateway stopped reaching them. Change evidence: NetworkPolicy 'chaos-isolate-api-gateway' denies all Ingress/Egress traffic for pods of api-gateway, created 20s ago; 12 ERROR log lines in the last 60s, e.g. 'upstream error (product-service)'. |
| 06:11:08 | DECIDE | api-gateway | Confidence in network_policy_rollback: 0.76 (history 0.80 over 1 attempt(s) x RCA 0.95 x blast factor 1.00). Decision: network_policy_rollback on api-gateway (fallback rolling_restart, confidence 0.76). |
| 06:11:08 | REMEDIATE | api-gateway | Executing network_policy_rollback on api-gateway. |
| 06:11:08 | REMEDIATE | api-gateway | network_policy_rollback succeeded in 0.0s — removed 1 isolating NetworkPolicy(ies): chaos-isolate-api-gateway. |
| 06:11:13 | VERIFY | api-gateway | api-gateway verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 6ms). |
| 06:11:53 | TEARDOWN | api-gateway | Round teardown for api-gateway: no residual fault found; autoscaler returned to declared bounds. |
| 06:12:03 | RECOVERED | api-gateway | api-gateway recovered: detected in 14.83s, mitigated in 5.62s, fully back to its normal operating band in 39.99s (target 90s — MET). Users saw 385 failed requests out of 1128 (34.2%) during the incident. |

## Round 5 — latency_injection → notification-service  ·  **UNDETECTED**

TTD — (target 35s, missed) · TTM — · TTR — (target 120s, missed) · healed by — · diagnosis wrong, classification wrong

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: First-time latency injection on notification-service, low impact but upstream dependent api-gateway, adds new fault type to the campaign.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | latency_injection | notification-service | 0.38 | never | — |
| 2 | latency_injection | order-service | 0.338 | 345.5 | mitigated |
| 3 | latency_injection | api-gateway | 0.255 | 312.0 | recovered_within_sla |
| 4 | latency_injection | payment-service | 0.21 | 333.0 | recovered_within_sla |
| 5 | latency_injection | product-service | 0.117 | 118.5 | recovered_within_sla |
| 6 | cpu_throttle | notification-service | -0.02 | never | — |
| 7 | network_partition | notification-service | -0.02 | never | — |
| 8 | pod_deletion | api-gateway | -0.137 | 346.4 | recovered_within_sla |
| 9 | replica_reduction | api-gateway | -0.145 | 313.0 | recovered_within_sla |
| 10 | pod_deletion | notification-service | -0.146 | 326.7 | recovered_within_sla |

### 2. Safety check before injecting

Decision **GO** · risk MEDIUM · system health 100.0% · target ready 1/1 · load 0.96× baseline · dependents api-gateway · users possibly affected 100%

### 3. Failure injected

`latency_injection` on **notification-service** at 06:12:28 UTC — succeeded

Details: `{"pod": "notification-service-85dc68594-thpcd", "delay": "200ms", "jitter": "50ms", "command": "tc qdisc replace dev eth0 root netem delay 200ms 50ms distribution normal", "replicas_ready": 1}`

### 4. Detection

Not detected within the detection window.

### 7. Remediation

No remediation was needed or attempted.

### 8. Teardown and user impact

Fault still present at teardown: **yes** · reverse `{"pod": "notification-service-85dc68594-thpcd", "removed": true, "note": "netem qdisc deleted"}` · autoscaler `{"unchanged": {"minReplicas": 1, "maxReplicas": 3}}`

Users: 0 failed of 2098 requests (0.0%) · user p99 243.3 ms over 105 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 06:12:10 | STRATEGY | notification-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose latency_injection on notification-service: First-time latency injection on notification-service, low impact but upstream dependent api-gateway, adds new fault type to the campaign. |
| 06:12:28 | PREFLIGHT | notification-service | GO: notification-service at 1/1 Ready, system 100% healthy. Blast radius: 1 dependent service(s) ['api-gateway'], ~100% of users, risk MEDIUM. |
| 06:12:28 | INJECT | notification-service | Injected latency_injection into notification-service: tc netem egress delay on one replica (notification-service-85dc68594-thpcd). |
| 06:14:03 | DETECT | notification-service | No anomaly confirmed within 90s of injecting latency_injection into notification-service. Reporting UNDETECTED. |
| 06:14:03 | TEARDOWN | notification-service | Round teardown for notification-service: the fault was still physically present and has now been reverted; autoscaler returned to declared bounds. |

## Campaign-level events

| Time (UTC) | Phase | Message |
|---|---|---|
| 06:05:45 | CAMPAIGN | Campaign c-20261011-060545-bc28 starting: 5 rounds (auto, auto, auto, auto, auto). |
| 06:14:13 | SUMMARY | Campaign completed: resilience score 80.6/100 — GOOD — reliable recovery with minor SLA or diagnosis misses. |
