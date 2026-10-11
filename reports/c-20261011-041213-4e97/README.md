# AutoHeal campaign `c-20261011-041213-4e97`

**Resilience score: 99.6/100** — EXCELLENT — every fault detected, diagnosed and healed within SLA

| Component | Points |
|---|---|
| recovery sla | 35.0 |
| detection sla | 20.0 |
| remediation effectiveness | 20.0 |
| diagnosis accuracy | 15.0 |
| user protection | 9.64 |

Mean time to detect: **8.81s** · mean time to recover: **36.0s** · RCA origin accuracy: **100%** · fault classification accuracy: **100%** · mean user failure ratio during incidents: **1.78%**

| # | Fault | Target | Detected as | RCA origin | Action | TTD | TTR | SLA | Users failed | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | pod_deletion | order-service | pod_crash | order-service | hpa_scaleout✓ | 4.82s | 20.0s | MET | 0.0% | RECOVERED |
| 2 | latency_injection | product-service | high_latency | product-service | traffic_reroute✓ | 9.82s | 45.0s | MET | 0.0% | RECOVERED |
| 3 | network_partition | payment-service | network_partition | payment-service | network_policy_rollback✓ | 9.81s | 50.0s | MET | 8.9% | RECOVERED |
| 4 | cpu_throttle | api-gateway | cpu_throttle | api-gateway | resource_restore✓ | 14.78s | 45.0s | MET | 0.0% | RECOVERED |
| 5 | replica_reduction | payment-service | replica_exhaustion | payment-service | hpa_scaleout✓ | 4.82s | 20.0s | MET | 0.0% | RECOVERED |
