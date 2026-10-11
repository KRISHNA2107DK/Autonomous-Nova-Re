# AutoHeal campaign `c-20261010-210835-1993`

**Resilience score: 98.5/100** — EXCELLENT — every fault detected, diagnosed and healed within SLA

| Component | Points |
|---|---|
| recovery sla | 35.0 |
| detection sla | 20.0 |
| remediation effectiveness | 20.0 |
| diagnosis accuracy | 15.0 |
| user protection | 8.47 |

Mean time to detect: **8.82s** · mean time to recover: **38.0s** · RCA origin accuracy: **100%** · fault classification accuracy: **100%** · mean user failure ratio during incidents: **7.67%**

| # | Fault | Target | Detected as | RCA origin | Action | TTD | TTR | SLA | Users failed | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | pod_deletion | payment-service | pod_crash | payment-service | hpa_scaleout✓ | 4.81s | 20.0s | MET | 0.0% | RECOVERED |
| 2 | cpu_throttle | product-service | cpu_throttle | product-service | resource_restore✓ | 9.83s | 60.0s | MET | 0.6% | RECOVERED |
| 3 | network_partition | api-gateway | network_partition | api-gateway | network_policy_rollback✓ | 14.82s | 40.0s | MET | 37.4% | RECOVERED |
| 4 | latency_injection | order-service | high_latency | order-service | traffic_reroute✓ | 9.82s | 50.01s | MET | 0.4% | RECOVERED |
| 5 | replica_reduction | payment-service | replica_exhaustion | payment-service | hpa_scaleout✓ | 4.83s | 19.99s | MET | 0.0% | RECOVERED |
