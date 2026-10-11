# AutoHeal campaign `c-20261011-095621-cefd`

**Resilience score: 99.5/100** — EXCELLENT — every fault detected, diagnosed and healed within SLA

| Component | Points |
|---|---|
| recovery sla | 35.0 |
| detection sla | 20.0 |
| remediation effectiveness | 20.0 |
| diagnosis accuracy | 15.0 |
| user protection | 9.52 |

Mean time to detect: **8.85s** · mean time to recover: **36.0s** · RCA origin accuracy: **100%** · fault classification accuracy: **100%** · mean user failure ratio during incidents: **2.40%**

| # | Fault | Target | Detected as | RCA origin | Action | TTD | TTR | SLA | Users failed | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | cpu_throttle | payment-service | cpu_throttle | payment-service | resource_restore✓ | 9.85s | 54.99s | MET | 0.0% | RECOVERED |
| 2 | replica_reduction | api-gateway | replica_exhaustion | api-gateway | hpa_scaleout✓ | 4.85s | 14.99s | MET | 0.0% | RECOVERED |
| 3 | latency_injection | product-service | high_latency | product-service | traffic_reroute✓ | 14.84s | 50.0s | MET | 0.0% | RECOVERED |
| 4 | network_partition | order-service | network_partition | order-service | network_policy_rollback✓ | 9.86s | 40.0s | MET | 12.0% | RECOVERED |
| 5 | pod_deletion | product-service | pod_crash | product-service | hpa_scaleout✓ | 4.85s | 20.0s | MET | 0.0% | RECOVERED |
