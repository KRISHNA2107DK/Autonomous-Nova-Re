# AutoHeal campaign `c-20261011-094619-5eb3`

**Resilience score: 80.6/100** — GOOD — reliable recovery with minor SLA or diagnosis misses

| Component | Points |
|---|---|
| recovery sla | 28.0 |
| detection sla | 16.0 |
| remediation effectiveness | 16.0 |
| diagnosis accuracy | 12.0 |
| user protection | 8.62 |

Mean time to detect: **9.82s** · mean time to recover: **33.74s** · RCA origin accuracy: **80%** · fault classification accuracy: **80%** · mean user failure ratio during incidents: **6.88%**

| # | Fault | Target | Detected as | RCA origin | Action | TTD | TTR | SLA | Users failed | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | replica_reduction | payment-service | replica_exhaustion | payment-service | hpa_scaleout✓ | 4.77s | 20.0s | MET | 0.0% | RECOVERED |
| 2 | network_partition | api-gateway | network_partition | api-gateway | network_policy_rollback✓ | 14.8s | 45.0s | MET | 34.2% | RECOVERED |
| 3 | cpu_throttle | notification-service | — | — | — | Nones | Nones | MISS | 0.0% | UNDETECTED |
| 4 | latency_injection | payment-service | high_latency | payment-service | traffic_reroute✓ | 14.86s | 49.99s | MET | 0.2% | RECOVERED |
| 5 | pod_deletion | product-service | pod_crash | product-service | hpa_scaleout✓ | 4.85s | 19.99s | MET | 0.0% | RECOVERED |
