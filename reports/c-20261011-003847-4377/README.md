# AutoHeal campaign `c-20261011-003847-4377`

**Resilience score: 98.9/100** — EXCELLENT — every fault detected, diagnosed and healed within SLA

| Component | Points |
|---|---|
| recovery sla | 35.0 |
| detection sla | 20.0 |
| remediation effectiveness | 20.0 |
| diagnosis accuracy | 15.0 |
| user protection | 8.94 |

Mean time to detect: **8.81s** · mean time to recover: **35.0s** · RCA origin accuracy: **100%** · fault classification accuracy: **100%** · mean user failure ratio during incidents: **5.30%**

| # | Fault | Target | Detected as | RCA origin | Action | TTD | TTR | SLA | Users failed | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | latency_injection | payment-service | high_latency | payment-service | traffic_reroute✓ | 14.81s | 50.0s | MET | 0.1% | RECOVERED |
| 2 | replica_reduction | api-gateway | replica_exhaustion | api-gateway | hpa_scaleout✓ | 4.82s | 15.0s | MET | 0.0% | RECOVERED |
| 3 | cpu_throttle | order-service | cpu_throttle | order-service | resource_restore✓ | 9.82s | 55.0s | MET | 5.9% | RECOVERED |
| 4 | network_partition | product-service | network_partition | product-service | network_policy_rollback✓ | 9.8s | 40.0s | MET | 20.5% | RECOVERED |
| 5 | pod_deletion | notification-service | pod_crash | notification-service | hpa_scaleout✓ | 4.81s | 15.0s | MET | 0.0% | RECOVERED |
