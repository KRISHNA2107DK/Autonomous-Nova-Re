# AutoHeal campaign `c-20261010-212640-8667`

**Resilience score: 98.4/100** — EXCELLENT — every fault detected, diagnosed and healed within SLA

| Component | Points |
|---|---|
| recovery sla | 35.0 |
| detection sla | 20.0 |
| remediation effectiveness | 20.0 |
| diagnosis accuracy | 15.0 |
| user protection | 8.36 |

Mean time to detect: **9.84s** · mean time to recover: **37.0s** · RCA origin accuracy: **100%** · fault classification accuracy: **100%** · mean user failure ratio during incidents: **8.22%**

| # | Fault | Target | Detected as | RCA origin | Action | TTD | TTR | SLA | Users failed | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | pod_deletion | payment-service | pod_crash | payment-service | hpa_scaleout✓ | 4.83s | 20.0s | MET | 0.0% | RECOVERED |
| 2 | cpu_throttle | product-service | cpu_throttle | product-service | resource_restore✓ | 9.81s | 60.01s | MET | 3.7% | RECOVERED |
| 3 | network_partition | api-gateway | network_partition | api-gateway | network_policy_rollback✓ | 14.84s | 39.99s | MET | 37.3% | RECOVERED |
| 4 | latency_injection | order-service | high_latency | order-service | traffic_reroute✓ | 14.87s | 44.99s | MET | 0.1% | RECOVERED |
| 5 | replica_reduction | payment-service | replica_exhaustion | payment-service | hpa_scaleout✓ | 4.83s | 20.0s | MET | 0.0% | RECOVERED |
