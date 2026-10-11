# AutoHeal campaign `c-20261011-005421-d315`

**Resilience score: 99.4/100** — EXCELLENT — every fault detected, diagnosed and healed within SLA

| Component | Points |
|---|---|
| recovery sla | 35.0 |
| detection sla | 20.0 |
| remediation effectiveness | 20.0 |
| diagnosis accuracy | 15.0 |
| user protection | 9.44 |

Mean time to detect: **7.83s** · mean time to recover: **35.0s** · RCA origin accuracy: **100%** · fault classification accuracy: **100%** · mean user failure ratio during incidents: **2.79%**

| # | Fault | Target | Detected as | RCA origin | Action | TTD | TTR | SLA | Users failed | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | network_partition | order-service | network_partition | order-service | network_policy_rollback✓ | 9.83s | 40.0s | MET | 10.3% | RECOVERED |
| 2 | cpu_throttle | product-service | cpu_throttle | product-service | resource_restore✓ | 9.84s | 55.0s | MET | 3.5% | RECOVERED |
| 3 | pod_deletion | payment-service | pod_crash | payment-service | hpa_scaleout✓ | 4.82s | 20.01s | MET | 0.0% | RECOVERED |
| 4 | replica_reduction | api-gateway | replica_exhaustion | api-gateway | hpa_scaleout✓ | 4.82s | 15.0s | MET | 0.0% | RECOVERED |
| 5 | latency_injection | api-gateway | high_latency | api-gateway | traffic_reroute✓ | 9.85s | 44.99s | MET | 0.2% | RECOVERED |
