# Incident log — campaign `c-20261010-211746-a9ae`

**Resilience score 94.5/100** — EXCELLENT — every fault detected, diagnosed and healed within SLA

| Component | Points |
|---|---|
| recovery sla | 35.0 |
| detection sla | 20.0 |
| remediation effectiveness | 18.0 |
| diagnosis accuracy | 13.5 |
| user protection | 8.05 |

| # | Fault | Target | Status | TTD | TTR | Users failed |
|---|---|---|---|---|---|---|
| 1 | pod_deletion | payment-service | RECOVERED | 4.84s | 40.0s | 0.0% |
| 2 | cpu_throttle | product-service | RECOVERED | 9.81s | 55.0s | 7.5% |
| 3 | network_partition | api-gateway | RECOVERED | 14.83s | 35.01s | 41.1% |
| 4 | latency_injection | order-service | RECOVERED | 9.82s | 45.01s | 0.2% |
| 5 | replica_reduction | payment-service | RECOVERED | 4.79s | 20.0s | 0.0% |

## Round 1 — pod_deletion → payment-service  ·  **RECOVERED**

TTD 4.84s (target 25s, met) · TTM 15.55s · TTR 40.0s (target 90s, met) · healed by fallback · diagnosis correct, classification wrong

### 2. Safety check before injecting

Decision **GO** · risk HIGH · system health 100.0% · target ready 2/2 · load 1.04× baseline · dependents api-gateway, order-service · users possibly affected 100%

### 3. Failure injected

`pod_deletion` on **payment-service** at 21:18:02 UTC — succeeded

Details: `{"pod": "payment-service-55fc55c58c-jx98h", "pod_ip": "10.244.0.84", "ready_pods_before": 2}`

### 4. Detection

Confirmed at 21:18:07 UTC on **payment-service** as `network_partition` · severity 0.76 · Isolation Forest score 0.1118 (threshold 0.1031) · flags: replicas_lost, metrics_unreachable

Evidence:
- replicas ready 2/2 (declared minimum 2)
- metrics endpoint unreachable on 50% of pods
- caller_error_rate=0.0% vs baseline 0.0% (z=+0.0)
- request_rate=6.20 req/s vs baseline 6.92 req/s (z=-1.0)
- pods are running (no container restarts) but cannot be reached over the pod network

LSTM 60 s forecast: score 0.1219 (returning to normal)

### 5. Root-cause analysis

Origin **payment-service** · type `network_partition` · confidence 0.953 · call path api-gateway → payment-service · affected payment-service

> Root cause localised to payment-service (network partition, confidence 95%). No other service deviates; the fault is contained to payment-service. Change evidence: Pod payment-service-55fc55c58c-4lnfd: Unhealthy — Startup probe failed: Get "http://10.244.0.86:8003/health": dial tcp 10.244.0.86:8003: connect: connection refused; Pod payment-service-55fc55c58c-ccxqd: Killing — Stopping container payment-service.

Evidence:
- replicas ready 2/2 (declared minimum 2)
- metrics endpoint unreachable on 50% of pods
- caller_error_rate=0.0% vs baseline 0.0% (z=+0.0)
- request_rate=6.20 req/s vs baseline 6.92 req/s (z=-1.0)
- pods are running (no container restarts) but cannot be reached over the pod network
- Pod payment-service-55fc55c58c-4lnfd: Unhealthy — Startup probe failed: Get "http://10.244.0.86:8003/health": dial tcp 10.244.0.86:8003: connect: connection refused
- Pod payment-service-55fc55c58c-ccxqd: Killing — Stopping container payment-service
- Pod payment-service-55fc55c58c-jx98h: Killing — Stopping container payment-service

| Candidate | Score | Why |
|---|---|---|
| payment-service | 4.412 | severity 0.46; no anomalous dependency explains it; earliest onset; structural fault on the service itself; Pod payment-service-55fc55c58c-4lnfd: Unhealthy — Startup probe failed: Get "http://10.244.0.86:8003/health": dial tcp 10.244.0.86:8003: connect: connection refused; Pod payment-service-55fc55c58c-ccxqd: Killing — Stopping container payment-service; Pod payment-service-55fc55c58c-jx98h: Kill… |

### 6. Decision

Action **network_policy_rollback** (fallback rolling_restart) · confidence 0.567 · priority 4.56

- payment-service: network partition at severity 0.46; business impact 10/10 -> priority 4.56. Playbook: network_policy_rollback, fallback rolling_restart.
- Confidence in network_policy_rollback: 0.57 (prior 0.70 (no history yet) x RCA 0.95 x blast factor 0.85).
- Decision: network_policy_rollback on payment-service (fallback rolling_restart, confidence 0.57).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| network_policy_rollback | payment-service | failed | no | 0.0s | no deny-all NetworkPolicy selects this service |
| rolling_restart | payment-service | success | yes | 10.1s | rolled 2 replica(s) onto the declared template |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"reversible": false, "note": "Kubernetes reschedules deleted pods by itself"}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 0 failed of 880 requests (0.0%) · user p99 242.9 ms over 44 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 21:17:47 | STRATEGY | payment-service | pod_deletion: selected payment-service (score 0.580: blast 0.5, impact 1.0, users 0.35, coverage penalty 0.0). |
| 21:18:02 | PREFLIGHT | payment-service | GO: payment-service at 2/2 Ready, system 100% healthy. Blast radius: 2 dependent service(s) ['api-gateway', 'order-service'], ~100% of users, risk HIGH. |
| 21:18:02 | INJECT | payment-service | Injected pod_deletion into payment-service: Force-delete one Ready pod (grace period 0) (payment-service-55fc55c58c-jx98h). |
| 21:18:07 | DETECT | payment-service | Anomaly confirmed on payment-service 5s after injection: pattern matches network partition. Isolation Forest score +0.112 (threshold +0.103), severity 0.76. Evidence: replicas ready 2/2 (declared minimum 2); metrics endpoint unreachable on 50% of pods; caller_error_rate=0.0% vs baseline 0.0% (z=+0.0). LSTM forecast for the next 60s: score +0.122 (returning to normal). |
| 21:18:12 | RCA | payment-service | Root cause localised to payment-service (network partition, confidence 95%). No other service deviates; the fault is contained to payment-service. Change evidence: Pod payment-service-55fc55c58c-4lnfd: Unhealthy — Startup probe failed: Get "http://10.244.0.86:8003/health": dial tcp 10.244.0.86:8003: connect: connection refused; Pod payment-service-55fc55c58c-ccxqd: Killing — Stopping container payment-service. |
| 21:18:12 | DECIDE | payment-service | Confidence in network_policy_rollback: 0.57 (prior 0.70 (no history yet) x RCA 0.95 x blast factor 0.85). Decision: network_policy_rollback on payment-service (fallback rolling_restart, confidence 0.57). |
| 21:18:13 | REMEDIATE | payment-service | Executing network_policy_rollback on payment-service. |
| 21:18:13 | REMEDIATE | payment-service | network_policy_rollback did not complete in 0.0s — no deny-all NetworkPolicy selects this service. |
| 21:18:13 | DECIDE | payment-service | network_policy_rollback did not restore payment-service; escalating to fallback rolling_restart. |
| 21:18:13 | REMEDIATE | payment-service | Executing rolling_restart on payment-service. |
| 21:18:23 | REMEDIATE | payment-service | rolling_restart succeeded in 10.1s — rolled 2 replica(s) onto the declared template. |
| 21:18:27 | VERIFY | payment-service | payment-service verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 7ms). |
| 21:18:57 | TEARDOWN | payment-service | Round teardown for payment-service: no residual fault found; autoscaler returned to declared bounds. |
| 21:19:07 | RECOVERED | payment-service | payment-service recovered: detected in 4.84s, mitigated in 15.55s, fully back to its normal operating band in 40.0s (target 90s — MET). Users saw 0 failed requests out of 880 (0.0%) during the incident. |

## Round 2 — cpu_throttle → product-service  ·  **RECOVERED**

TTD 9.81s (target 35s, met) · TTM 10.71s · TTR 55.0s (target 90s, met) · healed by primary · diagnosis correct, classification correct

### 2. Safety check before injecting

Decision **GO** · risk HIGH · system health 100.0% · target ready 2/2 · load 0.98× baseline · dependents api-gateway, order-service · users possibly affected 100%

### 3. Failure injected

`cpu_throttle` on **product-service** at 21:19:27 UTC — succeeded

Details: `{"pods": ["product-service-6dd7d4bc55-68nzf", "product-service-6dd7d4bc55-xlft5"], "cpu_limit": "25m", "original": {"product-service-6dd7d4bc55-68nzf": {"product-service": {"requests": {"cpu": "100m", "memory": "96Mi"}, "limits": {"cpu": "500m", "memory": "256Mi"}}}, "product-service-6dd7d4bc55-xlft5": {"product-service": {"requests": {"cpu": "100m", "memory": "96Mi"}, "limits": {"cpu": "500m", "memory": "256Mi"}}}}}`

### 4. Detection

Confirmed at 21:19:37 UTC on **product-service** as `high_latency` · severity 0.9511 · Isolation Forest score -0.0828 (threshold 0.1031) · flags: iforest, zscore:p99_latency_ms, zscore:inflight, zscore:caller_p99_ms

Evidence:
- p99_latency_ms=29.25ms vs baseline 16.09ms (z=+0.9)
- caller_p99_ms=391.88ms vs baseline 16.56ms (z=+25.0)

LSTM 60 s forecast: score -0.0832 (still anomalous)

### 5. Root-cause analysis

Origin **product-service** · type `cpu_throttle` · confidence 0.95 · call path api-gateway → product-service · affected api-gateway, product-service, order-service, payment-service, notification-service

> Root cause localised to product-service (cpu throttle, confidence 95%). api-gateway, order-service also deviate as callers of product-service: its failure propagates to them. payment-service, notification-service also deviate without a dependency explaining it (lower-ranked candidates). Change evidence: pod product-service-6dd7d4bc55-68nzf CPU limit is 25m vs declared 500m; pod product-service-6dd7d4bc55-xlft5 CPU limit is 25m vs declared 500m.

Evidence:
- p99_latency_ms=29.25ms vs baseline 16.09ms (z=+0.9)
- caller_p99_ms=391.88ms vs baseline 16.56ms (z=+25.0)
- pod product-service-6dd7d4bc55-68nzf CPU limit is 25m vs declared 500m
- pod product-service-6dd7d4bc55-xlft5 CPU limit is 25m vs declared 500m
- Pod product-service-6dd7d4bc55-68nzf: Unhealthy — Readiness probe failed: Get "http://10.244.0.63:8001/ready": context deadline exceeded (Client.Timeout exceeded while aw
- Pod product-service-6dd7d4bc55-68nzf: Unhealthy — Liveness probe failed: Get "http://10.244.0.63:8001/health": context deadline exceeded (Client.Timeout exceeded while aw
- Pod product-service-6dd7d4bc55-xlft5: Unhealthy — Readiness probe failed: Get "http://10.244.0.44:8001/ready": context deadline exceeded (Client.Timeout exceeded while aw

| Candidate | Score | Why |
|---|---|---|
| product-service | 11.079 | severity 0.99; no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service']; earliest onset; structural fault on the service itself; pod product-service-6dd7d4bc55-68nzf CPU limit is 25m vs declared 500m; pod product-service-6dd7d4bc55-xlft5 CPU limit is 25m vs declared 500m; Pod product-service-6dd7d4bc55-68nzf: Unhealthy — Readiness probe failed: Get "http:… |
| order-service | 2.507 | severity 0.97; its dependencies ['product-service'] are also anomalous (likely a victim); explains anomalies in callers ['api-gateway']; earliest onset; 104 ERROR log lines in the last 60s, e.g. 'dependency failure (product-service)' |
| api-gateway | 2.362 | severity 0.97; its dependencies ['product-service', 'order-service'] are also anomalous (likely a victim); earliest onset; 134 ERROR log lines in the last 60s, e.g. 'upstream error (order-service)' |
| payment-service | 0.799 | severity 0.10; only symptom is reduced traffic — consistent with an upstream failure; no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service'] |
| notification-service | 0.657 | severity 0.18; only symptom is reduced traffic — consistent with an upstream failure; no anomalous dependency explains it; explains anomalies in callers ['api-gateway'] |

### 6. Decision

Action **resource_restore** (fallback rolling_restart) · confidence 0.711 · priority 5.936

- product-service: cpu throttle at severity 0.99; business impact 6/10 -> priority 5.94. Playbook: resource_restore, fallback rolling_restart.
- Confidence in resource_restore: 0.71 (history 0.88 over 3 attempt(s) x RCA 0.95 x blast factor 0.85).
- Decision: resource_restore on product-service (fallback rolling_restart, confidence 0.71).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| resource_restore | product-service | success | yes | 2.1s | resized 2 container(s) in place to {'product-service': {'requests': {'cpu': '100m', 'memory': '96Mi'}, 'limits': {'cpu': '500m', 'memory': '256Mi'}}} |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"restored_pods": []}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 96 failed of 1286 requests (7.5%) · user p99 8903.6 ms over 64 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 21:19:12 | STRATEGY | product-service | cpu_throttle: selected product-service (score 0.577: blast 0.5, impact 0.6, users 0.75, coverage penalty 0.0). |
| 21:19:27 | PREFLIGHT | product-service | GO: product-service at 2/2 Ready, system 100% healthy. Blast radius: 2 dependent service(s) ['api-gateway', 'order-service'], ~100% of users, risk HIGH. |
| 21:19:28 | INJECT | product-service | Injected cpu_throttle into product-service: In-place resize of every replica's CPU limit to a starvation value (product-service-6dd7d4bc55-68nzf,product-service-6dd7d4bc55-xlft5). |
| 21:19:37 | DETECT | product-service | Anomaly confirmed on product-service 10s after injection: pattern matches high latency. Isolation Forest score -0.083 (threshold +0.103), severity 0.95. Evidence: p99_latency_ms=29.25ms vs baseline 16.09ms (z=+0.9); caller_p99_ms=391.88ms vs baseline 16.56ms (z=+25.0). Also deviating: api-gateway, order-service. LSTM forecast for the next 60s: score -0.083 (still anomalous). |
| 21:19:43 | RCA | product-service | Root cause localised to product-service (cpu throttle, confidence 95%). api-gateway, order-service also deviate as callers of product-service: its failure propagates to them. payment-service, notification-service also deviate without a dependency explaining it (lower-ranked candidates). Change evidence: pod product-service-6dd7d4bc55-68nzf CPU limit is 25m vs declared 500m; pod product-service-6dd7d4bc55-xlft5 CPU limit is 25m vs declared 500m. |
| 21:19:43 | DECIDE | product-service | Confidence in resource_restore: 0.71 (history 0.88 over 3 attempt(s) x RCA 0.95 x blast factor 0.85). Decision: resource_restore on product-service (fallback rolling_restart, confidence 0.71). |
| 21:19:43 | REMEDIATE | product-service | Executing resource_restore on product-service. |
| 21:19:45 | REMEDIATE | product-service | resource_restore succeeded in 2.1s — resized 2 container(s) in place to {'product-service': {'requests': {'cpu': '100m', 'memory': '96Mi'}, 'limits': {'cpu': '500m', 'memory': '256Mi'}}}. |
| 21:19:52 | VERIFY | product-service | product-service verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 7ms). |
| 21:20:42 | TEARDOWN | product-service | Round teardown for product-service: no residual fault found; autoscaler returned to declared bounds. |
| 21:20:52 | RECOVERED | product-service | product-service recovered: detected in 9.81s, mitigated in 10.71s, fully back to its normal operating band in 55.0s (target 90s — MET). Users saw 96 failed requests out of 1286 (7.5%) during the incident. |

## Round 3 — network_partition → api-gateway  ·  **RECOVERED**

TTD 14.83s (target 30s, met) · TTM 5.52s · TTR 35.01s (target 90s, met) · healed by primary · diagnosis correct, classification correct

### 2. Safety check before injecting

Decision **GO** · risk MEDIUM · system health 100.0% · target ready 2/2 · load 0.99× baseline · dependents none · users possibly affected 100%

### 3. Failure injected

`network_partition` on **api-gateway** at 21:21:12 UTC — succeeded

Details: `{"policy": "chaos-isolate-api-gateway", "effect": "deny all ingress + egress", "conntrack_flush": {"ok": true, "pod_ips": ["10.244.0.69", "10.244.0.68"], "agents": {"chaos-agent-45wxr": true}}}`

### 4. Detection

Confirmed at 21:21:27 UTC on **api-gateway** as `network_partition` · severity 0.975 · Isolation Forest score -0.0423 (threshold 0.1031) · flags: iforest, zscore:caller_error_rate, zscore:caller_p99_ms, metrics_unreachable

Evidence:
- replicas ready 2/2 (declared minimum 2)
- metrics endpoint unreachable on 100% of pods
- caller_error_rate=19.0% vs baseline 0.0% (z=+9.5)
- request_rate=13.44 req/s vs baseline 20.00 req/s (z=-3.3)
- pods are running (no container restarts) but cannot be reached over the pod network

LSTM 60 s forecast: score -0.0497 (still anomalous)

### 5. Root-cause analysis

Origin **api-gateway** · type `network_partition` · confidence 0.95 · call path api-gateway · affected api-gateway, product-service, order-service, payment-service, notification-service

> Root cause localised to api-gateway (network partition, confidence 95%). product-service, order-service, payment-service, notification-service deviate because requests from api-gateway stopped reaching them. Change evidence: NetworkPolicy 'chaos-isolate-api-gateway' denies all Ingress/Egress traffic for pods of api-gateway, created 20s ago; 6 ERROR log lines in the last 60s, e.g. 'upstream error (order-service)'.

Evidence:
- replicas ready 2/2 (declared minimum 2)
- metrics endpoint unreachable on 100% of pods
- caller_error_rate=19.0% vs baseline 0.0% (z=+9.5)
- request_rate=13.44 req/s vs baseline 20.00 req/s (z=-3.3)
- pods are running (no container restarts) but cannot be reached over the pod network
- NetworkPolicy 'chaos-isolate-api-gateway' denies all Ingress/Egress traffic for pods of api-gateway, created 20s ago
- 6 ERROR log lines in the last 60s, e.g. 'upstream error (order-service)'

| Candidate | Score | Why |
|---|---|---|
| api-gateway | 7.98 | severity 0.98; no anomalous dependency explains it; earliest onset; structural fault on the service itself; NetworkPolicy 'chaos-isolate-api-gateway' denies all Ingress/Egress traffic for pods of api-gateway, created 20s ago; 6 ERROR log lines in the last 60s, e.g. 'upstream error (order-service)' |
| product-service | 2.092 | severity 0.37; only symptom is reduced traffic — consistent with an upstream failure; no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service']; earliest onset |
| payment-service | 2.051 | severity 0.35; only symptom is reduced traffic — consistent with an upstream failure; no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service']; earliest onset |
| notification-service | 1.919 | severity 0.43; only symptom is reduced traffic — consistent with an upstream failure; no anomalous dependency explains it; explains anomalies in callers ['api-gateway']; earliest onset |
| order-service | 1.888 | severity 0.42; only symptom is reduced traffic — consistent with an upstream failure; no anomalous dependency explains it; explains anomalies in callers ['api-gateway']; earliest onset |

### 6. Decision

Action **network_policy_rollback** (fallback rolling_restart) · confidence 0.807 · priority 8.777

- api-gateway: network partition at severity 0.98; business impact 9/10 -> priority 8.78. Playbook: network_policy_rollback, fallback rolling_restart.
- Confidence in network_policy_rollback: 0.81 (history 0.85 over 2 attempt(s) x RCA 0.95 x blast factor 1.00).
- Decision: network_policy_rollback on api-gateway (fallback rolling_restart, confidence 0.81).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| network_policy_rollback | api-gateway | success | yes | 0.0s | removed 1 isolating NetworkPolicy(ies): chaos-isolate-api-gateway |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"policy": "chaos-isolate-api-gateway", "deleted": false}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 415 failed of 1010 requests (41.1%) · user p99 2480.1 ms over 49 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 21:20:57 | STRATEGY | api-gateway | network_partition: selected api-gateway (score 0.526: blast 0.0, impact 0.9, users 1.0, coverage penalty 0.0). |
| 21:21:12 | PREFLIGHT | api-gateway | GO: api-gateway at 2/2 Ready, system 100% healthy. Blast radius: 0 dependent service(s) , ~100% of users, risk MEDIUM. |
| 21:21:13 | INJECT | api-gateway | Injected network_partition into api-gateway: Deny-all NetworkPolicy selecting the service's pods (chaos-isolate-api-gateway). |
| 21:21:27 | DETECT | api-gateway | Anomaly confirmed on api-gateway 15s after injection: pattern matches network partition. Isolation Forest score -0.042 (threshold +0.103), severity 0.97. Evidence: replicas ready 2/2 (declared minimum 2); metrics endpoint unreachable on 100% of pods; caller_error_rate=19.0% vs baseline 0.0% (z=+9.5). Also deviating: product-service, notification-service. LSTM forecast for the next 60s: score -0.050 (still anomalous). |
| 21:21:33 | RCA | api-gateway | Root cause localised to api-gateway (network partition, confidence 95%). product-service, order-service, payment-service, notification-service deviate because requests from api-gateway stopped reaching them. Change evidence: NetworkPolicy 'chaos-isolate-api-gateway' denies all Ingress/Egress traffic for pods of api-gateway, created 20s ago; 6 ERROR log lines in the last 60s, e.g. 'upstream error (order-service)'. |
| 21:21:33 | DECIDE | api-gateway | Confidence in network_policy_rollback: 0.81 (history 0.85 over 2 attempt(s) x RCA 0.95 x blast factor 1.00). Decision: network_policy_rollback on api-gateway (fallback rolling_restart, confidence 0.81). |
| 21:21:33 | REMEDIATE | api-gateway | Executing network_policy_rollback on api-gateway. |
| 21:21:33 | REMEDIATE | api-gateway | network_policy_rollback succeeded in 0.0s — removed 1 isolating NetworkPolicy(ies): chaos-isolate-api-gateway. |
| 21:21:37 | VERIFY | api-gateway | api-gateway verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 6ms). |
| 21:22:12 | TEARDOWN | api-gateway | Round teardown for api-gateway: no residual fault found; autoscaler returned to declared bounds. |
| 21:22:22 | RECOVERED | api-gateway | api-gateway recovered: detected in 14.83s, mitigated in 5.52s, fully back to its normal operating band in 35.01s (target 90s — MET). Users saw 415 failed requests out of 1010 (41.1%) during the incident. |

## Round 4 — latency_injection → order-service  ·  **RECOVERED**

TTD 9.82s (target 35s, met) · TTM 16.61s · TTR 45.01s (target 120s, met) · healed by primary · diagnosis correct, classification correct

### 2. Safety check before injecting

Decision **GO** · risk MEDIUM · system health 100.0% · target ready 2/2 · load 0.87× baseline · dependents api-gateway · users possibly affected 100%

### 3. Failure injected

`latency_injection` on **order-service** at 21:22:42 UTC — succeeded

Details: `{"pod": "order-service-74ff6cb5bf-m7vh5", "delay": "200ms", "jitter": "50ms", "command": "tc qdisc replace dev eth0 root netem delay 200ms 50ms distribution normal", "replicas_ready": 2}`

### 4. Detection

Confirmed at 21:22:52 UTC on **product-service** as `high_latency` · severity 0.6224 · Isolation Forest score 0.0801 (threshold 0.1031) · flags: iforest, zscore:caller_p99_ms

Evidence:
- p99_latency_ms=17.88ms vs baseline 16.09ms (z=+0.1)
- caller_p99_ms=107.49ms vs baseline 16.56ms (z=+6.1)

LSTM 60 s forecast: score 0.0761 (still anomalous)

### 5. Root-cause analysis

Origin **order-service** · type `high_latency` · confidence 0.785 · call path api-gateway → order-service · affected product-service, order-service, api-gateway, payment-service

> Root cause localised to order-service (high latency, confidence 78%). api-gateway also deviate as callers of order-service: its failure propagates to them. product-service, payment-service deviate because requests from order-service stopped reaching them. Signal: p99_latency_ms=3441.64ms vs baseline 246.95ms (z=+25.0); caller_p99_ms=3408.33ms vs baseline 246.99ms (z=+25.0).

Evidence:
- p99_latency_ms=3441.64ms vs baseline 246.95ms (z=+25.0)
- caller_p99_ms=3408.33ms vs baseline 246.99ms (z=+25.0)

| Candidate | Score | Why |
|---|---|---|
| order-service | 4.386 | severity 0.92; its dependencies ['product-service', 'payment-service'] are also anomalous (likely a victim); explains anomalies in callers ['api-gateway']; earliest onset; its calls to product-service take 457ms longer than product-service itself needs to serve them (caller-side or network problem); its calls to payment-service take 439ms longer than payment-service itself needs to serve them (cal… |
| product-service | 2.623 | severity 0.89; its own server-side latency/errors are normal; the degradation is only visible from callers (network or caller-side problem); no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service']; earliest onset |
| payment-service | 1.149 | severity 0.52; its own server-side latency/errors are normal; the degradation is only visible from callers (network or caller-side problem); no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service'] |
| api-gateway | 0.316 | severity 0.91; its dependencies ['product-service', 'order-service', 'payment-service'] are also anomalous (likely a victim) |

### 6. Decision

Action **traffic_reroute** (fallback rolling_restart) · confidence 0.654 · priority 7.342

- order-service: high latency at severity 0.92; business impact 8/10 -> priority 7.34. Playbook: traffic_reroute, fallback rolling_restart.
- Confidence in traffic_reroute: 0.65 (history 0.90 over 4 attempt(s) x RCA 0.79 x blast factor 0.93).
- Decision: traffic_reroute on order-service (fallback rolling_restart, confidence 0.65).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| traffic_reroute | order-service | success | yes | 11.1s | quarantined order-service-74ff6cb5bf-m7vh5 (worst replica by live telemetry (p99=4590ms, next worst score 247 vs 4590)); traffic now on 2 healthy replica(s) |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"pod": "order-service-74ff6cb5bf-m7vh5", "note": "pod no longer exists (replaced)"}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 2 failed of 1082 requests (0.2%) · user p99 3120.8 ms over 54 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 21:22:28 | STRATEGY | order-service | latency_injection: selected order-service (score 0.464: blast 0.25, impact 0.8, users 0.4, coverage penalty 0.0). |
| 21:22:42 | PREFLIGHT | order-service | GO: order-service at 2/2 Ready, system 100% healthy. Blast radius: 1 dependent service(s) ['api-gateway'], ~100% of users, risk MEDIUM. |
| 21:22:42 | INJECT | order-service | Injected latency_injection into order-service: tc netem egress delay on one replica (order-service-74ff6cb5bf-m7vh5). |
| 21:22:52 | DETECT | product-service | Anomaly confirmed on product-service 10s after injection: pattern matches high latency. Isolation Forest score +0.080 (threshold +0.103), severity 0.62. Evidence: p99_latency_ms=17.88ms vs baseline 16.09ms (z=+0.1); caller_p99_ms=107.49ms vs baseline 16.56ms (z=+6.1). LSTM forecast for the next 60s: score +0.076 (still anomalous). |
| 21:22:58 | RCA | order-service | Root cause localised to order-service (high latency, confidence 78%). api-gateway also deviate as callers of order-service: its failure propagates to them. product-service, payment-service deviate because requests from order-service stopped reaching them. Signal: p99_latency_ms=3441.64ms vs baseline 246.95ms (z=+25.0); caller_p99_ms=3408.33ms vs baseline 246.99ms (z=+25.0). |
| 21:22:58 | DECIDE | order-service | Confidence in traffic_reroute: 0.65 (history 0.90 over 4 attempt(s) x RCA 0.79 x blast factor 0.93). Decision: traffic_reroute on order-service (fallback rolling_restart, confidence 0.65). |
| 21:22:58 | REMEDIATE | order-service | Executing traffic_reroute on order-service. |
| 21:23:09 | REMEDIATE | order-service | traffic_reroute succeeded in 11.1s — quarantined order-service-74ff6cb5bf-m7vh5 (worst replica by live telemetry (p99=4590ms, next worst score 247 vs 4590)); traffic now on 2 healthy replica(s). |
| 21:23:13 | VERIFY | order-service | order-service verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 7ms). |
| 21:23:47 | TEARDOWN | order-service | Round teardown for order-service: no residual fault found; autoscaler returned to declared bounds. |
| 21:23:58 | RECOVERED | order-service | order-service recovered: detected in 9.82s, mitigated in 16.61s, fully back to its normal operating band in 45.01s (target 120s — MET). Users saw 2 failed requests out of 1082 (0.2%) during the incident. |

## Round 5 — replica_reduction → payment-service  ·  **RECOVERED**

TTD 4.79s (target 35s, met) · TTM 11.47s · TTR 20.0s (target 120s, met) · healed by primary · diagnosis correct, classification correct

### 2. Safety check before injecting

Decision **GO** · risk HIGH · system health 100.0% · target ready 2/2 · load 1.06× baseline · dependents api-gateway, order-service · users possibly affected 100%

### 3. Failure injected

`replica_reduction` on **payment-service** at 21:24:17 UTC — succeeded

Details: `{"hpa": "payment-service-hpa", "original": {"minReplicas": 2, "maxReplicas": 4}, "patched_to": {"minReplicas": 1, "maxReplicas": 1}}`

### 4. Detection

Confirmed at 21:24:22 UTC on **payment-service** as `replica_exhaustion` · severity 0.8 · Isolation Forest score 0.1493 (threshold 0.1031) · flags: capacity_below_baseline, metrics_unreachable

Evidence:
- replicas ready 1/1 (declared minimum 2)
- metrics endpoint unreachable on 50% of pods
- autoscaler bounds min=1 max=1 below declared minimum 2

LSTM 60 s forecast: score 0.1473 (returning to normal)

### 5. Root-cause analysis

Origin **payment-service** · type `replica_exhaustion` · confidence 0.96 · call path api-gateway → payment-service · affected payment-service

> Root cause localised to payment-service (replica exhaustion, confidence 96%). No other service deviates; the fault is contained to payment-service. Change evidence: HPA bounds 1-1 are below the declared 2-4; Pod payment-service-697dcd6758-2vcs4: Killing — Stopping container payment-service.

Evidence:
- replicas ready 1/1 (declared minimum 2)
- metrics endpoint unreachable on 50% of pods
- autoscaler bounds min=1 max=1 below declared minimum 2
- HPA bounds 1-1 are below the declared 2-4
- Pod payment-service-697dcd6758-2vcs4: Killing — Stopping container payment-service

| Candidate | Score | Why |
|---|---|---|
| payment-service | 7.6 | severity 0.80; no anomalous dependency explains it; earliest onset; structural fault on the service itself; HPA bounds 1-1 are below the declared 2-4; Pod payment-service-697dcd6758-2vcs4: Killing — Stopping container payment-service |

### 6. Decision

Action **hpa_scaleout** (fallback resource_restore) · confidence 0.718 · priority 8.0

- payment-service: replica exhaustion at severity 0.80; business impact 10/10 -> priority 8.00. Playbook: hpa_scaleout, fallback resource_restore.
- Confidence in hpa_scaleout: 0.72 (history 0.88 over 3 attempt(s) x RCA 0.96 x blast factor 0.85).
- Decision: hpa_scaleout on payment-service (fallback resource_restore, confidence 0.72).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| hpa_scaleout | payment-service | success | yes | 6.1s | autoscaler 1-1 -> 3-4; 1 -> 3 Ready replicas |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"restored": false, "note": "autoscaler already at or above declared bounds"}` · autoscaler `{"from": {"minReplicas": 3, "maxReplicas": 4}, "to": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 0 failed of 482 requests (0.0%) · user p99 243.9 ms over 24 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 21:24:02 | STRATEGY | payment-service | replica_reduction: selected payment-service (score -0.004: blast 0.5, impact 1.0, users 0.35, coverage penalty 1.0). |
| 21:24:17 | PREFLIGHT | payment-service | GO: payment-service at 2/2 Ready, system 100% healthy. Blast radius: 2 dependent service(s) ['api-gateway', 'order-service'], ~100% of users, risk HIGH. |
| 21:24:17 | INJECT | payment-service | Injected replica_reduction into payment-service: Clamp HPA to min=max=1 (payment-service-hpa). |
| 21:24:22 | DETECT | payment-service | Anomaly confirmed on payment-service 5s after injection: pattern matches replica exhaustion. Isolation Forest score +0.149 (threshold +0.103), severity 0.80. Evidence: replicas ready 1/1 (declared minimum 2); metrics endpoint unreachable on 50% of pods; autoscaler bounds min=1 max=1 below declared minimum 2. LSTM forecast for the next 60s: score +0.147 (returning to normal). |
| 21:24:27 | RCA | payment-service | Root cause localised to payment-service (replica exhaustion, confidence 96%). No other service deviates; the fault is contained to payment-service. Change evidence: HPA bounds 1-1 are below the declared 2-4; Pod payment-service-697dcd6758-2vcs4: Killing — Stopping container payment-service. |
| 21:24:27 | DECIDE | payment-service | Confidence in hpa_scaleout: 0.72 (history 0.88 over 3 attempt(s) x RCA 0.96 x blast factor 0.85). Decision: hpa_scaleout on payment-service (fallback resource_restore, confidence 0.72). |
| 21:24:28 | REMEDIATE | payment-service | Executing hpa_scaleout on payment-service. |
| 21:24:34 | REMEDIATE | payment-service | hpa_scaleout succeeded in 6.1s — autoscaler 1-1 -> 3-4; 1 -> 3 Ready replicas. |
| 21:24:38 | VERIFY | payment-service | payment-service verified functional: 3/3 replicas Ready and 5 consecutive user-path probes OK (last 7ms). |
| 21:24:42 | TEARDOWN | payment-service | Round teardown for payment-service: no residual fault found; autoscaler returned to declared bounds. |
| 21:24:53 | RECOVERED | payment-service | payment-service recovered: detected in 4.79s, mitigated in 11.47s, fully back to its normal operating band in 20.0s (target 120s — MET). Users saw 0 failed requests out of 482 (0.0%) during the incident. |

## Campaign-level events

| Time (UTC) | Phase | Message |
|---|---|---|
| 21:17:46 | CAMPAIGN | Campaign c-20261010-211746-a9ae starting: 5 rounds (pod_deletion, cpu_throttle, network_partition, latency_injection, replica_reduction). |
| 21:24:53 | SUMMARY | Campaign completed: resilience score 94.5/100 — EXCELLENT — every fault detected, diagnosed and healed within SLA. |
