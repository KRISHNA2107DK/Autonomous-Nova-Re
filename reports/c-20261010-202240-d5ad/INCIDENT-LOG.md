# Incident log — campaign `c-20261010-202240-d5ad`

**Resilience score 98.9/100** — EXCELLENT — every fault detected, diagnosed and healed within SLA

| Component | Points |
|---|---|
| recovery sla | 35.0 |
| detection sla | 20.0 |
| remediation effectiveness | 20.0 |
| diagnosis accuracy | 15.0 |
| user protection | 8.91 |

| # | Fault | Target | Status | TTD | TTR | Users failed |
|---|---|---|---|---|---|---|
| 1 | pod_deletion | payment-service | RECOVERED | 4.86s | 20.01s | 0.0% |
| 2 | cpu_throttle | product-service | RECOVERED | 9.86s | 50.0s | 1.1% |
| 3 | network_partition | api-gateway | RECOVERED | 9.86s | 40.0s | 25.9% |
| 4 | latency_injection | order-service | RECOVERED | 14.85s | 49.99s | 0.4% |
| 5 | replica_reduction | payment-service | RECOVERED | 4.86s | 20.01s | 0.0% |

## Round 1 — pod_deletion → payment-service  ·  **RECOVERED**

TTD 4.86s (target 25s, met) · TTM 11.33s · TTR 20.01s (target 90s, met) · healed by primary · diagnosis correct, classification correct

### 2. Safety check before injecting

Decision **GO** · risk HIGH · system health 100.0% · target ready 2/2 · load 1.01× baseline · dependents api-gateway, order-service · users possibly affected 100%

### 3. Failure injected

`pod_deletion` on **payment-service** at 20:23:00 UTC — succeeded

Details: `{"pod": "payment-service-8478f885-klnwj", "pod_ip": "10.244.0.72", "ready_pods_before": 2}`

### 4. Detection

Confirmed at 20:23:05 UTC on **payment-service** as `pod_crash` · severity 0.4173 · Isolation Forest score 0.0936 (threshold 0.1031) · flags: replicas_lost

Evidence:
- replicas ready 2/2 (declared minimum 2)
- Ready pod(s) payment-service-8478f885-klnwj disappeared without a scale-down or rollout
- caller_error_rate=0.0% vs baseline 0.0% (z=+0.0)

### 5. Root-cause analysis

Origin **payment-service** · type `pod_crash` · confidence 0.92 · call path api-gateway → payment-service · affected payment-service

> Root cause localised to payment-service (pod crash, confidence 92%). No other service deviates; the fault is contained to payment-service. Change evidence: Pod payment-service-8478f885-4pftp: Unhealthy — Startup probe failed: Get "http://10.244.0.73:8003/health": dial tcp 10.244.0.73:8003: connect: connection refused; Pod payment-service-8478f885-klnwj: Killing — Stopping container payment-service.

Evidence:
- replicas ready 2/2 (declared minimum 2)
- Ready pod(s) payment-service-8478f885-klnwj disappeared without a scale-down or rollout
- caller_error_rate=0.0% vs baseline 0.0% (z=+0.0)
- Pod payment-service-8478f885-4pftp: Unhealthy — Startup probe failed: Get "http://10.244.0.73:8003/health": dial tcp 10.244.0.73:8003: connect: connection refused
- Pod payment-service-8478f885-klnwj: Killing — Stopping container payment-service

| Candidate | Score | Why |
|---|---|---|
| payment-service | 4.001 | severity 0.25; no anomalous dependency explains it; earliest onset; structural fault on the service itself; Pod payment-service-8478f885-4pftp: Unhealthy — Startup probe failed: Get "http://10.244.0.73:8003/health": dial tcp 10.244.0.73:8003: connect: connection refused; Pod payment-service-8478f885-klnwj: Killing — Stopping container payment-service |

### 6. Decision

Action **hpa_scaleout** (fallback rolling_restart) · confidence 0.547 · priority 2.504

- payment-service: pod crash at severity 0.25; business impact 10/10 -> priority 2.50. Playbook: hpa_scaleout, fallback rolling_restart.
- Confidence in hpa_scaleout: 0.55 (prior 0.70 (no history yet) x RCA 0.92 x blast factor 0.85).
- Decision: hpa_scaleout on payment-service (fallback rolling_restart, confidence 0.55).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| hpa_scaleout | payment-service | success | yes | 6.1s | autoscaler 2-4 -> 3-4; 2 -> 3 Ready replicas |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"reversible": false, "note": "Kubernetes reschedules deleted pods by itself"}` · autoscaler `{"from": {"minReplicas": 3, "maxReplicas": 4}, "to": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 0 failed of 479 requests (0.0%) · user p99 242.5 ms over 24 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 20:22:45 | STRATEGY | payment-service | pod_deletion: selected payment-service (score 0.596: blast 0.5, impact 1.0, users 0.35, coverage penalty 0.0). |
| 20:23:00 | PREFLIGHT | payment-service | GO: payment-service at 2/2 Ready, system 100% healthy. Blast radius: 2 dependent service(s) ['api-gateway', 'order-service'], ~100% of users, risk HIGH. |
| 20:23:00 | INJECT | payment-service | Injected pod_deletion into payment-service: Force-delete one Ready pod (grace period 0) (payment-service-8478f885-klnwj). |
| 20:23:05 | DETECT | payment-service | Anomaly confirmed on payment-service 5s after injection: pattern matches pod crash. Isolation Forest score +0.094 (threshold +0.103), severity 0.42. Evidence: replicas ready 2/2 (declared minimum 2); Ready pod(s) payment-service-8478f885-klnwj disappeared without a scale-down or rollout; caller_error_rate=0.0% vs baseline 0.0% (z=+0.0). |
| 20:23:10 | RCA | payment-service | Root cause localised to payment-service (pod crash, confidence 92%). No other service deviates; the fault is contained to payment-service. Change evidence: Pod payment-service-8478f885-4pftp: Unhealthy — Startup probe failed: Get "http://10.244.0.73:8003/health": dial tcp 10.244.0.73:8003: connect: connection refused; Pod payment-service-8478f885-klnwj: Killing — Stopping container payment-service. |
| 20:23:10 | DECIDE | payment-service | Confidence in hpa_scaleout: 0.55 (prior 0.70 (no history yet) x RCA 0.92 x blast factor 0.85). Decision: hpa_scaleout on payment-service (fallback rolling_restart, confidence 0.55). |
| 20:23:10 | REMEDIATE | payment-service | Executing hpa_scaleout on payment-service. |
| 20:23:16 | REMEDIATE | payment-service | hpa_scaleout succeeded in 6.1s — autoscaler 2-4 -> 3-4; 2 -> 3 Ready replicas. |
| 20:23:20 | VERIFY | payment-service | payment-service verified functional: 3/3 replicas Ready and 5 consecutive user-path probes OK (last 6ms). |
| 20:23:25 | TEARDOWN | payment-service | Round teardown for payment-service: no residual fault found; autoscaler returned to declared bounds. |
| 20:23:35 | RECOVERED | payment-service | payment-service recovered: detected in 4.86s, mitigated in 11.33s, fully back to its normal operating band in 20.01s (target 90s — MET). Users saw 0 failed requests out of 479 (0.0%) during the incident. |

## Round 2 — cpu_throttle → product-service  ·  **RECOVERED**

TTD 9.86s (target 35s, met) · TTM 7.48s · TTR 50.0s (target 90s, met) · healed by primary · diagnosis correct, classification correct

### 2. Safety check before injecting

Decision **GO** · risk HIGH · system health 100.0% · target ready 2/2 · load 1.01× baseline · dependents api-gateway, order-service · users possibly affected 100%

### 3. Failure injected

`cpu_throttle` on **product-service** at 20:23:55 UTC — succeeded

Details: `{"pods": ["product-service-6dd7d4bc55-68nzf", "product-service-6dd7d4bc55-xlft5"], "cpu_limit": "25m", "original": {"product-service-6dd7d4bc55-68nzf": {"product-service": {"requests": {"cpu": "100m", "memory": "96Mi"}, "limits": {"cpu": "500m", "memory": "256Mi"}}}, "product-service-6dd7d4bc55-xlft5": {"product-service": {"requests": {"cpu": "100m", "memory": "96Mi"}, "limits": {"cpu": "500m", "memory": "256Mi"}}}}}`

### 4. Detection

Confirmed at 20:24:05 UTC on **product-service** as `high_latency` · severity 0.9445 · Isolation Forest score -0.0632 (threshold 0.1031) · flags: iforest, zscore:p99_latency_ms, zscore:inflight, zscore:caller_p99_ms

Evidence:
- p99_latency_ms=506.99ms vs baseline 16.09ms (z=+25.0)
- caller_p99_ms=120.76ms vs baseline 16.56ms (z=+6.9)

LSTM 60 s forecast: score -0.0547 (still anomalous)

### 5. Root-cause analysis

Origin **product-service** · type `cpu_throttle` · confidence 0.95 · call path api-gateway → product-service · affected api-gateway, product-service, order-service

> Root cause localised to product-service (cpu throttle, confidence 95%). api-gateway, order-service also deviate, but as callers of product-service their symptoms are explained by it. Change evidence: pod product-service-6dd7d4bc55-68nzf CPU limit is 25m vs declared 500m; pod product-service-6dd7d4bc55-xlft5 CPU limit is 25m vs declared 500m.

Evidence:
- p99_latency_ms=506.99ms vs baseline 16.09ms (z=+25.0)
- caller_p99_ms=120.76ms vs baseline 16.56ms (z=+6.9)
- pod product-service-6dd7d4bc55-68nzf CPU limit is 25m vs declared 500m
- pod product-service-6dd7d4bc55-xlft5 CPU limit is 25m vs declared 500m

| Candidate | Score | Why |
|---|---|---|
| product-service | 9.249 | severity 0.95; no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service']; earliest onset; pod product-service-6dd7d4bc55-68nzf CPU limit is 25m vs declared 500m; pod product-service-6dd7d4bc55-xlft5 CPU limit is 25m vs declared 500m |
| order-service | 1.932 | severity 0.94; its dependencies ['product-service'] are also anomalous (likely a victim); explains anomalies in callers ['api-gateway']; earliest onset; 2 ERROR log lines in the last 60s, e.g. 'dependency failure (product-service)' |
| api-gateway | 1.716 | severity 0.94; its dependencies ['product-service', 'order-service'] are also anomalous (likely a victim); earliest onset; 18 ERROR log lines in the last 60s, e.g. 'upstream error (order-service)' |

### 6. Decision

Action **resource_restore** (fallback rolling_restart) · confidence 0.646 · priority 5.696

- product-service: cpu throttle at severity 0.95; business impact 6/10 -> priority 5.70. Playbook: resource_restore, fallback rolling_restart.
- Confidence in resource_restore: 0.65 (history 0.80 over 1 attempt(s) x RCA 0.95 x blast factor 0.85).
- Decision: resource_restore on product-service (fallback rolling_restart, confidence 0.65).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| resource_restore | product-service | success | yes | 2.1s | resized 2 container(s) in place to {'product-service': {'requests': {'cpu': '100m', 'memory': '96Mi'}, 'limits': {'cpu': '500m', 'memory': '256Mi'}}} |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"restored_pods": []}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 13 failed of 1192 requests (1.1%) · user p99 5370.8 ms over 59 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 20:23:40 | STRATEGY | product-service | cpu_throttle: selected product-service (score 0.576: blast 0.5, impact 0.6, users 0.75, coverage penalty 0.0). |
| 20:23:55 | PREFLIGHT | product-service | GO: product-service at 2/2 Ready, system 100% healthy. Blast radius: 2 dependent service(s) ['api-gateway', 'order-service'], ~100% of users, risk HIGH. |
| 20:23:55 | INJECT | product-service | Injected cpu_throttle into product-service: In-place resize of every replica's CPU limit to a starvation value (product-service-6dd7d4bc55-68nzf,product-service-6dd7d4bc55-xlft5). |
| 20:24:05 | DETECT | product-service | Anomaly confirmed on product-service 10s after injection: pattern matches high latency. Isolation Forest score -0.063 (threshold +0.103), severity 0.94. Evidence: p99_latency_ms=506.99ms vs baseline 16.09ms (z=+25.0); caller_p99_ms=120.76ms vs baseline 16.56ms (z=+6.9). Also deviating: api-gateway, order-service. LSTM forecast for the next 60s: score -0.055 (still anomalous). |
| 20:24:10 | RCA | product-service | Root cause localised to product-service (cpu throttle, confidence 95%). api-gateway, order-service also deviate, but as callers of product-service their symptoms are explained by it. Change evidence: pod product-service-6dd7d4bc55-68nzf CPU limit is 25m vs declared 500m; pod product-service-6dd7d4bc55-xlft5 CPU limit is 25m vs declared 500m. |
| 20:24:10 | DECIDE | product-service | Confidence in resource_restore: 0.65 (history 0.80 over 1 attempt(s) x RCA 0.95 x blast factor 0.85). Decision: resource_restore on product-service (fallback rolling_restart, confidence 0.65). |
| 20:24:10 | REMEDIATE | product-service | Executing resource_restore on product-service. |
| 20:24:12 | REMEDIATE | product-service | resource_restore succeeded in 2.1s — resized 2 container(s) in place to {'product-service': {'requests': {'cpu': '100m', 'memory': '96Mi'}, 'limits': {'cpu': '500m', 'memory': '256Mi'}}}. |
| 20:24:16 | VERIFY | product-service | product-service verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 5ms). |
| 20:25:05 | TEARDOWN | product-service | Round teardown for product-service: no residual fault found; autoscaler returned to declared bounds. |
| 20:25:15 | RECOVERED | product-service | product-service recovered: detected in 9.86s, mitigated in 7.48s, fully back to its normal operating band in 50.0s (target 90s — MET). Users saw 13 failed requests out of 1192 (1.1%) during the incident. |

## Round 3 — network_partition → api-gateway  ·  **RECOVERED**

TTD 9.86s (target 30s, met) · TTM 8.05s · TTR 40.0s (target 90s, met) · healed by primary · diagnosis correct, classification correct

### 2. Safety check before injecting

Decision **GO** · risk MEDIUM · system health 100.0% · target ready 2/2 · load 1.04× baseline · dependents none · users possibly affected 100%

### 3. Failure injected

`network_partition` on **api-gateway** at 20:25:35 UTC — succeeded

Details: `{"policy": "chaos-isolate-api-gateway", "effect": "deny all ingress + egress", "conntrack_flush": {"ok": true, "pod_ips": ["10.244.0.69", "10.244.0.68"], "agents": {"chaos-agent-45wxr": true}}}`

### 4. Detection

Confirmed at 20:25:45 UTC on **api-gateway** as `high_latency` · severity 0.9742 · Isolation Forest score -0.0357 (threshold 0.1031) · flags: iforest, zscore:caller_error_rate, zscore:caller_p99_ms, metrics_unreachable

Evidence:
- p99_latency_ms=241.36ms vs baseline 242.46ms (z=-0.0)
- caller_p99_ms=2324.23ms vs baseline 242.66ms (z=+25.0)

LSTM 60 s forecast: score -0.0506 (still anomalous)

### 5. Root-cause analysis

Origin **api-gateway** · type `network_partition` · confidence 0.95 · call path api-gateway · affected api-gateway, product-service, payment-service, notification-service, order-service

> Root cause localised to api-gateway (network partition, confidence 95%). product-service, payment-service, notification-service, order-service also deviate, but as callers of api-gateway their symptoms are explained by it. Change evidence: NetworkPolicy 'chaos-isolate-api-gateway' denies all Ingress/Egress traffic for pods of api-gateway, created 15s ago; 12 ERROR log lines in the last 60s, e.g. 'upstream error (order-service)'.

Evidence:
- p99_latency_ms=241.36ms vs baseline 242.46ms (z=-0.0)
- caller_p99_ms=2324.23ms vs baseline 242.66ms (z=+25.0)
- NetworkPolicy 'chaos-isolate-api-gateway' denies all Ingress/Egress traffic for pods of api-gateway, created 15s ago
- 12 ERROR log lines in the last 60s, e.g. 'upstream error (order-service)'

| Candidate | Score | Why |
|---|---|---|
| api-gateway | 8.008 | severity 0.97; no anomalous dependency explains it; earliest onset; structural fault on the service itself; NetworkPolicy 'chaos-isolate-api-gateway' denies all Ingress/Egress traffic for pods of api-gateway, created 15s ago; 12 ERROR log lines in the last 60s, e.g. 'upstream error (order-service)' |
| payment-service | 1.262 | severity 0.33; only symptom is reduced traffic — consistent with an upstream failure; no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service'] |
| product-service | 1.181 | severity 0.29; only symptom is reduced traffic — consistent with an upstream failure; no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service'] |
| notification-service | 0.741 | severity 0.22; only symptom is reduced traffic — consistent with an upstream failure; no anomalous dependency explains it; explains anomalies in callers ['api-gateway'] |
| order-service | 0.645 | severity 0.17; only symptom is reduced traffic — consistent with an upstream failure; no anomalous dependency explains it; explains anomalies in callers ['api-gateway'] |

### 6. Decision

Action **network_policy_rollback** (fallback rolling_restart) · confidence 0.665 · priority 8.766

- api-gateway: network partition at severity 0.97; business impact 9/10 -> priority 8.77. Playbook: network_policy_rollback, fallback rolling_restart.
- Confidence in network_policy_rollback: 0.67 (prior 0.70 (no history yet) x RCA 0.95 x blast factor 1.00).
- Decision: network_policy_rollback on api-gateway (fallback rolling_restart, confidence 0.67).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| network_policy_rollback | api-gateway | success | yes | 0.0s | removed 1 isolating NetworkPolicy(ies): chaos-isolate-api-gateway |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"policy": "chaos-isolate-api-gateway", "deleted": false}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 266 failed of 1027 requests (25.9%) · user p99 4902.3 ms over 49 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 20:25:20 | STRATEGY | api-gateway | network_partition: selected api-gateway (score 0.525: blast 0.0, impact 0.9, users 1.0, coverage penalty 0.0). |
| 20:25:35 | PREFLIGHT | api-gateway | GO: api-gateway at 2/2 Ready, system 100% healthy. Blast radius: 0 dependent service(s) , ~100% of users, risk MEDIUM. |
| 20:25:35 | INJECT | api-gateway | Injected network_partition into api-gateway: Deny-all NetworkPolicy selecting the service's pods (chaos-isolate-api-gateway). |
| 20:25:45 | DETECT | api-gateway | Anomaly confirmed on api-gateway 10s after injection: pattern matches high latency. Isolation Forest score -0.036 (threshold +0.103), severity 0.97. Evidence: p99_latency_ms=241.36ms vs baseline 242.46ms (z=-0.0); caller_p99_ms=2324.23ms vs baseline 242.66ms (z=+25.0). LSTM forecast for the next 60s: score -0.051 (still anomalous). |
| 20:25:50 | RCA | api-gateway | Root cause localised to api-gateway (network partition, confidence 95%). product-service, payment-service, notification-service, order-service also deviate, but as callers of api-gateway their symptoms are explained by it. Change evidence: NetworkPolicy 'chaos-isolate-api-gateway' denies all Ingress/Egress traffic for pods of api-gateway, created 15s ago; 12 ERROR log lines in the last 60s, e.g. 'upstream error (order-service)'. |
| 20:25:50 | DECIDE | api-gateway | Confidence in network_policy_rollback: 0.67 (prior 0.70 (no history yet) x RCA 0.95 x blast factor 1.00). Decision: network_policy_rollback on api-gateway (fallback rolling_restart, confidence 0.67). |
| 20:25:50 | REMEDIATE | api-gateway | Executing network_policy_rollback on api-gateway. |
| 20:25:50 | REMEDIATE | api-gateway | network_policy_rollback succeeded in 0.0s — removed 1 isolating NetworkPolicy(ies): chaos-isolate-api-gateway. |
| 20:25:57 | VERIFY | api-gateway | api-gateway verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 6ms). |
| 20:26:35 | TEARDOWN | api-gateway | Round teardown for api-gateway: no residual fault found; autoscaler returned to declared bounds. |
| 20:26:45 | RECOVERED | api-gateway | api-gateway recovered: detected in 9.86s, mitigated in 8.05s, fully back to its normal operating band in 40.0s (target 90s — MET). Users saw 266 failed requests out of 1027 (25.9%) during the incident. |

## Round 4 — latency_injection → order-service  ·  **RECOVERED**

TTD 14.85s (target 35s, met) · TTM 16.55s · TTR 49.99s (target 120s, met) · healed by primary · diagnosis correct, classification correct

### 2. Safety check before injecting

Decision **GO** · risk MEDIUM · system health 100.0% · target ready 2/2 · load 0.93× baseline · dependents api-gateway · users possibly affected 100%

### 3. Failure injected

`latency_injection` on **order-service** at 20:27:05 UTC — succeeded

Details: `{"pod": "order-service-74ff6cb5bf-b446z", "delay": "200ms", "jitter": "50ms", "command": "tc qdisc replace dev eth0 root netem delay 200ms 50ms distribution normal", "replicas_ready": 2}`

### 4. Detection

Confirmed at 20:27:20 UTC on **api-gateway** as `high_latency` · severity 0.9325 · Isolation Forest score -0.027 (threshold 0.1031) · flags: iforest, zscore:p99_latency_ms, zscore:caller_p99_ms

Evidence:
- p99_latency_ms=542.50ms vs baseline 242.46ms (z=+8.3)
- caller_p99_ms=1020.00ms vs baseline 242.66ms (z=+21.4)

LSTM 60 s forecast: score -0.0391 (still anomalous)

### 5. Root-cause analysis

Origin **order-service** · type `high_latency` · confidence 0.786 · call path api-gateway → order-service · affected api-gateway, product-service, order-service, payment-service

> Root cause localised to order-service (high latency, confidence 79%). api-gateway, product-service, payment-service also deviate, but as callers of order-service their symptoms are explained by it. Signal: p99_latency_ms=919.00ms vs baseline 246.95ms (z=+18.1); caller_p99_ms=1635.00ms vs baseline 246.99ms (z=+25.0).

Evidence:
- p99_latency_ms=919.00ms vs baseline 246.95ms (z=+18.1)
- caller_p99_ms=1635.00ms vs baseline 246.99ms (z=+25.0)

| Candidate | Score | Why |
|---|---|---|
| order-service | 4.414 | severity 0.93; its dependencies ['product-service', 'payment-service'] are also anomalous (likely a victim); explains anomalies in callers ['api-gateway']; earliest onset; its calls to product-service take 425ms longer than product-service itself needs to serve them (caller-side or network problem); its calls to payment-service take 248ms longer than payment-service itself needs to serve them (cal… |
| product-service | 2.644 | severity 0.90; its own server-side latency/errors are normal; the degradation is only visible from callers (network or caller-side problem); no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service']; earliest onset |
| api-gateway | 1.119 | severity 0.93; its dependencies ['product-service', 'order-service', 'payment-service'] are also anomalous (likely a victim); earliest onset |
| payment-service | 0.941 | severity 0.42; its own server-side latency/errors are normal; the degradation is only visible from callers (network or caller-side problem); no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service'] |

### 6. Decision

Action **traffic_reroute** (fallback rolling_restart) · confidence 0.618 · priority 7.455

- order-service: high latency at severity 0.93; business impact 8/10 -> priority 7.46. Playbook: traffic_reroute, fallback rolling_restart.
- Confidence in traffic_reroute: 0.62 (history 0.85 over 2 attempt(s) x RCA 0.79 x blast factor 0.93).
- Decision: traffic_reroute on order-service (fallback rolling_restart, confidence 0.62).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| traffic_reroute | order-service | success | yes | 11.1s | quarantined order-service-74ff6cb5bf-b446z (worst replica by live telemetry (p99=4858ms, next worst score 247 vs 4858)); traffic now on 2 healthy replica(s) |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"pod": "order-service-74ff6cb5bf-b446z", "note": "pod no longer exists (replaced)"}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 5 failed of 1283 requests (0.4%) · user p99 3806.0 ms over 64 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 20:26:50 | STRATEGY | order-service | latency_injection: selected order-service (score 0.466: blast 0.25, impact 0.8, users 0.4, coverage penalty 0.0). |
| 20:27:05 | PREFLIGHT | order-service | GO: order-service at 2/2 Ready, system 100% healthy. Blast radius: 1 dependent service(s) ['api-gateway'], ~100% of users, risk MEDIUM. |
| 20:27:05 | INJECT | order-service | Injected latency_injection into order-service: tc netem egress delay on one replica (order-service-74ff6cb5bf-b446z). |
| 20:27:20 | DETECT | api-gateway | Anomaly confirmed on api-gateway 15s after injection: pattern matches high latency. Isolation Forest score -0.027 (threshold +0.103), severity 0.93. Evidence: p99_latency_ms=542.50ms vs baseline 242.46ms (z=+8.3); caller_p99_ms=1020.00ms vs baseline 242.66ms (z=+21.4). Also deviating: product-service, order-service. LSTM forecast for the next 60s: score -0.039 (still anomalous). |
| 20:27:25 | RCA | order-service | Root cause localised to order-service (high latency, confidence 79%). api-gateway, product-service, payment-service also deviate, but as callers of order-service their symptoms are explained by it. Signal: p99_latency_ms=919.00ms vs baseline 246.95ms (z=+18.1); caller_p99_ms=1635.00ms vs baseline 246.99ms (z=+25.0). |
| 20:27:25 | DECIDE | order-service | Confidence in traffic_reroute: 0.62 (history 0.85 over 2 attempt(s) x RCA 0.79 x blast factor 0.93). Decision: traffic_reroute on order-service (fallback rolling_restart, confidence 0.62). |
| 20:27:25 | REMEDIATE | order-service | Executing traffic_reroute on order-service. |
| 20:27:36 | REMEDIATE | order-service | traffic_reroute succeeded in 11.1s — quarantined order-service-74ff6cb5bf-b446z (worst replica by live telemetry (p99=4858ms, next worst score 247 vs 4858)); traffic now on 2 healthy replica(s). |
| 20:27:40 | VERIFY | order-service | order-service verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 7ms). |
| 20:28:20 | TEARDOWN | order-service | Round teardown for order-service: no residual fault found; autoscaler returned to declared bounds. |
| 20:28:30 | RECOVERED | order-service | order-service recovered: detected in 14.85s, mitigated in 16.55s, fully back to its normal operating band in 49.99s (target 120s — MET). Users saw 5 failed requests out of 1283 (0.4%) during the incident. |

## Round 5 — replica_reduction → payment-service  ·  **RECOVERED**

TTD 4.86s (target 35s, met) · TTM 11.34s · TTR 20.01s (target 120s, met) · healed by primary · diagnosis correct, classification correct

### 2. Safety check before injecting

Decision **GO** · risk HIGH · system health 100.0% · target ready 2/2 · load 0.99× baseline · dependents api-gateway, order-service · users possibly affected 100%

### 3. Failure injected

`replica_reduction` on **payment-service** at 20:28:50 UTC — succeeded

Details: `{"hpa": "payment-service-hpa", "original": {"minReplicas": 2, "maxReplicas": 4}, "patched_to": {"minReplicas": 1, "maxReplicas": 1}}`

### 4. Detection

Confirmed at 20:28:55 UTC on **payment-service** as `replica_exhaustion` · severity 0.5 · Isolation Forest score 0.1124 (threshold 0.1031) · flags: capacity_below_baseline

Evidence:
- replicas ready 1/1 (declared minimum 2)
- autoscaler bounds min=1 max=1 below declared minimum 2

LSTM 60 s forecast: score 0.1366 (returning to normal)

### 5. Root-cause analysis

Origin **payment-service** · type `replica_exhaustion` · confidence 0.96 · call path api-gateway → payment-service · affected payment-service

> Root cause localised to payment-service (replica exhaustion, confidence 96%). No other service deviates; the fault is contained to payment-service. Change evidence: HPA bounds 1-1 are below the declared 2-4; Pod payment-service-8478f885-4pftp: Killing — Stopping container payment-service.

Evidence:
- replicas ready 1/1 (declared minimum 2)
- autoscaler bounds min=1 max=1 below declared minimum 2
- HPA bounds 1-1 are below the declared 2-4
- Pod payment-service-8478f885-4pftp: Killing — Stopping container payment-service

| Candidate | Score | Why |
|---|---|---|
| payment-service | 7.6 | severity 0.80; no anomalous dependency explains it; earliest onset; structural fault on the service itself; HPA bounds 1-1 are below the declared 2-4; Pod payment-service-8478f885-4pftp: Killing — Stopping container payment-service |

### 6. Decision

Action **hpa_scaleout** (fallback resource_restore) · confidence 0.653 · priority 8.0

- payment-service: replica exhaustion at severity 0.80; business impact 10/10 -> priority 8.00. Playbook: hpa_scaleout, fallback resource_restore.
- Confidence in hpa_scaleout: 0.65 (history 0.80 over 1 attempt(s) x RCA 0.96 x blast factor 0.85).
- Decision: hpa_scaleout on payment-service (fallback resource_restore, confidence 0.65).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| hpa_scaleout | payment-service | success | yes | 6.1s | autoscaler 1-1 -> 3-4; 1 -> 3 Ready replicas |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"restored": false, "note": "autoscaler already at or above declared bounds"}` · autoscaler `{"from": {"minReplicas": 3, "maxReplicas": 4}, "to": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 0 failed of 480 requests (0.0%) · user p99 242.7 ms over 24 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 20:28:35 | STRATEGY | payment-service | replica_reduction: selected payment-service (score -0.004: blast 0.5, impact 1.0, users 0.35, coverage penalty 1.0). |
| 20:28:50 | PREFLIGHT | payment-service | GO: payment-service at 2/2 Ready, system 100% healthy. Blast radius: 2 dependent service(s) ['api-gateway', 'order-service'], ~100% of users, risk HIGH. |
| 20:28:50 | INJECT | payment-service | Injected replica_reduction into payment-service: Clamp HPA to min=max=1 (payment-service-hpa). |
| 20:28:55 | DETECT | payment-service | Anomaly confirmed on payment-service 5s after injection: pattern matches replica exhaustion. Isolation Forest score +0.112 (threshold +0.103), severity 0.50. Evidence: replicas ready 1/1 (declared minimum 2); autoscaler bounds min=1 max=1 below declared minimum 2. LSTM forecast for the next 60s: score +0.137 (returning to normal). |
| 20:29:00 | RCA | payment-service | Root cause localised to payment-service (replica exhaustion, confidence 96%). No other service deviates; the fault is contained to payment-service. Change evidence: HPA bounds 1-1 are below the declared 2-4; Pod payment-service-8478f885-4pftp: Killing — Stopping container payment-service. |
| 20:29:00 | DECIDE | payment-service | Confidence in hpa_scaleout: 0.65 (history 0.80 over 1 attempt(s) x RCA 0.96 x blast factor 0.85). Decision: hpa_scaleout on payment-service (fallback resource_restore, confidence 0.65). |
| 20:29:00 | REMEDIATE | payment-service | Executing hpa_scaleout on payment-service. |
| 20:29:06 | REMEDIATE | payment-service | hpa_scaleout succeeded in 6.1s — autoscaler 1-1 -> 3-4; 1 -> 3 Ready replicas. |
| 20:29:10 | VERIFY | payment-service | payment-service verified functional: 3/3 replicas Ready and 5 consecutive user-path probes OK (last 7ms). |
| 20:29:15 | TEARDOWN | payment-service | Round teardown for payment-service: no residual fault found; autoscaler returned to declared bounds. |
| 20:29:25 | RECOVERED | payment-service | payment-service recovered: detected in 4.86s, mitigated in 11.34s, fully back to its normal operating band in 20.01s (target 120s — MET). Users saw 0 failed requests out of 480 (0.0%) during the incident. |

## Campaign-level events

| Time (UTC) | Phase | Message |
|---|---|---|
| 20:22:40 | CAMPAIGN | Campaign c-20261010-202240-d5ad starting: 5 rounds (pod_deletion, cpu_throttle, network_partition, latency_injection, replica_reduction). |
| 20:29:25 | SUMMARY | Campaign completed: resilience score 98.9/100 — EXCELLENT — every fault detected, diagnosed and healed within SLA. |
