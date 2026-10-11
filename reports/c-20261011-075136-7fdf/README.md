# AutoHeal campaign `c-20261011-075136-7fdf`

**Resilience score: 98.8/100** — EXCELLENT — every fault detected, diagnosed and healed within SLA

| Component | Points |
|---|---|
| recovery sla | 35.0 |
| detection sla | 20.0 |
| remediation effectiveness | 20.0 |
| diagnosis accuracy | 15.0 |
| user protection | 8.84 |

Mean time to detect: **8.86s** · mean time to recover: **36.0s** · RCA origin accuracy: **100%** · fault classification accuracy: **100%** · mean user failure ratio during incidents: **5.78%**

| # | Fault | Target | Detected as | RCA origin | Action | TTD | TTR | SLA | Users failed | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | replica_reduction | api-gateway | replica_exhaustion | api-gateway | hpa_scaleout✓ | 4.86s | 20.0s | MET | 0.0% | RECOVERED |
| 2 | cpu_throttle | order-service | cpu_throttle | order-service | resource_restore✓ | 9.85s | 55.0s | MET | 6.0% | RECOVERED |
| 3 | latency_injection | api-gateway | high_latency | api-gateway | traffic_reroute✓ | 14.85s | 45.0s | MET | 0.0% | RECOVERED |
| 4 | network_partition | product-service | network_partition | product-service | network_policy_rollback✓ | 9.86s | 40.0s | MET | 23.0% | RECOVERED |
| 5 | pod_deletion | payment-service | pod_crash | payment-service | hpa_scaleout✓ | 4.86s | 19.99s | MET | 0.0% | RECOVERED |
