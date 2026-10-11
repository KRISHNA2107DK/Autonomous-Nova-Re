# AutoHeal campaign `c-20261011-071521-1560`

**Resilience score: 77.9/100** — GOOD — reliable recovery with minor SLA or diagnosis misses

| Component | Points |
|---|---|
| recovery sla | 23.33 |
| detection sla | 20.0 |
| remediation effectiveness | 13.33 |
| diagnosis accuracy | 12.5 |
| user protection | 8.7 |

Mean time to detect: **9.83s** · mean time to recover: **35.0s** · RCA origin accuracy: **100%** · fault classification accuracy: **67%** · mean user failure ratio during incidents: **6.48%**

| # | Fault | Target | Detected as | RCA origin | Action | TTD | TTR | SLA | Users failed | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | latency_injection | order-service | high_latency | order-service | traffic_reroute✓ | 14.83s | 49.99s | MET | 0.3% | RECOVERED |
| 2 | pod_deletion | payment-service | network_partition | payment-service | network_policy_rollback✗, rolling_restart✓ | 4.82s | 20.0s | MET | 0.0% | RECOVERED |
| 3 | network_partition | payment-service | network_partition | payment-service | rolling_restart✗, network_policy_rollback✓ | 9.84s | Nones | MISS | 19.2% | MITIGATED |
| 4 | replica_reduction | api-gateway | — | — | — | —s | —s | MISS | 0.0% | SKIPPED_PREFLIGHT |
| 5 | cpu_throttle | product-service | — | — | — | —s | —s | MISS | 0.0% | SKIPPED_PREFLIGHT |
