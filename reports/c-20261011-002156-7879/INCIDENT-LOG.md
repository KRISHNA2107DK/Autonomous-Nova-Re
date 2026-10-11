# Incident log — campaign `c-20261011-002156-7879`

**Resilience score 87.2/100** — GOOD — reliable recovery with minor SLA or diagnosis misses

| Component | Points |
|---|---|
| recovery sla | 28.0 |
| detection sla | 20.0 |
| remediation effectiveness | 17.0 |
| diagnosis accuracy | 13.5 |
| user protection | 8.71 |

| # | Fault | Target | Status | TTD | TTR | Users failed |
|---|---|---|---|---|---|---|
| 1 | cpu_throttle | payment-service | RECOVERED | 14.82s | 50.01s | 0.0% |
| 2 | network_partition | api-gateway | RECOVERED | 14.83s | 40.0s | 31.5% |
| 3 | pod_deletion | api-gateway | RECOVERED | 4.81s | 15.0s | 0.0% |
| 4 | latency_injection | order-service | MITIGATED | 14.81s | — | 0.7% |
| 5 | replica_reduction | product-service | RECOVERED | 4.82s | 20.0s | 0.0% |

## Round 1 — cpu_throttle → payment-service  ·  **RECOVERED**

TTD 14.82s (target 35s, met) · TTM 7.71s · TTR 50.01s (target 90s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: High business impact (10), critical dependents (api-gateway, order-service), never tried, and CPU throttling stresses payment-service most severely.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | network_partition | api-gateway | 0.635 | never | — |
| 2 | pod_deletion | api-gateway | 0.635 | never | — |
| 3 | replica_reduction | api-gateway | 0.635 | never | — |
| 4 | cpu_throttle | payment-service | 0.585 | never | — |
| 5 | latency_injection | payment-service | 0.585 | never | — |
| 6 | cpu_throttle | product-service | 0.565 | never | — |
| 7 | latency_injection | product-service | 0.565 | never | — |
| 8 | network_partition | product-service | 0.565 | never | — |
| 9 | pod_deletion | product-service | 0.565 | never | — |
| 10 | replica_reduction | product-service | 0.565 | never | — |

### 2. Safety check before injecting

Decision **GO** · risk HIGH · system health 100.0% · target ready 2/2 · load 1.09× baseline · dependents api-gateway, order-service · users possibly affected 100%

### 3. Failure injected

`cpu_throttle` on **payment-service** at 00:22:16 UTC — succeeded

Details: `{"pods": ["payment-service-b6f875b8d-6jctr", "payment-service-b6f875b8d-njmg9"], "cpu_limit": "25m", "original": {"payment-service-b6f875b8d-6jctr": {"payment-service": {"requests": {"cpu": "100m", "memory": "96Mi"}, "limits": {"cpu": "500m", "memory": "256Mi"}}}, "payment-service-b6f875b8d-njmg9": {"payment-service": {"requests": {"cpu": "100m", "memory": "96Mi"}, "limits": {"cpu": "500m", "memory": "256Mi"}}}}}`

### 4. Detection

Confirmed at 00:22:31 UTC on **payment-service** as `high_latency` · severity 0.8857 · Isolation Forest score -0.0141 (threshold 0.1031) · flags: iforest, zscore:p99_latency_ms, zscore:caller_p99_ms

Evidence:
- p99_latency_ms=545.00ms vs baseline 246.49ms (z=+8.1)
- caller_p99_ms=761.25ms vs baseline 246.52ms (z=+13.9)

LSTM 60 s forecast: score -0.0415 (still anomalous)

### 5. Root-cause analysis

Origin **payment-service** · type `cpu_throttle` · confidence 0.95 · call path api-gateway → payment-service · affected api-gateway, order-service, payment-service

> Root cause localised to payment-service (cpu throttle, confidence 95%). api-gateway, order-service also deviate as callers of payment-service: its failure propagates to them. Change evidence: pod payment-service-b6f875b8d-6jctr CPU limit is 25m vs declared 500m; pod payment-service-b6f875b8d-njmg9 CPU limit is 25m vs declared 500m.

Evidence:
- p99_latency_ms=545.00ms vs baseline 246.49ms (z=+8.1)
- caller_p99_ms=761.25ms vs baseline 246.52ms (z=+13.9)
- pod payment-service-b6f875b8d-6jctr CPU limit is 25m vs declared 500m
- pod payment-service-b6f875b8d-njmg9 CPU limit is 25m vs declared 500m

| Candidate | Score | Why |
|---|---|---|
| payment-service | 9.121 | severity 0.89; no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service']; earliest onset; pod payment-service-b6f875b8d-6jctr CPU limit is 25m vs declared 500m; pod payment-service-b6f875b8d-njmg9 CPU limit is 25m vs declared 500m |
| order-service | 1.348 | severity 0.90; its dependencies ['payment-service'] are also anomalous (likely a victim); explains anomalies in callers ['api-gateway']; earliest onset |
| api-gateway | 0.994 | severity 0.87; its dependencies ['order-service', 'payment-service'] are also anomalous (likely a victim); earliest onset |

### 6. Decision

Action **resource_restore** (fallback rolling_restart) · confidence 0.565 · priority 8.854

- payment-service: cpu throttle at severity 0.89; business impact 10/10 -> priority 8.85. Playbook: resource_restore, fallback rolling_restart.
- Confidence in resource_restore: 0.56 (prior 0.70 (no history yet) x RCA 0.95 x blast factor 0.85).
- Decision: resource_restore on payment-service (fallback rolling_restart, confidence 0.56).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| resource_restore | payment-service | success | yes | 2.2s | resized 2 container(s) in place to {'payment-service': {'requests': {'cpu': '100m', 'memory': '96Mi'}, 'limits': {'cpu': '500m', 'memory': '256Mi'}}} |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"restored_pods": []}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 0 failed of 1282 requests (0.0%) · user p99 736.3 ms over 64 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 00:21:57 | STRATEGY | payment-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose cpu_throttle on payment-service: High business impact (10), critical dependents (api-gateway, order-service), never tried, and CPU throttling stresses payment-service most severely. |
| 00:22:16 | PREFLIGHT | payment-service | GO: payment-service at 2/2 Ready, system 100% healthy. Blast radius: 2 dependent service(s) ['api-gateway', 'order-service'], ~100% of users, risk HIGH. |
| 00:22:16 | INJECT | payment-service | Injected cpu_throttle into payment-service: In-place resize of every replica's CPU limit to a starvation value (payment-service-b6f875b8d-6jctr,payment-service-b6f875b8d-njmg9). |
| 00:22:31 | DETECT | payment-service | Anomaly confirmed on payment-service 15s after injection: pattern matches high latency. Isolation Forest score -0.014 (threshold +0.103), severity 0.89. Evidence: p99_latency_ms=545.00ms vs baseline 246.49ms (z=+8.1); caller_p99_ms=761.25ms vs baseline 246.52ms (z=+13.9). Also deviating: api-gateway, order-service. LSTM forecast for the next 60s: score -0.042 (still anomalous). |
| 00:22:36 | RCA | payment-service | Root cause localised to payment-service (cpu throttle, confidence 95%). api-gateway, order-service also deviate as callers of payment-service: its failure propagates to them. Change evidence: pod payment-service-b6f875b8d-6jctr CPU limit is 25m vs declared 500m; pod payment-service-b6f875b8d-njmg9 CPU limit is 25m vs declared 500m. |
| 00:22:36 | DECIDE | payment-service | Confidence in resource_restore: 0.56 (prior 0.70 (no history yet) x RCA 0.95 x blast factor 0.85). Decision: resource_restore on payment-service (fallback rolling_restart, confidence 0.56). |
| 00:22:36 | REMEDIATE | payment-service | Executing resource_restore on payment-service. |
| 00:22:38 | REMEDIATE | payment-service | resource_restore succeeded in 2.2s — resized 2 container(s) in place to {'payment-service': {'requests': {'cpu': '100m', 'memory': '96Mi'}, 'limits': {'cpu': '500m', 'memory': '256Mi'}}}. |
| 00:22:43 | VERIFY | payment-service | payment-service verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 7ms). |
| 00:23:31 | TEARDOWN | payment-service | Round teardown for payment-service: no residual fault found; autoscaler returned to declared bounds. |
| 00:23:41 | RECOVERED | payment-service | payment-service recovered: detected in 14.82s, mitigated in 7.71s, fully back to its normal operating band in 50.01s (target 90s — MET). Users saw 0 failed requests out of 1282 (0.0%) during the incident. |

## Round 2 — network_partition → api-gateway  ·  **RECOVERED**

TTD 14.83s (target 30s, met) · TTM 5.87s · TTR 40.0s (target 90s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: Inject network partition on api-gateway, highest impact service never tried, maximizes learning about critical traffic path.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | network_partition | api-gateway | 0.635 | never | — |
| 2 | pod_deletion | api-gateway | 0.635 | never | — |
| 3 | replica_reduction | api-gateway | 0.635 | never | — |
| 4 | latency_injection | product-service | 0.565 | never | — |
| 5 | network_partition | product-service | 0.565 | never | — |
| 6 | pod_deletion | product-service | 0.565 | never | — |
| 7 | replica_reduction | product-service | 0.565 | never | — |
| 8 | latency_injection | order-service | 0.56 | never | — |
| 9 | network_partition | order-service | 0.56 | never | — |
| 10 | pod_deletion | order-service | 0.56 | never | — |

### 2. Safety check before injecting

Decision **GO** · risk MEDIUM · system health 100.0% · target ready 2/2 · load 1.06× baseline · dependents none · users possibly affected 100%

### 3. Failure injected

`network_partition` on **api-gateway** at 00:24:06 UTC — succeeded

Details: `{"policy": "chaos-isolate-api-gateway", "effect": "deny all ingress + egress", "conntrack_flush": {"ok": true, "pod_ips": ["10.244.0.23", "10.244.0.25"], "agents": {"chaos-agent-zm457": true}}}`

### 4. Detection

Confirmed at 00:24:21 UTC on **api-gateway** as `network_partition` · severity 0.9741 · Isolation Forest score -0.035 (threshold 0.1031) · flags: iforest, zscore:caller_error_rate, zscore:caller_p99_ms, metrics_unreachable

Evidence:
- replicas ready 2/2 (declared minimum 2)
- metrics endpoint unreachable on 100% of pods
- caller_error_rate=0.0% vs baseline 0.0% (z=+0.0)
- request_rate=14.54 req/s vs baseline 20.00 req/s (z=-2.7)
- pods are running (no container restarts) but cannot be reached over the pod network

LSTM 60 s forecast: score -0.045 (still anomalous)

### 5. Root-cause analysis

Origin **api-gateway** · type `network_partition` · confidence 0.95 · call path api-gateway · affected api-gateway, product-service, order-service, payment-service, notification-service

> Root cause localised to api-gateway (network partition, confidence 95%). product-service, order-service, payment-service, notification-service deviate because requests from api-gateway stopped reaching them. Change evidence: NetworkPolicy 'chaos-isolate-api-gateway' denies all Ingress/Egress traffic for pods of api-gateway, created 20s ago; 12 ERROR log lines in the last 60s, e.g. 'upstream error (order-service)'.

Evidence:
- replicas ready 2/2 (declared minimum 2)
- metrics endpoint unreachable on 100% of pods
- caller_error_rate=0.0% vs baseline 0.0% (z=+0.0)
- request_rate=14.54 req/s vs baseline 20.00 req/s (z=-2.7)
- pods are running (no container restarts) but cannot be reached over the pod network
- NetworkPolicy 'chaos-isolate-api-gateway' denies all Ingress/Egress traffic for pods of api-gateway, created 20s ago
- 12 ERROR log lines in the last 60s, e.g. 'upstream error (order-service)'

| Candidate | Score | Why |
|---|---|---|
| api-gateway | 8.007 | severity 0.97; no anomalous dependency explains it; earliest onset; structural fault on the service itself; NetworkPolicy 'chaos-isolate-api-gateway' denies all Ingress/Egress traffic for pods of api-gateway, created 20s ago; 12 ERROR log lines in the last 60s, e.g. 'upstream error (order-service)' |
| product-service | 2.182 | severity 0.42; only symptom is reduced traffic — consistent with an upstream failure; no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service']; earliest onset |
| payment-service | 2.145 | severity 0.40; only symptom is reduced traffic — consistent with an upstream failure; no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service']; earliest onset |
| notification-service | 1.911 | severity 0.43; only symptom is reduced traffic — consistent with an upstream failure; no anomalous dependency explains it; explains anomalies in callers ['api-gateway']; earliest onset |
| order-service | 1.271 | severity 0.49; only symptom is reduced traffic — consistent with an upstream failure; no anomalous dependency explains it; explains anomalies in callers ['api-gateway'] |

### 6. Decision

Action **network_policy_rollback** (fallback rolling_restart) · confidence 0.665 · priority 8.761

- api-gateway: network partition at severity 0.97; business impact 9/10 -> priority 8.76. Playbook: network_policy_rollback, fallback rolling_restart.
- Confidence in network_policy_rollback: 0.67 (prior 0.70 (no history yet) x RCA 0.95 x blast factor 1.00).
- Decision: network_policy_rollback on api-gateway (fallback rolling_restart, confidence 0.67).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| network_policy_rollback | api-gateway | success | yes | 0.0s | removed 1 isolating NetworkPolicy(ies): chaos-isolate-api-gateway |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"policy": "chaos-isolate-api-gateway", "deleted": false}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 323 failed of 1025 requests (31.5%) · user p99 4146.4 ms over 54 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 00:23:47 | STRATEGY | api-gateway | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose network_partition on api-gateway: Inject network partition on api-gateway, highest impact service never tried, maximizes learning about critical traffic path. |
| 00:24:06 | PREFLIGHT | api-gateway | GO: api-gateway at 2/2 Ready, system 100% healthy. Blast radius: 0 dependent service(s) , ~100% of users, risk MEDIUM. |
| 00:24:06 | INJECT | api-gateway | Injected network_partition into api-gateway: Deny-all NetworkPolicy selecting the service's pods (chaos-isolate-api-gateway). |
| 00:24:21 | DETECT | api-gateway | Anomaly confirmed on api-gateway 15s after injection: pattern matches network partition. Isolation Forest score -0.035 (threshold +0.103), severity 0.97. Evidence: replicas ready 2/2 (declared minimum 2); metrics endpoint unreachable on 100% of pods; caller_error_rate=0.0% vs baseline 0.0% (z=+0.0). Also deviating: product-service, payment-service, notification-service. LSTM forecast for the next 60s: score -0.045 (still anomalous). |
| 00:24:26 | RCA | api-gateway | Root cause localised to api-gateway (network partition, confidence 95%). product-service, order-service, payment-service, notification-service deviate because requests from api-gateway stopped reaching them. Change evidence: NetworkPolicy 'chaos-isolate-api-gateway' denies all Ingress/Egress traffic for pods of api-gateway, created 20s ago; 12 ERROR log lines in the last 60s, e.g. 'upstream error (order-service)'. |
| 00:24:27 | DECIDE | api-gateway | Confidence in network_policy_rollback: 0.67 (prior 0.70 (no history yet) x RCA 0.95 x blast factor 1.00). Decision: network_policy_rollback on api-gateway (fallback rolling_restart, confidence 0.67). |
| 00:24:27 | REMEDIATE | api-gateway | Executing network_policy_rollback on api-gateway. |
| 00:24:27 | REMEDIATE | api-gateway | network_policy_rollback succeeded in 0.0s — removed 1 isolating NetworkPolicy(ies): chaos-isolate-api-gateway. |
| 00:24:31 | VERIFY | api-gateway | api-gateway verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 6ms). |
| 00:25:11 | TEARDOWN | api-gateway | Round teardown for api-gateway: no residual fault found; autoscaler returned to declared bounds. |
| 00:25:21 | RECOVERED | api-gateway | api-gateway recovered: detected in 14.83s, mitigated in 5.87s, fully back to its normal operating band in 40.0s (target 90s — MET). Users saw 323 failed requests out of 1025 (31.5%) during the incident. |

## Round 3 — pod_deletion → api-gateway  ·  **RECOVERED**

TTD 4.81s (target 25s, met) · TTM 9.45s · TTR 15.0s (target 90s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: High‑impact api‑gateway pod deletion affects all traffic and many dependents, and this fault/service combo hasn’t been tried yet in the campaign.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | latency_injection | product-service | 0.565 | never | — |
| 2 | pod_deletion | product-service | 0.565 | never | — |
| 3 | replica_reduction | product-service | 0.565 | never | — |
| 4 | latency_injection | order-service | 0.56 | never | — |
| 5 | pod_deletion | order-service | 0.56 | never | — |
| 6 | replica_reduction | order-service | 0.56 | never | — |
| 7 | pod_deletion | api-gateway | 0.385 | never | — |
| 8 | replica_reduction | api-gateway | 0.385 | never | — |
| 9 | latency_injection | notification-service | 0.38 | never | — |
| 10 | pod_deletion | notification-service | 0.38 | never | — |

### 2. Safety check before injecting

Decision **GO** · risk MEDIUM · system health 100.0% · target ready 2/2 · load 1.06× baseline · dependents none · users possibly affected 100%

### 3. Failure injected

`pod_deletion` on **api-gateway** at 00:25:46 UTC — succeeded

Details: `{"pod": "api-gateway-6f5c8cf68b-dnbgh", "pod_ip": "10.244.0.25", "ready_pods_before": 2}`

### 4. Detection

Confirmed at 00:25:51 UTC on **api-gateway** as `pod_crash` · severity 0.4 · Isolation Forest score 0.1251 (threshold 0.1031) · flags: replicas_lost

Evidence:
- replicas ready 2/2 (declared minimum 2)
- Ready pod(s) api-gateway-6f5c8cf68b-dnbgh disappeared without a scale-down or rollout
- caller_error_rate=0.0% vs baseline 0.0% (z=+0.0)

LSTM 60 s forecast: score 0.1216 (returning to normal)

### 5. Root-cause analysis

Origin **api-gateway** · type `pod_crash` · confidence 0.918 · call path api-gateway · affected api-gateway

> Root cause localised to api-gateway (pod crash, confidence 92%). No other service deviates; the fault is contained to api-gateway. Change evidence: Pod api-gateway-6f5c8cf68b-dnbgh: Killing — Stopping container api-gateway.

Evidence:
- replicas ready 2/2 (declared minimum 2)
- Ready pod(s) api-gateway-6f5c8cf68b-dnbgh disappeared without a scale-down or rollout
- caller_error_rate=0.0% vs baseline 0.0% (z=+0.0)
- Pod api-gateway-6f5c8cf68b-dnbgh: Killing — Stopping container api-gateway

| Candidate | Score | Why |
|---|---|---|
| api-gateway | 3.98 | severity 0.24; no anomalous dependency explains it; earliest onset; structural fault on the service itself; Pod api-gateway-6f5c8cf68b-dnbgh: Killing — Stopping container api-gateway |

### 6. Decision

Action **hpa_scaleout** (fallback rolling_restart) · confidence 0.643 · priority 2.16

- api-gateway: pod crash at severity 0.24; business impact 9/10 -> priority 2.16. Playbook: hpa_scaleout, fallback rolling_restart.
- Confidence in hpa_scaleout: 0.64 (prior 0.70 (no history yet) x RCA 0.92 x blast factor 1.00).
- Decision: hpa_scaleout on api-gateway (fallback rolling_restart, confidence 0.64).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| hpa_scaleout | api-gateway | success | yes | 4.1s | autoscaler 2-4 -> 3-4; 2 -> 3 Ready replicas |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"reversible": false, "note": "Kubernetes reschedules deleted pods by itself"}` · autoscaler `{"from": {"minReplicas": 3, "maxReplicas": 4}, "to": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 0 failed of 380 requests (0.0%) · user p99 243.5 ms over 19 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 00:25:27 | STRATEGY | api-gateway | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose pod_deletion on api-gateway: High‑impact api‑gateway pod deletion affects all traffic and many dependents, and this fault/service combo hasn’t been tried yet in the campaign. |
| 00:25:46 | PREFLIGHT | api-gateway | GO: api-gateway at 2/2 Ready, system 100% healthy. Blast radius: 0 dependent service(s) , ~100% of users, risk MEDIUM. |
| 00:25:46 | INJECT | api-gateway | Injected pod_deletion into api-gateway: Force-delete one Ready pod (grace period 0) (api-gateway-6f5c8cf68b-dnbgh). |
| 00:25:51 | DETECT | api-gateway | Anomaly confirmed on api-gateway 5s after injection: pattern matches pod crash. Isolation Forest score +0.125 (threshold +0.103), severity 0.40. Evidence: replicas ready 2/2 (declared minimum 2); Ready pod(s) api-gateway-6f5c8cf68b-dnbgh disappeared without a scale-down or rollout; caller_error_rate=0.0% vs baseline 0.0% (z=+0.0). LSTM forecast for the next 60s: score +0.122 (returning to normal). |
| 00:25:56 | RCA | api-gateway | Root cause localised to api-gateway (pod crash, confidence 92%). No other service deviates; the fault is contained to api-gateway. Change evidence: Pod api-gateway-6f5c8cf68b-dnbgh: Killing — Stopping container api-gateway. |
| 00:25:56 | DECIDE | api-gateway | Confidence in hpa_scaleout: 0.64 (prior 0.70 (no history yet) x RCA 0.92 x blast factor 1.00). Decision: hpa_scaleout on api-gateway (fallback rolling_restart, confidence 0.64). |
| 00:25:56 | REMEDIATE | api-gateway | Executing hpa_scaleout on api-gateway. |
| 00:26:00 | REMEDIATE | api-gateway | hpa_scaleout succeeded in 4.1s — autoscaler 2-4 -> 3-4; 2 -> 3 Ready replicas. |
| 00:26:04 | VERIFY | api-gateway | api-gateway verified functional: 3/3 replicas Ready and 5 consecutive user-path probes OK (last 8ms). |
| 00:26:06 | TEARDOWN | api-gateway | Round teardown for api-gateway: no residual fault found; autoscaler returned to declared bounds. |
| 00:26:16 | RECOVERED | api-gateway | api-gateway recovered: detected in 4.81s, mitigated in 9.45s, fully back to its normal operating band in 15.0s (target 90s — MET). Users saw 0 failed requests out of 380 (0.0%) during the incident. |

## Round 4 — latency_injection → order-service  ·  **MITIGATED**

TTD 14.81s (target 35s, met) · TTM 16.8s · TTR — (target 120s, missed) · healed by primary · diagnosis wrong, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: High business impact (8) on order-service, a critical upstream for api-gateway, with a fresh latency fault not yet used in this campaign.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | latency_injection | product-service | 0.565 | never | — |
| 2 | replica_reduction | product-service | 0.565 | never | — |
| 3 | latency_injection | order-service | 0.56 | never | — |
| 4 | replica_reduction | order-service | 0.56 | never | — |
| 5 | replica_reduction | api-gateway | 0.385 | never | — |
| 6 | latency_injection | notification-service | 0.38 | never | — |
| 7 | latency_injection | payment-service | 0.335 | never | — |
| 8 | cpu_throttle | product-service | 0.165 | never | — |
| 9 | network_partition | product-service | 0.165 | never | — |
| 10 | pod_deletion | product-service | 0.165 | never | — |

### 2. Safety check before injecting

Decision **GO** · risk MEDIUM · system health 100.0% · target ready 2/2 · load 1.0× baseline · dependents api-gateway · users possibly affected 100%

### 3. Failure injected

`latency_injection` on **order-service** at 00:26:41 UTC — succeeded

Details: `{"pod": "order-service-6d874b5f49-84lmr", "delay": "200ms", "jitter": "50ms", "command": "tc qdisc replace dev eth0 root netem delay 200ms 50ms distribution normal", "replicas_ready": 2}`

### 4. Detection

Confirmed at 00:26:56 UTC on **order-service** as `high_latency` · severity 0.9372 · Isolation Forest score -0.041 (threshold 0.1031) · flags: iforest, zscore:p99_latency_ms, zscore:caller_p99_ms

Evidence:
- p99_latency_ms=855.00ms vs baseline 246.95ms (z=+16.4)
- caller_p99_ms=2600.00ms vs baseline 246.99ms (z=+25.0)

LSTM 60 s forecast: score -0.0376 (still anomalous)

### 5. Root-cause analysis

Origin **product-service** · type `high_latency` · confidence 0.583 · call path api-gateway → product-service · affected api-gateway, product-service, order-service, payment-service

> Root cause localised to product-service (high latency, confidence 58%). api-gateway, order-service also deviate as callers of product-service: its failure propagates to them. payment-service also deviate without a dependency explaining it (lower-ranked candidates). Signal: p99_latency_ms=22.60ms vs baseline 16.09ms (z=+0.4); caller_p99_ms=222.36ms vs baseline 16.56ms (z=+13.7).

Evidence:
- p99_latency_ms=22.60ms vs baseline 16.09ms (z=+0.4)
- caller_p99_ms=222.36ms vs baseline 16.56ms (z=+13.7)

| Candidate | Score | Why |
|---|---|---|
| product-service | 4.172 | severity 0.91; no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service']; earliest onset |
| order-service | 3.921 | severity 0.94; its dependencies ['product-service', 'payment-service'] are also anomalous (likely a victim); explains anomalies in callers ['api-gateway']; earliest onset; Pod order-service-6d874b5f49-84lmr: Unhealthy — Readiness probe failed: Get "http://10.244.0.27:8002/ready": context deadline exceeded (Client.Timeout exceeded while aw; its calls to payment-service take 478ms longer than paymen… |
| payment-service | 2.012 | severity 0.58; its own server-side latency/errors are normal; the degradation is only visible from callers (network or caller-side problem); no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service']; earliest onset |
| api-gateway | 1.111 | severity 0.93; its dependencies ['product-service', 'order-service', 'payment-service'] are also anomalous (likely a victim); earliest onset |

### 6. Decision

Action **traffic_reroute** (fallback rolling_restart) · confidence 0.347 · priority 5.465

- product-service: high latency at severity 0.91; business impact 6/10 -> priority 5.46. Playbook: traffic_reroute, fallback rolling_restart.
- Confidence in traffic_reroute: 0.35 (prior 0.70 (no history yet) x RCA 0.58 x blast factor 0.85).
- Decision: traffic_reroute on product-service (fallback rolling_restart, confidence 0.35).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| traffic_reroute | product-service | success | yes | 11.2s | quarantined product-service-6947766bf9-6rm4v (worst replica by live telemetry (p99=107ms, next worst score 7 vs 107)); traffic now on 2 healthy replica(s) |

### 8. Teardown and user impact

Fault still present at teardown: **yes** · reverse `{"pod": "order-service-6d874b5f49-84lmr", "removed": true, "note": "netem qdisc deleted"}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 30 failed of 4002 requests (0.7%) · user p99 4872.0 ms over 200 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 00:26:23 | STRATEGY | order-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose latency_injection on order-service: High business impact (8) on order-service, a critical upstream for api-gateway, with a fresh latency fault not yet used in this campaign. |
| 00:26:41 | PREFLIGHT | order-service | GO: order-service at 2/2 Ready, system 100% healthy. Blast radius: 1 dependent service(s) ['api-gateway'], ~100% of users, risk MEDIUM. |
| 00:26:41 | INJECT | order-service | Injected latency_injection into order-service: tc netem egress delay on one replica (order-service-6d874b5f49-84lmr). |
| 00:26:56 | DETECT | order-service | Anomaly confirmed on order-service 15s after injection: pattern matches high latency. Isolation Forest score -0.041 (threshold +0.103), severity 0.94. Evidence: p99_latency_ms=855.00ms vs baseline 246.95ms (z=+16.4); caller_p99_ms=2600.00ms vs baseline 246.99ms (z=+25.0). Also deviating: api-gateway, product-service. LSTM forecast for the next 60s: score -0.038 (still anomalous). |
| 00:27:01 | RCA | product-service | Root cause localised to product-service (high latency, confidence 58%). api-gateway, order-service also deviate as callers of product-service: its failure propagates to them. payment-service also deviate without a dependency explaining it (lower-ranked candidates). Signal: p99_latency_ms=22.60ms vs baseline 16.09ms (z=+0.4); caller_p99_ms=222.36ms vs baseline 16.56ms (z=+13.7). |
| 00:27:01 | DECIDE | product-service | Confidence in traffic_reroute: 0.35 (prior 0.70 (no history yet) x RCA 0.58 x blast factor 0.85). Decision: traffic_reroute on product-service (fallback rolling_restart, confidence 0.35). |
| 00:27:01 | REMEDIATE | product-service | Executing traffic_reroute on product-service. |
| 00:27:13 | REMEDIATE | product-service | traffic_reroute succeeded in 11.2s — quarantined product-service-6947766bf9-6rm4v (worst replica by live telemetry (p99=107ms, next worst score 7 vs 107)); traffic now on 2 healthy replica(s). |
| 00:27:17 | VERIFY | product-service | product-service verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 5ms). |
| 00:29:51 | TEARDOWN | order-service | Round teardown for order-service: the fault was still physically present and has now been reverted; autoscaler returned to declared bounds. |

## Round 5 — replica_reduction → product-service  ·  **RECOVERED**

TTD 4.82s (target 35s, met) · TTM 11.44s · TTR 20.0s (target 120s, met) · healed by primary · diagnosis correct, classification correct

### 1. Why this experiment

Chosen by **LLM agent (groq/openai/gpt-oss-120b)**: First replica_reduction on high‑traffic product-service, never tried before and impacts multiple dependents, maximizing new resilience insight.

| # | Fault | Service | Rule score | Minutes since last tried | Last outcome |
|---|---|---|---|---|---|
| 1 | replica_reduction | product-service | 0.565 | never | — |
| 2 | replica_reduction | api-gateway | 0.385 | never | — |
| 3 | replica_reduction | order-service | 0.31 | never | — |
| 4 | cpu_throttle | product-service | 0.165 | never | — |
| 5 | latency_injection | product-service | 0.165 | never | — |
| 6 | network_partition | product-service | 0.165 | never | — |
| 7 | pod_deletion | product-service | 0.165 | never | — |
| 8 | replica_reduction | payment-service | 0.091 | 49.2 | recovered_within_sla |
| 9 | cpu_throttle | notification-service | -0.02 | never | — |
| 10 | latency_injection | notification-service | -0.02 | never | — |

### 2. Safety check before injecting

Decision **GO** · risk HIGH · system health 100.0% · target ready 2/2 · load 0.91× baseline · dependents api-gateway, order-service · users possibly affected 100%

### 3. Failure injected

`replica_reduction` on **product-service** at 00:30:41 UTC — succeeded

Details: `{"hpa": "product-service-hpa", "original": {"minReplicas": 2, "maxReplicas": 4}, "patched_to": {"minReplicas": 1, "maxReplicas": 1}}`

### 4. Detection

Confirmed at 00:30:46 UTC on **product-service** as `replica_exhaustion` · severity 0.5 · Isolation Forest score 0.1111 (threshold 0.1031) · flags: capacity_below_baseline

Evidence:
- replicas ready 1/1 (declared minimum 2)
- autoscaler bounds min=1 max=1 below declared minimum 2

LSTM 60 s forecast: score 0.1344 (returning to normal)

### 5. Root-cause analysis

Origin **product-service** · type `replica_exhaustion` · confidence 0.96 · call path api-gateway → product-service · affected product-service

> Root cause localised to product-service (replica exhaustion, confidence 96%). No other service deviates; the fault is contained to product-service. Change evidence: HPA bounds 1-1 are below the declared 2-4; Pod product-service-6947766bf9-vtpbd: Killing — Stopping container product-service.

Evidence:
- replicas ready 1/1 (declared minimum 2)
- autoscaler bounds min=1 max=1 below declared minimum 2
- HPA bounds 1-1 are below the declared 2-4
- Pod product-service-6947766bf9-vtpbd: Killing — Stopping container product-service

| Candidate | Score | Why |
|---|---|---|
| product-service | 7.6 | severity 0.80; no anomalous dependency explains it; earliest onset; structural fault on the service itself; HPA bounds 1-1 are below the declared 2-4; Pod product-service-6947766bf9-vtpbd: Killing — Stopping container product-service |

### 6. Decision

Action **hpa_scaleout** (fallback resource_restore) · confidence 0.571 · priority 4.8

- product-service: replica exhaustion at severity 0.80; business impact 6/10 -> priority 4.80. Playbook: hpa_scaleout, fallback resource_restore.
- Confidence in hpa_scaleout: 0.57 (prior 0.70 (no history yet) x RCA 0.96 x blast factor 0.85).
- Decision: hpa_scaleout on product-service (fallback resource_restore, confidence 0.57).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| hpa_scaleout | product-service | success | yes | 6.1s | autoscaler 1-1 -> 3-4; 1 -> 3 Ready replicas |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"restored": false, "note": "autoscaler already at or above declared bounds"}` · autoscaler `{"from": {"minReplicas": 3, "maxReplicas": 4}, "to": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 0 failed of 481 requests (0.0%) · user p99 242.9 ms over 24 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 00:30:08 | STRATEGY | product-service | Chaos Planner — LLM agent (groq/openai/gpt-oss-120b) chose replica_reduction on product-service: First replica_reduction on high‑traffic product-service, never tried before and impacts multiple dependents, maximizing new resilience insight. |
| 00:30:16 | PREFLIGHT | product-service | Waiting for steady state before injecting: steady state not met: api-gateway, product-service, order-service, payment-service currently anomalous. |
| 00:30:41 | PREFLIGHT | product-service | GO: product-service at 2/2 Ready, system 100% healthy. Blast radius: 2 dependent service(s) ['api-gateway', 'order-service'], ~100% of users, risk HIGH. |
| 00:30:41 | INJECT | product-service | Injected replica_reduction into product-service: Clamp HPA to min=max=1 (product-service-hpa). |
| 00:30:46 | DETECT | product-service | Anomaly confirmed on product-service 5s after injection: pattern matches replica exhaustion. Isolation Forest score +0.111 (threshold +0.103), severity 0.50. Evidence: replicas ready 1/1 (declared minimum 2); autoscaler bounds min=1 max=1 below declared minimum 2. LSTM forecast for the next 60s: score +0.134 (returning to normal). |
| 00:30:51 | RCA | product-service | Root cause localised to product-service (replica exhaustion, confidence 96%). No other service deviates; the fault is contained to product-service. Change evidence: HPA bounds 1-1 are below the declared 2-4; Pod product-service-6947766bf9-vtpbd: Killing — Stopping container product-service. |
| 00:30:51 | DECIDE | product-service | Confidence in hpa_scaleout: 0.57 (prior 0.70 (no history yet) x RCA 0.96 x blast factor 0.85). Decision: hpa_scaleout on product-service (fallback resource_restore, confidence 0.57). |
| 00:30:51 | REMEDIATE | product-service | Executing hpa_scaleout on product-service. |
| 00:30:57 | REMEDIATE | product-service | hpa_scaleout succeeded in 6.1s — autoscaler 1-1 -> 3-4; 1 -> 3 Ready replicas. |
| 00:31:01 | VERIFY | product-service | product-service verified functional: 3/3 replicas Ready and 5 consecutive user-path probes OK (last 5ms). |
| 00:31:06 | TEARDOWN | product-service | Round teardown for product-service: no residual fault found; autoscaler returned to declared bounds. |
| 00:31:16 | RECOVERED | product-service | product-service recovered: detected in 4.82s, mitigated in 11.44s, fully back to its normal operating band in 20.0s (target 120s — MET). Users saw 0 failed requests out of 481 (0.0%) during the incident. |

## Campaign-level events

| Time (UTC) | Phase | Message |
|---|---|---|
| 00:21:56 | CAMPAIGN | Campaign c-20261011-002156-7879 starting: 5 rounds (auto, auto, auto, auto, auto). |
| 00:31:16 | SUMMARY | Campaign completed: resilience score 87.2/100 — GOOD — reliable recovery with minor SLA or diagnosis misses. |
