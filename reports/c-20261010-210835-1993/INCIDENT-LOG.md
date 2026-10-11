# Incident log — campaign `c-20261010-210835-1993`

**Resilience score 98.5/100** — EXCELLENT — every fault detected, diagnosed and healed within SLA

| Component | Points |
|---|---|
| recovery sla | 35.0 |
| detection sla | 20.0 |
| remediation effectiveness | 20.0 |
| diagnosis accuracy | 15.0 |
| user protection | 8.47 |

| # | Fault | Target | Status | TTD | TTR | Users failed |
|---|---|---|---|---|---|---|
| 1 | pod_deletion | payment-service | RECOVERED | 4.81s | 20.0s | 0.0% |
| 2 | cpu_throttle | product-service | RECOVERED | 9.83s | 60.0s | 0.6% |
| 3 | network_partition | api-gateway | RECOVERED | 14.82s | 40.0s | 37.4% |
| 4 | latency_injection | order-service | RECOVERED | 9.82s | 50.01s | 0.4% |
| 5 | replica_reduction | payment-service | RECOVERED | 4.83s | 19.99s | 0.0% |

## Round 1 — pod_deletion → payment-service  ·  **RECOVERED**

TTD 4.81s (target 25s, met) · TTM 11.4s · TTR 20.0s (target 90s, met) · healed by primary · diagnosis correct, classification correct

### 2. Safety check before injecting

Decision **GO** · risk HIGH · system health 100.0% · target ready 2/2 · load 0.98× baseline · dependents api-gateway, order-service · users possibly affected 100%

### 3. Failure injected

`pod_deletion` on **payment-service** at 21:08:52 UTC — succeeded

Details: `{"pod": "payment-service-8478f885-w5kwf", "pod_ip": "10.244.0.76", "ready_pods_before": 2}`

### 4. Detection

Confirmed at 21:08:57 UTC on **payment-service** as `pod_crash` · severity 0.4185 · Isolation Forest score 0.0929 (threshold 0.1031) · flags: replicas_lost

Evidence:
- replicas ready 2/2 (declared minimum 2)
- Ready pod(s) payment-service-8478f885-w5kwf disappeared without a scale-down or rollout
- caller_error_rate=0.0% vs baseline 0.0% (z=+0.0)

LSTM 60 s forecast: score 0.0772 (returning to normal)

### 5. Root-cause analysis

Origin **payment-service** · type `pod_crash` · confidence 0.92 · call path api-gateway → payment-service · affected payment-service

> Root cause localised to payment-service (pod crash, confidence 92%). No other service deviates; the fault is contained to payment-service. Change evidence: Pod payment-service-8478f885-gpz7v: Unhealthy — Startup probe failed: Get "http://10.244.0.78:8003/health": dial tcp 10.244.0.78:8003: connect: connection refused; Pod payment-service-8478f885-w5kwf: Killing — Stopping container payment-service.

Evidence:
- replicas ready 2/2 (declared minimum 2)
- Ready pod(s) payment-service-8478f885-w5kwf disappeared without a scale-down or rollout
- caller_error_rate=0.0% vs baseline 0.0% (z=+0.0)
- Pod payment-service-8478f885-gpz7v: Unhealthy — Startup probe failed: Get "http://10.244.0.78:8003/health": dial tcp 10.244.0.78:8003: connect: connection refused
- Pod payment-service-8478f885-w5kwf: Killing — Stopping container payment-service

| Candidate | Score | Why |
|---|---|---|
| payment-service | 4.002 | severity 0.25; no anomalous dependency explains it; earliest onset; structural fault on the service itself; Pod payment-service-8478f885-gpz7v: Unhealthy — Startup probe failed: Get "http://10.244.0.78:8003/health": dial tcp 10.244.0.78:8003: connect: connection refused; Pod payment-service-8478f885-w5kwf: Killing — Stopping container payment-service |

### 6. Decision

Action **hpa_scaleout** (fallback rolling_restart) · confidence 0.626 · priority 2.511

- payment-service: pod crash at severity 0.25; business impact 10/10 -> priority 2.51. Playbook: hpa_scaleout, fallback rolling_restart.
- Confidence in hpa_scaleout: 0.63 (history 0.80 over 1 attempt(s) x RCA 0.92 x blast factor 0.85).
- Decision: hpa_scaleout on payment-service (fallback rolling_restart, confidence 0.63).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| hpa_scaleout | payment-service | success | yes | 6.1s | autoscaler 2-4 -> 3-4; 2 -> 3 Ready replicas |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"reversible": false, "note": "Kubernetes reschedules deleted pods by itself"}` · autoscaler `{"from": {"minReplicas": 3, "maxReplicas": 4}, "to": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 0 failed of 481 requests (0.0%) · user p99 243.3 ms over 24 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 21:08:37 | STRATEGY | payment-service | pod_deletion: selected payment-service (score 0.596: blast 0.5, impact 1.0, users 0.35, coverage penalty 0.0). |
| 21:08:52 | PREFLIGHT | payment-service | GO: payment-service at 2/2 Ready, system 100% healthy. Blast radius: 2 dependent service(s) ['api-gateway', 'order-service'], ~100% of users, risk HIGH. |
| 21:08:52 | INJECT | payment-service | Injected pod_deletion into payment-service: Force-delete one Ready pod (grace period 0) (payment-service-8478f885-w5kwf). |
| 21:08:57 | DETECT | payment-service | Anomaly confirmed on payment-service 5s after injection: pattern matches pod crash. Isolation Forest score +0.093 (threshold +0.103), severity 0.42. Evidence: replicas ready 2/2 (declared minimum 2); Ready pod(s) payment-service-8478f885-w5kwf disappeared without a scale-down or rollout; caller_error_rate=0.0% vs baseline 0.0% (z=+0.0). LSTM forecast for the next 60s: score +0.077 (returning to normal). |
| 21:09:02 | RCA | payment-service | Root cause localised to payment-service (pod crash, confidence 92%). No other service deviates; the fault is contained to payment-service. Change evidence: Pod payment-service-8478f885-gpz7v: Unhealthy — Startup probe failed: Get "http://10.244.0.78:8003/health": dial tcp 10.244.0.78:8003: connect: connection refused; Pod payment-service-8478f885-w5kwf: Killing — Stopping container payment-service. |
| 21:09:02 | DECIDE | payment-service | Confidence in hpa_scaleout: 0.63 (history 0.80 over 1 attempt(s) x RCA 0.92 x blast factor 0.85). Decision: hpa_scaleout on payment-service (fallback rolling_restart, confidence 0.63). |
| 21:09:02 | REMEDIATE | payment-service | Executing hpa_scaleout on payment-service. |
| 21:09:09 | REMEDIATE | payment-service | hpa_scaleout succeeded in 6.1s — autoscaler 2-4 -> 3-4; 2 -> 3 Ready replicas. |
| 21:09:13 | VERIFY | payment-service | payment-service verified functional: 3/3 replicas Ready and 5 consecutive user-path probes OK (last 6ms). |
| 21:09:17 | TEARDOWN | payment-service | Round teardown for payment-service: no residual fault found; autoscaler returned to declared bounds. |
| 21:09:27 | RECOVERED | payment-service | payment-service recovered: detected in 4.81s, mitigated in 11.4s, fully back to its normal operating band in 20.0s (target 90s — MET). Users saw 0 failed requests out of 481 (0.0%) during the incident. |

## Round 2 — cpu_throttle → product-service  ·  **RECOVERED**

TTD 9.83s (target 35s, met) · TTM 7.47s · TTR 60.0s (target 90s, met) · healed by primary · diagnosis correct, classification correct

### 2. Safety check before injecting

Decision **GO** · risk HIGH · system health 100.0% · target ready 2/2 · load 1.01× baseline · dependents api-gateway, order-service · users possibly affected 100%

### 3. Failure injected

`cpu_throttle` on **product-service** at 21:09:57 UTC — succeeded

Details: `{"pods": ["product-service-6dd7d4bc55-68nzf", "product-service-6dd7d4bc55-xlft5"], "cpu_limit": "25m", "original": {"product-service-6dd7d4bc55-68nzf": {"product-service": {"requests": {"cpu": "100m", "memory": "96Mi"}, "limits": {"cpu": "500m", "memory": "256Mi"}}}, "product-service-6dd7d4bc55-xlft5": {"product-service": {"requests": {"cpu": "100m", "memory": "96Mi"}, "limits": {"cpu": "500m", "memory": "256Mi"}}}}}`

### 4. Detection

Confirmed at 21:10:07 UTC on **api-gateway** as `high_latency` · severity 0.9408 · Isolation Forest score -0.0519 (threshold 0.1031) · flags: iforest, zscore:p99_latency_ms, zscore:inflight, zscore:caller_p99_ms

Evidence:
- p99_latency_ms=937.15ms vs baseline 242.46ms (z=+19.1)
- caller_p99_ms=441.87ms vs baseline 242.66ms (z=+5.5)

LSTM 60 s forecast: score -0.0464 (still anomalous)

### 5. Root-cause analysis

Origin **product-service** · type `cpu_throttle` · confidence 0.95 · call path api-gateway → product-service · affected api-gateway, product-service, order-service

> Root cause localised to product-service (cpu throttle, confidence 95%). api-gateway, order-service also deviate as callers of product-service: its failure propagates to them. Change evidence: pod product-service-6dd7d4bc55-68nzf CPU limit is 25m vs declared 500m; pod product-service-6dd7d4bc55-xlft5 CPU limit is 25m vs declared 500m.

Evidence:
- p99_latency_ms=22.20ms vs baseline 16.09ms (z=+0.4)
- caller_p99_ms=929.29ms vs baseline 16.56ms (z=+25.0)
- pod product-service-6dd7d4bc55-68nzf CPU limit is 25m vs declared 500m
- pod product-service-6dd7d4bc55-xlft5 CPU limit is 25m vs declared 500m

| Candidate | Score | Why |
|---|---|---|
| product-service | 9.23 | severity 0.94; no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service']; earliest onset; pod product-service-6dd7d4bc55-68nzf CPU limit is 25m vs declared 500m; pod product-service-6dd7d4bc55-xlft5 CPU limit is 25m vs declared 500m |
| order-service | 1.943 | severity 0.94; its dependencies ['product-service'] are also anomalous (likely a victim); explains anomalies in callers ['api-gateway']; earliest onset; 4 ERROR log lines in the last 60s, e.g. 'dependency failure (product-service)' |
| api-gateway | 1.683 | severity 0.94; its dependencies ['product-service', 'order-service'] are also anomalous (likely a victim); earliest onset; 10 ERROR log lines in the last 60s, e.g. 'upstream error (order-service)' |

### 6. Decision

Action **resource_restore** (fallback rolling_restart) · confidence 0.686 · priority 5.641

- product-service: cpu throttle at severity 0.94; business impact 6/10 -> priority 5.64. Playbook: resource_restore, fallback rolling_restart.
- Confidence in resource_restore: 0.69 (history 0.85 over 2 attempt(s) x RCA 0.95 x blast factor 0.85).
- Decision: resource_restore on product-service (fallback rolling_restart, confidence 0.69).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| resource_restore | product-service | success | yes | 2.1s | resized 2 container(s) in place to {'product-service': {'requests': {'cpu': '100m', 'memory': '96Mi'}, 'limits': {'cpu': '500m', 'memory': '256Mi'}}} |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"restored_pods": []}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 8 failed of 1385 requests (0.6%) · user p99 4616.8 ms over 69 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 21:09:32 | STRATEGY | product-service | cpu_throttle: selected product-service (score 0.573: blast 0.5, impact 0.6, users 0.75, coverage penalty 0.0). |
| 21:09:37 | PREFLIGHT | product-service | Waiting for steady state before injecting: steady state not met: payment-service currently anomalous. |
| 21:09:57 | PREFLIGHT | product-service | GO: product-service at 2/2 Ready, system 100% healthy. Blast radius: 2 dependent service(s) ['api-gateway', 'order-service'], ~100% of users, risk HIGH. |
| 21:09:57 | INJECT | product-service | Injected cpu_throttle into product-service: In-place resize of every replica's CPU limit to a starvation value (product-service-6dd7d4bc55-68nzf,product-service-6dd7d4bc55-xlft5). |
| 21:10:07 | DETECT | api-gateway | Anomaly confirmed on api-gateway 10s after injection: pattern matches high latency. Isolation Forest score -0.052 (threshold +0.103), severity 0.94. Evidence: p99_latency_ms=937.15ms vs baseline 242.46ms (z=+19.1); caller_p99_ms=441.87ms vs baseline 242.66ms (z=+5.5). Also deviating: product-service, order-service. LSTM forecast for the next 60s: score -0.046 (still anomalous). |
| 21:10:13 | RCA | product-service | Root cause localised to product-service (cpu throttle, confidence 95%). api-gateway, order-service also deviate as callers of product-service: its failure propagates to them. Change evidence: pod product-service-6dd7d4bc55-68nzf CPU limit is 25m vs declared 500m; pod product-service-6dd7d4bc55-xlft5 CPU limit is 25m vs declared 500m. |
| 21:10:13 | DECIDE | product-service | Confidence in resource_restore: 0.69 (history 0.85 over 2 attempt(s) x RCA 0.95 x blast factor 0.85). Decision: resource_restore on product-service (fallback rolling_restart, confidence 0.69). |
| 21:10:13 | REMEDIATE | product-service | Executing resource_restore on product-service. |
| 21:10:15 | REMEDIATE | product-service | resource_restore succeeded in 2.1s — resized 2 container(s) in place to {'product-service': {'requests': {'cpu': '100m', 'memory': '96Mi'}, 'limits': {'cpu': '500m', 'memory': '256Mi'}}}. |
| 21:10:19 | VERIFY | product-service | product-service verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 8ms). |
| 21:11:17 | TEARDOWN | product-service | Round teardown for product-service: no residual fault found; autoscaler returned to declared bounds. |
| 21:11:28 | RECOVERED | product-service | product-service recovered: detected in 9.83s, mitigated in 7.47s, fully back to its normal operating band in 60.0s (target 90s — MET). Users saw 8 failed requests out of 1385 (0.6%) during the incident. |

## Round 3 — network_partition → api-gateway  ·  **RECOVERED**

TTD 14.82s (target 30s, met) · TTM 5.54s · TTR 40.0s (target 90s, met) · healed by primary · diagnosis correct, classification correct

### 2. Safety check before injecting

Decision **GO** · risk MEDIUM · system health 100.0% · target ready 2/2 · load 1.01× baseline · dependents none · users possibly affected 100%

### 3. Failure injected

`network_partition` on **api-gateway** at 21:11:47 UTC — succeeded

Details: `{"policy": "chaos-isolate-api-gateway", "effect": "deny all ingress + egress", "conntrack_flush": {"ok": true, "pod_ips": ["10.244.0.69", "10.244.0.68"], "agents": {"chaos-agent-45wxr": true}}}`

### 4. Detection

Confirmed at 21:12:02 UTC on **api-gateway** as `network_partition` · severity 0.9748 · Isolation Forest score -0.0403 (threshold 0.1031) · flags: iforest, zscore:caller_error_rate, zscore:caller_p99_ms, metrics_unreachable

Evidence:
- replicas ready 2/2 (declared minimum 2)
- metrics endpoint unreachable on 100% of pods
- caller_error_rate=20.2% vs baseline 0.0% (z=+10.1)
- request_rate=13.99 req/s vs baseline 20.00 req/s (z=-3.0)
- pods are running (no container restarts) but cannot be reached over the pod network

LSTM 60 s forecast: score -0.0484 (still anomalous)

### 5. Root-cause analysis

Origin **api-gateway** · type `network_partition` · confidence 0.95 · call path api-gateway · affected api-gateway, product-service, order-service, payment-service, notification-service

> Root cause localised to api-gateway (network partition, confidence 95%). product-service, order-service, payment-service, notification-service deviate because requests from api-gateway stopped reaching them. Change evidence: NetworkPolicy 'chaos-isolate-api-gateway' denies all Ingress/Egress traffic for pods of api-gateway, created 20s ago; 12 ERROR log lines in the last 60s, e.g. 'upstream error (order-service)'.

Evidence:
- replicas ready 2/2 (declared minimum 2)
- metrics endpoint unreachable on 100% of pods
- caller_error_rate=20.2% vs baseline 0.0% (z=+10.1)
- request_rate=13.99 req/s vs baseline 20.00 req/s (z=-3.0)
- pods are running (no container restarts) but cannot be reached over the pod network
- NetworkPolicy 'chaos-isolate-api-gateway' denies all Ingress/Egress traffic for pods of api-gateway, created 20s ago
- 12 ERROR log lines in the last 60s, e.g. 'upstream error (order-service)'

| Candidate | Score | Why |
|---|---|---|
| api-gateway | 8.012 | severity 0.98; no anomalous dependency explains it; earliest onset; structural fault on the service itself; NetworkPolicy 'chaos-isolate-api-gateway' denies all Ingress/Egress traffic for pods of api-gateway, created 20s ago; 12 ERROR log lines in the last 60s, e.g. 'upstream error (order-service)' |
| payment-service | 2.327 | severity 0.49; only symptom is reduced traffic — consistent with an upstream failure; no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service']; earliest onset |
| product-service | 2.167 | severity 0.41; only symptom is reduced traffic — consistent with an upstream failure; no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service']; earliest onset |
| order-service | 1.978 | severity 0.46; only symptom is reduced traffic — consistent with an upstream failure; no anomalous dependency explains it; explains anomalies in callers ['api-gateway']; earliest onset |
| notification-service | 1.977 | severity 0.46; only symptom is reduced traffic — consistent with an upstream failure; no anomalous dependency explains it; explains anomalies in callers ['api-gateway']; earliest onset |

### 6. Decision

Action **network_policy_rollback** (fallback rolling_restart) · confidence 0.76 · priority 8.783

- api-gateway: network partition at severity 0.98; business impact 9/10 -> priority 8.78. Playbook: network_policy_rollback, fallback rolling_restart.
- Confidence in network_policy_rollback: 0.76 (history 0.80 over 1 attempt(s) x RCA 0.95 x blast factor 1.00).
- Decision: network_policy_rollback on api-gateway (fallback rolling_restart, confidence 0.76).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| network_policy_rollback | api-gateway | success | yes | 0.0s | removed 1 isolating NetworkPolicy(ies): chaos-isolate-api-gateway |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"policy": "chaos-isolate-api-gateway", "deleted": false}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 417 failed of 1116 requests (37.4%) · user p99 2498.8 ms over 54 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 21:11:32 | STRATEGY | api-gateway | network_partition: selected api-gateway (score 0.524: blast 0.0, impact 0.9, users 1.0, coverage penalty 0.0). |
| 21:11:47 | PREFLIGHT | api-gateway | GO: api-gateway at 2/2 Ready, system 100% healthy. Blast radius: 0 dependent service(s) , ~100% of users, risk MEDIUM. |
| 21:11:48 | INJECT | api-gateway | Injected network_partition into api-gateway: Deny-all NetworkPolicy selecting the service's pods (chaos-isolate-api-gateway). |
| 21:12:02 | DETECT | api-gateway | Anomaly confirmed on api-gateway 15s after injection: pattern matches network partition. Isolation Forest score -0.040 (threshold +0.103), severity 0.97. Evidence: replicas ready 2/2 (declared minimum 2); metrics endpoint unreachable on 100% of pods; caller_error_rate=20.2% vs baseline 0.0% (z=+10.1). Also deviating: order-service, payment-service, notification-service. LSTM forecast for the next 60s: score -0.048 (still anomalous). |
| 21:12:08 | RCA | api-gateway | Root cause localised to api-gateway (network partition, confidence 95%). product-service, order-service, payment-service, notification-service deviate because requests from api-gateway stopped reaching them. Change evidence: NetworkPolicy 'chaos-isolate-api-gateway' denies all Ingress/Egress traffic for pods of api-gateway, created 20s ago; 12 ERROR log lines in the last 60s, e.g. 'upstream error (order-service)'. |
| 21:12:08 | DECIDE | api-gateway | Confidence in network_policy_rollback: 0.76 (history 0.80 over 1 attempt(s) x RCA 0.95 x blast factor 1.00). Decision: network_policy_rollback on api-gateway (fallback rolling_restart, confidence 0.76). |
| 21:12:08 | REMEDIATE | api-gateway | Executing network_policy_rollback on api-gateway. |
| 21:12:08 | REMEDIATE | api-gateway | network_policy_rollback succeeded in 0.0s — removed 1 isolating NetworkPolicy(ies): chaos-isolate-api-gateway. |
| 21:12:12 | VERIFY | api-gateway | api-gateway verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 6ms). |
| 21:12:52 | TEARDOWN | api-gateway | Round teardown for api-gateway: no residual fault found; autoscaler returned to declared bounds. |
| 21:13:02 | RECOVERED | api-gateway | api-gateway recovered: detected in 14.82s, mitigated in 5.54s, fully back to its normal operating band in 40.0s (target 90s — MET). Users saw 417 failed requests out of 1116 (37.4%) during the incident. |

## Round 4 — latency_injection → order-service  ·  **RECOVERED**

TTD 9.82s (target 35s, met) · TTM 17.45s · TTR 50.01s (target 120s, met) · healed by primary · diagnosis correct, classification correct

### 2. Safety check before injecting

Decision **GO** · risk MEDIUM · system health 100.0% · target ready 2/2 · load 0.89× baseline · dependents api-gateway · users possibly affected 100%

### 3. Failure injected

`latency_injection` on **order-service** at 21:13:22 UTC — succeeded

Details: `{"pod": "order-service-74ff6cb5bf-tcgsw", "delay": "200ms", "jitter": "50ms", "command": "tc qdisc replace dev eth0 root netem delay 200ms 50ms distribution normal", "replicas_ready": 2}`

### 4. Detection

Confirmed at 21:13:32 UTC on **order-service** as `high_latency` · severity 0.9371 · Isolation Forest score -0.0408 (threshold 0.1031) · flags: iforest, zscore:p99_latency_ms, zscore:caller_p99_ms

Evidence:
- p99_latency_ms=575.00ms vs baseline 246.95ms (z=+8.9)
- caller_p99_ms=1045.03ms vs baseline 246.99ms (z=+21.5)

LSTM 60 s forecast: score -0.0372 (still anomalous)

### 5. Root-cause analysis

Origin **order-service** · type `high_latency` · confidence 0.788 · call path api-gateway → order-service · affected api-gateway, product-service, order-service, payment-service

> Root cause localised to order-service (high latency, confidence 79%). api-gateway also deviate as callers of order-service: its failure propagates to them. product-service, payment-service deviate because requests from order-service stopped reaching them. Signal: p99_latency_ms=575.00ms vs baseline 246.95ms (z=+8.9); caller_p99_ms=1045.03ms vs baseline 246.99ms (z=+21.5).

Evidence:
- p99_latency_ms=575.00ms vs baseline 246.95ms (z=+8.9)
- caller_p99_ms=1045.03ms vs baseline 246.99ms (z=+21.5)

| Candidate | Score | Why |
|---|---|---|
| order-service | 4.433 | severity 0.94; its dependencies ['product-service', 'payment-service'] are also anomalous (likely a victim); explains anomalies in callers ['api-gateway']; earliest onset; its calls to product-service take 473ms longer than product-service itself needs to serve them (caller-side or network problem); its calls to payment-service take 492ms longer than payment-service itself needs to serve them (cal… |
| product-service | 2.65 | severity 0.90; its own server-side latency/errors are normal; the degradation is only visible from callers (network or caller-side problem); no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service']; earliest onset |
| payment-service | 2.234 | severity 0.69; its own server-side latency/errors are normal; the degradation is only visible from callers (network or caller-side problem); no anomalous dependency explains it; explains anomalies in callers ['api-gateway', 'order-service']; earliest onset |
| api-gateway | 1.631 | severity 0.94; its dependencies ['product-service', 'order-service', 'payment-service'] are also anomalous (likely a victim); earliest onset; 2 ERROR log lines in the last 60s, e.g. 'upstream error (order-service)' |

### 6. Decision

Action **traffic_reroute** (fallback rolling_restart) · confidence 0.641 · priority 7.532

- order-service: high latency at severity 0.94; business impact 8/10 -> priority 7.53. Playbook: traffic_reroute, fallback rolling_restart.
- Confidence in traffic_reroute: 0.64 (history 0.88 over 3 attempt(s) x RCA 0.79 x blast factor 0.93).
- Decision: traffic_reroute on order-service (fallback rolling_restart, confidence 0.64).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| traffic_reroute | order-service | success | yes | 11.1s | quarantined order-service-74ff6cb5bf-tcgsw (worst replica by live telemetry (p99=4920ms, next worst score 246 vs 4920)); traffic now on 2 healthy replica(s) |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"pod": "order-service-74ff6cb5bf-tcgsw", "note": "pod no longer exists (replaced)"}` · autoscaler `{"unchanged": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 4 failed of 1181 requests (0.4%) · user p99 4284.8 ms over 59 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 21:13:08 | STRATEGY | order-service | latency_injection: selected order-service (score 0.471: blast 0.25, impact 0.8, users 0.4, coverage penalty 0.0). |
| 21:13:22 | PREFLIGHT | order-service | GO: order-service at 2/2 Ready, system 100% healthy. Blast radius: 1 dependent service(s) ['api-gateway'], ~100% of users, risk MEDIUM. |
| 21:13:22 | INJECT | order-service | Injected latency_injection into order-service: tc netem egress delay on one replica (order-service-74ff6cb5bf-tcgsw). |
| 21:13:32 | DETECT | order-service | Anomaly confirmed on order-service 10s after injection: pattern matches high latency. Isolation Forest score -0.041 (threshold +0.103), severity 0.94. Evidence: p99_latency_ms=575.00ms vs baseline 246.95ms (z=+8.9); caller_p99_ms=1045.03ms vs baseline 246.99ms (z=+21.5). LSTM forecast for the next 60s: score -0.037 (still anomalous). |
| 21:13:38 | RCA | order-service | Root cause localised to order-service (high latency, confidence 79%). api-gateway also deviate as callers of order-service: its failure propagates to them. product-service, payment-service deviate because requests from order-service stopped reaching them. Signal: p99_latency_ms=575.00ms vs baseline 246.95ms (z=+8.9); caller_p99_ms=1045.03ms vs baseline 246.99ms (z=+21.5). |
| 21:13:38 | DECIDE | order-service | Confidence in traffic_reroute: 0.64 (history 0.88 over 3 attempt(s) x RCA 0.79 x blast factor 0.93). Decision: traffic_reroute on order-service (fallback rolling_restart, confidence 0.64). |
| 21:13:38 | REMEDIATE | order-service | Executing traffic_reroute on order-service. |
| 21:13:49 | REMEDIATE | order-service | traffic_reroute succeeded in 11.1s — quarantined order-service-74ff6cb5bf-tcgsw (worst replica by live telemetry (p99=4920ms, next worst score 246 vs 4920)); traffic now on 2 healthy replica(s). |
| 21:13:54 | VERIFY | order-service | order-service verified functional: 2/2 replicas Ready and 5 consecutive user-path probes OK (last 6ms). |
| 21:14:32 | TEARDOWN | order-service | Round teardown for order-service: no residual fault found; autoscaler returned to declared bounds. |
| 21:14:42 | RECOVERED | order-service | order-service recovered: detected in 9.82s, mitigated in 17.45s, fully back to its normal operating band in 50.01s (target 120s — MET). Users saw 4 failed requests out of 1181 (0.4%) during the incident. |

## Round 5 — replica_reduction → payment-service  ·  **RECOVERED**

TTD 4.83s (target 35s, met) · TTM 11.42s · TTR 19.99s (target 120s, met) · healed by primary · diagnosis correct, classification correct

### 2. Safety check before injecting

Decision **GO** · risk HIGH · system health 100.0% · target ready 2/2 · load 0.92× baseline · dependents api-gateway, order-service · users possibly affected 100%

### 3. Failure injected

`replica_reduction` on **payment-service** at 21:15:02 UTC — succeeded

Details: `{"hpa": "payment-service-hpa", "original": {"minReplicas": 2, "maxReplicas": 4}, "patched_to": {"minReplicas": 1, "maxReplicas": 1}}`

### 4. Detection

Confirmed at 21:15:07 UTC on **payment-service** as `replica_exhaustion` · severity 0.5 · Isolation Forest score 0.1391 (threshold 0.1031) · flags: capacity_below_baseline

Evidence:
- replicas ready 1/1 (declared minimum 2)
- autoscaler bounds min=1 max=1 below declared minimum 2

LSTM 60 s forecast: score 0.1453 (returning to normal)

### 5. Root-cause analysis

Origin **payment-service** · type `replica_exhaustion` · confidence 0.96 · call path api-gateway → payment-service · affected payment-service

> Root cause localised to payment-service (replica exhaustion, confidence 96%). No other service deviates; the fault is contained to payment-service. Change evidence: HPA bounds 1-1 are below the declared 2-4; Pod payment-service-8478f885-fnvgm: Killing — Stopping container payment-service.

Evidence:
- replicas ready 1/1 (declared minimum 2)
- autoscaler bounds min=1 max=1 below declared minimum 2
- HPA bounds 1-1 are below the declared 2-4
- Pod payment-service-8478f885-fnvgm: Killing — Stopping container payment-service

| Candidate | Score | Why |
|---|---|---|
| payment-service | 7.0 | severity 0.50; no anomalous dependency explains it; earliest onset; structural fault on the service itself; HPA bounds 1-1 are below the declared 2-4; Pod payment-service-8478f885-fnvgm: Killing — Stopping container payment-service |

### 6. Decision

Action **hpa_scaleout** (fallback resource_restore) · confidence 0.694 · priority 5.0

- payment-service: replica exhaustion at severity 0.50; business impact 10/10 -> priority 5.00. Playbook: hpa_scaleout, fallback resource_restore.
- Confidence in hpa_scaleout: 0.69 (history 0.85 over 2 attempt(s) x RCA 0.96 x blast factor 0.85).
- Decision: hpa_scaleout on payment-service (fallback resource_restore, confidence 0.69).

### 7. Remediation

| Remediator | Service | Result | Verified | Duration | Summary |
|---|---|---|---|---|---|
| hpa_scaleout | payment-service | success | yes | 6.1s | autoscaler 1-1 -> 3-4; 1 -> 3 Ready replicas |

### 8. Teardown and user impact

Fault still present at teardown: **no** · reverse `{"restored": false, "note": "autoscaler already at or above declared bounds"}` · autoscaler `{"from": {"minReplicas": 3, "maxReplicas": 4}, "to": {"minReplicas": 2, "maxReplicas": 4}}`

Users: 0 failed of 480 requests (0.0%) · user p99 243.4 ms over 24 s

### 9. Full narration

| Time (UTC) | Phase | Service | Message |
|---|---|---|---|
| 21:14:47 | STRATEGY | payment-service | replica_reduction: selected payment-service (score -0.010: blast 0.5, impact 1.0, users 0.35, coverage penalty 1.0). |
| 21:15:02 | PREFLIGHT | payment-service | GO: payment-service at 2/2 Ready, system 100% healthy. Blast radius: 2 dependent service(s) ['api-gateway', 'order-service'], ~100% of users, risk HIGH. |
| 21:15:02 | INJECT | payment-service | Injected replica_reduction into payment-service: Clamp HPA to min=max=1 (payment-service-hpa). |
| 21:15:07 | DETECT | payment-service | Anomaly confirmed on payment-service 5s after injection: pattern matches replica exhaustion. Isolation Forest score +0.139 (threshold +0.103), severity 0.50. Evidence: replicas ready 1/1 (declared minimum 2); autoscaler bounds min=1 max=1 below declared minimum 2. LSTM forecast for the next 60s: score +0.145 (returning to normal). |
| 21:15:12 | RCA | payment-service | Root cause localised to payment-service (replica exhaustion, confidence 96%). No other service deviates; the fault is contained to payment-service. Change evidence: HPA bounds 1-1 are below the declared 2-4; Pod payment-service-8478f885-fnvgm: Killing — Stopping container payment-service. |
| 21:15:12 | DECIDE | payment-service | Confidence in hpa_scaleout: 0.69 (history 0.85 over 2 attempt(s) x RCA 0.96 x blast factor 0.85). Decision: hpa_scaleout on payment-service (fallback resource_restore, confidence 0.69). |
| 21:15:13 | REMEDIATE | payment-service | Executing hpa_scaleout on payment-service. |
| 21:15:19 | REMEDIATE | payment-service | hpa_scaleout succeeded in 6.1s — autoscaler 1-1 -> 3-4; 1 -> 3 Ready replicas. |
| 21:15:23 | VERIFY | payment-service | payment-service verified functional: 3/3 replicas Ready and 5 consecutive user-path probes OK (last 8ms). |
| 21:15:27 | TEARDOWN | payment-service | Round teardown for payment-service: no residual fault found; autoscaler returned to declared bounds. |
| 21:15:37 | RECOVERED | payment-service | payment-service recovered: detected in 4.83s, mitigated in 11.42s, fully back to its normal operating band in 19.99s (target 120s — MET). Users saw 0 failed requests out of 480 (0.0%) during the incident. |

## Campaign-level events

| Time (UTC) | Phase | Message |
|---|---|---|
| 21:08:35 | CAMPAIGN | Campaign c-20261010-210835-1993 starting: 5 rounds (pod_deletion, cpu_throttle, network_partition, latency_injection, replica_reduction). |
| 21:15:38 | SUMMARY | Campaign completed: resilience score 98.5/100 — EXCELLENT — every fault detected, diagnosed and healed within SLA. |
