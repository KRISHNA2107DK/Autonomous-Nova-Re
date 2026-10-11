# Incident log — campaign `c-20261011-070048-d4fe`

**Resilience score 99.6/100** — EXCELLENT — every fault detected, diagnosed and healed within SLA

| Component | Points |
|---|---|
| recovery sla | 35.0 |
| detection sla | 20.0 |
| remediation effectiveness | 20.0 |
| diagnosis accuracy | 15.0 |
| user protection | 9.57 |

| # | Fault | Target | Status | TTD | TTR | Users failed |
|---|---|---|---|---|---|---|
| 1 | latency_injection | payment-service | RECOVERED | 14.82s | 50.0s | 0.3% |
| 2 | pod_deletion | api-gateway | RECOVERED | 4.81s | 14.99s | 0.0% |
| 3 | network_partition | order-service | RECOVERED | 9.83s | 50.0s | 10.6% |
| 4 | replica_reduction | product-service | RECOVERED | 4.83s | 20.0s | 0.0% |
| 5 | cpu_throttle | api-gateway | RECOVERED | 14.83s | 50.01s | 0.0% |

## Round 1 — latency_injection → payment-service  ·  **RECOVERED**

TTD 14.82s (target 35s, met) · TTM 17.33s · TTR 50.0s (target 120s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: High business impact (10) on payment-service, long idle time, and latency injection not yet used this campaign, maximizing insight into critical path resilience.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | latency_injection | order-service | 0.599 | 394.1 | mitigated |
| 2 | pod_deletion | api-gateway | 0.524 | 395.1 | recovered_within_sla |
| 3 | replica_reduction | api-gateway | 0.517 | 361.7 | recovered_within_sla |
| 4 | latency_injection | api-gateway | 0.517 | 360.7 | recovered_within_sla |
| 5 | latency_injection | payment-service | 0.471 | 381.6 | recovered_within_sla |
| 6 | pod_deletion | payment-service | 0.467 | 362.7 | recovered_within_sla |
| 7 | cpu_throttle | api-gateway | 0.458 | 163.8 | recovered_within_sla |
| 8 | replica_reduction | product-service | 0.453 | 390.1 | recovered_within_sla |
| 9 | network_partition | product-service | 0.45 | 377.0 | recovered_within_sla |
| 10 | cpu_throttle | product-service | 0.447 | 364.5 | recovered_within_sla |

### 2. Safety check before injecting

Decision **GO** · risk HIGH · system health 100.0% · target ready 2/2 · load 0.9× baseline · dependents api-gateway, order-service · users possibly affected 100%

### 3. Failure injected

`latency_injection` on **payment-service** at 07:01:10 UTC — succeeded

Details: `{"pod": "payment-service-7745b65785-hhvxh", "delay": "200ms", "jitter": "50ms", "command": "tc qdisc replace dev eth0 root netem delay 200ms 50ms distribution normal", "replicas_ready": 2}`

### 4. Detection

Confirmed at 07:01:24 UTC on **api-gateway** as `high_latency` · severity 0.9368 · Isolation Forest score -0.0401 (threshold 0.1031) · flags: iforest, zscore:p99_latency_ms, zscore:caller_p99_ms

Evidence:
- p99_latency_ms=248.03ms vs baseline 242.46ms (z=+0.2)
- caller_p99_ms=1010.00ms vs baseline 242.66ms (z=+21.1)

LSTM 60 s forecast: score -0.0371 (still anomalous)

### 5. Root-cause analysis

Origin **payment-service** · type `high_latency` · confidence 0.95 · call path api-gateway → payment-service · affected api-gateway, order-service, payment-service

> Root cause localised to payment-service (high latency, confidence 95%). api-gateway, order-service also deviate as callers of payment-service: its failure propagates to them. Change evidence: Pod payment-service-7745b65785-hhvxh: Unhealthy — Readiness probe failed: Get "http://10.244.0.30:8003/ready": context deadline exceeded (Client.Timeout exceeded while aw.

Evidence:
- p99_latency_ms=3050.00ms vs baseline 246.49ms (z=+25.0)
- caller_p99_ms=3112.51ms vs baseline 246.52ms (z=+25.0)
- Pod payment-service-7745b65785-hhvxh: Unhealthy — Readiness probe failed: Get "http://10.244.0.30:8003/ready": context deadline exceeded (Client.Timeout exceeded while aw

| Candidate | Score | Why |
|---|---|---|
| payment-service | 5.219 | severity 0.93; no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service']; earliest onset; Pod payment-service-7745b65785-hhvxh: Unhealthy — Readiness probe failed: Get "http://10.244.0.30:8003/ready": context deadline exceeded (Client.Timeout exceeded while aw |
| order-service | 1.418 | severity 0.93; its dependencies ['payment-service'] are also anomalous (likely a victim); explains anomalies in callers ['api-gateway']; earliest onset |
| api-gateway | 1.122 | severity 0.94; its dependencies ['order-service', 'payment-service'] are also anomalous (likely a victim); earliest onset |

### 6. Decision

Action **traffic_reroute** (fallback rolling_restart) · confidence 0.711 · priority 9.346

- payment-service: high latency at severity 0.93; business impact 10/10 -> priority 9.35. Playbook: traffic_reroute, fallback rolling_restart.
- Confidence in traffic_reroute: 0.71 (history 0.88 over 3 attempt(s) x RCA 0.95 x blast factor 0.85).
- Decision: traffic_reroute on payment-service (fallback rolling_restart, confidence 0.71).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| traffic_reroute | payment-service | success | yes | 11.1s | quarantined payment-service-7745b65785-hhvxh (worst replica by live telemetry (p99=4789ms, next worst score 246 vs 4789)); traffic now on 2 healthy replica(s) |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"pod": "payment-service-7745b65785-hhvxh", "note": "pod no longer exists (replaced)"}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 4 failed of 1284 requests (0.3%) · user p99 4189.0 ms over 64 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 07:00:52 | STRATEGY | payment-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose latency_injection on payment-service: High business impact (10) on payment-service, long idle time, and latency injection not yet used this campaign, maximizing insight into critical path resilience. |
| 07:01:10 | PREFLIGHT | payment-service | GO: payment-service at 2/2 Ready, system 100% healthy. Blast radius: 2 dependent service(s) ['api-gateway', 'order-service'], ~100% of users, risk HIGH. |
| 07:01:10 | INJECT | payment-service | Injected latency_injection into payment-service: tc netem egress delay on one replica (payment-service-7745b65785-hhvxh). |
| 07:01:25 | DETECT | api-gateway | Anomaly confirmed on api-gateway 15s after injection: pattern matches high latency. Isolation Forest score -0.040 (threshold +0.103), severity 0.94. Evidence: p99_latency_ms=248.03ms vs baseline 242.46ms (z=+0.2); caller_p99_ms=1010.00ms vs baseline 242.66ms (z=+21.1). Also deviating: order-service, payment-service. LSTM forecast for the next 60s: score -0.037 (still anomalous). |
| 07:01:30 | RCA | payment-service | Root cause localised to payment-service (high latency, confidence 95%). api-gateway, order-service also deviate as callers of payment-service: its failure propagates to them. Change evidence: Pod payment-service-7745b65785-hhvxh: Unhealthy — Readiness probe failed: Get "http://10.244.0.30:8003/ready": context deadline exceeded (Client.Timeout exceeded while aw. |
| 07:01:30 | DECIDE | payment-service | Confidence in traffic_reroute: 0.71 (history 0.88 over 3 attempt(s) x RCA 0.95 x blast factor 0.85). Decision: traffic_reroute on payment-service (fallback rolling_restart, confidence 0.71). |
| 07:01:30 | REMEDIATE | payment-service | Executing traffic_reroute on payment-service. |
| 07:01:41 | REMEDIATE | payment-service | traffic_reroute succeeded in 11.1s — quarantined payment-service-7745b65785-hhvxh (worst replica by live telemetry (p99=4789ms, next worst score 246 vs 4789)); traffic now on 2 healthy replica(s). |
| 07:01:46 | VERIFY | payment-service | payment-service verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 7ms). |
| 07:02:25 | TEARDOWN | payment-service | Round teardown for payment-service: no residual fault found; autoscaler returned to declared bounds. |
| 07:02:35 | RECOVERED | payment-service | payment-service recovered: detected in 14.82s, mitigated in 17.33s, fully back to its normal operating band in 50.0s (target 120s — MET). Users saw 4 failed requests out of 1284 (0.3%) during the incident. |

## Round 2 — pod_deletion → api-gateway  ·  **RECOVERED**

TTD 4.81s (target 25s, met) · TTM 9.36s · TTR 14.99s (target 90s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: High‑impact api‑gateway pod deletion hasn't been tried in ~397 min, offering fresh insight into core traffic resilience.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | pod_deletion | api-gateway | 0.524 | 396.9 | recovered_within_sla |
| 2 | replica_reduction | api-gateway | 0.517 | 363.5 | recovered_within_sla |
| 3 | cpu_throttle | api-gateway | 0.458 | 165.7 | recovered_within_sla |
| 4 | replica_reduction | product-service | 0.453 | 392.0 | recovered_within_sla |
| 5 | network_partition | product-service | 0.45 | 378.8 | recovered_within_sla |
| 6 | cpu_throttle | product-service | 0.448 | 366.3 | recovered_within_sla |
| 7 | cpu_throttle | order-service | 0.446 | 380.6 | recovered_within_sla |
| 8 | network_partition | order-service | 0.443 | 367.9 | recovered_within_sla |
| 9 | network_partition | api-gateway | 0.393 | 51.9 | recovered_within_sla |
| 10 | pod_deletion | order-service | 0.385 | 170.1 | recovered_within_sla |

### 2. Safety check before injecting

Decision **GO** · risk MEDIUM · system health 100.0% · target ready 2/2 · load 0.91× baseline · dependents none · users possibly affected 100%

### 3. Failure injected

`pod_deletion` on **api-gateway** at 07:03:00 UTC — succeeded

Details: `{"pod": "api-gateway-6488bc94fb-2jrp7", "pod_ip": "10.244.0.5", "ready_pods_before": 2}`

### 4. Detection

Confirmed at 07:03:04 UTC on **api-gateway** as `pod_crash` · severity 0.4 · Isolation Forest score 0.1375 (threshold 0.1031) · flags: replicas_lost

Evidence:
- replicas ready 2/2 (declared minimum 2)
- Ready pod(s) api-gateway-6488bc94fb-2jrp7 disappeared without a scale-down or rollout
- caller_error_rate=0.0% vs baseline 0.0% (z=+0.0)

LSTM 60 s forecast: score 0.1266 (returning to normal)

### 5. Root-cause analysis

Origin **api-gateway** · type `pod_crash` · confidence 0.918 · call path api-gateway · affected api-gateway

> Root cause localised to api-gateway (pod crash, confidence 92%). No other service deviates; the fault is contained to api-gateway. Change evidence: Pod api-gateway-6488bc94fb-2jrp7: Killing — Stopping container api-gateway.

Evidence:
- replicas ready 2/2 (declared minimum 2)
- Ready pod(s) api-gateway-6488bc94fb-2jrp7 disappeared without a scale-down or rollout
- caller_error_rate=0.0% vs baseline 0.0% (z=+0.0)
- Pod api-gateway-6488bc94fb-2jrp7: Killing — Stopping container api-gateway

| Candidate | Score | Why |
|---|---|---|
| api-gateway | 3.98 | severity 0.24; no anomalous dependency explains it; earliest onset; structural fault on the service itself; Pod api-gateway-6488bc94fb-2jrp7: Killing — Stopping container api-gateway |

### 6. Decision

Action **hpa_scaleout** (fallback rolling_restart) · confidence 0.734 · priority 2.16

- api-gateway: pod crash at severity 0.24; business impact 9/10 -> priority 2.16. Playbook: hpa_scaleout, fallback rolling_restart.
- Confidence in hpa_scaleout: 0.73 (history 0.80 over 1 attempt(s) x RCA 0.92 x blast factor 1.00).
- Decision: hpa_scaleout on api-gateway (fallback rolling_restart, confidence 0.73).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| hpa_scaleout | api-gateway | success | yes | 4.1s | autoscaler 2-4 -> 3-4; 2 -> 3 Ready replicas |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"reversible": false, "note": "Kubernetes reschedules deleted pods by itself"}` · autoscaler `{"from": {"minReplicas": 3, "maxReplicas": 4}, "to": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 0 failed of 378 requests (0.0%) · user p99 243.2 ms over 19 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 07:02:41 | STRATEGY | api-gateway | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose pod_deletion on api-gateway: High‑impact api‑gateway pod deletion hasn't been tried in ~397 min, offering fresh insight into core traffic resilience. |
| 07:03:00 | PREFLIGHT | api-gateway | GO: api-gateway at 2/2 Ready, system 100% healthy. Blast radius: 0 dependent service(s) , ~100% of users, risk MEDIUM. |
| 07:03:00 | INJECT | api-gateway | Injected pod_deletion into api-gateway: Force-delete one Ready pod (grace period 0) (api-gateway-6488bc94fb-2jrp7). |
| 07:03:05 | DETECT | api-gateway | Anomaly confirmed on api-gateway 5s after injection: pattern matches pod crash. Isolation Forest score +0.138 (threshold +0.103), severity 0.40. Evidence: replicas ready 2/2 (declared minimum 2); Ready pod(s) api-gateway-6488bc94fb-2jrp7 disappeared without a scale-down or rollout; caller_error_rate=0.0% vs baseline 0.0% (z=+0.0). LSTM forecast for the next 60s: score +0.127 (returning to normal). |
| 07:03:10 | RCA | api-gateway | Root cause localised to api-gateway (pod crash, confidence 92%). No other service deviates; the fault is contained to api-gateway. Change evidence: Pod api-gateway-6488bc94fb-2jrp7: Killing — Stopping container api-gateway. |
| 07:03:10 | DECIDE | api-gateway | Confidence in hpa_scaleout: 0.73 (history 0.80 over 1 attempt(s) x RCA 0.92 x blast factor 1.00). Decision: hpa_scaleout on api-gateway (fallback rolling_restart, confidence 0.73). |
| 07:03:10 | REMEDIATE | api-gateway | Executing hpa_scaleout on api-gateway. |
| 07:03:14 | REMEDIATE | api-gateway | hpa_scaleout succeeded in 4.1s — autoscaler 2-4 -> 3-4; 2 -> 3 Ready replicas. |
| 07:03:18 | VERIFY | api-gateway | api-gateway verified functional: 3/3 replicas Ready and 5 consecutive user-path probes OK (last 7ms). |
| 07:03:20 | TEARDOWN | api-gateway | Round teardown for api-gateway: no residual fault found; autoscaler returned to declared bounds. |
| 07:03:30 | RECOVERED | api-gateway | api-gateway recovered: detected in 4.81s, mitigated in 9.36s, fully back to its normal operating band in 14.99s (target 90s — MET). Users saw 0 failed requests out of 378 (0.0%) during the incident. |

## Round 3 — network_partition → order-service  ·  **RECOVERED**

TTD 9.83s (target 30s, met) · TTM 10.45s · TTR 50.0s (target 90s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: Network partition on order-service hasn't been tried for ~369 min, high business impact (8) and critical dependents, offering fresh insight while avoiding previously used services/faults.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | replica_reduction | product-service | 0.453 | 392.9 | recovered_within_sla |
| 2 | network_partition | product-service | 0.451 | 379.7 | recovered_within_sla |
| 3 | cpu_throttle | product-service | 0.448 | 367.2 | recovered_within_sla |
| 4 | cpu_throttle | order-service | 0.446 | 381.6 | recovered_within_sla |
| 5 | network_partition | order-service | 0.443 | 368.8 | recovered_within_sla |
| 6 | cpu_throttle | notification-service | 0.38 | never | — |
| 7 | network_partition | notification-service | 0.38 | never | — |
| 8 | replica_reduction | order-service | 0.321 | 55.6 | recovered_within_sla |
| 9 | replica_reduction | api-gateway | 0.267 | 364.4 | recovered_within_sla |
| 10 | cpu_throttle | api-gateway | 0.209 | 166.6 | recovered_within_sla |

### 2. Safety check before injecting

Decision **GO** · risk MEDIUM · system health 100.0% · target ready 2/2 · load 0.93× baseline · dependents api-gateway · users possibly affected 100%

### 3. Failure injected

`network_partition` on **order-service** at 07:03:55 UTC — succeeded

Details: `{"policy": "chaos-isolate-order-service", "effect": "deny all ingress + egress", "conntrack_flush": {"ok": true, "pod_ips": ["10.244.0.22", "10.244.0.25"], "agents": {"chaos-agent-l7fcx": true}}}`

### 4. Detection

Confirmed at 07:04:04 UTC on **order-service** as `network_partition` · severity 0.987 · Isolation Forest score 0.0145 (threshold 0.1031) · flags: iforest, zscore:caller_p99_ms, replicas_lost, metrics_unreachable

Evidence:
- replicas ready 2/2 (declared minimum 2)
- metrics endpoint unreachable on 50% of pods
- caller_error_rate=0.0% vs baseline 0.0% (z=+0.0)
- request_rate=6.40 req/s vs baseline 8.08 req/s (z=-2.1)
- pods are running (no container restarts) but cannot be reached over the pod network

LSTM 60 s forecast: score 0.0252 (still anomalous)

### 5. Root-cause analysis

Origin **order-service** · type `network_partition` · confidence 0.95 · call path api-gateway → order-service · affected api-gateway, order-service, notification-service

> Root cause localised to order-service (network partition, confidence 95%). api-gateway also deviate as callers of order-service: its failure propagates to them. notification-service also deviate without a dependency explaining it (lower-ranked candidates). Change evidence: NetworkPolicy 'chaos-isolate-order-service' denies all Ingress/Egress traffic for pods of order-service, created 15s ago; 2 ERROR log lines in the last 60s, e.g. 'dependency failure (product-service)'.

Evidence:
- replicas ready 2/2 (declared minimum 2)
- metrics endpoint unreachable on 50% of pods
- caller_error_rate=0.0% vs baseline 0.0% (z=+0.0)
- request_rate=6.40 req/s vs baseline 8.08 req/s (z=-2.1)
- pods are running (no container restarts) but cannot be reached over the pod network
- NetworkPolicy 'chaos-isolate-order-service' denies all Ingress/Egress traffic for pods of order-service, created 15s ago
- Pod order-service-848895fdff-l8zbh: Unhealthy — Readiness probe failed: Get "http://10.244.0.22:8002/ready": context deadline exceeded (Client.Timeout exceeded while aw
- Pod order-service-848895fdff-nkgrs: Unhealthy — Readiness probe failed: Get "http://10.244.0.25:8002/ready": context deadline exceeded (Client.Timeout exceeded while aw
- 2 ERROR log lines in the last 60s, e.g. 'dependency failure (product-service)'

| Candidate | Score | Why |
|---|---|---|
| order-service | 9.307 | severity 1.00; no anomalous dependency explains it; explains anomalies in callers ['api-gateway']; earliest onset; structural fault on the service itself; NetworkPolicy 'chaos-isolate-order-service' denies all Ingress/Egress traffic for pods of order-service, created 15s ago; Pod order-service-848895fdff-l8zbh: Unhealthy — Readiness probe failed: Get "http://10.244.0.22:8002/ready": context deadli… |
| api-gateway | 2.66 | severity 0.97; its dependencies ['order-service'] are also anomalous (likely a victim); earliest onset; 195 ERROR log lines in the last 60s, e.g. 'upstream error (order-service)' |
| notification-service | 1.588 | severity 0.27; only symptom is reduced traffic — consistent with an upstream failure; no anomalous dependency explains it; explains anomalies in callers ['api-gateway']; earliest onset |

### 6. Decision

Action **network_policy_rollback** (fallback rolling_restart) · confidence 0.703 · priority 7.99

- order-service: network partition at severity 1.00; business impact 8/10 -> priority 7.99. Playbook: network_policy_rollback, fallback rolling_restart.
- Confidence in network_policy_rollback: 0.70 (history 0.80 over 1 attempt(s) x RCA 0.95 x blast factor 0.93).
- Decision: network_policy_rollback on order-service (fallback rolling_restart, confidence 0.70).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| network_policy_rollback | order-service | success | yes | 4.0s | removed 1 isolating NetworkPolicy(ies): chaos-isolate-order-service |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"policy": "chaos-isolate-order-service", "deleted": false}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 130 failed of 1226 requests (10.6%) · user p99 9350.6 ms over 59 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 07:03:36 | STRATEGY | order-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose network_partition on order-service: Network partition on order-service hasn't been tried for ~369 min, high business impact (8) and critical dependents, offering fresh insight while avoiding previously used services/faults. |
| 07:03:55 | PREFLIGHT | order-service | GO: order-service at 2/2 Ready, system 100% healthy. Blast radius: 1 dependent service(s) ['api-gateway'], ~100% of users, risk MEDIUM. |
| 07:03:55 | INJECT | order-service | Injected network_partition into order-service: Deny-all NetworkPolicy selecting the service's pods (chaos-isolate-order-service). |
| 07:04:05 | DETECT | order-service | Anomaly confirmed on order-service 10s after injection: pattern matches network partition. Isolation Forest score +0.015 (threshold +0.103), severity 0.99. Evidence: replicas ready 2/2 (declared minimum 2); metrics endpoint unreachable on 50% of pods; caller_error_rate=0.0% vs baseline 0.0% (z=+0.0). Also deviating: api-gateway. LSTM forecast for the next 60s: score +0.025 (still anomalous). |
| 07:04:10 | RCA | order-service | Root cause localised to order-service (network partition, confidence 95%). api-gateway also deviate as callers of order-service: its failure propagates to them. notification-service also deviate without a dependency explaining it (lower-ranked candidates). Change evidence: NetworkPolicy 'chaos-isolate-order-service' denies all Ingress/Egress traffic for pods of order-service, created 15s ago; 2 ERROR log lines in the last 60s, e.g. 'dependency failure (product-service)'. |
| 07:04:10 | DECIDE | order-service | Confidence in network_policy_rollback: 0.70 (history 0.80 over 1 attempt(s) x RCA 0.95 x blast factor 0.93). Decision: network_policy_rollback on order-service (fallback rolling_restart, confidence 0.70). |
| 07:04:10 | REMEDIATE | order-service | Executing network_policy_rollback on order-service. |
| 07:04:14 | REMEDIATE | order-service | network_policy_rollback succeeded in 4.0s — removed 1 isolating NetworkPolicy(ies): chaos-isolate-order-service. |
| 07:04:19 | VERIFY | order-service | order-service verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 7ms). |
| 07:05:05 | TEARDOWN | order-service | Round teardown for order-service: no residual fault found; autoscaler returned to declared bounds. |
| 07:05:15 | RECOVERED | order-service | order-service recovered: detected in 9.83s, mitigated in 10.45s, fully back to its normal operating band in 50.0s (target 90s — MET). Users saw 130 failed requests out of 1226 (10.6%) during the incident. |

## Round 4 — replica_reduction → product-service  ·  **RECOVERED**

TTD 4.83s (target 35s, met) · TTM 11.38s · TTR 20.0s (target 120s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: Select replica_reduction on product-service, a high‑traffic core service not yet used this campaign, with many dependents and longest time since last try.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | replica_reduction | product-service | 0.454 | 394.6 | recovered_within_sla |
| 2 | cpu_throttle | product-service | 0.448 | 369.0 | recovered_within_sla |
| 3 | cpu_throttle | notification-service | 0.38 | never | — |
| 4 | replica_reduction | api-gateway | 0.268 | 366.2 | recovered_within_sla |
| 5 | cpu_throttle | api-gateway | 0.21 | 168.3 | recovered_within_sla |
| 6 | cpu_throttle | order-service | 0.196 | 383.3 | recovered_within_sla |
| 7 | replica_reduction | payment-service | 0.159 | 166.5 | recovered_within_sla |
| 8 | cpu_throttle | payment-service | 0.099 | 59.2 | recovered_within_sla |
| 9 | replica_reduction | order-service | 0.073 | 57.4 | recovered_within_sla |
| 10 | network_partition | product-service | 0.051 | 381.5 | recovered_within_sla |

### 2. Safety check before injecting

Decision **GO** · risk HIGH · system health 100.0% · target ready 2/2 · load 1.01× baseline · dependents api-gateway, order-service · users possibly affected 100%

### 3. Failure injected

`replica_reduction` on **product-service** at 07:05:40 UTC — succeeded

Details: `{"hpa": "product-service-hpa", "original": {"minReplicas": 2, "maxReplicas": 4}, "patched_to": {"minReplicas": 1, "maxReplicas": 1}}`

### 4. Detection

Confirmed at 07:05:44 UTC on **product-service** as `replica_exhaustion` · severity 0.5 · Isolation Forest score 0.115 (threshold 0.1031) · flags: capacity_below_baseline

Evidence:
- replicas ready 1/1 (declared minimum 2)
- autoscaler bounds min=1 max=1 below declared minimum 2

LSTM 60 s forecast: score 0.1322 (returning to normal)

### 5. Root-cause analysis

Origin **product-service** · type `replica_exhaustion` · confidence 0.96 · call path api-gateway → product-service · affected product-service

> Root cause localised to product-service (replica exhaustion, confidence 96%). No other service deviates; the fault is contained to product-service. Change evidence: HPA bounds 1-1 are below the declared 2-4; Pod product-service-78f8dcb767-kbvl4: Killing — Stopping container product-service.

Evidence:
- replicas ready 1/1 (declared minimum 2)
- autoscaler bounds min=1 max=1 below declared minimum 2
- HPA bounds 1-1 are below the declared 2-4
- Pod product-service-78f8dcb767-kbvl4: Killing — Stopping container product-service

| Candidate | Score | Why |
|---|---|---|
| product-service | 7.0 | severity 0.50; no anomalous dependency explains it; earliest onset; structural fault on the service itself; HPA bounds 1-1 are below the declared 2-4; Pod product-service-78f8dcb767-kbvl4: Killing — Stopping container product-service |

### 6. Decision

Action **hpa_scaleout** (fallback resource_restore) · confidence 0.653 · priority 3.0

- product-service: replica exhaustion at severity 0.50; business impact 6/10 -> priority 3.00. Playbook: hpa_scaleout, fallback resource_restore.
- Confidence in hpa_scaleout: 0.65 (history 0.80 over 1 attempt(s) x RCA 0.96 x blast factor 0.85).
- Decision: hpa_scaleout on product-service (fallback resource_restore, confidence 0.65).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| hpa_scaleout | product-service | success | yes | 6.1s | autoscaler 1-1 -> 3-4; 1 -> 3 Ready replicas |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"restored": false, "note": "autoscaler already at or above declared bounds"}` · autoscaler `{"from": {"minReplicas": 3, "maxReplicas": 4}, "to": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 0 failed of 478 requests (0.0%) · user p99 243.5 ms over 24 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 07:05:21 | STRATEGY | product-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose replica_reduction on product-service: Select replica_reduction on product-service, a high‑traffic core service not yet used this campaign, with many dependents and longest time since last try. |
| 07:05:40 | PREFLIGHT | product-service | GO: product-service at 2/2 Ready, system 100% healthy. Blast radius: 2 dependent service(s) ['api-gateway', 'order-service'], ~100% of users, risk HIGH. |
| 07:05:40 | INJECT | product-service | Injected replica_reduction into product-service: Clamp HPA to min=max=1 (product-service-hpa). |
| 07:05:45 | DETECT | product-service | Anomaly confirmed on product-service 5s after injection: pattern matches replica exhaustion. Isolation Forest score +0.115 (threshold +0.103), severity 0.50. Evidence: replicas ready 1/1 (declared minimum 2); autoscaler bounds min=1 max=1 below declared minimum 2. LSTM forecast for the next 60s: score +0.132 (returning to normal). |
| 07:05:50 | RCA | product-service | Root cause localised to product-service (replica exhaustion, confidence 96%). No other service deviates; the fault is contained to product-service. Change evidence: HPA bounds 1-1 are below the declared 2-4; Pod product-service-78f8dcb767-kbvl4: Killing — Stopping container product-service. |
| 07:05:50 | DECIDE | product-service | Confidence in hpa_scaleout: 0.65 (history 0.80 over 1 attempt(s) x RCA 0.96 x blast factor 0.85). Decision: hpa_scaleout on product-service (fallback resource_restore, confidence 0.65). |
| 07:05:50 | REMEDIATE | product-service | Executing hpa_scaleout on product-service. |
| 07:05:56 | REMEDIATE | product-service | hpa_scaleout succeeded in 6.1s — autoscaler 1-1 -> 3-4; 1 -> 3 Ready replicas. |
| 07:06:00 | VERIFY | product-service | product-service verified functional: 3/3 replicas Ready and 5 consecutive user-path probes OK (last 5ms). |
| 07:06:05 | TEARDOWN | product-service | Round teardown for product-service: no residual fault found; autoscaler returned to declared bounds. |
| 07:06:15 | RECOVERED | product-service | product-service recovered: detected in 4.83s, mitigated in 11.38s, fully back to its normal operating band in 20.0s (target 120s — MET). Users saw 0 failed requests out of 478 (0.0%) during the incident. |

## Round 5 — cpu_throttle → api-gateway  ·  **RECOVERED**

TTD 14.83s (target 35s, met) · TTM 7.49s · TTR 50.01s (target 90s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: High‑impact cpu_throttle on api‑gateway, many dependencies, long idle time since last run, and not yet used in this campaign.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | cpu_throttle | notification-service | 0.38 | never | — |
| 2 | cpu_throttle | api-gateway | 0.21 | 169.3 | recovered_within_sla |
| 3 | cpu_throttle | product-service | 0.199 | 370.0 | recovered_within_sla |
| 4 | cpu_throttle | order-service | 0.197 | 384.3 | recovered_within_sla |
| 5 | cpu_throttle | payment-service | 0.1 | 60.2 | recovered_within_sla |
| 6 | network_partition | notification-service | -0.02 | never | — |
| 7 | latency_injection | order-service | -0.05 | 399.6 | mitigated |
| 8 | latency_injection | notification-service | -0.11 | 53.9 | undetected |
| 9 | replica_reduction | api-gateway | -0.132 | 367.2 | recovered_within_sla |
| 10 | latency_injection | api-gateway | -0.132 | 366.2 | recovered_within_sla |

### 2. Safety check before injecting

Decision **GO** · risk MEDIUM · system health 100.0% · target ready 2/2 · load 0.92× baseline · dependents none · users possibly affected 100%

### 3. Failure injected

`cpu_throttle` on **api-gateway** at 07:06:40 UTC — succeeded

Details: `{"pods": ["api-gateway-6488bc94fb-f9qqs", "api-gateway-6488bc94fb-zzt9d"], "cpu_limit": "25m", "original": {"api-gateway-6488bc94fb-f9qqs": {"api-gateway": {"requests": {"cpu": "100m", "memory": "64Mi"}, "limits": {"cpu": "500m", "memory": "192Mi"}}}, "api-gateway-6488bc94fb-zzt9d": {"api-gateway": {"requests": {"cpu": "100m", "memory": "64Mi"}, "limits": {"cpu": "500m", "memory": "192Mi"}}}}}`

### 4. Detection

Confirmed at 07:06:54 UTC on **product-service** as `high_latency` · severity 0.5792 · Isolation Forest score 0.0635 (threshold 0.1031) · flags: iforest, zscore:caller_p99_ms

Evidence:
- p99_latency_ms=15.83ms vs baseline 16.09ms (z=-0.0)
- caller_p99_ms=157.37ms vs baseline 16.56ms (z=+9.4)

LSTM 60 s forecast: score 0.0554 (still anomalous)

### 5. Root-cause analysis

Origin **api-gateway** · type `cpu_throttle` · confidence 0.95 · call path api-gateway · affected api-gateway, product-service, order-service

> Root cause localised to api-gateway (cpu throttle, confidence 95%). product-service, order-service deviate because requests from api-gateway stopped reaching them. Change evidence: pod api-gateway-6488bc94fb-f9qqs CPU limit is 25m vs declared 500m; pod api-gateway-6488bc94fb-zzt9d CPU limit is 25m vs declared 500m.

Evidence:
- p99_latency_ms=248.86ms vs baseline 242.46ms (z=+0.2)
- caller_p99_ms=453.59ms vs baseline 242.66ms (z=+5.8)
- pod api-gateway-6488bc94fb-f9qqs CPU limit is 25m vs declared 500m
- pod api-gateway-6488bc94fb-zzt9d CPU limit is 25m vs declared 500m

| Candidate | Score | Why |
|---|---|---|
| api-gateway | 8.449 | severity 0.60; its dependencies ['product-service', 'order-service'] are also anomalous (likely a victim); earliest onset; pod api-gateway-6488bc94fb-f9qqs CPU limit is 25m vs declared 500m; pod api-gateway-6488bc94fb-zzt9d CPU limit is 25m vs declared 500m; its calls to product-service take 316ms longer than product-service itself needs to serve them (caller-side or network problem); its calls to… |
| product-service | 2.325 | severity 0.74; its own server-side latency/errors are normal; the degradation is only visible from callers (network or caller-side problem); no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service']; earliest onset |
| order-service | -2.181 | severity 0.26; its own server-side latency/errors are normal; the degradation is only visible from callers (network or caller-side problem); its dependencies ['product-service'] are also anomalous (likely a victim); explains anomalies in callers ['api-gateway'] |

### 6. Decision

Action **resource_restore** (fallback rolling_restart) · confidence 0.807 · priority 5.396

- api-gateway: cpu throttle at severity 0.60; business impact 9/10 -> priority 5.40. Playbook: resource_restore, fallback rolling_restart.
- Confidence in resource_restore: 0.81 (history 0.85 over 2 attempt(s) x RCA 0.95 x blast factor 1.00).
- Decision: resource_restore on api-gateway (fallback rolling_restart, confidence 0.81).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| resource_restore | api-gateway | success | yes | 2.1s | resized 2 container(s) in place to {'api-gateway': {'requests': {'cpu': '100m', 'memory': '64Mi'}, 'limits': {'cpu': '500m', 'memory': '192Mi'}}} |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"restored_pods": []}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 0 failed of 1282 requests (0.0%) · user p99 478.4 ms over 64 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 07:06:21 | STRATEGY | api-gateway | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose cpu_throttle on api-gateway: High‑impact cpu_throttle on api‑gateway, many dependencies, long idle time since last run, and not yet used in this campaign. |
| 07:06:40 | PREFLIGHT | api-gateway | GO: api-gateway at 2/2 Ready, system 100% healthy. Blast radius: 0 dependent service(s) , ~100% of users, risk MEDIUM. |
| 07:06:40 | INJECT | api-gateway | Injected cpu_throttle into api-gateway: In-place resize of every replica's CPU limit to a starvation value (api-gateway-6488bc94fb-f9qqs,api-gateway-6488bc94fb-zzt9d). |
| 07:06:54 | DETECT | product-service | Anomaly confirmed on product-service 15s after injection: pattern matches high latency. Isolation Forest score +0.064 (threshold +0.103), severity 0.58. Evidence: p99_latency_ms=15.83ms vs baseline 16.09ms (z=-0.0); caller_p99_ms=157.37ms vs baseline 16.56ms (z=+9.4). LSTM forecast for the next 60s: score +0.055 (still anomalous). |
| 07:07:00 | RCA | api-gateway | Root cause localised to api-gateway (cpu throttle, confidence 95%). product-service, order-service deviate because requests from api-gateway stopped reaching them. Change evidence: pod api-gateway-6488bc94fb-f9qqs CPU limit is 25m vs declared 500m; pod api-gateway-6488bc94fb-zzt9d CPU limit is 25m vs declared 500m. |
| 07:07:00 | DECIDE | api-gateway | Confidence in resource_restore: 0.81 (history 0.85 over 2 attempt(s) x RCA 0.95 x blast factor 1.00). Decision: resource_restore on api-gateway (fallback rolling_restart, confidence 0.81). |
| 07:07:00 | REMEDIATE | api-gateway | Executing resource_restore on api-gateway. |
| 07:07:02 | REMEDIATE | api-gateway | resource_restore succeeded in 2.1s — resized 2 container(s) in place to {'api-gateway': {'requests': {'cpu': '100m', 'memory': '64Mi'}, 'limits': {'cpu': '500m', 'memory': '192Mi'}}}. |
| 07:07:06 | VERIFY | api-gateway | api-gateway verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 8ms). |
| 07:07:55 | TEARDOWN | api-gateway | Round teardown for api-gateway: no residual fault found; autoscaler returned to declared bounds. |
| 07:08:05 | RECOVERED | api-gateway | api-gateway recovered: detected in 14.83s, mitigated in 7.49s, fully back to its normal operating band in 50.01s (target 90s — MET). Users saw 0 failed requests out of 1282 (0.0%) during the incident. |

## Campaign-level events

| Time (UTC) | Phase | Message |
|---|---|---|
| 07:00:49 | CAMPAIGN | Campaign c-20261011-070048-d4fe starting: 5 rounds (auto, auto, auto, auto, auto). |
| 07:08:05 | SUMMARY | Campaign completed: resilience score 99.6/100 — EXCELLENT — every fault detected, diagnosed and healed within SLA. |
