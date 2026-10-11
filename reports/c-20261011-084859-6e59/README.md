# AutoHeal campaign `c-20261011-084859-6e59`

**Resilience score: 95.0/100** — EXCELLENT — every fault detected, diagnosed and healed within SLA

| Component | Points |
|---|---|
| recovery sla | 35.0 |
| detection sla | 16.0 |
| remediation effectiveness | 20.0 |
| diagnosis accuracy | 15.0 |
| user protection | 9.02 |

Mean time to detect: **18.76s** · mean time to recover: **33.0s** · RCA origin accuracy: **100%** · fault classification accuracy: **100%** · mean user failure ratio during incidents: **4.89%**

| # | Fault | Target | Detected as | RCA origin | Action | TTD | TTR | SLA | Users failed | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | cpu_throttle | product-service | cpu_throttle | product-service | resource_restore✓ | 9.75s | 50.0s | MET | 14.3% | RECOVERED |
| 2 | network_partition | payment-service | network_partition | payment-service | network_policy_rollback✓ | 9.78s | 50.01s | MET | 9.9% | RECOVERED |
| 3 | latency_injection | notification-service | high_latency | notification-service | rolling_restart✓ | 64.75s | 30.0s | MET | 0.0% | RECOVERED |
| 4 | pod_deletion | api-gateway | pod_crash | api-gateway | hpa_scaleout✓ | 4.76s | 15.0s | MET | 0.3% | RECOVERED |
| 5 | pod_deletion | order-service | pod_crash | order-service | hpa_scaleout✓ | 4.75s | 19.99s | MET | 0.0% | RECOVERED |
