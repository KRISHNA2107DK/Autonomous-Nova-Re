# AutoHeal campaign `c-20261010-211746-a9ae`

**Resilience score: 94.5/100** — EXCELLENT — every fault detected, diagnosed and healed within SLA

| Component | Points |
|---|---|
| recovery sla | 35.0 |
| detection sla | 20.0 |
| remediation effectiveness | 18.0 |
| diagnosis accuracy | 13.5 |
| user protection | 8.05 |

Mean time to detect: **8.82s** · mean time to recover: **39.0s** · RCA origin accuracy: **100%** · fault classification accuracy: **80%** · mean user failure ratio during incidents: **9.74%**

| # | Fault | Target | Detected as | RCA origin | Action | TTD | TTR | SLA | Users failed | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | pod_deletion | payment-service | network_partition | payment-service | network_policy_rollback✗, rolling_restart✓ | 4.84s | 40.0s | MET | 0.0% | RECOVERED |
| 2 | cpu_throttle | product-service | cpu_throttle | product-service | resource_restore✓ | 9.81s | 55.0s | MET | 7.5% | RECOVERED |
| 3 | network_partition | api-gateway | network_partition | api-gateway | network_policy_rollback✓ | 14.83s | 35.01s | MET | 41.1% | RECOVERED |
| 4 | latency_injection | order-service | high_latency | order-service | traffic_reroute✓ | 9.82s | 45.01s | MET | 0.2% | RECOVERED |
| 5 | replica_reduction | payment-service | replica_exhaustion | payment-service | hpa_scaleout✓ | 4.79s | 20.0s | MET | 0.0% | RECOVERED |
