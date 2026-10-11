# AutoHeal — Autonomous Chaos Engineering & Self-Healing 

AutoHeal breaks a real microservice application on purpose, notices on its own,
works out *why*, fixes it, proves the fix worked — and explains every step in
plain English while it happens.

```
 inject ─▶ detect ─▶ diagnose ─▶ decide ─▶ remediate ─▶ verify ─▶ score
 (real      (ML on     (RCA with    (play-    (real K8s    (user-path   (SLA, user
  K8s        live       change       book +    actions,     probes +     impact, RCA
  faults)    telemetry) evidence)    guard-    fallback,    telemetry    accuracy vs
                                     rails)    re-diagnose) recovery)    ground truth)
```

It runs entirely on one Windows/macOS/Linux machine: a `kind` Kubernetes
cluster, a 5-service shop (**ShopFusion**), Prometheus, an in-cluster traffic
generator, and the AutoHeal control plane with a live dashboard.

> This is a ground-up rebuild of `KRISHNA2107DK/final_novasurge`. The original's
> loop was largely simulated and several pieces could not run as committed — see
> **[CHANGES.md](CHANGES.md)** for the full audit.

---

## Quick start (Windows)

**You need:** Docker Desktop (running), Python 3.11+, ~4 GB RAM for Docker,
internet for the first run. Node.js is *not* needed (the dashboard ships pre-built).

```powershell
cd path\to\NOVA
.\nova.ps1 demo
```

That single command:

1. creates a Python venv in `%LOCALAPPDATA%\AutoHeal` (outside the repo) and installs dependencies
2. downloads `kind` (checksum-verified), creates the cluster, builds and loads 7 images
3. deploys ShopFusion, Postgres, Redis, Prometheus, metrics-server, the traffic generator and the chaos agent
4. **first run only:** records ~9 minutes of clean live traffic and trains the models on it
5. opens the dashboard at **http://127.0.0.1:8000** and runs the 5-round chaos campaign
6. keeps the dashboard running with **autopilot** on (Ctrl+C to stop)

First run: ~15 minutes (mostly the baseline recording). After that, everything
is cached: `.\nova.ps1 demo` is ready in about a minute and a campaign takes ~10 minutes.

Linux/macOS: `./nova.sh demo` (same commands as below with `./nova.sh`).

### Everyday commands

| Command | What it does |
|---|---|
| `.\nova.ps1 demo` | Everything above, end to end |
| `.\nova.ps1 serve` | Dashboard + API on :8000 with autopilot (heals anomalies AutoHeal did not inject) |
| `.\nova.ps1 campaign` | Run the 5-round campaign (attaches to a running `serve` so the dashboard shows it) |
| `.\nova.ps1 campaign --injector cpu_throttle --target payment-service` | One specific experiment |
| `.\nova.ps1 campaign --dry-run` | The same campaign against the built-in simulator — no cluster, ~2 min |
| `.\nova.ps1 inject network_partition product-service` | Break something by hand and watch autopilot heal it |
| `.\nova.ps1 revert` | Undo manual injections |
| `.\nova.ps1 status` | Health of Docker, cluster, pods, Prometheus, API, models, last campaign |
| `.\nova.ps1 report` | Print the latest campaign report |
| `.\nova.ps1 train` | Retrain the models on fresh clean telemetry (refuses chaos-contaminated windows) |
| `.\nova.ps1 test` | Run the test-suite (simulator-based, ~70 s, no cluster needed) |
| `.\nova.ps1 down` / `down --delete` | Pause the cluster (resume in seconds with `up`) / delete it |

Endpoints while running: dashboard & API `http://127.0.0.1:8000` (OpenAPI at `/docs`),
shop `http://127.0.0.1:30080` (try `/products/1`), Prometheus `http://127.0.0.1:30090`.

---

## What happens in a round

```
STRATEGY   pick a target: blast radius x business impact x user traffic x load x redundancy, minus coverage
PREFLIGHT  steady-state gate — never inject into a degraded or unobservable system (waits up to 3 min)
INJECT     real fault on the cluster
DETECT     live detector confirms an anomaly (or the round is honestly reported UNDETECTED)
RCA        which service is the origin, and what kind of fault, with evidence
DECIDE     playbook + 4 guardrails + confidence learned from past outcomes
REMEDIATE  real Kubernetes action; if it doesn't verify, re-diagnose and escalate to the fallback
VERIFY     full Ready capacity + 5 consecutive fast user-path probes through nginx
RECOVER    the whole system back inside its learned normal band (recovery time = first clean window)
TEARDOWN   check whether the fault is *physically* gone (else MASKED), revert residue, hand back surge capacity
SCORE      TTD / TTM / TTR vs SLA, real user impact, RCA correctness vs the known injected fault
```

A watchdog aborts the experiment (immediate revert) if synthetic users see >50 %
failures for more than 4 minutes.

### Chaos Planner agent — which fault, on which service

Each round the **Chaos Planner** (`novasurge/chaos/planner.py`) picks the fault *and* the service:

1. It lists every applicable (fault, service) pair and gives each one facts: services that depend on it,
   services it depends on, business impact, user traffic share, **minutes since this exact pair was last
   injected** (from the history of all campaigns), times tried, and how the last attempt went.
2. A rule-based score ranks them: staleness 30 %, dependents 20 %, past weakness 15 %, impact 15 %,
   users 10 %, dependencies 10 %, minus a variety penalty for a fault type or service already used this campaign.
3. The top 10 go to an **LLM** (one API call per round), which answers `{"candidate_id", "reason"}`. The answer is
   validated against the list. With no key, an API error, a rate limit or an invalid answer, the top rule-based
   pick is used, so a campaign never breaks. The choice and its reason appear in the reasoning feed, tagged LLM or rules.

Set it up once (Groq recommended for its generous free tier; Gemini also supported):

```powershell
.\nova.ps1 agent-key groq     # paste the key (hidden); stored in %LOCALAPPDATA%\AutoHeal\llm.env, never in the repo
.\nova.ps1 agent-test         # one real call to verify
```

`.\nova.ps1 campaign --no-llm` uses the rule-based planner only; `--fixed` runs the old one-of-each-fault order.

### Chaos experiments

| Injector | Real mechanism | Expected diagnosis | Playbook (primary → fallback) |
|---|---|---|---|
| `pod_deletion` | force-delete a Ready pod (grace 0) | `pod_crash` | `hpa_scaleout` → `rolling_restart` |
| `cpu_throttle` | **in-place pod resize** of every replica's CPU limit to 25m (live cgroup change, no restart) | `cpu_throttle` | `resource_restore` → `rolling_restart` |
| `network_partition` | deny-all NetworkPolicy + conntrack flush via the node chaos-agent (cuts established flows too) | `network_partition` | `network_policy_rollback` → `rolling_restart` |
| `latency_injection` | `tc netem` 200±50 ms egress delay on **one** replica | `high_latency` | `traffic_reroute` (quarantine that replica) → `rolling_restart` |
| `replica_reduction` | clamp the HPA to min=max=1 | `replica_exhaustion` | `hpa_scaleout` → `resource_restore` |

Additional fault classes the detector/RCA recognise: `pod_unready`, `oom_kill`,
`error_spike`, `cache_miss_spike` (with `pod_restart` and `cache_flush` remediators).

### Remediators

| Remediator | What it really does |
|---|---|
| `hpa_scaleout` | restores autoscaler bounds to at least the declared baseline (+1 surge replica), waits for Ready capacity |
| `resource_restore` | reconciles live pod resources (in-place resize) and the template to the declared baseline annotation |
| `network_policy_rollback` | deletes NetworkPolicies that select the service and deny all traffic — found by *effect*, not by a chaos label |
| `traffic_reroute` | quarantines the worst replica (picked from per-pod Prometheus latency/errors/throttling): relabels it out of the Service and ReplicaSet, waits for the replacement, then removes it |
| `pod_restart` | replaces the worst/unready replica |
| `rolling_restart` | zero-downtime rollout (`maxUnavailable: 0`) |
| `cache_flush` | evicts `products:*` keys via `redis-cli` in the Redis pod |

### Guardrails

* **G1 duplicate** — one remediation per service at a time (locks expire if a process dies)
* **G2 replica safety** — never remove the last *serving* replica (replacing an unready one is allowed)
* **G3 failure memory** — a remediator that failed on this service in the last 5 min goes to the back of the queue
* **G4 cascade protection** — with ≥2 remediations in flight, only the highest business-impact service proceeds

Confidence = smoothed historical success (per service × remediator × fault, from SQLite) × RCA confidence × blast factor;
below 0.4 the engine escalates to the fallback if that scores higher.

---

## How detection works

**Telemetry** (every 5 s, per service) — Prometheus (5 s scrapes) plus the Kubernetes API:

`request_rate · error_rate · p99_latency_ms · inflight · cpu_cores · cpu_throttle_ratio · memory_mb ·
caller_error_rate · caller_p99_ms` and structural state (Ready pods by identity, desired vs declared
replicas, HPA bounds, scrape reachability, restarts). The *caller-side* features matter: a partitioned
service cannot report on itself, but its callers (and for the gateway, the synthetic users) still see it fail.

**Detector** — an ensemble that votes per service per window:

1. **Isolation Forest** on per-service robust z-scores (each service against *its own* baseline), trained with
   jitter augmentation; the threshold is calibrated between the clean-data floor and single-feature fault probes.
2. **Robust z-score rule**: any feature ≥ 6σ in its harmful direction.
3. **Structural invariants**: a Ready pod vanished without a scale-down/rollout, capacity below the declared
   minimum, metrics endpoint unreachable, container restarts.

Statistical signals confirm after 2 of 3 windows; deterministic Kubernetes facts confirm immediately.
The episode's classification and evidence are kept until it clears.

**LSTM forecaster** — 60 s of history → the next 60 s of telemetry (residual parameterisation); the forecast
is scored by the Isolation Forest (`predicted_score_60s`), and the one-step error is a temporal "surprise" signal.

**Training** — `train` pulls the baseline from Prometheus with *exactly* the inference PromQL, refuses windows
that contain chaos activity, and writes [`novasurge/models/model_card.json`](novasurge/models/model_card.json)
with the threshold calibration, hold-out false-positive rate, fault-probe detection rates and forecaster skill
vs. a persistence baseline.

**RCA** — scores every anomalous (or currently deviating) service: own failure symptoms vs. "only receives less
traffic", whether a failing dependency explains it, onset order, change evidence from the cluster (isolating
NetworkPolicies, live resources below the declared baseline, HPA bounds below the declared minimum, pod
lifecycle events — excluding AutoHeal's own actions), error logs, and caller-side-only latency (attributed to
the caller whose calls show the excess). The result is an origin, a refined fault class, a confidence and a narrative.

---

## Dashboard

`http://127.0.0.1:8000` — one WebSocket frame per detector tick; no mock data ever (if the server is down it says so).

* **Header** — live user SLI (req/s, failure %, p99), last resilience score, round/phase, autopilot toggle, *Run campaign*
* **Anomaly score** — Isolation Forest score per service against the learned threshold
* **Autonomous reasoning** — the narrated decision log
* **System health** — status, req/s, p99, 5xx, Ready/desired pods, classification and top deviation
* **Decision trace** — one row per round with diagnosis ✓/✗ against the injected fault, actions ✓/✗, TTD, TTR, SLA, user impact
* **Dependency graph** — live call rates as edge widths, anomalous nodes pulse, blast radius edges animate
* **LSTM forecast** — last 2 minutes of score + the 60 s forecast

## Scorecard (0–100)

| Points | Component | Measured as |
|---|---|---|
| 35 | Recovery SLA | TTR (detection → system back in its normal band) ≤ target per fault type |
| 20 | Detection SLA | TTD (injection → confirmed anomaly) ≤ target |
| 20 | Remediation effectiveness | 1.0 first action / 0.5 fallback / 0 failed; ×0.25 if the fault was still present (masked) |
| 15 | Diagnosis accuracy | RCA origin == injected service, and fault class == expected |
| 10 | User protection | 1 − 2 × mean user failure ratio during incidents |

## Results from the live run

Campaign `c-20261010-202240-d5ad` on a laptop (Docker Desktop, 4 CPUs / 3.8 GB), targets chosen by the strategy:

**Resilience score 98.9 / 100** · mean time to detect **8.9 s** · mean time to recover **36 s** ·
RCA origin accuracy **100 %** · fault classification accuracy **100 %**

| # | Fault | Target | Diagnosed as | RCA origin | Action (verified) | TTD | TTR | SLA | Users failed |
|---|---|---|---|---|---|---|---|---|---|
| 1 | pod_deletion | payment-service | pod_crash | payment-service | hpa_scaleout ✓ | 4.9 s | 20 s | MET | 0.0 % |
| 2 | cpu_throttle | product-service | cpu_throttle | product-service | resource_restore ✓ | 9.9 s | 50 s | MET | 1.1 % |
| 3 | network_partition | api-gateway | network_partition | api-gateway | network_policy_rollback ✓ | 9.9 s | 40 s | MET | 25.9 % |
| 4 | latency_injection | order-service | high_latency | order-service | traffic_reroute ✓ | 14.9 s | 50 s | MET | 0.4 % |
| 5 | replica_reduction | payment-service | replica_exhaustion | payment-service | hpa_scaleout ✓ | 4.9 s | 20 s | MET | 0.0 % |

The only points lost are *user protection* (8.9/10): partitioning the API gateway is a total outage for every
shopper until the policy is rolled back (~18 s), and that is honestly counted. Full report:
[`reports/LATEST.md`](reports/LATEST.md); raw round records and scorecard in `reports/c-20261010-202240-d5ad/`.
Every new campaign writes its own folder and updates `LATEST.md`.

---

## API

| | |
|---|---|
| `GET /api/health`, `/api/status` | liveness, platform status |
| `GET /api/anomaly/current` | detector verdict (primary + all anomalous services) |
| `GET /api/detection`, `/api/metrics/current` | full per-service detection / latest telemetry |
| `GET /api/topology`, `/api/events?after=` | live dependency graph, reasoning feed |
| `GET /api/model`, `/api/campaigns`, `/api/campaigns/{id}`, `/api/rounds` | model card, campaign history |
| `POST /api/campaign/start`, `/api/campaign/stop` | `{"rounds": N}` or `{"plan": [...]}` |
| `POST /api/autopilot`, `/api/chaos/inject` | `{"enabled": bool}`, `{"injector", "service"}` |
| `WS /ws/stream` | `hello` frame, then one `tick` frame per detector tick |

Legacy aliases kept: `/health`, `/anomaly/current`, `/metrics/current`, `/rounds`.

## Configuration

| Env var | Default |
|---|---|
| `NOVASURGE_HOME` | `%LOCALAPPDATA%\AutoHeal` / `~/.cache/novasurge` — venv, tools, SQLite, telemetry |
| `NOVASURGE_CLUSTER`, `NOVASURGE_KUBE_CONTEXT` | `novasurge`, `kind-novasurge` |
| `PROMETHEUS_URL`, `GATEWAY_URL` | `http://127.0.0.1:30090`, `http://127.0.0.1:30080` |
| `NOVASURGE_API_PORT` | `8000` |
| `NOVASURGE_THROTTLE_CPU`, `NOVASURGE_NETEM_DELAY`, `NOVASURGE_NETEM_JITTER` | `25m`, `200ms`, `50ms` |
| `RPS` (traffic-generator Deployment) | `20` |

Campaign plan: [`config/campaign.json`](config/campaign.json) (`"target": "auto"` or a service name).

## Project layout

```
nova.ps1 / nova.sh / Makefile   launchers (venv bootstrap + CLI)
novasurge/                      control plane (python -m novasurge ...)
  cli.py infra.py               commands; cluster/images/deploy lifecycle (hash-based incremental builds)
  telemetry.py                  PromQL feature extraction + Kubernetes structure, probes, user impact
  ml/                           features (robust normalisation), train, detector, LSTM forecaster
  monitor.py                    the single 5 s detection loop
  rca.py decision_engine.py     root-cause analysis; playbooks, guardrails, confidence
  healer.py orchestrator.py     diagnose→verify pipeline (campaign + autopilot); campaign rounds
  chaos/ remediators/           5 injectors + target strategy; 7 remediators
  blast_radius.py sla_tracker.py reasoning.py state_db.py topology.py cluster.py
  sim/                          stateful cluster + telemetry simulator (dry-run, tests)
  api/server.py                 FastAPI REST + WebSocket + dashboard host + autopilot
  models/                       trained models + model_card.json
services/                       ShopFusion (FastAPI ×3, Express ×2), traffic generator, chaos agent
k8s/                            kind config + manifests (applied in file order)
dashboard/                      React + Vite + Tailwind + Recharts + d3 (dist/ is committed)
tests/                          30 simulator-based tests
reports/                        campaign reports (LATEST.md)
```

## Troubleshooting

* **"Docker is installed but not running"** — start Docker Desktop and wait for *Engine running*.
* **Port 8000 / 30080 / 30090 in use** — stop whatever uses it, or set `NOVASURGE_API_PORT`.
* **Pods Pending** — Docker Desktop needs ~4 GB (Settings → Resources); `.\nova.ps1 status` shows readiness.
* **Models missing / stale** — `.\nova.ps1 train` (needs ~9 quiet minutes; it waits and shows progress).
* **Start completely fresh** — `.\nova.ps1 down --delete`, then `.\nova.ps1 demo`.

## Honest limitations

* Single-node `kind` cluster; fault effects are real but the scale is a laptop's.
* The detector learns "normal" from ~10 minutes of synthetic shopper traffic; a production deployment would train on days of real traffic and retrain on drift.
* The LSTM is trained mostly on healthy data, so its 60 s forecast is conservative (it predicts persistence/mean-reversion better than onset); `train --include-recorded` adds telemetry recorded during past campaigns.
* The platform runs on the host with your kubeconfig; `k8s/base/60-novasurge-rbac.yaml` documents the least-privilege role for running it in-cluster.
