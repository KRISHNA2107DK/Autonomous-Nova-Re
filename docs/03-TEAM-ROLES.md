# AutoHeal — Work Split for a Team of Five

AutoHeal is divided into five equal parts. Each section below is self-contained: a person can study only their
section and know exactly what they own, what decisions they made and why, which files are theirs, how their work
connects to the others, and how to demonstrate it.

| Person | Area | One-line responsibility |
|---|---|---|
| Person 1 | Platform, infrastructure & quality | The cluster, deployment, tooling, simulator and tests |
| Person 2 | Application & user experience | ShopFusion services, traffic generator, API server and dashboard |
| Person 3 | Telemetry & ML detection | Turning metrics into features and detecting anomalies |
| Person 4 | Diagnosis & self-healing | Root-cause analysis, decisions, guardrails, remediation and verification |
| Person 5 | Chaos, orchestration & the AI agent | Fault injection, the LLM Chaos Planner, the campaign loop and scoring |

Shared contracts every person must respect:
- `novasurge/topology.py` — the single service dependency graph and business-impact weights.
- `novasurge/cluster.py` — the only way code talks to Kubernetes (real cluster or simulator).
- Uniform metric names emitted by every service (`http_requests_total{method,route,status_code}`, etc.).
- The declared-baseline annotations on Deployments and HPAs (`novasurge.io/baseline-*`).
- SQLite tables in `state_db.py` and narration events in `reasoning.py`.

---

## Person 1 — Platform, infrastructure & quality

### Owns
`k8s/` (all manifests, kind config), `novasurge/infra.py`, `novasurge/config.py`, `novasurge/cluster.py`,
`nova.ps1`, `nova.sh`, `Makefile`, `requirements.txt`, `pyproject.toml`, `services/chaos-agent/`,
`novasurge/sim/`, `tests/`, `.gitignore`, `.gitattributes`.

### What they built
1. **Local Kubernetes** with kind v0.33.0: one control-plane node, NodePorts 30080 (shop) and 30090
   (Prometheus) bound to 127.0.0.1.
2. **Manifests** in apply order: namespaces (`shopfusion`, `novasurge-system`), Postgres 16 StatefulSet with an
   init script creating `ordersdb`/`paymentsdb`, Redis 7.4 (no persistence, 64 MB LRU), five app Deployments +
   Services + HPAs, nginx, Prometheus, metrics-server, traffic generator, chaos-agent, least-privilege RBAC.
3. **Prometheus**: 5 s pod scrapes (annotation-based discovery, `app` label → `service`), 10 s cAdvisor scrapes
   through the API-server proxy, metric filtering to keep the TSDB small.
4. **Chaos agent DaemonSet**: hostNetwork + NET_ADMIN + conntrack-tools, so network partitions cut established flows.
5. **`infra.py`**: checksum-verified tool downloads; create or resume the cluster; content-hash image builds
   (rebuild only changed images, load only what the cluster has not seen, restart only affected workloads);
   random DB password Secret; apply, wait for rollouts, wait for Prometheus and the shop.
6. **Launchers**: venv created outside the repository, dependencies reinstalled only when `requirements.txt` changes.
7. **Cluster facade**: typed value objects and one `Cluster` interface (pods, deployments, HPAs, NetworkPolicies,
   in-place resize, exec with return codes, events, logs) with a real implementation.
8. **Simulator**: a stateful model of the cluster (ReplicaSets, rolling updates, HPA clamps, readiness, NetworkPolicies,
   resizes, netem, quarantine) and telemetry derived from that state, so dry-runs exercise the real code.
9. **Test-suite**: 36 tests running on the simulator in about 70 seconds.

### Decisions and reasons
| Decision | Reason |
|---|---|
| kind instead of Docker Desktop Kubernetes / k3s / minikube | Scriptable without a GUI; kindnet enforces NetworkPolicy; runs inside the existing Docker |
| No Helm; plain manifests | Bitnami images became paywalled; fewer moving parts |
| Lean Prometheus instead of kube-prometheus-stack + Loki + Grafana | Only ~3.8 GB of RAM for the whole cluster |
| No `replicas` in HPA-managed Deployments; HPA stabilisation windows | `kubectl apply` was fighting the HPA; start-up CPU spikes caused scale-outs |
| CPU requests raised to 100m | 50m left services at 56–64 % utilisation, flapping around the 70 % HPA target |
| Removed the "allow all" NetworkPolicy | Policies are additive; it neutralised the partition experiment |
| Runtime state, venv and node_modules outside the repo | The repo lives in OneDrive (sync churn, SQLite locking) |
| Random DB password generated at deploy time | The original committed the password in five files |
| Cluster "resume" checks the container is running, not just that the cluster exists | Found when a paused cluster made `up` fail |
| Tests use a private temp directory and never call the LLM | Sandbox denied pytest's temp dir; tests must be free and deterministic |

### Interfaces with others
Provides the cluster and `Cluster` facade to Persons 3, 4 and 5; builds Person 2's images; runs everyone's code
in the simulator and tests.

### How to demonstrate
`.\nova.ps1 up` (≈ 6 s when nothing changed), `.\nova.ps1 status`, `.\nova.ps1 test`, `.\nova.ps1 campaign --dry-run`.

---

## Person 2 — Application & user experience

### Owns
`services/` (product, order, payment, api-gateway, notification, traffic-generator, `pycommon/`, Dockerfiles),
`novasurge/api/server.py`, `dashboard/`.

### What they built
1. **ShopFusion**, the system under test:
   - product-service: catalogue, Redis cache-aside (60 s), atomic stock reservation with a single conditional
     `UPDATE`, compensating release, replenishment thread.
   - order-service: saga product → reserve → order → payment → confirm or compensate → publish event; 503 on
     dependency failure; pooled HTTP client with tight timeouts.
   - payment-service: 40–160 ms processing, 3 % declines, publishes events.
   - notification-service: Redis pub/sub consumer with per-channel counters.
   - api-gateway: path-prefix proxy using undici with a hard 5 s deadline (504 on timeout), connection recycling
     every 25 requests, `/health/dependencies`.
2. **Uniform instrumentation** (`pycommon/observability.py`): RED metrics with route templates, in-flight gauge,
   outbound-call metrics, JSON logs, Postgres wait, advisory-lock schema creation.
3. **Traffic generator**: in-cluster open-loop shoppers at 20 req/s with a fixed request mix, exporting the
   user-facing SLI (`loadgen_requests_total`, `loadgen_request_duration_seconds`).
4. **API server**: REST + WebSocket stream, campaign start/stop, autopilot, manual injection, agent status,
   serving the dashboard.
5. **Dashboard**: header with live user SLI and controls, anomaly score chart, reasoning feed, health grid,
   decision trace, dependency graph, LSTM forecast; no mock data.

### Decisions and reasons
| Decision | Reason |
|---|---|
| Advisory lock around schema creation and seeding | Two replicas raced on `CREATE TABLE` and crashed (seen live) |
| Sync FastAPI endpoints for DB work | The original blocked the event loop inside `async def` |
| Route templates as metric labels | Raw paths create unbounded label cardinality |
| Caller-side (outbound) metrics in gateway and order-service | A partitioned or crashed service cannot report on itself; its callers can |
| Gateway rewritten from http-proxy-middleware to undici fetch | `proxyTimeout` never fired on a stuck connect, so partitions looked like hangs |
| Recycle upstream connections every 25 requests (and nginx every 50) | Keep-alive pinned traffic to one replica; a slow replica took 60 s to detect, now ~15 s |
| Traffic generator inside the cluster with metrics | Constant load independent of the host; real user impact per incident |
| Dashboard served by the API, relative URLs | Removes the hard-coded LAN IP; works from any host |
| Never show mock data | The original showed fabricated data when disconnected |
| Request models at module level in FastAPI | Nested models broke under postponed annotations (bug found live) |

### Interfaces with others
Emits the metrics Person 3 consumes; exposes the probes Person 4 uses for verification; displays Person 5's
narration and campaign status; the API hosts Person 4's autopilot and Person 5's campaigns.

### How to demonstrate
`curl http://127.0.0.1:30080/products/1`, place an order with `POST /orders`, open `http://127.0.0.1:8000`,
toggle autopilot, start a campaign from the button.

---

## Person 3 — Telemetry & ML detection

### Owns
`novasurge/telemetry.py`, `novasurge/ml/` (`features.py`, `forecaster.py`, `train.py`, `detector.py`),
`novasurge/monitor.py`, `novasurge/models/`.

### What they built
1. **Nine features per service every 5 s** from PromQL: request rate, error ratio, p99, in-flight, CPU per pod,
   CPU throttle ratio, memory per pod, caller error ratio, caller p99 (gateway: synthetic users' view), plus
   structural state from Kubernetes (Ready pod names, desired vs declared replicas, HPA bounds, scrape health,
   restarts) and the user SLI.
2. **Per-service robust normalisation**: median/MAD z-scores with measurement-resolution floors and harmful directions.
3. **Isolation Forest**: 200 trees on jitter-augmented z-vectors; threshold calibrated between the clean-data
   floor and the weakest 4σ single-feature probe; hold-out false-positive rate and probe detection reported.
4. **LSTM forecaster**: 60 s history → 60 s forecast, residual parameterisation, early stopping; skill measured
   against a persistence forecast; forecast scored by the Isolation Forest.
5. **Training pipeline**: identical PromQL for training and inference, clean-baseline guard (no chaos in the
   window), model card.
6. **Online detector**: IF + z-score rule + structural invariants; 2-of-3 confirmation for statistics,
   immediate for Kubernetes facts; identity-based replica-loss detection; episode memory; severity; classification.
7. **Monitor**: the single 5 s loop feeding the dashboard, autopilot, orchestrator and the telemetry log.

### Decisions and reasons
| Decision | Reason |
|---|---|
| Per-service normalisation instead of one pooled scaler | Healthy operating points differ by 10× between services |
| Absent traffic = 0, absent latency = unknown | The original replaced missing data with "typical" values, hiding outages |
| 1-minute window for cAdvisor features | Idle containers update every 10–15 s; 30 s windows held a single sample |
| Jitter augmentation | An IF cannot split on a constant feature |
| Midpoint threshold calibration | IF scores saturate beyond the training range (3σ and 20σ score the same) |
| Hybrid detector (IF + z-rule + structural) | The IF alone misses single-feature faults; Kubernetes facts need no statistics |
| Identity-based replica loss | Kubernetes replaces a deleted pod in ~5 s, inside one tick; counts missed it |
| Episode memory | A diagnosis made a tick later must still see the incident |
| Severity `1 − e^{−x/8}` | Linear severity saturated at 1.0 for every service |
| Throttle checked before partition; partition requires unreachability | CPU starvation was being called a partition |
| Train only on clean windows | Chaos-contaminated data teaches the model that faults are normal |

Final model: 10 clean minutes, threshold 0.1031, false positives 0 %, probe detection 100 %, LSTM +30.5 % vs persistence.

### Interfaces with others
Consumes Person 2's metrics and Person 1's cluster facade; hands `DetectionResult` to Person 4 (RCA) and Person 5
(detection wait, preflight); the API streams it to the dashboard.

### How to demonstrate
`.\nova.ps1 train`, open `novasurge/models/model_card.json`, watch scores cross the threshold on the dashboard
during a fault, `GET /api/anomaly/current`.

---

## Person 4 — Diagnosis & self-healing

### Owns
`novasurge/rca.py`, `novasurge/decision_engine.py`, `novasurge/remediators/`, `novasurge/healer.py`,
autopilot behaviour (with Person 2's API).

### What they built
1. **Root-cause analysis**: candidates = confirmed + currently deviating services; evidence from the cluster
   (deny-all NetworkPolicies, live CPU below the declared baseline, HPA below the declared minimum, pod events
   excluding AutoHeal's own actions, error logs); scoring with severity, failing-dependency explanation, traffic-only
   victims, caller-side-only attribution via excess latency, onset order; type refinement by evidence; confidence;
   narrative distinguishing upstream callers from starved downstream services.
2. **Decision engine**: playbook per fault class, four guardrails (G1 duplicate, G2 replica safety, G3 failure
   memory, G4 cascade), confidence from smoothed historical success × RCA confidence × blast factor, escalation
   below 0.4.
3. **Seven remediators**: hpa_scaleout, resource_restore (in-place resize back to declared), network_policy_rollback
   (by effect, not label), traffic_reroute (quarantine the worst replica), pod_restart, rolling_restart, cache_flush.
4. **Healer**: settle tick → RCA → decide → remediate → verify functionally (capacity + 5 user-path probes) →
   re-diagnose and escalate on failure → wait for system recovery (first clean window).
5. **Autopilot**: heals anomalies AutoHeal did not inject, with a cooldown.

### Decisions and reasons
| Decision | Reason |
|---|---|
| RCA scores candidates instead of walking to callers | Failures propagate upstream; the original blamed the gateway |
| Change evidence weighted highest | Most real incidents follow a change |
| Caller-side-only attribution using excess latency > 100 ms | A slow replica's outbound calls made a healthy callee look slow (seen live) |
| Exclude self-inflicted pod events; cap generic events | Old Killing events from AutoHeal's own restarts misled RCA |
| Settling tick + current-window candidates | The culprit's signal can trail its callers' by one window |
| Verify with real probes, not the remediator's report | A remediator can "succeed" without restoring service |
| Re-diagnose before escalating | The first diagnosis may have been on incomplete evidence |
| Network policy rollback by effect | Works for a human mistake, not only for chaos-labelled policies |
| Quarantine instead of nginx rewrites | Relabelling removes the pod from the Service instantly and gets a replacement |
| G2 allows replacing a non-serving pod | Replacing an unready pod costs no capacity |
| `pod_unready` class | Latency can make Kubernetes take a pod out of rotation; replacing it is the fix |

### Interfaces with others
Consumes Person 3's detection; uses Person 1's facade and Person 2's probes; returns a `HealOutcome` to Person 5;
writes remediation history used for confidence and by Person 5's planner.

### How to demonstrate
`.\nova.ps1 serve`, then `.\nova.ps1 inject network_partition product-service` and watch autopilot diagnose and
roll back the policy in the reasoning feed.

---

## Person 5 — Chaos, orchestration & the AI agent

### Owns
`novasurge/chaos/` (injectors, `strategy.py`, `planner.py`), `novasurge/llm.py`, `novasurge/orchestrator.py`,
`novasurge/blast_radius.py`, `novasurge/sla_tracker.py`, `novasurge/reasoning.py`, `novasurge/state_db.py`,
`config/campaign.json`, `reports/`.

### What they built
1. **Five real injectors**: pod deletion (grace 0), CPU throttle via in-place pod resize to 25m, network partition
   (deny-all NetworkPolicy + conntrack flush), latency (tc netem 200 ± 50 ms on one replica), replica reduction
   (HPA min = max = 1); each with `compatible`, `still_active` and idempotent `reverse`.
2. **Chaos Planner agent**: builds every applicable (fault, service) pair with dependency, impact, traffic and
   history facts (time since that exact pair was last tried, times tried, last outcome), ranks them with a rule
   score, sends the top 10 to an LLM (Groq `openai/gpt-oss-120b` with fallbacks, or Gemini) — one call per round —
   validates the answer and falls back to rules on any failure.
3. **Campaign orchestrator**: planning → steady-state gate with blast-radius preflight → inject → detect or report
   UNDETECTED → heal (with a user-impact watchdog that aborts) → teardown (detect MASKED fixes, restore declared
   state) → SLA, user impact and ground-truth grading → reports.
4. **Scorecard**: recovery SLA 35, detection SLA 20, remediation effectiveness 20, diagnosis accuracy 15, user
   protection 10.
5. **Narration and state**: every step narrated with live numbers; SQLite persistence of campaigns, rounds,
   remediations, guardrails, events.

### Decisions and reasons
| Decision | Reason |
|---|---|
| Undo the fault only after recovery is measured | The original reverted first, so remediation never had to work |
| No synthetic detection fallback | Undetected faults must be reported honestly |
| In-place resize for CPU throttle, 25m | Immediate effect without a stalled rollout; 15m caused an outage, not throttling |
| Conntrack flush after the NetworkPolicy | CNIs only filter new connections |
| netem 200 ± 50 ms on one replica | 400 ms made readiness remove the pod, masking the fault |
| LLM chooses only among validated candidates; code computes facts | Accuracy, and the campaign never depends on the API |
| Groq free tier, one call per round, daily cap, key outside repo | Most free requests; cost and secret safety |
| Model fallback list | Groq retired the first model (HTTP 404 seen live) |
| Steady-state gate before injecting | Injecting into a degraded system makes results meaningless and risky |
| Grade against ground truth, including MASKED | The original awarded points for guardrails firing |

Live result (5 rounds): score 98.9/100, mean TTD 8.9 s, mean TTR 36 s, RCA and classification accuracy 100 %.

### Interfaces with others
Drives Person 4's healer and waits on Person 3's detector; uses Person 1's facade; Person 2's dashboard displays
narration, campaign status and the decision trace.

### How to demonstrate
`.\nova.ps1 agent-test`, `.\nova.ps1 campaign`, then `.\nova.ps1 report`; show the planner's reasons in the feed.
