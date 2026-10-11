# AutoHeal 2.0 — audit of the original project and what was rebuilt

The original repository (`KRISHNA2107DK/final_novasurge`) described a complete
*inject → detect → decide → recover* platform, but most of the loop was
simulated, and much of the real infrastructure could not have worked as
committed. Everything below was found by reading every file and then by
running the system against a live cluster. Each item lists what was wrong and
what replaced it.

## 1. The core loop was faked

| Original behaviour | Consequence | Now |
|---|---|---|
| `orchestrator.py` forced `NOVASURGE_MOCK_K8S=true` and `NOVASURGE_MOCK_ANOMALY=true` | No experiment ever touched Kubernetes; nothing was ever detected | Real Kubernetes API; mocks removed. `--dry-run` uses a stateful simulator instead |
| The "anomaly endpoint" mock slept 20 s and returned *the service and type that had just been injected* | Detection and classification were 100 % by construction | Live detector on Prometheus + Kubernetes telemetry; an undetected fault is reported as `UNDETECTED` |
| If nothing was detected the orchestrator invented a payload (`severity 0.70`) | Failed detections looked like successes | Removed — no synthetic fallback anywhere |
| Hard-coded per-round metric "scenarios" and LSTM predictions written into the dashboard's state files | The dashboard showed scripted numbers | Dashboard shows only live telemetry and real detector output |
| Narrative claimed "All other services remain unaffected" for every round | False statements in the reasoning feed | Every sentence is generated from measured values |
| The injected fault was **reversed before recovery was measured** | Remediation never had to fix anything; "recovery" was the teardown | Recovery is verified first (user-path probes + telemetry); teardown runs afterwards and reports whether the fault was *still present* (`MASKED` if symptoms cleared while the cause remained) |
| Fallback remediation was computed but never executed; BLOCKED/DEFERRED decisions were silently swapped for the fallback | Guardrails had no effect | Fallback runs when the primary action fails verification, with re-diagnosis in between; BLOCKED waits for the lock, DEFERRED waits 30 s |
| `failure_strategy.select_target()` was computed and then ignored for hard-coded targets | "Intelligent targeting" was cosmetic | Strategy picks every `auto` target, with a coverage penalty and an auditable score breakdown |
| Every service's "health check" hit the same nginx URL | A healthy gateway meant every service was "healthy" | Per-service user-path probes through nginx → gateway, plus Ready capacity ≥ declared minimum |
| "LSTM predicts 60 s ahead" was `score + (score - score) * 0.5` | The prediction always equalled the current score | A real LSTM seq-to-seq forecaster (60 s history → 60 s forecast) scored by the Isolation Forest; skill vs. a persistence baseline is measured and reported |
| Mock Kubernetes client: a new instance per call, replica counts keyed by HPA name but read by service name | State was lost between calls; the replica-reduction wait looped for 120 s | `SimulatedCluster`: one stateful model with ReplicaSet, rollout, HPA and kubelet behaviour |

## 2. Infrastructure that could not work as committed

* **Image names never matched**: `bootstrap.sh` built `shopfusion/<svc>:latest`, the manifests ran `novasurge/<svc>:latest` with `imagePullPolicy: Never` → every pod stuck in `ErrImageNeverPull`.
* **Redis was unreachable**: the Bitnami chart with `fullnameOverride: redis-service` creates `redis-service-master`, but every service connected to `redis-service`. The cache-flush remediator connected to cluster DNS from the host machine, which cannot resolve it.
* **Bitnami Helm charts** for Postgres/Redis: Bitnami moved its public images behind a paywall in 2025, so the bootstrap would fail on a fresh machine. Replaced with plain, small manifests (Postgres 16 StatefulSet, Redis 7 cache).
* **The network-partition experiment was a no-op**: `namespace.yaml` installed a `default-allow-all` NetworkPolicy. NetworkPolicies are additive allow-lists, so the injector's deny-all policy could never block anything. Removed.
* **Even without that, partitions were partial**: this CNI (like most) evaluates policy only for *new* connections; pooled keep-alive connections survived. A node-level `chaos-agent` DaemonSet now flushes conntrack for the isolated pods so the partition is real.
* **Traffic reroute could never work**: it looked for pods labelled `app=nginx` (the deployment is `nginx-gateway`), patched an `upstream <service>` block that doesn't exist, wrote port 8080, called pod exec without the WebSocket `stream()` helper, and the nginx ConfigMap was mounted with `subPath` (which never receives updates). Replaced by a real quarantine: the worst replica is relabelled out of the Service and its ReplicaSet, replaced, then removed.
* **Deployments hard-coded `replicas` while HPAs owned them**, so every `kubectl apply` fought the autoscaler. Removed; HPAs also got stabilisation windows so start-up CPU bursts don't trigger scale-outs.
* **Prometheus**: the ServiceMonitors were never applied, and kube-prometheus-stack + Loki + Grafana need more RAM than a laptop's Docker VM. Replaced by one lean Prometheus (5 s scrapes, kubelet cAdvisor via the API proxy) — ~250 MB.
* **Linux/macOS only**: `bootstrap.sh` exited on Windows. The new CLI is cross-platform and creates a `kind` cluster with checksum-verified tool downloads.
* **Secrets**: a database password was committed in plain text in five manifests. Now generated randomly at first deploy into a Kubernetes Secret.
* **Repository hygiene**: `node_modules/` (~200 MB), a runtime SQLite DB, logs, state files and a duplicated `novasurge/novasurge/` tree were committed. The duplicate was created by the API's cwd-relative paths (see §4).

## 3. Service bugs (found by running them)

* **Start-up race**: two replicas running `CREATE TABLE` simultaneously crash on Postgres' catalog unique index (observed live: `CrashLoopBackOff`), and the product seeder could double-seed. Schema creation and seeding now run under a Postgres advisory lock.
* **Orders never reserved stock** and had no compensation; payment declines became HTTP 402. Now: atomic conditional `UPDATE … WHERE stock >= qty` reservation, release on decline or failure, replenishment job, 503 on dependency failure.
* **Blocking calls in `async def` endpoints** (sync SQLAlchemy and `time.sleep` on the event loop) in order- and payment-service → handlers are sync (thread pool) with pooled `httpx` clients and tight timeouts.
* **Gateway**: written against the http-proxy-middleware v3 API while depending on v2 (the error handler never ran); `proxyTimeout` did not cover a stuck TCP connect, so requests to a partitioned service hung until nginx gave up at 10 s and were never counted as upstream errors (observed live). Replaced by an undici-based proxy with a hard 5 s deadline. Long-lived keep-alive connections pinned all traffic to whichever replica they first reached (observed: a slow replica got almost no traffic, so detection took 60 s); connections are now recycled every 25 requests (as Envoy's `max_requests_per_connection` does) — detection dropped to ~15 s.
* **Metrics**: raw request paths as label values (unbounded cardinality); a Gauge named `*_total`; no caller-side metrics. All services now emit the same RED metrics with route templates, plus outbound-call metrics, which RCA needs when a service cannot report on itself.
* **Load generator** ran on the host, had no metrics and spawned unbounded tasks when the backend slowed. It now runs in-cluster as an open-loop generator with a concurrency cap, and exports the **user-facing SLI** used to measure each incident's real impact.

## 4. Platform bugs

* `GET /health` was registered *after* `uvicorn.run()` in `api/main.py`, so it returned 404 when the API was started as documented.
* All paths were cwd-relative (`"novasurge/state"`): `cd novasurge && python -m api.main` (the documented command) wrote to `novasurge/novasurge/…`, and `python -m orchestrator` from inside `novasurge/` could not import `novasurge.*` at all — so `make demo` and `make api` crashed.
* `/rounds` sorted by a key that does not exist; the dashboard and backend disagreed on field names (`round/status` vs `current_round/phase`).
* **RCA walked the wrong way**: it walked from the affected service to its *callers* and blamed the earliest deviating caller. Failures propagate upstream, so it blamed the gateway for backend faults. The new RCA scores candidates (downstream explanation, onset order, change evidence, error logs, caller-side-only attribution).
* **Guardrail 3** stored ISO-string timestamps and compared them with floats (a `TypeError` once exercised). Active-remediation locks were never cleared after a crash (Guardrail 1 would block forever); they now expire.
* **ML**: one scaler pooled across services (payment's normal 250 ms p99 looks anomalous next to product's 15 ms); training on synthetic data whose scale never matched live telemetry; the Prometheus fetcher took `result[0]` of multi-series queries; error rate was an absolute rate in production but a ratio in training; missing data was replaced with fixed "typical" values, which hid outages; the IF threshold was a fixed −0.15. The new pipeline trains on a clean live baseline with per-service robust normalisation, data-driven threshold calibration, measured false-positive and detection rates, and a model card.
* **Injectors**: `cpu_throttle` also set memory to 64 Mi (an OOM loop) and depended on a rollout that `maxUnavailable` would never let finish → replaced by in-place pod resize (live cgroup change, no restart). `latency_injection` ran `apt-get install` without `apt-get update` and ignored its own failure result → `tc` is baked into the images.
* **SLA tracker**: `if recovery_seconds` treated 0 s as missing; naive and aware datetimes were mixed; the resilience score *awarded* points simply for guardrails firing. The new scorecard is computed from measured TTD/TTR, ground-truth RCA accuracy, whether the fault was actually removed, and real user impact.
* **Dashboard**: the WebSocket URL was a teammate's LAN IP (`ws://172.20.66.195:8000`); whenever disconnected it rendered fabricated "MOCK" data and fake decision rows; its dependency graph differed from the real call graph. Rebuilt on the live stream only, served by the API itself.

## 5. Things learned from live runs (and handled)

* A deleted pod is replaced in **~5 s** on this cluster — inside one detector tick. Counting Ready replicas missed it; the detector now tracks pod *identity* between ticks (a Ready pod that vanished without a scale-down or rollout is a lost replica).
* A 400 ms netem delay makes the readiness probe fail, so **Kubernetes itself** removes the slow pod and the fault looks like a crash. The experiment now uses 200 ± 50 ms (a slow-but-serving replica), and the scorecard distinguishes a real fix from symptoms *masked* by readiness.
* Isolation Forest scores saturate outside the training range (a 3σ and a 20σ deviation score the same), so the threshold is calibrated between the clean-data floor and single-feature fault probes, and a robust z-score rule plus structural checks complete the ensemble.
* A culprit's own signal can trail its callers' by one window in a cascade; RCA waits one settling tick, includes services anomalous in the current window, and re-diagnoses if a remediation does not verify.
