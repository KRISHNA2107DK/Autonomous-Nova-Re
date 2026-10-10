# NovaSurge — evaluation guide

**One line:** NovaSurge injects real faults into a Kubernetes microservice shop, detects them with
models trained on that shop's own telemetry, finds the root cause, heals it, proves the fix with
real user-path probes, and narrates every decision — then grades itself against the ground truth.

## Run it (Windows, Docker Desktop running)

```powershell
.\nova.ps1 demo          # first run ~15 min (cluster + 9-min baseline + training), later ~1 min to ready
```

Dashboard: http://127.0.0.1:8000 — press **Run 5-round campaign**, or watch the one `demo` starts.
No cluster? `.\nova.ps1 campaign --dry-run` runs the identical logic against the simulator (~2 min).

## Where to look

| Claim | Evidence |
|---|---|
| Real multi-service app | `services/` (3 × FastAPI, 2 × Express) — stock reservation saga, Redis cache + pub/sub, Postgres |
| Real failure injection | `novasurge/chaos/injectors/` — pod deletion, **in-place CPU resize**, NetworkPolicy + conntrack flush, `tc netem`, HPA clamp |
| Own ML anomaly detection | `novasurge/ml/` — per-service robust features, Isolation Forest with data-calibrated threshold, LSTM 60 s forecaster; `novasurge/models/model_card.json` (hold-out FP rate, probe detection, forecaster skill) |
| Root cause analysis | `novasurge/rca.py` — dependency-aware scoring, change evidence, caller-side attribution |
| Autonomous decisions | `novasurge/decision_engine.py` — playbooks, 4 guardrails, learned confidence |
| Verified healing | `novasurge/healer.py` — fallback + re-diagnosis, user-path verification, masked-fix detection |
| End-to-end loop | `novasurge/orchestrator.py` — steady-state gate, blast radius, watchdog, teardown, scoring |
| Real-time dashboard | `dashboard/src/` — WebSocket per detector tick, no mock data |
| Self-assessment | `reports/LATEST.md` — TTD/TTR/SLA, RCA accuracy vs injected fault, user impact |
| Tests | `tests/` — 30 tests on a stateful cluster simulator (`.\nova.ps1 test`) |
| What was fixed | `CHANGES.md` — audit of the original repository |

## Differentiators

1. **Graded against ground truth.** Every round knows what was injected, so RCA accuracy, classification
   accuracy and "was the fault actually removed?" are measured, not claimed.
2. **Change-aware RCA.** Correlates symptoms with what changed in the cluster (isolating policies, resource
   drift from the declared baseline, autoscaler clamps) — the way human SREs find most incidents.
3. **Honest outcomes.** `UNDETECTED`, `MASKED`, `FAILED` and `ABORTED` are first-class results.
4. **Safety first.** Steady-state gate before injecting, blast-radius preflight, four guardrails, a user-impact
   watchdog that aborts experiments, idempotent teardown back to the declared state.
5. **Autopilot.** The same pipeline heals faults NovaSurge did not inject (`.\nova.ps1 inject …`).
