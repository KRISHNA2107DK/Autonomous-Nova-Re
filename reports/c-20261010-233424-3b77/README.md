# AutoHeal campaign `c-20261010-233424-3b77`

**Resilience score: 99.6/100** — EXCELLENT — every fault detected, diagnosed and healed within SLA

| Component | Points |
|---|---|
| recovery sla | 35.0 |
| detection sla | 20.0 |
| remediation effectiveness | 20.0 |
| diagnosis accuracy | 15.0 |
| user protection | 9.58 |

Mean time to detect: **8.84s** · mean time to recover: **36.0s** · RCA origin accuracy: **100%** · fault classification accuracy: **100%** · mean user failure ratio during incidents: **2.12%**

| # | Fault | Target | Detected as | RCA origin | Action | TTD | TTR | SLA | Users failed | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | network_partition | payment-service | network_partition | payment-service | network_policy_rollback✓ | 9.85s | 44.99s | MET | 10.4% | RECOVERED |
| 2 | cpu_throttle | api-gateway | cpu_throttle | api-gateway | resource_restore✓ | 14.82s | 50.01s | MET | 0.0% | RECOVERED |
| 3 | latency_injection | api-gateway | high_latency | api-gateway | traffic_reroute✓ | 9.85s | 44.99s | MET | 0.2% | RECOVERED |
| 4 | pod_deletion | payment-service | pod_crash | payment-service | hpa_scaleout✓ | 4.84s | 20.0s | MET | 0.0% | RECOVERED |
| 5 | replica_reduction | payment-service | replica_exhaustion | payment-service | hpa_scaleout✓ | 4.84s | 20.01s | MET | 0.0% | RECOVERED |
