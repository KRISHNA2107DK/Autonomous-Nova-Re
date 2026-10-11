# AutoHeal — Technical Reference (rebuild-from-scratch specification)

This document describes every component of AutoHeal with the parameters, formulas, interfaces and file
layout needed to rebuild it. Names: the product is **AutoHeal**; the Python package and CLI are still called
`novasurge` (`python -m novasurge …`), the system namespace `novasurge-system`, environment variables
`NOVASURGE_*`.

---

## 1. Technology stack

| Layer | Technology | Version used |
|---|---|---|
| Container runtime | Docker Desktop (WSL2 backend) | Docker 29.8 |
| Kubernetes | kind (single control-plane node, kindnet CNI) | kind v0.33.0, Kubernetes v1.37.0 |
| Application services | Python FastAPI ×3, Node.js Express ×2 | Python 3.12-slim images, Node 22-alpine images |
| Datastores | PostgreSQL, Redis | postgres:16-alpine, redis:7.4-alpine |
| Ingress | nginx | nginx:1.27-alpine |
| Metrics | Prometheus (+ kubelet cAdvisor) | prom/prometheus:v2.55.1 |
| Autoscaling metrics | metrics-server | v0.7.2 |
| Platform (host) | Python 3.11+ (built with 3.13) | FastAPI, uvicorn, httpx, kubernetes client, numpy, scikit-learn, PyTorch (CPU) |
| ML | scikit-learn IsolationForest, PyTorch LSTM | sklearn 1.9, torch 2.14 |
| State | SQLite (WAL mode) | stdlib |
| Dashboard | React, Vite, Tailwind CSS, Recharts, d3 | React 19, Vite 8, Tailwind 3, Recharts 3, d3 7 |
| LLM agent | Groq (OpenAI-compatible) or Google Gemini | default `openai/gpt-oss-120b` |
| Tests | pytest | 36 tests |

Python service dependencies (pinned in `services/requirements-python.txt`): fastapi 0.115.12,
uvicorn[standard] 0.34.2, SQLAlchemy 2.0.40, psycopg2-binary 2.9.10, redis 5.2.1, prometheus-client 0.21.1,
httpx 0.28.1, pydantic 2.11.4. Node: express ^4.21.2, prom-client ^15.1.3, undici ^6.21.0 (gateway),
ioredis ^5.6.1 (notification).

---

## 2. Repository layout

```
nova.ps1 / nova.sh / Makefile      launchers: create venv outside repo, install requirements.txt, run CLI
requirements.txt                   platform deps (fastapi, uvicorn, httpx, kubernetes, numpy, scikit-learn, torch, pytest)
pyproject.toml                     pytest config
config/campaign.json               campaign plan (5 rounds of {"injector":"auto","target":"auto"})
k8s/kind-config.yaml               kind cluster (NodePorts 30080, 30090 on 127.0.0.1)
k8s/base/00..60-*.yaml             all manifests, applied in file order
services/                          ShopFusion services, shared Dockerfiles, traffic generator, chaos agent
novasurge/                         the AutoHeal control plane (Python package)
  __main__.py cli.py infra.py config.py topology.py cluster.py telemetry.py monitor.py
  ml/ (features.py forecaster.py train.py detector.py)
  rca.py decision_engine.py healer.py orchestrator.py blast_radius.py sla_tracker.py reasoning.py state_db.py llm.py
  chaos/ (injectors/*.py strategy.py planner.py)    remediators/*.py
  sim/ (cluster.py telemetry.py __init__.py)         api/server.py
  models/ (normalizer.json iforest.joblib lstm_forecaster.pt model_card.json)
dashboard/ (src/, dist/ committed)  tests/  reports/  docs/
```

Runtime state (never in the repo): `%LOCALAPPDATA%\AutoHeal\` on Windows (`~/.cache/novasurge` elsewhere,
override `NOVASURGE_HOME`): `venv/`, `bin/kind.exe`, `runtime/state/novasurge.db`, `runtime/data/telemetry.jsonl`,
`infra-state.json` (image hashes), `llm.env` (API key), `dashboard-build/`, `sim/`.

---

## 3. The application under test: ShopFusion

### 3.1 Services

| Service | Lang | Port | Role | Endpoints |
|---|---|---|---|---|
| api-gateway | Node/Express | 3000 | Single entry point; proxies by path prefix | `/products*`, `/orders*`, `/payments*`, `/notifications*`, `/health`, `/ready`, `/health/dependencies`, `/metrics` |
| product-service | FastAPI | 8001 | Catalogue, Redis cache-aside (`products:{id}`, TTL 60 s), atomic stock reservation, replenishment job | `GET /products`, `GET /products/{id}`, `POST /products`, `POST /products/{id}/reserve`, `POST /products/{id}/release` |
| order-service | FastAPI | 8002 | Order saga | `POST /orders`, `GET /orders/{id}` |
| payment-service | FastAPI | 8003 | Simulated card processor | `POST /payments`, `GET /payments/{id}` |
| notification-service | Node | 3001 | Consumes Redis pub/sub `order-events`, `payment-events` | `GET /notifications/stats` |
| nginx-gateway | nginx | 80 → NodePort 30080 | Public ingress to the gateway | `/nginx-health` |
| postgres | | 5432 | DBs `productsdb`, `ordersdb`, `paymentsdb` (init script creates the latter two) | |
| redis | | 6379 | Cache + event bus; `--save "" --appendonly no --maxmemory 64mb --maxmemory-policy allkeys-lru` | |

**Order saga (`POST /orders`)**: GET product (price) → `POST /reserve` (409 if insufficient) → insert order
`pending` → `POST /payments` → `confirmed`, or `payment_declined` + release stock → publish `order-events`.
Transport/5xx failures from dependencies → release reserved stock → HTTP 503.

**Product reservation**: a single conditional `UPDATE products SET stock = stock - q WHERE id = :id AND stock >= q
RETURNING …` (no overselling). Replenishment thread every 15 s resets products below 100 to their `restock_level`.

**Payment**: sleeps 40–160 ms (sync endpoint → threadpool), 3 % declines (`PAYMENT_DECLINE_RATE`), publishes `payment-events`.

**Start-up**: services wait for Postgres (retry up to 90 s), then create the schema and seed inside one
transaction holding `pg_advisory_xact_lock(7310001)` — prevents concurrent `CREATE TABLE` races and double seeding.

**Gateway proxy**: undici `fetch` with an `Agent({keepAliveTimeout: 4000, maxRequestsPerClient: 25,
connect: {timeout: 5000}})` and `AbortSignal.timeout(5000)`. Timeout → 504, other transport errors → 502.
Hop-by-hop headers stripped. `maxRequestsPerClient` recycles connections so keep-alive does not pin traffic to
one replica (Kubernetes Services balance per connection). `/health/dependencies` checks each upstream's
`/ready` (1.5 s timeout) and returns 503 if any fails.

### 3.2 Uniform metrics (every service)
```
http_requests_total{method, route, status_code}       route = matched route template (bounded cardinality)
http_request_duration_seconds{method, route}           histogram, buckets .005 .01 .025 .05 .1 .25 .5 1 2.5 5 10
http_requests_in_flight
http_client_requests_total{target, status_code}        outbound calls (gateway, order-service); status "transport_error" on failure
http_client_request_duration_seconds{target}
```
`/health`, `/ready`, `/metrics` are excluded from RED metrics. Notification-service additionally exports
`notifications_received_total{channel,status}` and `notification_processing_seconds{channel}`; product-service
`cache_lookups_total{result}`. Prometheus attaches `service` (from the pod's `app` label), `pod`, `namespace`.
Logs are one JSON object per line with `timestamp, service, level, message, …`.

### 3.3 Traffic generator (in-cluster, namespace novasurge-system)
Open-loop arrivals at `RPS=20` through `http://nginx-gateway.shopfusion.svc.cluster.local`, concurrency cap 100,
timeout 8 s. Mix: 40 % `GET /products/{1..20}`, 10 % `GET /products`, 25 % `POST /orders` (qty 1–3),
15 % `GET /orders/{id}` (ids harvested from created orders), 10 % `GET /payments/{id}`. Exports on :9100
`loadgen_requests_total{endpoint,outcome}` (ok, client_error, server_error, timeout, connection_error) and
`loadgen_request_duration_seconds{endpoint}` — the **user-facing SLI**.

### 3.4 Chaos agent (DaemonSet, novasurge-system)
Alpine + `conntrack-tools iproute2`, `hostNetwork: true`, capability `NET_ADMIN`. Used to run
`conntrack -D -s <podIP>; conntrack -D -d <podIP>` so a new NetworkPolicy also applies to established flows.

### 3.5 Kubernetes manifests (key settings)
- Namespaces `shopfusion`, `novasurge-system`. **No baseline NetworkPolicy** (policies are additive allow-lists).
- App Deployments: no `replicas` field (HPA-owned), RollingUpdate `maxSurge 1 / maxUnavailable 0`,
  `imagePullPolicy: Never`, image `novasurge/<svc>:local`, capability `NET_ADMIN` (for `tc`), probes:
  startup `/health` every 2 s ×60, readiness `/ready` every 5 s timeout 2 s ×2, liveness `/health` every 10 s ×6.
- Resources: product/order/payment requests 100m/96Mi limits 500m/256Mi; gateway 100m/64Mi, 500m/192Mi;
  notification 25m/64Mi, 250m/192Mi.
- Declared-baseline annotations (the "known good" state remediators restore):
  Deployment `novasurge.io/baseline-resources: {"<container>": {"requests":…, "limits":…}}`,
  HPA `novasurge.io/baseline: {"minReplicas":…, "maxReplicas":…}`.
- HPAs: CPU 70 %, min/max 2/4 (notification 1/3), `behavior.scaleUp.stabilizationWindowSeconds: 60`, scale-down 120.
- DB password: Secret `shopfusion-db` created with a random value on first deploy.
- Prometheus: ConfigMap + Deployment + NodePort 30090, RBAC to read nodes/proxy/pods. Jobs: `pods`
  (kubernetes_sd pods in both namespaces, keep `prometheus.io/scrape=true`, port/path from annotations,
  `app`→`service`, every 5 s) and `kubelet-cadvisor` (via `kubernetes.default.svc:443/api/v1/nodes/<node>/proxy/metrics/cadvisor`,
  every 10 s, keeping only CPU usage, CFS periods/throttled periods, memory working set).
- metrics-server with `--kubelet-insecure-tls`. Least-privilege Role for the platform documented in `60-novasurge-rbac.yaml`.

---

## 4. Platform architecture

```
          ┌────────────────────────── AutoHeal process (host) ───────────────────────────┐
Prometheus│  Telemetry ──► Monitor (5 s loop) ──► Detector ──► listeners:                  │
K8s API ──┤                                     │              ├─ WebSocket → dashboard   │
          │                                     │              ├─ Autopilot → Healer      │
          │  Orchestrator (campaign) ◄──────────┘              └─ telemetry.jsonl          │
          │     ├─ Chaos Planner (rules + LLM) / Strategy                                  │
          │     ├─ Preflight (steady-state gate, blast radius)                             │
          │     ├─ Injector ──► Kubernetes                                                 │
          │     ├─ Healer: RCA → Decision engine (guardrails) → Remediator → Verify        │
          │     └─ Teardown → SLA/scorecard → SQLite + reports/                           │
          └────────────────────────────────────────────────────────────────────────────────┘
```

### 4.1 Configuration (`config.py`)
`STEP_SECONDS=5`, `RATE_WINDOW="30s"`, `LSTM_HISTORY=12`, `LSTM_HORIZON=12`, `NAMESPACE=shopfusion`,
`KUBE_CONTEXT=kind-novasurge`, `PROMETHEUS_URL=http://127.0.0.1:30090`, `GATEWAY_URL=http://127.0.0.1:30080`,
API `127.0.0.1:8000`. All paths absolute (derived from the package location).

### 4.2 Topology (`topology.py`) — single source of truth
```
SYNC_CALLS:  api-gateway → product, order, payment, notification
             order-service → product, payment
ASYNC_FLOWS: order-service → notification; payment-service → notification
BUSINESS_IMPACT: payment 10, gateway 9, order 8, product 6, notification 2
USER_TRAFFIC_SHARE: gateway 1.0, product 0.75, order 0.40, payment 0.35, notification 0.0
```
Helpers: `callers_of`, `callees_of`, `upstream_closure` (everything that breaks if X breaks),
`downstream_closure` (everything X depends on), `call_path` (BFS from the gateway), `edges()`.
This graph drives RCA, preflight, strategy, planner and the dashboard graph.

### 4.3 Cluster facade (`cluster.py`)
A `Cluster` protocol with value objects (`PodInfo`, `DeploymentInfo`, `HpaInfo`, `NetworkPolicyInfo`,
`EventInfo`, `ExecResult`): `list_pods(app, namespace)`, `delete_pod`, `patch_pod_labels`, `annotate_pod`,
`resize_pod` (pod `resize` subresource — in-place vertical scaling), `get/patch_deployment`, `get/patch_hpa`,
`list/create/delete_network_policy`, `exec` (kubernetes `stream` with a dedicated ApiClient; returns return code),
`list_events(since)`, `pod_logs`. Implementations: `KubeCluster` (real) and `sim.SimulatedCluster`.
`PodInfo.resources` reflects the *applied* resources from container status (so resizes are visible).

### 4.4 Telemetry (`telemetry.py`)
Nine features per service per tick:

| Feature | PromQL (`NS` = namespace selector, `W`=30s, cAdvisor window 1m) |
|---|---|
| request_rate | `sum by (service)(rate(http_requests_total{NS,service!="notification-service"}[W]))`; notification: `rate(notifications_received_total)` |
| error_rate | 5xx rate / total rate (notification: malformed / total events) |
| p99_latency_ms | `histogram_quantile(0.99, sum by (service,le)(rate(..._bucket[W])))*1000` |
| inflight | `sum by (service)(http_requests_in_flight)` |
| cpu_cores | `avg by (service)(label_replace(sum by (pod)(rate(container_cpu_usage_seconds_total[1m])), "service","$1","pod","(.+)-[a-z0-9]+-[a-z0-9]+"))` |
| cpu_throttle_ratio | throttled periods rate / periods rate, per pod, averaged by service |
| memory_mb | working set per pod averaged by service / 1 MiB |
| caller_error_rate | callers' `http_client_requests_total{target=S}` failed / total; for the gateway: synthetic users' failure ratio |
| caller_p99_ms | callers' client-latency p99 for target S; for the gateway: users' p99 |

Missing data is never invented: absent `request_rate`, `error_rate`, `inflight`, `caller_error_rate` → 0;
absent latency/CPU → `None` (treated neutrally by the detector). Structural state per service from the K8s
API: desired/ready replicas, Ready pod names, all pod names, quarantined pods, deployment generation, HPA
min/max, declared minimum (annotation), restarts, scrape health `avg(up)`. Also: user SLI (rps, failure
ratio, p99), live call rates `caller->callee`. Extra queries: `history()` (query_range with identical PromQL,
for training), `per_pod()` (p99/error/throttle per pod), `caller_breakdown()` (each caller's view of a target),
`probe()` (a real request through nginx: gateway `/health/dependencies`, product `/products/1`, order
`/orders/1`, payment `/payments/1`, notification `/notifications/stats`; OK if status < 500 and ≤ 1000 ms),
`user_impact(start,end)` (`increase(loadgen_requests_total[…])`).

---

## 5. Machine learning

### 5.1 Per-service robust normalisation (`ml/features.py`)
For each service and feature: `median`, `scale = max(1.4826·MAD, abs_floor, rel_floor·|median|)`,
`z = clip((x − median)/scale, −25, 25)`, missing → 0.

| Feature | abs floor | rel floor | Harmful direction |
|---|---|---|---|
| request_rate | 0.5 | 0.10 | down (−1) |
| error_rate | 0.02 | 0 | up |
| p99_latency_ms | 15 | 0.15 | up |
| inflight | 1.0 | 0.25 | up |
| cpu_cores | 0.01 | 0.20 | up |
| cpu_throttle_ratio | 0.05 | 0 | up |
| memory_mb | 10 | 0.10 | up |
| caller_error_rate | 0.02 | 0 | up |
| caller_p99_ms | 15 | 0.15 | up |

Why per service: payment's normal p99 (~250 ms) would look anomalous against product's (~15 ms) under a pooled scaler.
`harmful_z` projects z onto the harmful direction (e.g. a latency drop is not harmful).

### 5.2 Isolation Forest
An Isolation Forest isolates points with random axis-aligned splits; anomalies need fewer splits, so their
average path length is short. `decision_function` > 0 ≈ normal, lower = more anomalous.
- Training data: z-vectors of the baseline (all services pooled — each already relative to its own baseline),
  earliest 80 % in time; plus **4 jittered copies** with Gaussian noise σ=0.75 (an IF cannot split on a constant
  feature, so without jitter an error-rate explosion on a zero-error baseline would be invisible).
- `IsolationForest(n_estimators=200, max_samples=256, contamination="auto", random_state=42)`.
- **Threshold calibration**: `clean_floor` = 0.1 % quantile of training scores; for each feature set it to
  +4σ (harmful direction) on the hold-out vectors and take the median score; `weakest` = the highest of those.
  `threshold = (clean_floor + weakest)/2` if weakest < clean_floor else `clean_floor − 0.01`.
  Rationale: IF scores saturate beyond the training range.
- Reported: hold-out (last 20 %) false-positive rate, single-feature 8σ probe detection per feature.
- Final model: threshold 0.1031, FP 0 %, probe detection 100 %.

### 5.3 LSTM forecaster (`ml/forecaster.py`)
- Input: last 12 z-vectors (60 s) of one service; output: next 12 vectors (60 s).
- `LSTM(9 → 48, 1 layer)` → last hidden → `Linear(48,48) → ReLU → Linear(48, 12·9)` → reshape; **residual**:
  output = last observation + predicted delta (prior: "things stay as they are").
- Training: sliding windows per service (time-ordered 80/20 split per series), MSE, Adam lr 3e-3,
  weight decay 1e-5, batch 64, grad-clip 1.0, up to 300 epochs, early stopping patience 20.
- Reported: val MSE vs persistence MSE (skill = 1 − val/persistence; final +30.5 %), one-step residual mean/std.
- Inference: `predicted_score_60s` = IF score of the forecast at +60 s; `predicted_anomaly` if below threshold
  and some forecast feature ≥ 3σ harmful; `forecast_scores` (all 12 steps, for the dashboard); `residual_z` =
  surprise of the newest observation vs the previous one-step forecast.
- `train --include-recorded` adds telemetry recorded during campaigns (degradation/recovery dynamics).

### 5.4 Training pipeline (`ml/train.py`, `cli train`)
Pull `[now − minutes, now]` via `history()` (identical PromQL); require ≥ 34 samples/service; the CLI refuses
windows that include chaos activity (last INJECT/REMEDIATE/… event + 1.5 min) and waits for clean traffic.
Writes `normalizer.json`, `iforest.joblib`, `lstm_forecaster.pt`, `model_card.json` (data window, samples,
threshold, calibration, quantiles, FP rate, probe detection, forecaster stats, baseline medians).

### 5.5 Online detector (`ml/detector.py`)
Per service, per tick, three voters:
1. **IF**: `score < threshold` and max harmful z ≥ `Z_SUPPORT=3`.
2. **z-rule**: any harmful z ≥ `Z_ALERT=6`.
3. **Structural**: `all_replicas_down` (ready = 0), `replicas_lost` (a pod Ready last tick is no longer Ready,
   and the deployment was not scaled down/rolled out and the pod was not quarantined — identity-based, catches
   5-second self-heals; or ready < min(desired, last stable ready)), `container_restarted`,
   `capacity_below_baseline` (desired or HPA max < declared minimum), `metrics_unreachable` (scrape up ≤ 0.5).

Confirmation: strong flags (`all_replicas_down`, `replicas_lost`, `container_restarted`,
`capacity_below_baseline`) confirm immediately; otherwise 2 of the last 3 windows. Clears after 3 consecutive
clean windows. **Episode memory** keeps the first non-unknown classification, its evidence, all flags and peak
severity until the episode clears.

Severity = `1 − Π(1 − p)` over: `0.9·clip((thr − score)/0.3)`, `0.95·(1 − e^{−(hz−3)/8})`, 0.95 if all down,
`0.4 + 0.4·(1 − ready_ratio)` if replicas lost, 0.5 restarts, 0.5 capacity, 0.6 unreachable (capped 0.9999).
Primary anomaly = earliest onset, then highest severity, then deepest in the call graph.

Classification order: capacity_below_baseline → `replica_exhaustion`; metrics_unreachable with running pods and
no restarts → `network_partition`; lost/down/restart → `pod_unready` (pod still running but NotReady) or
`pod_crash`; throttle z ≥ 4 or ratio ≥ 0.25 → `cpu_throttle`; callers failing + traffic < 15 % of baseline +
own latency normal → `network_partition`; memory z ≥ 6 → `oom_kill`; latency z ≥ 4 with error z < 6 →
`high_latency`; error z ≥ 4 → `error_spike`; else `unknown`. Each class carries human-readable evidence.

---

## 6. Monitor (`monitor.py`)
Single asyncio loop every 5 s: snapshot (thread) → detector.step → publish to listeners (WebSocket, autopilot)
→ append `{t, features, anomalous, context}` to `telemetry.jsonl` (rotated at 50 MB) → `next_tick()` waiters.

---

## 7. Root-cause analysis (`rca.py`)

Candidates = confirmed anomalous ∪ services anomalous in the current window. Evidence (read-only, scoped to
the incident onset + 30 s):

| Evidence | Weight |
|---|---|
| NetworkPolicy selecting the pods with a policyType and no rules (deny-all), not labelled baseline | +3.0 |
| Live pod CPU limit < 50 % of the declared baseline | +2.5 |
| HPA max below the declared minimum | +2.5 |
| Pod events Killing/OOMKilling/BackOff/Unhealthy/FailedScheduling (≤ 3, total ≤ 1.0, excluding pods AutoHeal itself acted on) | ≤ +1.0 |
| ERROR log lines in the last 60 s | min(1.5, 0.5 + n/200) |

Scoring per candidate: `+2·severity`; `−1.0` if only symptom is reduced traffic; **caller-side-only** (own p99,
error, throttle z < 3 but caller z ≥ 4) `−1.5` and each caller whose view shows **excess latency > 100 ms** over
the callee's own p99 (or > 5 % errors) gets `+1.5`; `−1.5` if a failing dependency explains it else `+1.0`;
`+0.3` per anomalous upstream victim; `+0.75` earliest onset (within 5 s); `+0.75` own structural fault;
`+` evidence weights. Confidence: `0.55 + 0.4·min(margin/3, 1)` (single candidate `0.6 + 0.08·min(score, 4.5)`),
cap 0.97. Type refinement by evidence: NetworkPolicy → `network_partition`; HPA drift → `replica_exhaustion`;
resource drift → `cpu_throttle`; OOMKilled → `oom_kill`. Output: origin, type, confidence, call path,
affected, evidence, ranked candidates, narrative (distinguishes upstream callers vs downstream starved services).

---

## 8. Decision engine (`decision_engine.py`)

| Fault | Primary | Fallback |
|---|---|---|
| pod_crash | hpa_scaleout | rolling_restart |
| pod_unready | pod_restart | rolling_restart |
| oom_kill / cpu_throttle | resource_restore | rolling_restart |
| network_partition | network_policy_rollback | rolling_restart |
| replica_exhaustion | hpa_scaleout | resource_restore |
| high_latency | traffic_reroute | rolling_restart |
| error_spike / unknown | rolling_restart | hpa_scaleout |
| cache_miss_spike | cache_flush | hpa_scaleout |

Guardrails: **G1** another owner already remediating this service → BLOCKED (wait, retry); **G4** ≥ 2 other
remediations active and a higher-impact one among them → DEFERRED 30 s; **G2** capacity-removing action
(pod_restart, traffic_reroute) with ≤ 1 Ready and no unready pod → switch to rolling_restart; **G3** the action
failed on this service within 300 s → swap with fallback. Priority = impact × severity.
Confidence = `((successes + 0.7·2)/(n + 2)) × rca_confidence × (1 − 0.3·min(upstream/4, 1))` (history per service ×
remediator × fault from SQLite); below 0.4 → use the fallback if it scores higher. Active-remediation locks
expire after 600 s.

---

## 9. Remediators (`remediators/`)
Common: `RemediationContext(cluster, telemetry, timeout_s=120, poll_s=2)`, result
`{remediator, service, success, summary, started_at, completed_at, duration_s, details}`; `worst_pod()` picks a
non-Ready pod first, else the highest `p99 + 2000·error + 1000·throttle` from per-pod metrics.

| Remediator | Action | Done when |
|---|---|---|
| pod_restart | delete worst pod (grace 5 s) | it is gone and deployment converged |
| rolling_restart | patch template annotation `novasurge.io/restarted-at` | no old pod left, converged (timeout ×1.5) |
| hpa_scaleout | HPA min = max(declared min, ready)+1 (≤ max), max ≥ declared | ≥ new min Ready |
| resource_restore | patch template if drifted; `resize_pod` each drifted container to declared | live = declared and converged |
| network_policy_rollback | delete deny-all policies selecting the pods (not labelled baseline) | converged |
| traffic_reroute | relabel worst pod `app=<svc>-quarantined` (leaves Service + ReplicaSet); refuse if < 2 serving; delete it after 5 s | replacement Ready |
| cache_flush | `redis-cli --scan --pattern 'products:*'` + DEL in the Redis pod | exec OK |

---

## 10. Healer (`healer.py`) — shared by campaigns and autopilot
1. Wait one settling tick; RCA on the latest detection.
2. If the origin is already clean → "self-healing", wait for recovery.
3. Decide (handles BLOCKED/DEFERRED, up to 6 tries).
4. Up to 3 attempts: mark lock → record attempt → remediate → **verify functional** (Ready ≥ max(desired,
   declared min) and 5 consecutive probes OK within 75 s) → complete record. On failure **re-diagnose**; if the
   origin changed, decide again for the new origin, else use the fallback.
5. Wait for **system recovery**: no confirmed anomalies; recovered_at = first clean window of the streak (≤ 150 s).
Statuses: RECOVERED, MITIGATED, FAILED, NO_ACTION; healed_by primary/fallback/self-healing.

---

## 11. Chaos

### 11.1 Injectors (`chaos/injectors/`)
Contract: `NAME, DESCRIPTION, EXPECTED_SIGNATURE, compatible(), inject() → Injection, still_active(), reverse()`.

| Injector | Mechanism | Expected class |
|---|---|---|
| pod_deletion | delete a random Ready pod, grace 0 | pod_crash |
| cpu_throttle | in-place `resize_pod` of every running pod: CPU request = limit = **25m** (`NOVASURGE_THROTTLE_CPU`), annotate `novasurge.io/chaos` | cpu_throttle |
| network_partition | NetworkPolicy `chaos-isolate-<svc>` selecting `app=<svc>`, types Ingress+Egress, no rules; then conntrack flush via chaos-agent | network_partition |
| latency_injection | `tc qdisc replace dev eth0 root netem delay 200ms 50ms distribution normal` on one Ready pod | high_latency |
| replica_reduction | HPA min = max = 1 (only if declared min ≥ 2) | replica_exhaustion |

`reverse` is teardown only (after recovery is measured), idempotent.

### 11.2 Strategy (`chaos/strategy.py`, used when a fault is pinned and target is auto)
`0.35·upstream/4 + 0.25·impact/10 + 0.20·user_share + 0.10·min(rps/baseline,2)/2 + 0.10/ready − 0.60·already_targeted`.

### 11.3 Chaos Planner agent (`chaos/planner.py`, rounds with `"injector": "auto"`)
Candidates = every applicable (fault, service) pair not used this campaign. Facts: dependents, dependencies,
impact, user share, **minutes since this exact pair was last injected** (`state_db.fault_history()` across all
campaigns), times tried, last outcome. Rule score:
`0.30·staleness + 0.20·dependents/4 + 0.15·weakness + 0.15·impact/10 + 0.10·user_share + 0.10·deps/4 − 0.40·(fault used this campaign) − 0.25·(service used this campaign)`;
staleness = 1 if never tried else `min(1, ln(1+hours)/ln(1+24))`; weakness: undetected/failed 1.0,
masked 0.8, misdiagnosed 0.7, SLA missed 0.6, fine 0.
The top 10 go to the LLM (system prompt with the selection principles; user message = JSON with round,
already chosen pairs, system health, candidates). Expected reply `{"candidate_id": int, "reason": str}`;
validated against the list; otherwise the rule-based top pick, with the failure reason narrated.

### 11.4 LLM client (`llm.py`)
OpenAI-compatible POST `/chat/completions`, `temperature 0.2`, `max_tokens 1024`,
`response_format: json_object` (retried without it on 400), `reasoning_effort: low` for gpt-oss models,
timeout 20 s. Groq models tried in order: `openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `qwen/qwen3.8-27b`
(404/429 → next); Gemini: `gemini-2.5-flash`, `gemini-2.5-flash-lite`. Key from env or
`<home>/llm.env` (`GROQ_API_KEY`/`GEMINI_API_KEY`, `NOVASURGE_LLM_PROVIDER`, `NOVASURGE_LLM_MODEL`,
`NOVASURGE_LLM_DAILY_CAP`=500); daily usage counted in SQLite.

---

## 12. Campaign orchestrator (`orchestrator.py`)
Per round: PLANNING (agent) → STRATEGY → **steady-state gate** (preflight GO for 3 consecutive ticks, ≤ 180 s:
Prometheus OK, no service anomalous, target at full capacity, load ≤ 1.8× baseline) → INJECT → DETECT (≤ 90 s,
else UNDETECTED) → RECOVERING (Healer, with a **watchdog** aborting if user failures > 50 % for > 240 s) →
TEARDOWN (check `still_active` → if RECOVERED but still present → **MASKED**; reverse; restore HPA to declared;
settle 10 s) → SLA evaluation, user impact, diagnosis/classification correctness vs ground truth → SQLite,
`reports/<campaign>/{rounds.json, scorecard.json, README.md}`, `reports/LATEST.md`.
Preflight risk: points = (2 if users ≥ 75 %, 1 if ≥ 35 %) + (1 if ≥ 2 dependents) → HIGH ≥ 3, MEDIUM ≥ 1.

### 12.1 SLA and scorecard (`sla_tracker.py`)
TTD = detected − injected; TTM = mitigated − detected; TTR = recovered − detected.
Recovery targets: pod_deletion 90 s, cpu_throttle 90, network_partition 90, latency 120, replica 120.
Detection targets: 25, 35, 30, 35, 35 s.
Score: 35·recovery-SLA rate + 20·detection-SLA rate + 20·effectiveness (primary/self-healing 1.0, fallback 0.5,
×0.25 if fault still present) + 15·(RCA origin accuracy + classification accuracy)/2 + 10·max(0, 1 − 2·mean user
failure ratio).

### 12.2 Narration (`reasoning.py`)
`Narrator.say(phase, message, service, data)` → SQLite `events` → streamed to the dashboard. Phases: CAMPAIGN,
PREFLIGHT, STRATEGY, INJECT, DETECT, RCA, DECIDE, GUARDRAIL, REMEDIATE, VERIFY, RECOVERED, FAILED, TEARDOWN,
SUMMARY, AUTOPILOT. All numbers come from live data.

### 12.3 State (`state_db.py`, SQLite WAL)
Tables: `campaigns`, `rounds` (full JSON), `remediations`, `guardrail_events`, `active_remediations`, `events`,
`kv` (campaign status, detector heartbeat, manual injections, own pod actions, LLM usage). UTC ISO timestamps.

---

## 13. API and dashboard

FastAPI (`api/server.py`) on 127.0.0.1:8000: `GET /api/health, /api/status, /api/anomaly/current,
/api/detection, /api/metrics/current, /api/topology, /api/events?after=&limit=, /api/model, /api/agent,
/api/campaigns, /api/campaigns/{id}, /api/rounds`; `POST /api/campaign/start {rounds|plan, use_llm},
/api/campaign/stop, /api/autopilot {enabled}, /api/chaos/inject {injector, service}`; `WS /ws/stream` (a
`hello` frame with services, edges, impact, recent events, model info; then one `tick` frame per detector tick
with per-service status/score/severity/type/flags/top deviations/metrics/replicas/LSTM, threshold, anomaly
payload, user SLI, call rates, campaign status, autopilot state, new events). Request models are module-level
(required by postponed annotations). Autopilot: on a confirmed anomaly with no campaign running, run the Healer
(owner "autopilot"), cooldown 30 s.

Dashboard (served from `dashboard/dist` by the API; dev via Vite on :5173 with proxies): header (LIVE/RECONNECTING,
user req/s, failure %, p99, last score, round/phase, autopilot toggle, run/stop campaign), anomaly score chart
(per-service IF score + threshold), reasoning feed (phase pills), health grid, decision trace (✓/✗ vs ground
truth), dependency graph (d3-force layout ranked by call depth, edge width = log of live req/s, dashed async
edges, pulsing anomalous nodes, animated edges into anomalous nodes, ready/desired pods), LSTM forecast chart.
No mock data; reconnect with exponential back-off.

---

## 14. Infrastructure tooling (`infra.py`, `cli.py`)
- `kind_bin()` / `kubectl_bin()`: use PATH, else download pinned versions and verify SHA-256.
- `ensure_cluster()`: create from `k8s/kind-config.yaml` if absent; if the node container is stopped, start it.
- `build_and_load_images()`: per image, SHA-256 of its input files (16 hex chars) → rebuild if changed/missing
  → `kind load docker-image` only if the cluster incarnation (container creation time) has not seen that
  hash → returns images whose workloads must be restarted.
- `deploy()`: namespaces, random DB Secret, `kubectl apply -f k8s/base`, rollout restarts; `wait_rollouts()`;
  wait for Prometheus and the shop.
- CLI commands: `demo, up [--rebuild] [--skip-models], train [--minutes 8] [--include-recorded] [--no-wait],
  serve [--port] [--no-autopilot] [--no-browser], campaign [--rounds N] [--plan] [--injector X --target Y]
  [--fixed] [--no-llm] [--dry-run], inject <fault> <svc>, revert, agent-key <groq|gemini>, agent-test, status,
  report, down [--delete], dashboard-build, test`. `campaign` attaches to a running server if present.
- Launchers create the venv outside the repo and reinstall only when `requirements.txt`'s hash changes.

## 15. Simulator and tests
`SimulatedCluster` models ReplicaSets, rolling updates (maxUnavailable 0, unhealthy old pods removed first),
HPA clamping, kubelet readiness (2 s start-up; isolated pods NotReady after 2 s), NetworkPolicies, resizes,
netem flags, quarantine relabels, events, logs. `SimulatedTelemetry` uses measured healthy baselines plus
noise and reproduces fault signatures and cascades. `--dry-run` runs the real orchestrator with 1 s ticks and
fast timeouts, separate DB/models/reports. Tests (36): topology & normalisation, detection + RCA for each
fault, pod-deletion identity detection, scale-up not mistaken for loss, guardrails G1–G4 and learned
confidence, each injector cleared by its playbook remediator, idempotent reverse, refusal cases, full dry-run
campaign (all RECOVERED, 100 % RCA/classification, score ≥ 90), SLA math, masked/misdiagnosis penalties, API,
planner (candidates, recency, weakness, LLM choice, invalid/failed LLM fallback, no-key path). Tests force
`NOVASURGE_LLM_PROVIDER=none`.

## 16. Rebuild order (summary)
1. kind config + manifests + Prometheus; 2. services with uniform metrics; 3. traffic generator and chaos agent;
4. topology, cluster facade, telemetry; 5. normalisation, IF, LSTM, training, detector; 6. injectors and
remediators; 7. RCA, decision engine, healer; 8. orchestrator, SLA, narration, state; 9. API + dashboard;
10. infra/CLI/launchers; 11. simulator + tests; 12. planner + LLM client; 13. collect a clean 8–10 minute
baseline, train, run a campaign.
