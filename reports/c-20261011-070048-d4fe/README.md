# AutoHeal campaign `c-20261011-070048-d4fe`

**Resilience score: 99.6/100** — EXCELLENT — every fault detected, diagnosed and healed within SLA

| Component | Points |
|---|---|
| recovery sla | 35.0 |
| detection sla | 20.0 |
| remediation effectiveness | 20.0 |
| diagnosis accuracy | 15.0 |
| user protection | 9.57 |

Mean time to detect: **9.82s** · mean time to recover: **37.0s** · RCA origin accuracy: **100%** · fault classification accuracy: **100%** · mean user failure ratio during incidents: **2.17%**

| # | Fault | Target | Detected as | RCA origin | Action | TTD | TTR | SLA | Users failed | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | latency_injection | payment-service | high_latency | payment-service | traffic_reroute✓ | 14.82s | 50.0s | MET | 0.3% | RECOVERED |
| 2 | pod_deletion | api-gateway | pod_crash | api-gateway | hpa_scaleout✓ | 4.81s | 14.99s | MET | 0.0% | RECOVERED |
| 3 | network_partition | order-service | network_partition | order-service | network_policy_rollback✓ | 9.83s | 50.0s | MET | 10.6% | RECOVERED |
| 4 | replica_reduction | product-service | replica_exhaustion | product-service | hpa_scaleout✓ | 4.83s | 20.0s | MET | 0.0% | RECOVERED |
| 5 | cpu_throttle | api-gateway | cpu_throttle | api-gateway | resource_restore✓ | 14.83s | 50.01s | MET | 0.0% | RECOVERED |
