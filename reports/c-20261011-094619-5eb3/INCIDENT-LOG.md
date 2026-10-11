# Incident log — campaign `c-20261011-094619-5eb3`

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
| 1 | replica_reduction | payment-service | RECOVERED | 4.77s | 20.0s | 0.0% |
| 2 | network_partition | api-gateway | RECOVERED | 14.8s | 45.0s | 34.2% |
| 3 | cpu_throttle | notification-service | UNDETECTED | — | — | 0.0% |
| 4 | latency_injection | payment-service | RECOVERED | 14.86s | 49.99s | 0.2% |
| 5 | pod_deletion | product-service | RECOVERED | 4.85s | 19.99s | 0.0% |

## Round 1 — replica_reduction → payment-service  ·  **RECOVERED**

TTD 4.77s (target 35s, met) · TTM 11.48s · TTR 20.0s (target 120s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: Payment service replica reduction hasn't been tried in over 5 hours, has highest business impact and critical dependents, maximizing insight into recovery under load.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | network_partition | api-gateway | 0.477 | 215.6 | recovered_within_sla |
| 2 | replica_reduction | payment-service | 0.459 | 327.5 | recovered_within_sla |
| 3 | cpu_throttle | api-gateway | 0.456 | 159.7 | recovered_within_sla |
| 4 | latency_injection | product-service | 0.44 | 332.8 | recovered_within_sla |
| 5 | replica_reduction | api-gateway | 0.434 | 114.4 | recovered_within_sla |
| 6 | latency_injection | api-gateway | 0.433 | 111.6 | recovered_within_sla |
| 7 | cpu_throttle | payment-service | 0.429 | 220.2 | recovered_within_sla |
| 8 | latency_injection | payment-service | 0.408 | 165.2 | recovered_within_sla |
| 9 | pod_deletion | product-service | 0.407 | 216.7 | recovered_within_sla |
| 10 | replica_reduction | order-service | 0.403 | 218.4 | recovered_within_sla |

### 2. Safety check before injecting

Decision **GO** · risk HIGH · system health 100.0% · target ready 2/2 · load 1.06× baseline · dependents api-gateway, order-service · users possibly affected 100%

### 3. Failure injected

`replica_reduction` on **payment-service** at 09:46:43 UTC — succeeded

Details: `{"hpa": "payment-service-hpa", "original": {"minReplicas": 2, "maxReplicas": 4}, "patched_to": {"minReplicas": 1, "maxReplicas": 1}}`

### 4. Detection

Confirmed at 09:46:48 UTC on **payment-service** as `replica_exhaustion` · severity 0.8 · Isolation Forest score 0.147 (threshold 0.1031) · flags: capacity_below_baseline, metrics_unreachable

Evidence:
- replicas ready 1/1 (declared minimum 2)
- metrics endpoint unreachable on 50% of pods
- autoscaler bounds min=1 max=1 below declared minimum 2

LSTM 60 s forecast: score 0.1474 (returning to normal)

### 5. Root-cause analysis

Origin **payment-service** · type `replica_exhaustion` · confidence 0.96 · call path api-gateway → payment-service · affected payment-service

> Root cause localised to payment-service (replica exhaustion, confidence 96%). No other service deviates; the fault is contained to payment-service. Change evidence: HPA bounds 1-1 are below the declared 2-4; Pod payment-service-64d79d469d-2hzcm: Killing — Stopping container payment-service.

Evidence:
- replicas ready 1/1 (declared minimum 2)
- metrics endpoint unreachable on 50% of pods
- autoscaler bounds min=1 max=1 below declared minimum 2
- HPA bounds 1-1 are below the declared 2-4
- Pod payment-service-64d79d469d-2hzcm: Killing — Stopping container payment-service
- Pod payment-service-64d79d469d-2hzcm: Unhealthy — Readiness probe failed: Get "http://10.244.0.49:8003/ready": dial tcp 10.244.0.49:8003: connect: connection refused

| Candidate | Score | Why |
|---|---|---|
| payment-service | 7.6 | severity 0.80; no anomalous dependency explains it; earliest onset; structural fault on the service itself; HPA bounds 1-1 are below the declared 2-4; Pod payment-service-64d79d469d-2hzcm: Killing — Stopping container payment-service; Pod payment-service-64d79d469d-2hzcm: Unhealthy — Readiness probe failed: Get "http://10.244.0.49:8003/ready": dial tcp 10.244.0.49:8003: connect: connection refused |

### 6. Decision

Action **hpa_scaleout** (fallback resource_restore) · confidence 0.694 · priority 8.0

- payment-service: replica exhaustion at severity 0.80; business impact 10/10 -> priority 8.00. Playbook: hpa_scaleout, fallback resource_restore.
- Confidence in hpa_scaleout: 0.69 (history 0.85 over 2 attempt(s) x RCA 0.96 x blast factor 0.85).
- Decision: hpa_scaleout on payment-service (fallback resource_restore, confidence 0.69).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| hpa_scaleout | payment-service | success | yes | 6.1s | autoscaler 1-1 -> 3-4; 1 -> 3 Ready replicas |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"restored": false, "note": "autoscaler already at or above declared bounds"}` · autoscaler `{"from": {"minReplicas": 3, "maxReplicas": 4}, "to": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 0 failed of 482 requests (0.0%) · user p99 244.3 ms over 24 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 09:46:25 | STRATEGY | payment-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose replica_reduction on payment-service: Payment service replica reduction hasn't been tried in over 5 hours, has highest business impact and critical dependents, maximizing insight into recovery under load. |
| 09:46:43 | PREFLIGHT | payment-service | GO: payment-service at 2/2 Ready, system 100% healthy. Blast radius: 2 dependent service(s) ['api-gateway', 'order-service'], ~100% of users, risk HIGH. |
| 09:46:43 | INJECT | payment-service | Injected replica_reduction into payment-service: Clamp HPA to min=max=1 (payment-service-hpa). |
| 09:46:48 | DETECT | payment-service | Anomaly confirmed on payment-service 5s after injection: pattern matches replica exhaustion. Isolation Forest score +0.147 (threshold +0.103), severity 0.80. Evidence: replicas ready 1/1 (declared minimum 2); metrics endpoint unreachable on 50% of pods; autoscaler bounds min=1 max=1 below declared minimum 2. LSTM forecast for the next 60s: score +0.147 (returning to normal). |
| 09:46:53 | RCA | payment-service | Root cause localised to payment-service (replica exhaustion, confidence 96%). No other service deviates; the fault is contained to payment-service. Change evidence: HPA bounds 1-1 are below the declared 2-4; Pod payment-service-64d79d469d-2hzcm: Killing — Stopping container payment-service. |
| 09:46:53 | DECIDE | payment-service | Confidence in hpa_scaleout: 0.69 (history 0.85 over 2 attempt(s) x RCA 0.96 x blast factor 0.85). Decision: hpa_scaleout on payment-service (fallback resource_restore, confidence 0.69). |
| 09:46:53 | REMEDIATE | payment-service | Executing hpa_scaleout on payment-service (step 1, primary). |
| 09:46:59 | REMEDIATE | payment-service | hpa_scaleout succeeded in 6.1s — autoscaler 1-1 -> 3-4; 1 -> 3 Ready replicas. |
| 09:47:03 | VERIFY | payment-service | payment-service verified functional: 3/3 replicas Ready and 5 consecutive user-path probes OK (last 9ms). |
| 09:47:13 | TEARDOWN | payment-service | Round teardown for payment-service: no residual fault found; autoscaler returned to declared bounds. |
| 09:47:23 | RECOVERED | payment-service | payment-service recovered: detected in 4.77s, mitigated in 11.48s, fully back to its normal operating band in 20.0s (target 120s — MET). Users saw 0 failed requests out of 482 (0.0%) during the incident. |

## Round 2 — network_partition → api-gateway  ·  **RECOVERED**

TTD 14.8s (target 30s, met) · TTM 5.69s · TTR 45.0s (target 90s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: High‑impact network partition on the degraded api‑gateway, long idle time and many dependents, and a fault/service pair not yet used in this campaign.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | network_partition | api-gateway | 0.477 | 216.7 | recovered_within_sla |
| 2 | cpu_throttle | api-gateway | 0.456 | 160.8 | recovered_within_sla |
| 3 | latency_injection | product-service | 0.44 | 333.9 | recovered_within_sla |
| 4 | latency_injection | api-gateway | 0.434 | 112.7 | recovered_within_sla |
| 5 | pod_deletion | product-service | 0.408 | 217.7 | recovered_within_sla |
| 6 | pod_deletion | api-gateway | 0.393 | 52.2 | recovered_within_sla |
| 7 | network_partition | order-service | 0.383 | 163.6 | recovered_within_sla |
| 8 | cpu_throttle | notification-service | 0.38 | never | — |
| 9 | network_partition | notification-service | 0.38 | never | — |
| 10 | latency_injection | order-service | 0.378 | 151.7 | recovered_within_sla |

### 2. Safety check before injecting

Decision **GO** · risk MEDIUM · system health 100.0% · target ready 2/2 · load 1.0× baseline · dependents none · users possibly affected 100%

### 3. Failure injected

`network_partition` on **api-gateway** at 09:47:48 UTC — succeeded

Details: `{"policy": "chaos-isolate-api-gateway", "effect": "deny all ingress + egress", "conntrack_flush": {"ok": true, "pod_ips": ["10.244.0.18", "10.244.0.56"], "agents": {"chaos-agent-l7fcx": true}}}`

### 4. Detection

Confirmed at 09:48:03 UTC on **api-gateway** as `network_partition` · severity 0.978 · Isolation Forest score -0.0649 (threshold 0.1031) · flags: iforest, zscore:caller_error_rate, zscore:caller_p99_ms, metrics_unreachable

Evidence:
- replicas ready 2/2 (declared minimum 2)
- metrics endpoint unreachable on 100% of pods
- caller_error_rate=16.5% vs baseline 0.0% (z=+8.3)
- request_rate=12.40 req/s vs baseline 20.00 req/s (z=-3.8)
- pods are running (no container restarts) but cannot be reached over the pod network

LSTM 60 s forecast: score -0.0763 (still anomalous)

### 5. Root-cause analysis

Origin **api-gateway** · type `network_partition` · confidence 0.95 · call path api-gateway · affected api-gateway, product-service, order-service, payment-service, notification-service

> Root cause localised to api-gateway (network partition, confidence 95%). product-service, order-service, payment-service, notification-service deviate because requests from api-gateway stopped reaching them. Change evidence: NetworkPolicy 'chaos-isolate-api-gateway' denies all Ingress/Egress traffic for pods of api-gateway, created 20s ago; 18 ERROR log lines in the last 60s, e.g. 'upstream error (payment-service)'.

Evidence:
- replicas ready 2/2 (declared minimum 2)
- metrics endpoint unreachable on 100% of pods
- caller_error_rate=16.5% vs baseline 0.0% (z=+8.3)
- request_rate=12.40 req/s vs baseline 20.00 req/s (z=-3.8)
- pods are running (no container restarts) but cannot be reached over the pod network
- NetworkPolicy 'chaos-isolate-api-gateway' denies all Ingress/Egress traffic for pods of api-gateway, created 20s ago
- 18 ERROR log lines in the last 60s, e.g. 'upstream error (payment-service)'

| Candidate | Score | Why |
|---|---|---|
| api-gateway | 8.046 | severity 0.98; no anomalous dependency explains it; earliest onset; structural fault on the service itself; NetworkPolicy 'chaos-isolate-api-gateway' denies all Ingress/Egress traffic for pods of api-gateway, created 20s ago; 18 ERROR log lines in the last 60s, e.g. 'upstream error (payment-service)' |
| product-service | 2.301 | severity 0.48; only symptom is reduced traffic — consistent with an upstream failure; no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service']; earliest onset |
| order-service | 1.976 | severity 0.46; only symptom is reduced traffic — consistent with an upstream failure; no anomalous dependency explains it; explains anomalies in callers ['api-gateway']; earliest onset |
| notification-service | 1.353 | severity 0.53; only symptom is reduced traffic — consistent with an upstream failure; no anomalous dependency explains it; explains anomalies in callers ['api-gateway'] |
| payment-service | 1.315 | severity 0.36; only symptom is reduced traffic — consistent with an upstream failure; no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service'] |

### 6. Decision

Action **network_policy_rollback** (fallback rolling_restart) · confidence 0.807 · priority 8.8

- api-gateway: network partition at severity 0.98; business impact 9/10 -> priority 8.80. Playbook: network_policy_rollback, fallback rolling_restart.
- Confidence in network_policy_rollback: 0.81 (history 0.85 over 2 attempt(s) x RCA 0.95 x blast factor 1.00).
- Decision: network_policy_rollback on api-gateway (fallback rolling_restart, confidence 0.81).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| network_policy_rollback | api-gateway | success | yes | 0.1s | removed 1 isolating NetworkPolicy(ies): chaos-isolate-api-gateway |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"policy": "chaos-isolate-api-gateway", "deleted": false}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 410 failed of 1197 requests (34.2%) · user p99 5350.0 ms over 59 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 09:47:30 | STRATEGY | api-gateway | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose network_partition on api-gateway: High‑impact network partition on the degraded api‑gateway, long idle time and many dependents, and a fault/service pair not yet used in this campaign. |
| 09:47:48 | PREFLIGHT | api-gateway | GO: api-gateway at 2/2 Ready, system 100% healthy. Blast radius: 0 dependent service(s) , ~100% of users, risk MEDIUM. |
| 09:47:49 | INJECT | api-gateway | Injected network_partition into api-gateway: Deny-all NetworkPolicy selecting the service's pods (chaos-isolate-api-gateway). |
| 09:48:03 | DETECT | api-gateway | Anomaly confirmed on api-gateway 15s after injection: pattern matches network partition. Isolation Forest score -0.065 (threshold +0.103), severity 0.98. Evidence: replicas ready 2/2 (declared minimum 2); metrics endpoint unreachable on 100% of pods; caller_error_rate=16.5% vs baseline 0.0% (z=+8.3). Also deviating: product-service, order-service. LSTM forecast for the next 60s: score -0.076 (still anomalous). |
| 09:48:08 | RCA | api-gateway | Root cause localised to api-gateway (network partition, confidence 95%). product-service, order-service, payment-service, notification-service deviate because requests from api-gateway stopped reaching them. Change evidence: NetworkPolicy 'chaos-isolate-api-gateway' denies all Ingress/Egress traffic for pods of api-gateway, created 20s ago; 18 ERROR log lines in the last 60s, e.g. 'upstream error (payment-service)'. |
| 09:48:08 | DECIDE | api-gateway | Confidence in network_policy_rollback: 0.81 (history 0.85 over 2 attempt(s) x RCA 0.95 x blast factor 1.00). Decision: network_policy_rollback on api-gateway (fallback rolling_restart, confidence 0.81). |
| 09:48:08 | REMEDIATE | api-gateway | Executing network_policy_rollback on api-gateway (step 1, primary). |
| 09:48:08 | REMEDIATE | api-gateway | network_policy_rollback succeeded in 0.1s — removed 1 isolating NetworkPolicy(ies): chaos-isolate-api-gateway. |
| 09:48:13 | VERIFY | api-gateway | api-gateway verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 10ms). |
| 09:48:58 | TEARDOWN | api-gateway | Round teardown for api-gateway: no residual fault found; autoscaler returned to declared bounds. |
| 09:49:08 | RECOVERED | api-gateway | api-gateway recovered: detected in 14.8s, mitigated in 5.69s, fully back to its normal operating band in 45.0s (target 90s — MET). Users saw 410 failed requests out of 1197 (34.2%) during the incident. |

## Round 3 — cpu_throttle → notification-service  ·  **UNDETECTED**

TTD — (target 35s, missed) · TTM — · TTR — (target 90s, missed) · healed by — · diagnosis wrong, classification wrong

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: Never‑tried cpu_throttle on notification-service, a degraded low‑impact service, adds fresh insight and respects campaign variety.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | latency_injection | product-service | 0.441 | 335.6 | recovered_within_sla |
| 2 | pod_deletion | product-service | 0.408 | 219.5 | recovered_within_sla |
| 3 | cpu_throttle | notification-service | 0.38 | never | — |
| 4 | latency_injection | order-service | 0.378 | 153.5 | recovered_within_sla |
| 5 | cpu_throttle | order-service | 0.36 | 116.2 | recovered_within_sla |
| 6 | cpu_throttle | product-service | 0.329 | 59.8 | recovered_within_sla |
| 7 | pod_deletion | order-service | 0.319 | 53.1 | recovered_within_sla |
| 8 | pod_deletion | notification-service | 0.295 | 543.8 | recovered_within_sla |
| 9 | cpu_throttle | api-gateway | 0.207 | 162.6 | recovered_within_sla |
| 10 | latency_injection | api-gateway | 0.184 | 114.4 | recovered_within_sla |

### 2. Safety check before injecting

Decision **GO** · risk MEDIUM · system health 100.0% · target ready 1/1 · load 1.01× baseline · dependents api-gateway · users possibly affected 100%

### 3. Failure injected

`cpu_throttle` on **notification-service** at 09:49:33 UTC — succeeded

Details: `{"pods": ["notification-service-9f4db9ffd-4lt75"], "cpu_limit": "25m", "original": {"notification-service-9f4db9ffd-4lt75": {"notification-service": {"requests": {"cpu": "25m", "memory": "64Mi"}, "limits": {"cpu": "250m", "memory": "192Mi"}}}}}`

### 4. Detection

Not detected within the detection window.

### 7. Remediation

No remediation was needed or attempted.

### 8. Teardown and user impact

Fault still present at teardown: **yes** · reverse `{"restored_pods": ["notification-service-9f4db9ffd-4lt75"]}` · autoscaler `{"unchanged": {"minReplicas": 1, "maxReplicas": 3}}`

Users: 0 failed of 2099 requests (0.0%) · user p99 242.0 ms over 105 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 09:49:15 | STRATEGY | notification-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose cpu_throttle on notification-service: Never‑tried cpu_throttle on notification-service, a degraded low‑impact service, adds fresh insight and respects campaign variety. |
| 09:49:33 | PREFLIGHT | notification-service | GO: notification-service at 1/1 Ready, system 100% healthy. Blast radius: 1 dependent service(s) ['api-gateway'], ~100% of users, risk MEDIUM. |
| 09:49:33 | INJECT | notification-service | Injected cpu_throttle into notification-service: In-place resize of every replica's CPU limit to a starvation value (notification-service-9f4db9ffd-4lt75). |
| 09:51:08 | DETECT | notification-service | No anomaly confirmed within 90s of injecting cpu_throttle into notification-service. Reporting UNDETECTED. |
| 09:51:08 | TEARDOWN | notification-service | Round teardown for notification-service: the fault was still physically present and has now been reverted; autoscaler returned to declared bounds. |

## Round 4 — latency_injection → payment-service  ·  **RECOVERED**

TTD 14.86s (target 35s, met) · TTM 17.38s · TTR 49.99s (target 120s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: High‑impact latency injection on payment-service (impact 10) with multiple dependents and not yet used in this campaign.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | latency_injection | product-service | 0.441 | 337.8 | recovered_within_sla |
| 2 | pod_deletion | product-service | 0.409 | 221.7 | recovered_within_sla |
| 3 | latency_injection | order-service | 0.379 | 155.6 | recovered_within_sla |
| 4 | pod_deletion | order-service | 0.321 | 55.2 | recovered_within_sla |
| 5 | latency_injection | api-gateway | 0.186 | 116.6 | recovered_within_sla |
| 6 | latency_injection | payment-service | 0.16 | 170.2 | recovered_within_sla |
| 7 | pod_deletion | api-gateway | 0.147 | 56.2 | recovered_within_sla |
| 8 | pod_deletion | payment-service | 0.134 | 113.2 | recovered_within_sla |
| 9 | pod_deletion | notification-service | 0.046 | 545.9 | recovered_within_sla |
| 10 | replica_reduction | order-service | 0.005 | 223.4 | recovered_within_sla |

### 2. Safety check before injecting

Decision **GO** · risk HIGH · system health 100.0% · target ready 2/2 · load 1.06× baseline · dependents api-gateway, order-service · users possibly affected 100%

### 3. Failure injected

`latency_injection` on **payment-service** at 09:51:43 UTC — succeeded

Details: `{"pod": "payment-service-64d79d469d-2mbsp", "delay": "200ms", "jitter": "50ms", "command": "tc qdisc replace dev eth0 root netem delay 200ms 50ms distribution normal", "replicas_ready": 2}`

### 4. Detection

Confirmed at 09:51:58 UTC on **payment-service** as `high_latency` · severity 0.9215 · Isolation Forest score 0.0061 (threshold 0.1031) · flags: iforest, zscore:p99_latency_ms, zscore:caller_p99_ms

Evidence:
- p99_latency_ms=3849.96ms vs baseline 246.49ms (z=+25.0)
- caller_p99_ms=3818.73ms vs baseline 246.52ms (z=+25.0)

LSTM 60 s forecast: score -0.0239 (still anomalous)

### 5. Root-cause analysis

Origin **payment-service** · type `high_latency` · confidence 0.856 · call path api-gateway → payment-service · affected api-gateway, order-service, payment-service

> Root cause localised to payment-service (high latency, confidence 86%). api-gateway, order-service also deviate as callers of payment-service: its failure propagates to them. Signal: p99_latency_ms=3849.96ms vs baseline 246.49ms (z=+25.0); caller_p99_ms=3818.73ms vs baseline 246.52ms (z=+25.0).

Evidence:
- p99_latency_ms=3849.96ms vs baseline 246.49ms (z=+25.0)
- caller_p99_ms=3818.73ms vs baseline 246.52ms (z=+25.0)

| Candidate | Score | Why |
|---|---|---|
| payment-service | 4.195 | severity 0.92; no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service']; earliest onset |
| order-service | 1.899 | severity 0.92; its dependencies ['payment-service'] are also anomalous (likely a victim); explains anomalies in callers ['api-gateway']; earliest onset; 2 ERROR log lines in the last 60s, e.g. 'dependency failure (payment-service)' |
| api-gateway | 0.862 | severity 0.93; its dependencies ['order-service', 'payment-service'] are also anomalous (likely a victim); 1 ERROR log lines in the last 60s, e.g. 'request failed' |

### 6. Decision

Action **traffic_reroute** (fallback rolling_restart) · confidence 0.655 · priority 9.224

- payment-service: high latency at severity 0.92; business impact 10/10 -> priority 9.22. Playbook: traffic_reroute, fallback rolling_restart.
- Confidence in traffic_reroute: 0.66 (history 0.90 over 4 attempt(s) x RCA 0.86 x blast factor 0.85).
- Decision: traffic_reroute on payment-service (fallback rolling_restart, confidence 0.66).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| traffic_reroute | payment-service | success | yes | 11.2s | quarantined payment-service-64d79d469d-2mbsp (worst replica by live telemetry (p99=4936ms, next worst score 247 vs 4936)); traffic now on 2 healthy replica(s) |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"pod": "payment-service-64d79d469d-2mbsp", "note": "pod no longer exists (replaced)"}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 2 failed of 1280 requests (0.2%) · user p99 2857.1 ms over 64 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 09:51:27 | STRATEGY | payment-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose latency_injection on payment-service: High‑impact latency injection on payment-service (impact 10) with multiple dependents and not yet used in this campaign. |
| 09:51:43 | PREFLIGHT | payment-service | GO: payment-service at 2/2 Ready, system 100% healthy. Blast radius: 2 dependent service(s) ['api-gateway', 'order-service'], ~100% of users, risk HIGH. |
| 09:51:43 | INJECT | payment-service | Injected latency_injection into payment-service: tc netem egress delay on one replica (payment-service-64d79d469d-2mbsp). |
| 09:51:58 | DETECT | payment-service | Anomaly confirmed on payment-service 15s after injection: pattern matches high latency. Isolation Forest score +0.006 (threshold +0.103), severity 0.92. Evidence: p99_latency_ms=3849.96ms vs baseline 246.49ms (z=+25.0); caller_p99_ms=3818.73ms vs baseline 246.52ms (z=+25.0). Also deviating: order-service. LSTM forecast for the next 60s: score -0.024 (still anomalous). |
| 09:52:03 | RCA | payment-service | Root cause localised to payment-service (high latency, confidence 86%). api-gateway, order-service also deviate as callers of payment-service: its failure propagates to them. Signal: p99_latency_ms=3849.96ms vs baseline 246.49ms (z=+25.0); caller_p99_ms=3818.73ms vs baseline 246.52ms (z=+25.0). |
| 09:52:03 | DECIDE | payment-service | Confidence in traffic_reroute: 0.66 (history 0.90 over 4 attempt(s) x RCA 0.86 x blast factor 0.85). Decision: traffic_reroute on payment-service (fallback rolling_restart, confidence 0.66). |
| 09:52:03 | REMEDIATE | payment-service | Executing traffic_reroute on payment-service (step 1, primary). |
| 09:52:14 | REMEDIATE | payment-service | traffic_reroute succeeded in 11.2s — quarantined payment-service-64d79d469d-2mbsp (worst replica by live telemetry (p99=4936ms, next worst score 247 vs 4936)); traffic now on 2 healthy replica(s). |
| 09:52:19 | VERIFY | payment-service | payment-service verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 6ms). |
| 09:52:58 | TEARDOWN | payment-service | Round teardown for payment-service: no residual fault found; autoscaler returned to declared bounds. |
| 09:53:08 | RECOVERED | payment-service | payment-service recovered: detected in 14.86s, mitigated in 17.38s, fully back to its normal operating band in 49.99s (target 120s — MET). Users saw 2 failed requests out of 1280 (0.2%) during the incident. |

## Round 5 — pod_deletion → product-service  ·  **RECOVERED**

TTD 4.85s (target 25s, met) · TTM 11.35s · TTR 19.99s (target 90s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: Pod deletion on product-service, a high‑traffic core service not yet tested this campaign, with long time since last try and strong downstream dependents.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | pod_deletion | product-service | 0.41 | 223.5 | recovered_within_sla |
| 2 | pod_deletion | order-service | 0.322 | 57.1 | recovered_within_sla |
| 3 | pod_deletion | api-gateway | 0.148 | 58.0 | recovered_within_sla |
| 4 | pod_deletion | payment-service | 0.135 | 115.1 | recovered_within_sla |
| 5 | pod_deletion | notification-service | 0.046 | 547.8 | recovered_within_sla |
| 6 | latency_injection | product-service | 0.042 | 339.6 | recovered_within_sla |
| 7 | replica_reduction | order-service | 0.005 | 225.2 | recovered_within_sla |
| 8 | replica_reduction | product-service | -0.011 | 167.6 | recovered_within_sla |
| 9 | network_partition | order-service | -0.015 | 169.3 | recovered_within_sla |
| 10 | latency_injection | order-service | -0.02 | 157.5 | recovered_within_sla |

### 2. Safety check before injecting

Decision **GO** · risk HIGH · system health 100.0% · target ready 2/2 · load 0.96× baseline · dependents api-gateway, order-service · users possibly affected 100%

### 3. Failure injected

`pod_deletion` on **product-service** at 09:53:33 UTC — succeeded

Details: `{"pod": "product-service-78f8dcb767-b475x", "pod_ip": "10.244.0.52", "ready_pods_before": 2}`

### 4. Detection

Confirmed at 09:53:38 UTC on **product-service** as `pod_crash` · severity 0.4563 · Isolation Forest score 0.0719 (threshold 0.1031) · flags: replicas_lost

Evidence:
- replicas ready 2/2 (declared minimum 2)
- Ready pod(s) product-service-78f8dcb767-b475x disappeared without a scale-down or rollout
- caller_error_rate=0.0% vs baseline 0.0% (z=+0.0)

LSTM 60 s forecast: score 0.0451 (returning to normal)

### 5. Root-cause analysis

Origin **product-service** · type `pod_crash` · confidence 0.924 · call path api-gateway → product-service · affected product-service

> Root cause localised to product-service (pod crash, confidence 92%). No other service deviates; the fault is contained to product-service. Change evidence: Pod product-service-78f8dcb767-b475x: Killing — Stopping container product-service; Pod product-service-78f8dcb767-b475x: Unhealthy — Readiness probe failed: Get "http://10.244.0.52:8001/ready": dial tcp 10.244.0.52:8001: connect: connection refused.

Evidence:
- replicas ready 2/2 (declared minimum 2)
- Ready pod(s) product-service-78f8dcb767-b475x disappeared without a scale-down or rollout
- caller_error_rate=0.0% vs baseline 0.0% (z=+0.0)
- Pod product-service-78f8dcb767-b475x: Killing — Stopping container product-service
- Pod product-service-78f8dcb767-b475x: Unhealthy — Readiness probe failed: Get "http://10.244.0.52:8001/ready": dial tcp 10.244.0.52:8001: connect: connection refused
- Pod product-service-78f8dcb767-lb2t6: Unhealthy — Startup probe failed: Get "http://10.244.0.65:8001/health": dial tcp 10.244.0.65:8001: connect: connection refused

| Candidate | Score | Why |
|---|---|---|
| product-service | 4.048 | severity 0.27; no anomalous dependency explains it; earliest onset; structural fault on the service itself; Pod product-service-78f8dcb767-b475x: Killing — Stopping container product-service; Pod product-service-78f8dcb767-b475x: Unhealthy — Readiness probe failed: Get "http://10.244.0.52:8001/ready": dial tcp 10.244.0.52:8001: connect: connection refused; Pod product-service-78f8dcb767-lb2t6: Unh… |

### 6. Decision

Action **hpa_scaleout** (fallback rolling_restart) · confidence 0.628 · priority 1.643

- product-service: pod crash at severity 0.27; business impact 6/10 -> priority 1.64. Playbook: hpa_scaleout, fallback rolling_restart.
- Confidence in hpa_scaleout: 0.63 (history 0.80 over 1 attempt(s) x RCA 0.92 x blast factor 0.85).
- Decision: hpa_scaleout on product-service (fallback rolling_restart, confidence 0.63).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| hpa_scaleout | product-service | success | yes | 6.1s | autoscaler 2-4 -> 3-4; 2 -> 3 Ready replicas |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"reversible": false, "note": "Kubernetes reschedules deleted pods by itself"}` · autoscaler `{"from": {"minReplicas": 3, "maxReplicas": 4}, "to": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 0 failed of 480 requests (0.0%) · user p99 242.3 ms over 24 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 09:53:15 | STRATEGY | product-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose pod_deletion on product-service: Pod deletion on product-service, a high‑traffic core service not yet tested this campaign, with long time since last try and strong downstream dependents. |
| 09:53:33 | PREFLIGHT | product-service | GO: product-service at 2/2 Ready, system 100% healthy. Blast radius: 2 dependent service(s) ['api-gateway', 'order-service'], ~100% of users, risk HIGH. |
| 09:53:33 | INJECT | product-service | Injected pod_deletion into product-service: Force-delete one Ready pod (grace period 0) (product-service-78f8dcb767-b475x). |
| 09:53:38 | DETECT | product-service | Anomaly confirmed on product-service 5s after injection: pattern matches pod crash. Isolation Forest score +0.072 (threshold +0.103), severity 0.46. Evidence: replicas ready 2/2 (declared minimum 2); Ready pod(s) product-service-78f8dcb767-b475x disappeared without a scale-down or rollout; caller_error_rate=0.0% vs baseline 0.0% (z=+0.0). LSTM forecast for the next 60s: score +0.045 (returning to normal). |
| 09:53:43 | RCA | product-service | Root cause localised to product-service (pod crash, confidence 92%). No other service deviates; the fault is contained to product-service. Change evidence: Pod product-service-78f8dcb767-b475x: Killing — Stopping container product-service; Pod product-service-78f8dcb767-b475x: Unhealthy — Readiness probe failed: Get "http://10.244.0.52:8001/ready": dial tcp 10.244.0.52:8001: connect: connection refused. |
| 09:53:43 | DECIDE | product-service | Confidence in hpa_scaleout: 0.63 (history 0.80 over 1 attempt(s) x RCA 0.92 x blast factor 0.85). Decision: hpa_scaleout on product-service (fallback rolling_restart, confidence 0.63). |
| 09:53:43 | REMEDIATE | product-service | Executing hpa_scaleout on product-service (step 1, primary). |
| 09:53:49 | REMEDIATE | product-service | hpa_scaleout succeeded in 6.1s — autoscaler 2-4 -> 3-4; 2 -> 3 Ready replicas. |
| 09:53:53 | VERIFY | product-service | product-service verified functional: 3/3 replicas Ready and 5 consecutive user-path probes OK (last 5ms). |
| 09:53:58 | TEARDOWN | product-service | Round teardown for product-service: no residual fault found; autoscaler returned to declared bounds. |
| 09:54:08 | RECOVERED | product-service | product-service recovered: detected in 4.85s, mitigated in 11.35s, fully back to its normal operating band in 19.99s (target 90s — MET). Users saw 0 failed requests out of 480 (0.0%) during the incident. |

## Campaign-level events

| Time (UTC) | Phase | Message |
|---|---|---|
| 09:46:19 | CAMPAIGN | Campaign c-20261011-094619-5eb3 starting: 5 rounds (auto, auto, auto, auto, auto). |
| 09:54:08 | SUMMARY | Campaign completed: resilience score 80.6/100 — GOOD — reliable recovery with minor SLA or diagnosis misses. |
