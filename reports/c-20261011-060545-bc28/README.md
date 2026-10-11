# AutoHeal campaign `c-20261011-060545-bc28`

**Resilience score: 80.6/100** — GOOD — reliable recovery with minor SLA or diagnosis misses

| Component | Points |
|---|---|
| recovery sla | 28.0 |
| detection sla | 16.0 |
| remediation effectiveness | 16.0 |
| diagnosis accuracy | 12.0 |
| user protection | 8.62 |

Mean time to detect: **8.57s** · mean time to recover: **42.49s** · RCA origin accuracy: **80%** · fault classification accuracy: **80%** · mean user failure ratio during incidents: **6.90%**

| # | Fault | Target | Detected as | RCA origin | Action | TTD | TTR | SLA | Users failed | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | cpu_throttle | payment-service | cpu_throttle | payment-service | resource_restore✓ | 9.84s | 54.99s | MET | 0.4% | RECOVERED |
| 2 | replica_reduction | order-service | replica_exhaustion | order-service | hpa_scaleout✓ | 4.81s | 55.0s | MET | 0.0% | RECOVERED |
| 3 | pod_deletion | product-service | pod_crash | product-service | hpa_scaleout✓ | 4.8s | 19.99s | MET | 0.0% | RECOVERED |
| 4 | network_partition | api-gateway | network_partition | api-gateway | network_policy_rollback✓ | 14.83s | 39.99s | MET | 34.2% | RECOVERED |
| 5 | latency_injection | notification-service | — | — | — | Nones | Nones | MISS | 0.0% | UNDETECTED |
