# AutoHeal campaign `c-20261011-002156-7879`

**Resilience score: 87.2/100** — GOOD — reliable recovery with minor SLA or diagnosis misses

| Component | Points |
|---|---|
| recovery sla | 28.0 |
| detection sla | 20.0 |
| remediation effectiveness | 17.0 |
| diagnosis accuracy | 13.5 |
| user protection | 8.71 |

Mean time to detect: **10.82s** · mean time to recover: **31.25s** · RCA origin accuracy: **80%** · fault classification accuracy: **100%** · mean user failure ratio during incidents: **6.45%**

| # | Fault | Target | Detected as | RCA origin | Action | TTD | TTR | SLA | Users failed | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | cpu_throttle | payment-service | cpu_throttle | payment-service | resource_restore✓ | 14.82s | 50.01s | MET | 0.0% | RECOVERED |
| 2 | network_partition | api-gateway | network_partition | api-gateway | network_policy_rollback✓ | 14.83s | 40.0s | MET | 31.5% | RECOVERED |
| 3 | pod_deletion | api-gateway | pod_crash | api-gateway | hpa_scaleout✓ | 4.81s | 15.0s | MET | 0.0% | RECOVERED |
| 4 | latency_injection | order-service | high_latency | product-service | traffic_reroute✓ | 14.81s | Nones | MISS | 0.7% | MITIGATED |
| 5 | replica_reduction | product-service | replica_exhaustion | product-service | hpa_scaleout✓ | 4.82s | 20.0s | MET | 0.0% | RECOVERED |
