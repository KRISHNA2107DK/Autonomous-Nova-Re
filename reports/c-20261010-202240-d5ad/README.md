# AutoHeal campaign `c-20261010-202240-d5ad`

**Resilience score: 98.9/100** — EXCELLENT — every fault detected, diagnosed and healed within SLA

| Component | Points |
|---|---|
| recovery sla | 35.0 |
| detection sla | 20.0 |
| remediation effectiveness | 20.0 |
| diagnosis accuracy | 15.0 |
| user protection | 8.91 |

Mean time to detect: **8.86s** · mean time to recover: **36.0s** · RCA origin accuracy: **100%** · fault classification accuracy: **100%** · mean user failure ratio during incidents: **5.47%**

| # | Fault | Target | Detected as | RCA origin | Action | TTD | TTR | SLA | Users failed | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | pod_deletion | payment-service | pod_crash | payment-service | hpa_scaleout✓ | 4.86s | 20.01s | MET | 0.0% | RECOVERED |
| 2 | cpu_throttle | product-service | cpu_throttle | product-service | resource_restore✓ | 9.86s | 50.0s | MET | 1.1% | RECOVERED |
| 3 | network_partition | api-gateway | network_partition | api-gateway | network_policy_rollback✓ | 9.86s | 40.0s | MET | 25.9% | RECOVERED |
| 4 | latency_injection | order-service | high_latency | order-service | traffic_reroute✓ | 14.85s | 49.99s | MET | 0.4% | RECOVERED |
| 5 | replica_reduction | payment-service | replica_exhaustion | payment-service | hpa_scaleout✓ | 4.86s | 20.01s | MET | 0.0% | RECOVERED |
