# AutoHeal — Complete Project History

This document records everything that happened while building AutoHeal (originally named NovaSurge):
every request, investigation, decision, alternative considered, bug found, fix applied, measurement and
result, in the order it happened. It is written so that someone who was not present can understand
exactly what was done and why.

---

## Part 0 — Starting point

### 0.1 The request
The work began with this request: open the `NOVA` folder on the Desktop, pull the existing project from
`https://github.com/KRISHNA2107DK/final_novasurge`, read every file, find what needed correcting, "debug it
and implement it from scratch", replace any "easy way out" shortcuts with proper implementations, run the
whole project end to end, make it re-runnable "as fast as possible", create a new repository called
"Autonomous Nova Re" and push to it, and explain any manual steps.

### 0.2 The machine
Inspected before doing anything:

| Item | Found |
|---|---|
| OS | Windows 11 Home Single Language (10.0.26100) |
| Project folder | `C:\Users\moham\OneDrive\Desktop\NOVA` — **inside OneDrive** (empty at the start) |
| Python | 3.13.9 |
| Node / npm | v22.20.0 / 10.9.3 |
| Docker | 29.8.2, Docker Desktop running (WSL2 kernel 6.18), **4 CPUs, ~3.8 GB RAM** for the Docker VM |
| kubectl | v1.36.1 (bundled with Docker Desktop) |
| Kubernetes | **not enabled** in Docker Desktop (no `~/.kube/config`) |
| kind / helm / minikube / GitHub CLI | **none installed** |
| Host RAM | 15 GB |
| Git | 2.47.1, user `Zafar3712`, Git Credential Manager configured |

Two constraints shaped every later decision: only ~3.8 GB for all of Kubernetes, and the project living in a
OneDrive-synced folder.

### 0.3 The original repository
- Two commits ("Initial commit", "Pushing entire directory to final branch").
- 238 MB on disk, ~12,000 files — mostly a committed `dashboard/node_modules/`.
- A duplicated `novasurge/novasurge/` directory with copies of models and data.
- Committed runtime artefacts: a SQLite DB, round logs, state JSON files, a `.bak` file.
- Contents: `bootstrap.sh`, `Makefile`, `scripts/demo.sh`, a React dashboard, Kubernetes manifests,
  5 microservices ("ShopFusion"), and the `novasurge/` Python platform (orchestrator, decision engine, RCA,
  reasoning, SLA tracker, blast radius, injectors, remediators, ML scripts, FastAPI API).

The first clone landed inside the OneDrive folder. Moving it out failed ("Permission denied" — OneDrive held
files; then "Device or resource busy" because the shell's working directory was inside it). Decision: re-clone
a shallow copy into the session's scratchpad (outside OneDrive) as a read-only reference and delete the
OneDrive copy so 12,000 files would not sync.

---

## Part 1 — The audit (reading every file)

Every source file was read. The findings were grouped into five categories.

### 1.1 The core loop was simulated
- The orchestrator forced `NOVASURGE_MOCK_K8S=true` and `NOVASURGE_MOCK_ANOMALY=true`; nothing touched Kubernetes.
- The "anomaly endpoint" mock slept 20 seconds and returned **the same service and type that had just been
  injected** — detection and classification were correct by construction.
- If nothing was detected, the orchestrator invented an anomaly (severity 0.70).
- Hard-coded per-round metric "scenarios" and LSTM predictions were written into the files the dashboard read.
- Every reasoning message ended with "All other services remain unaffected".
- The injected fault was **reversed before recovery was measured**, so remediation never had to fix anything.
- The fallback remediation was computed but never executed; BLOCKED/DEFERRED decisions silently became the fallback.
- `failure_strategy.select_target()` was computed and then ignored for hard-coded targets.
- All five services' health checks hit the same nginx URL.
- The "60-second LSTM prediction" was `score + (score - score) * 0.5`, i.e. always the current score.
- The mock Kubernetes client created a new instance per call (state lost); replica counts were stored under the
  HPA name but read under the service name, so a wait loop ran its full 120 s.

### 1.2 Infrastructure that could not run
- Images were built as `shopfusion/<svc>:latest` but manifests ran `novasurge/<svc>:latest` with
  `imagePullPolicy: Never` → no pod could start.
- The Bitnami Redis chart with `fullnameOverride: redis-service` creates `redis-service-master`; services
  connected to `redis-service`.
- Bitnami images had moved behind a paywall in 2025 (fragile for a fresh install).
- A `default-allow-all` NetworkPolicy made the network-partition experiment a no-op (policies are additive).
- The traffic-reroute remediator targeted label `app=nginx` (real label `nginx-gateway`), a non-existent upstream
  block, port 8080, called pod exec without the WebSocket helper, and the nginx ConfigMap was mounted with
  `subPath` (never updates).
- Deployments hard-coded `replicas` while HPAs owned them.
- ServiceMonitors were never applied; kube-prometheus-stack + Loki + Grafana would not fit in 3.8 GB.
- `bootstrap.sh` refused to run on Windows.
- The DB password `novasurge123` was committed in five manifests.

### 1.3 Service bugs
- Order service never reserved stock; payment declines became HTTP 402.
- Blocking SQLAlchemy calls and `time.sleep` inside `async def` endpoints.
- Gateway used http-proxy-middleware v3 option syntax with a v2 dependency (error handler ignored); raw paths as
  metric labels; notification service used a Gauge named `*_total`.
- Load generator ran on the host with unbounded task creation and no metrics.

### 1.4 Platform bugs
- `GET /health` was registered after `uvicorn.run()` → 404 when started as documented.
- All paths were relative to the current directory; `cd novasurge && python -m api.main` wrote into
  `novasurge/novasurge/…` (the origin of the duplicated folder); `python -m orchestrator` from inside
  `novasurge/` could not import `novasurge.*`, so `make demo` crashed.
- `/rounds` sorted by a non-existent key; dashboard and backend disagreed on field names.
- RCA walked from the affected service to its **callers** and blamed the earliest — backwards, since failures
  propagate upstream.
- Guardrail 3 compared ISO-string timestamps with floats.
- ML: one scaler pooled across services; training on synthetic data unrelated to live scales; the Prometheus
  fetcher took `result[0]` of multi-series queries; error rate was an absolute rate live but a ratio in
  training; missing data replaced by invented "typical" values; fixed threshold −0.15.
- `cpu_throttle` also set memory to 64 Mi (OOM loop) and relied on a rollout that could never finish;
  `latency_injection` ran `apt-get install` without `apt-get update`.
- SLA tracker: `if recovery_seconds` treated 0 as missing; mixed naive/aware datetimes; the resilience score
  awarded points simply for guardrails firing.
- Dashboard: WebSocket URL hard-coded to a LAN IP `ws://172.20.66.195:8000`; on disconnect it displayed fabricated
  "MOCK" data and fake decision rows.

### 1.5 Conclusion of the audit
A rewrite was warranted ("implement it from scratch"), keeping the original's intent: a 5-service shop,
5 fault types, ML detection, RCA, guardrailed decisions, remediation, narration and a dashboard.

---

## Part 2 — Architecture decisions

| Decision | Chosen | Alternatives considered | Reason |
|---|---|---|---|
| Kubernetes | **kind v0.33.0** (single node) | Docker Desktop's built-in K8s; k3s/minikube | Scriptable without GUI; kindnet enforces NetworkPolicy (Docker Desktop's does not); runs inside existing Docker |
| Tool install | Download into `%LOCALAPPDATA%\…\bin` with **SHA-256 verification** | winget/choco | No admin needed, reproducible, verifiable |
| Python env | venv **outside the repo** (`%LOCALAPPDATA%`) | `.venv` in repo | OneDrive would sync ~1 GB of packages |
| Dashboard build | `node_modules` in an external build folder; only `dist/` committed | build in repo | Same OneDrive reason; users without Node can still run it |
| Monitoring | One lean **Prometheus v2.55.1** (5 s scrapes, cAdvisor via API proxy) | kube-prometheus-stack, Loki, Grafana | ~250 MB vs. multiple GB; Loki replaced by reading pod logs through the K8s API |
| Databases | Plain manifests: **Postgres 16-alpine** StatefulSet, **Redis 7.4-alpine** | Bitnami Helm charts | No Helm needed; Bitnami images paywalled |
| Autoscaling metrics | Vendored **metrics-server v0.7.2** with `--kubelet-insecure-tls` | none | HPAs need CPU metrics |
| Secrets | Random DB password generated into a Secret on first deploy | committed password | Security |
| Runtime state | SQLite (WAL) in `%LOCALAPPDATA%`; reports written once into `reports/` | SQLite in repo | SQLite + OneDrive locking problems |
| Traffic | In-cluster traffic generator exporting user-facing SLI metrics | host load generator | Constant load regardless of host; gives real user impact |
| Entry point | One Python CLI (`python -m novasurge …`) wrapped by `nova.ps1` / `nova.sh` | bash scripts | Cross-platform |

### 2.1 Feasibility tests before building on assumptions
A throw-away namespace with two Alpine pods verified on this exact kernel:
- `tc qdisc add … netem delay 300ms` worked: a request went from 0.00 s to **0.60 s**.
- A deny-all NetworkPolicy blocked traffic: `wget` timed out → **BLOCKED**.

---

## Part 3 — Building and fixing ShopFusion

1. Wrote shared Python helpers `services/pycommon/` (uniform RED metrics with route templates, JSON logging,
   DB wait). Wrote product, order, payment services; rewrote gateway and notification service; wrote the
   in-cluster traffic generator; shared `python.Dockerfile` / `node.Dockerfile` (iproute2 baked in for `tc`).
2. Generated npm lockfiles outside OneDrive; built 6 images; created the kind cluster (ready in ~14 s,
   Kubernetes **v1.37.0**); loaded images; wrote manifests `k8s/base/00…60`.
3. **First deploy** worked end to end (`/products/1` through nginx returned data) but pods had restarted.
   Logs showed a **race**: two replicas ran `CREATE TABLE` simultaneously and one crashed on Postgres' catalog
   unique index. Fix: schema creation and seeding run inside a transaction holding
   `pg_advisory_xact_lock(7310001)` (also prevents double seeding).
4. **First telemetry test** returned real per-service RPS, error ratios, p99, CPU, memory, caller-side views,
   user SLI and live call rates. Two problems: notification-service CPU missing (cAdvisor refreshes idle
   containers every ~10–15 s, so a 30 s `rate()` window could hold one sample → CPU features moved to a
   **1-minute window**) and HPAs had scaled to 3–4 replicas on start-up CPU bursts → added HPA
   **stabilisation windows** (scale-up 60 s, scale-down 120 s).
5. Re-applying manifests reset replica counts: Deployments hard-coded `replicas` while HPAs owned them →
   removed `replicas` from HPA-managed Deployments.
6. CPU usage sat at 56–64 % of a 50m request, just under the 70 % HPA target → raised requests to **100m**
   for product/order/payment/gateway (and updated the declared-baseline annotations).
7. Recorded the baseline start time so clean telemetry could accumulate while the ML code was written.

---

## Part 4 — The ML pipeline and its calibration

1. Wrote per-service robust normalisation (`ml/features.py`), the LSTM forecaster, the training pipeline and
   the online detector.
2. **First training attempt** stopped by its own guard: only 22 samples per service (needs ≥ 34).
3. **In-place pod resize test**: resizing one payment pod to a 15m CPU limit (no restart) produced throttle
   ratio **0.203** and p99 **974 ms vs 247 ms** on that pod. Reverted; baseline clock reset because the test
   contaminated it.
4. **First real training (8.5 min)**: threshold got clamped to 0 and single-feature fault probes scored 0 %
   detection. Analysis showed **Isolation Forest score saturation**: any value beyond the training range lands
   in the same leaf, so 3σ and 20σ deviations score identically (~0.03) while clean data never scored below
   0.065. Decision: calibrate the threshold at the **midpoint between the clean-data floor and the weakest
   4σ single-feature probe**, keep a robust **z-score rule** for single-feature explosions and **structural
   checks** for Kubernetes facts. Result: hold-out false-positive rate 0 %.

---

## Part 5 — Live testing, fault by fault (the most important phase)

Every fault type was run against the real cluster; each failure was diagnosed from evidence and fixed.

### 5.1 CPU throttle
- Live detector test (15m limit): anomaly **confirmed 10 s after injection**; RCA correctly blamed payment with
  the CPU-limit drift as evidence. Problems: classifier said `network_partition` (callers erroring + fewer
  completions looked like unreachability); severity saturated at 1.0 for all services so the "primary"
  defaulted to list order; 15m caused 40 % user failures (an outage, not throttling).
- Fixes: throttle check ordered before partition; partition requires the metrics endpoint unreachable or
  traffic truly vanished without server latency; smooth severity (`1 − exp(−x/8)`); primary = earliest onset,
  then severity, then call-graph depth; throttle value **25m**.
- Full orchestrated round: TTD 14.9 s, `resource_restore` fixed it in place in 2.2 s, recovered in 30 s, score 100.

### 5.2 Pod deletion
- Twice **UNDETECTED** with zero user impact. A tick-by-tick trace showed Kubernetes replaces a deleted pod in
  **~5 seconds** — inside one 5 s detector tick.
- Fix 1: structural Kubernetes facts confirm immediately (not 2-of-3 windows).
- Fix 2 (the real one): **identity-based replica loss** — compare which pods were Ready last tick with now; a
  Ready pod that vanished without a scale-down/rollout/quarantine is a lost replica.
- Result: detected in **4.8 s**, healed with `hpa_scaleout`, score 100.

### 5.3 Network partition
- First attempt **FAILED**: RCA blamed the gateway, remediated the wrong service twice (both correctly failed
  verification), teardown reverted the fault.
- Trace findings: (a) **gateway bug** — requests to a partitioned service hung until nginx gave up at 10 s;
  http-proxy-middleware's `proxyTimeout` never fired on a stuck TCP connect, so failures were never counted as
  upstream errors; (b) **partial partition** — Prometheus scrapes and kubelet probes still succeeded because the
  CNI only filters **new** connections; established keep-alive flows survived.
- Fixes: evidence-settling tick before RCA; RCA includes services anomalous in the current window; healer
  re-diagnoses after a failed remediation; gateway rewritten with fetch and a hard 5 s deadline; a node-level
  **chaos-agent DaemonSet** (hostNetwork, NET_ADMIN, conntrack-tools) flushes conntrack for the isolated pods
  (`ss -K` was tried first but the kernel rejected it).
- Result: detected **9.85 s**, RCA 95 % citing the NetworkPolicy, rollback in 4 s, recovered in **40 s**.

### 5.4 Latency injection
- First attempt (400 ms netem): the slow pod failed its readiness probe, so **Kubernetes removed it**; detector
  called it a pod crash; RCA blamed product-service because product's *caller-side* latency rose (the slow
  order pod's outbound calls) while product's own server latency was normal; a healthy product pod was
  quarantined. Score still read 92 → the scoring was too lenient.
- Fixes: caller-side-only attribution (excess latency points at the caller); `pod_unready` class (running but
  NotReady → replace that pod); Guardrail 2 allows replacing a non-serving pod; scorecard checks whether the
  fault is **physically gone** (status `MASKED` otherwise, ×0.25 effectiveness); netem **200 ± 50 ms** so the
  replica stays Ready.
- Second attempt: correct origin and the right pod quarantined, but detection took **60 s**. Cause: HTTP
  keep-alive defeats Kubernetes' per-connection load balancing; the gateway's pooled connections were pinned
  to the healthy pod. Fix: gateway uses an undici Agent with `maxRequestsPerClient: 25`; nginx
  `keepalive_requests 50`. Detection fell to **14.9 s**.

### 5.5 Replica reduction
- Detected in **4.87 s** (`capacity_below_baseline`), RCA 96 % citing the HPA clamp, `hpa_scaleout`
  restored capacity, recovered in **20 s**, 0 failed user requests.

---

## Part 6 — Tooling, dashboard, simulator, tests

1. **`infra.py` + CLI**: content-hash image builds (rebuild only changed images, load only images the cluster
   has not seen, restart only affected workloads). The first `up` failed on `npm ci` because a dependency had
   been added without regenerating the lockfile — the error handling surfaced it clearly; fixed. `up` took 37 s;
   a repeat `up` is a **6-second no-op**.
2. **Dashboard** rebuilt (React 19, Vite 8, Tailwind 3, Recharts 3, d3 7); served by the API itself; no mock data.
3. **API bug**: request-body models defined inside `create_app()` could not be resolved under
   `from __future__ import annotations` → FastAPI treated them as query parameters. Moved to module level.
4. **Autopilot test**: a CPU throttle injected manually through the API was detected, diagnosed (95 %),
   restored in 2.1 s and verified without any campaign running.
5. **Simulator** (`novasurge/sim/`): stateful cluster (ReplicaSet, rollouts with maxUnavailable 0, HPA clamp,
   readiness, NetworkPolicies, in-place resize, netem, quarantine) + telemetry derived from state. First full
   dry-run (1 m 46 s) exposed two logic flaws that would also affect live runs: RCA counted Kubernetes
   `Killing` events from NovaSurge's own earlier rolling restart (fix: scope evidence to the incident, cap
   generic events, exclude self-inflicted pod actions), and caller-side attribution used a relative threshold
   (fix: absolute **excess latency > 100 ms**). Also added **episode memory** in the detector so a diagnosis made
   a tick later still sees the incident. Dry-run score rose from 84.4 to **97.4**.
6. **Tests**: 30 tests on the simulator. pytest's default temp dir was denied by the sandbox → fixtures use a
   private temp dir. One failure found a real robustness bug in the scorecard (missing `injector` key).
7. **Clean-baseline guard**: training refuses windows containing chaos activity (last chaos event + 1.5 min).
8. **Final model training** on 10 clean minutes (121 samples × 5 services): threshold **0.1031**, hold-out
   false-positive rate **0 %**, single-feature 8σ probe detection **100 %**, LSTM **+30.5 %** better than a
   persistence forecast.

---

## Part 7 — Final live demo and delivery

Run through the Windows wrapper exactly as a user would (`.\nova.ps1 demo --no-browser --exit-after`):

| # | Fault | Target (chosen by strategy) | Diagnosed | TTD | TTR | Users failed |
|---|---|---|---|---|---|---|
| 1 | pod_deletion | payment | pod_crash ✓ | 4.9 s | 20 s | 0.0 % |
| 2 | cpu_throttle | product | cpu_throttle ✓ | 9.9 s | 50 s | 1.1 % |
| 3 | network_partition | api-gateway | network_partition ✓ | 9.9 s | 40 s | 25.9 % |
| 4 | latency_injection | order | high_latency ✓ | 14.9 s | 50 s | 0.4 % |
| 5 | replica_reduction | payment | replica_exhaustion ✓ | 4.9 s | 20 s | 0.0 % |

**Resilience score 98.9/100**, RCA and classification accuracy 100 %, mean TTD 8.9 s, mean TTR 36 s.

Written: README, CHANGES (audit), JUDGING, LICENSE, Makefile, `.gitignore`, `.gitattributes`. Development-run
reports were deleted, keeping the final campaign. Commit `8e4885f` (128 files). A fresh clone passed all
30 tests.

**GitHub**: no GitHub CLI; Git Credential Manager held login `Zafar3712`, but GitHub answered **401 Bad
credentials** (expired). Repo names cannot contain spaces → `Autonomous-Nova-Re`. Manual steps were given; the
user created and pushed to **`https://github.com/KRISHNA2107DK/Autonomous-Nova-Re`**.

---

## Part 8 — Running it for the user

- The dashboard at :8000 refused connections: the demo had used `--exit-after`, so the server stopped when the
  campaign ended. The cluster was healthy.
- Started `nova.ps1 serve` and `nova.ps1 campaign` in **two visible PowerShell windows** (so they survive
  independently of the assistant). Later campaigns by the user scored 98.4 and 99.6.

---

## Part 9 — Questions answered

- **Stopping**: "Stop after round" button; Ctrl+C in the server window (closing with X skips teardown);
  `.\nova.ps1 down` pauses the cluster; closing the narration window does not stop a campaign.
- **Starting from CLI**: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once (Windows blocks scripts by
  default), `.\nova.ps1 up`, `.\nova.ps1 serve`, then the button or `.\nova.ps1 campaign`.
- **"Agents"**: no LLM agents at that point; the autonomous components were Monitor/Detector, RCA, Decision
  engine, Healer, Orchestrator+Strategy, Autopilot, plus the in-cluster traffic generator and chaos-agent.
- **Was chaos autonomous?** Honestly: only partly. The fault order was fixed in `config/campaign.json`; the
  target was computed but from near-static inputs, so it always picked payment → product → gateway → order →
  payment. No cross-campaign memory, no recency, no randomness.

---

## Part 10 — The Chaos Planner (LLM) agent

**Request**: add an agent with an API/LLM that decides which failure to inject into which service, based on
dependencies and time since the same fault on the same service was last tried, without many API calls, using
the free tier with the most calls.

**Decisions**
- Provider: **Groq** (OpenAI-compatible, the largest free request quota); Gemini supported as backup through the
  same code path.
- One call per round (5 per campaign).
- Code computes the facts; the LLM only chooses among validated candidates → accuracy. Any failure falls back to
  the rule-based pick → campaigns never break.
- Key stored outside the repo (`llm.env`), entered with hidden input; daily call cap 500.

**Built**: `novasurge/llm.py`, `novasurge/chaos/planner.py`, `state_db.fault_history()`, orchestrator `auto`
rounds, CLI `agent-key` / `agent-test`, `--no-llm` / `--fixed`, `/api/agent`, default plan of 5 `auto` rounds,
6 new tests (36 total). Dry-run: each round chose a different fault on a different service; score 98.0.
Commit `ea7e848`.

**Running it, issues found by the user**
1. `.\nova.ps1 up` failed: the cluster container was stopped but the code only checked that the cluster existed.
   Fixed to check `State.Running` and start it (commit `eed49cc`). Second run succeeded.
2. `agent-test` returned **HTTP 404 model_not_found** for `llama-3.3-70b-versatile` — the key was valid (a bad
   key gives 401) but Groq had retired the model. Listed the models available to the key; switched to
   **`openai/gpt-oss-120b`** (low reasoning effort) with automatic fallbacks `gpt-oss-20b` → `qwen3.8-27b` on
   404/429 (commit `400724f`). `agent-test` then returned: *network_partition on payment-service — "the
   highest-impact service with multiple dependents, and a fault type not yet used in this campaign"* — a
   different choice from the rule-based top pick, showing the LLM genuinely decides.

---

## Part 11 — Rename to AutoHeal

Every occurrence of "NovaSurge" (71, across dashboard, docs, comments, messages, the LLM prompt and the local
data folder name) was replaced with **AutoHeal**; the dashboard hook `useNovaSurge` became `useAutoHeal` (file
renamed so the import resolves). Lower-case identifiers (`novasurge` package/command, `novasurge-system`
namespace, `NOVASURGE_*` variables) were deliberately unchanged because they are code identifiers and the
instruction was to change nothing else. The user's real local data folder must be renamed with
`Rename-Item "$env:LOCALAPPDATA\NovaSurge" AutoHeal`. Commit `298da1a`; 36 tests pass.

---

## Part 12 — Commit log

| Commit | Content |
|---|---|
| `8e4885f` | NovaSurge 2.0 rebuild (128 files) |
| `ea7e848` | Chaos Planner agent (LLM-assisted fault + target choice) |
| `eed49cc` | Resume a paused kind cluster |
| `400724f` | Available Groq models with automatic fallback |
| `298da1a` | Rename NovaSurge → AutoHeal |
