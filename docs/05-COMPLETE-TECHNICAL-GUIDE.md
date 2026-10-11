# AutoHeal — The Complete Technical Guide (Beginner to Advanced)

> **Who this is for:** someone who has never worked with microservices, Kubernetes, monitoring or machine
> learning, and wants to understand every tool, algorithm and design decision in AutoHeal deeply enough to
> explain it, defend it and rebuild it.
>
> **How it is organised:** Part A explains the big picture and the shared vocabulary. Part B divides the
> project into **five major components**, each owned by one person. Every component section goes from
> "what is this and why does it exist" (beginner) to "exact algorithms, parameters and edge cases" (advanced).

---

# PART A — FOUNDATIONS

## A1. What AutoHeal does, in one paragraph

AutoHeal runs a small online shop made of several cooperating programs ("microservices") on your computer.
It deliberately breaks part of that shop — kills a program, starves it of CPU, cuts its network, slows it down,
or takes away its spare copies. Then, without human help, it **notices** that something is wrong, **figures
out** which part caused it, **chooses and applies a fix**, **proves** the shop works again, **explains** every
step in plain English on a live web dashboard, and **grades itself** because it knows exactly what it broke.
An AI language model helps decide *what* to break next.

## A2. The five components (and who owns them)

```
 ┌──────────────────────┐     ┌──────────────────────┐     ┌──────────────────────┐
 │ 1. PLATFORM          │     │ 2. APPLICATION & UX  │     │ 3. TELEMETRY & ML    │
 │ Person 1             │     │ Person 2             │     │ Person 3             │
 │ Docker, Kubernetes,  │────►│ The shop services,   │────►│ Prometheus metrics → │
 │ kind, Prometheus,    │     │ traffic generator,   │     │ features → Isolation │
 │ tooling, simulator,  │     │ API server, React    │     │ Forest + LSTM →      │
 │ tests                │     │ dashboard, storefront│     │ anomaly detection    │
 └──────────────────────┘     └──────────────────────┘     └──────────┬───────────┘
                                                                     │ "something is wrong"
 ┌──────────────────────┐     ┌──────────────────────┐               ▼
 │ 5. CHAOS, AGENT &    │     │ 4. DIAGNOSIS &       │◄──────────────┘
 │ ORCHESTRATION        │────►│ SELF-HEALING         │
 │ Person 5             │     │ Person 4             │
 │ Fault injectors, LLM │     │ Root-cause analysis, │
 │ Chaos Planner, the   │     │ decision engine,     │
 │ campaign loop, SLAs, │     │ guardrails, fixes,   │
 │ scoring, narration   │     │ verification         │
 └──────────────────────┘     └──────────────────────┘
```

## A3. Vocabulary you need first

| Term | Plain meaning |
|---|---|
| **Program / process** | Software that is running. |
| **Server** | A program that waits for requests and answers them (e.g. "give me product #3"). |
| **HTTP** | The language browsers and servers use. A request has a *method* (GET = read, POST = create) and a *path* (`/products/3`). The answer has a *status code*: 200 OK, 201 Created, 404 Not Found, 409 Conflict, 5xx = server error. |
| **API** | A set of HTTP paths a program offers to other programs. |
| **JSON** | A text format for data: `{"id": 3, "price": 49.99}`. |
| **Latency** | How long a request takes (milliseconds, ms). |
| **Microservice** | A small program that does one job, talking to others over HTTP, instead of one big program doing everything. |
| **Container** | A program packaged with everything it needs (libraries, settings) so it runs identically anywhere. Docker builds and runs containers. |
| **Image** | The packaged, frozen recipe a container is started from. |
| **Kubernetes (K8s)** | Software that runs many containers, restarts them when they crash, makes copies, and routes traffic to them. |
| **Cluster / node** | A cluster is a Kubernetes installation; a node is a machine in it. We use one node. |
| **Metric** | A number measured over time (requests per second, CPU used). |
| **Anomaly** | Behaviour that is unusual compared with normal. |
| **Chaos engineering** | Breaking things on purpose, safely, to learn how a system copes. |
| **Root cause** | The original fault that started a chain of problems. |
| **Remediation** | A fix. |
| **SLA / SLO** | A promise / target about reliability, e.g. "recover within 90 seconds". |
| **p99 latency** | The time under which 99 % of requests finish — it shows the slow tail that users notice. |
| **Replica** | One running copy of a service. Two replicas = two copies sharing the load. |

## A4. The full pipeline in one picture

```
traffic generator (fake shoppers)
        │ HTTP
        ▼
 nginx ─► api-gateway ─► product / order / payment / notification ─► Postgres, Redis
        │ every service publishes metrics
        ▼
 Prometheus (collects every 5 s) + Kubernetes API (pods, replicas)
        │
        ▼
 Telemetry → 9 features per service → normalise → Isolation Forest + rules + LSTM   [Person 3]
        │ anomaly confirmed
        ▼
 Root-cause analysis → decision engine (+ guardrails) → remediation → verification  [Person 4]
        ▲                                                                │
        │ inject fault                                                   ▼
 Chaos Planner (rules + LLM) → injector → campaign loop → SLA + score ─► SQLite, reports [Person 5]
        │
        ▼
 FastAPI server ─► WebSocket ─► React dashboard (live)                             [Person 2]
 Everything above runs on Docker + kind + Prometheus, built and tested by tooling  [Person 1]
```

---

# PART B — THE FIVE COMPONENTS

---

## COMPONENT 1 — PLATFORM, INFRASTRUCTURE & QUALITY
### Owner: **Person 1**

### 1.1 Beginner: why a "platform" is needed
A shop made of eight programs (five services, a database, a cache, a web server) needs somewhere to run them,
something to restart them if they die, something to measure them, and a way to install all of this with one
command. Person 1 builds that foundation, plus the safety net: a simulator and automated tests.

### 1.2 Tool: Docker
- **What it is:** Docker builds *images* from a recipe file called a **Dockerfile**, and runs them as containers.
- **Example (our Python services):**
  ```dockerfile
  FROM python:3.12-slim                 # start from a small Linux with Python
  RUN apt-get install -y iproute2       # add the `tc` network tool (used by a chaos experiment)
  COPY requirements-python.txt …        # copy the list of libraries
  RUN pip install -r …                  # install them
  COPY pycommon/ ./pycommon/            # shared code
  COPY ${SERVICE}/main.py ./main.py     # this service's code
  CMD uvicorn main:app --port ${PORT}   # how to start it
  ```
  One shared Dockerfile builds all three Python services (the service name is a *build argument*);
  another builds both Node.js services.
- **Docker Desktop** runs Docker on Windows inside a small Linux virtual machine (WSL2). On this machine that VM
  has 4 CPUs and ~3.8 GB of memory — a hard budget that shaped many choices.

### 1.3 Tool: Kubernetes, explained through its objects
| Object | What it is | How we use it |
|---|---|---|
| **Pod** | The smallest unit: one running container (plus its IP address). | Each service replica is a pod. |
| **Deployment** | "Keep N identical pods running from this template." If a pod dies, it creates a new one. | One per service. |
| **ReplicaSet** | The helper a Deployment uses to count pods. | Indirect. |
| **Service** | A stable name and address that load-balances across a Deployment's pods. | `product-service:8001` etc. |
| **StatefulSet** | Like a Deployment but for things with permanent data. | Postgres. |
| **PersistentVolume(Claim)** | Disk storage that survives pod restarts. | Postgres data (1 GiB). |
| **ConfigMap / Secret** | Configuration files / sensitive values given to pods. | nginx config, Prometheus config / DB password. |
| **HorizontalPodAutoscaler (HPA)** | Automatically adds or removes replicas based on CPU use, within a min/max. | One per service (min 2, max 4; notification 1–3). |
| **NetworkPolicy** | Firewall rules for pods. | Used *as a fault* (to cut a service off). |
| **DaemonSet** | "Run one pod on every node." | The chaos agent. |
| **Namespace** | A folder that groups objects. | `shopfusion` (the shop), `novasurge-system` (monitoring, traffic, agent). |
| **Probe** | Kubernetes repeatedly checks a pod: *startup* (has it started?), *readiness* (may it receive traffic?), *liveness* (is it stuck? restart it). | Every service. |
| **Labels / selectors** | Tags like `app=product-service`; Services and Deployments find pods by label. | Also used by the "quarantine" fix. |
| **Annotations** | Free-form notes on objects. | We store the declared ("known good") resources and replica limits here. |

**Rolling update:** when a Deployment's template changes, Kubernetes replaces pods gradually. We set
`maxSurge: 1, maxUnavailable: 0`: add one new pod, wait until it is Ready, then remove one old one — capacity
never drops.

**In-place pod resize:** newer Kubernetes can change a running container's CPU/memory limit without restarting
it. Our CPU-throttle experiment and its fix both use this.

### 1.4 Tool: kind (Kubernetes IN Docker)
- Runs a whole Kubernetes cluster as **one Docker container** (`novasurge-control-plane`).
- Why kind and not the alternatives:
  - Docker Desktop's built-in Kubernetes must be enabled by hand in a GUI and does **not enforce NetworkPolicies**
    (so the partition experiment would do nothing).
  - k3s/minikube need extra installs or a VM.
  - kind's default network plugin (**kindnet**) enforces NetworkPolicy, and kind is scriptable.
- Config `k8s/kind-config.yaml` publishes two ports to your PC (only on 127.0.0.1): **30080** (the shop) and
  **30090** (Prometheus). A *NodePort* Service exposes a pod on a fixed port of the node.

### 1.5 The manifests (`k8s/base/`, applied in file-name order)
`00` namespaces → `10` Postgres (+ init script creating `ordersdb`, `paymentsdb`) → `11` Redis → `20–24` the five
services (Deployment + Service + HPA each) → `30` nginx → `40` Prometheus → `41` metrics-server → `45` chaos agent →
`50` traffic generator → `60` least-privilege permissions (RBAC) for AutoHeal.

Key settings and *why*:
| Setting | Why |
|---|---|
| No `replicas:` in HPA-managed Deployments | Otherwise every `kubectl apply` reset the count and fought the HPA (observed). |
| HPA stabilisation: scale-up 60 s, scale-down 120 s | Python start-up CPU spikes triggered needless scale-outs (observed). |
| CPU request 100m (0.1 CPU) | At 50m the services sat at 56–64 % of the 70 % HPA target and flapped. |
| No baseline NetworkPolicy | NetworkPolicies *add* permissions; an "allow all" policy (in the original project) made the partition fault impossible. |
| `NET_ADMIN` capability on app containers | Needed to run `tc` for the latency experiment. |
| Random DB password in a Secret | The original committed the password in five files. |
| Probes: startup every 2 s ×60, readiness every 5 s (2 failures), liveness every 10 s (6 failures) | Fast readiness without killing slow-starting Python pods. |

### 1.6 Tool: Prometheus (monitoring)
- **What it does:** every few seconds it calls `/metrics` on each pod ("scraping") and stores the numbers as
  **time series** (value + timestamp, with labels such as `service="order-service"`).
- **Service discovery:** it asks Kubernetes for the list of pods and scrapes those annotated
  `prometheus.io/scrape: "true"` — every **5 s** (fast detection). The pod's `app` label becomes the `service` label.
- **cAdvisor:** the kubelet (Kubernetes' agent on the node) measures each container's CPU, CPU throttling and
  memory. Prometheus reads it every 10 s through the Kubernetes API proxy.
- **Why one lean Prometheus** instead of the usual "kube-prometheus-stack + Loki + Grafana": those need several GB
  of RAM; ours uses ~250 MB. Logs are read directly from Kubernetes when needed.
- **metrics-server** gives HPAs their CPU numbers (`--kubelet-insecure-tls` because kind's certificates are self-signed).

### 1.7 The chaos agent (a small DaemonSet)
Alpine Linux with `conntrack-tools`, running in the node's own network (`hostNetwork`) with the `NET_ADMIN`
permission. **Conntrack** is the Linux table of open network connections; firewalls usually only check *new*
connections. Flushing a pod's entries forces existing connections to be re-checked, so a network cut is real.

### 1.8 Tooling: `infra.py`, the CLI and the launchers
- **Launchers** `nova.ps1` (Windows) / `nova.sh`: create a Python *virtual environment* (an isolated set of
  libraries) in `%LOCALAPPDATA%\AutoHeal\venv` — **outside** the OneDrive-synced project so 1 GB of libraries is
  not uploaded — and reinstall only when `requirements.txt` changes (detected by a SHA-256 fingerprint).
- **Tool downloads** (`kind`, `kubectl` if missing): from official URLs, verified with **SHA-256 checksums**
  (a checksum proves the file is exactly the published one).
- **Incremental image builds:** for each image, hash all its input files. Rebuild only if the hash changed; load
  into the cluster only if that cluster has not seen the hash; restart only the affected workloads. A repeat
  `up` takes ~6 seconds.
- **Cluster lifecycle:** create if missing; if the cluster container is stopped (paused), start it (this case was a
  real bug found by the user and fixed).
- **CLI** (`python -m novasurge …`): `demo, up, train, serve, campaign, inject, revert, agent-key, agent-test,
  status, report, down, test, dashboard-build`.

### 1.9 The cluster facade (`cluster.py`)
All other components talk to Kubernetes only through one interface (`list_pods`, `delete_pod`, `resize_pod`,
`patch_hpa`, `create_network_policy`, `exec`, `list_events`, `pod_logs`, …). Two implementations exist: the real
one (official Kubernetes Python client) and the simulator. This is the **adapter pattern** — it makes testing
possible without a cluster.

### 1.10 Advanced: the simulator (`novasurge/sim/`)
A dry run must exercise the *real* decision code, so the simulator is a **stateful model**, not canned answers:
- ReplicaSet: keeps the desired number of pods with `app=<svc>`; a relabelled (quarantined) pod is orphaned and replaced.
- Rolling update: surge one new pod, delete an old one only if Ready capacity stays ≥ desired; unhealthy old pods
  are removed first (as the real controller does).
- HPA: clamps desired replicas into [min, max].
- Kubelet: pods become Ready 2 s after creation; pods isolated by a deny-all NetworkPolicy fail readiness after 2 s.
- Faults live where they really live: NetworkPolicies, live pod resources, a per-pod "netem" flag.
- Simulated telemetry: measured healthy baselines + Gaussian noise, plus fault signatures (e.g. an isolated
  service's traffic falls to 5 %, its callers see 65 % errors and 5 s latency).

### 1.11 Tests (36, pytest, ~70 s, no cluster)
Topology, normalisation, detection and RCA for each fault, pod-deletion detection even when healed within a tick,
"scale-up is not a lost replica", all four guardrails, learned confidence, every injector cleared by its fix,
safe refusals, a full 5-round dry-run campaign (must score ≥ 90 with 100 % diagnosis), SLA maths, penalties for
wrong diagnoses and masked fixes, the API, and the LLM planner with a fake AI (tests never spend real API calls).

---

## COMPONENT 2 — APPLICATION & USER EXPERIENCE
### Owner: **Person 2**

### 2.1 Beginner: what the shop is
**ShopFusion** is a mini online store. A shopper browses products, buys one, pays, and gets a notification.
Instead of one program, it is split into services that call each other — exactly the kind of system where one
failure spreads.

### 2.2 The services
| Service | Language & framework | Job |
|---|---|---|
| **nginx** | nginx web server | The front door on port 30080; forwards everything to the gateway. |
| **api-gateway** | Node.js + Express | Routes `/products…`, `/orders…`, `/payments…`, `/notifications…` to the right service; serves the storefront page. |
| **product-service** | Python + FastAPI | Catalogue, stock, cache. |
| **order-service** | Python + FastAPI | Places orders by coordinating product and payment services. |
| **payment-service** | Python + FastAPI | Simulates a card processor. |
| **notification-service** | Node.js | Listens for order/payment events. |
| **PostgreSQL** | Database | Stores products, orders, payments (three databases). |
| **Redis** | In-memory store | Cache for products + message bus for events. |

**Frameworks explained:** *FastAPI* is a Python library for writing HTTP APIs (it validates input with *Pydantic*
models). *Express* is the equivalent for Node.js. *SQLAlchemy* lets Python talk to Postgres. *uvicorn* runs FastAPI.

### 2.3 How an order works (a "saga")
```
POST /orders {user, product_id, quantity}
 1. order-service → GET product (price)                         product-service
 2. order-service → POST /products/{id}/reserve (take stock)    product-service   (409 if not enough)
 3. save order as "pending"                                     ordersdb
 4. order-service → POST /payments {order_id, amount}           payment-service  (40–160 ms, 3 % declined)
 5. confirmed  — or —  payment_declined + give the stock back (compensation)
 6. publish "order-events" on Redis                              → notification-service
```
A **saga** is a multi-step business action across services where each step can be undone by a *compensating*
step if a later one fails. If product or payment is unreachable, stock already reserved is released and the user
gets HTTP 503 (Service Unavailable).

**Atomic stock reservation:** a single database statement
`UPDATE products SET stock = stock − q WHERE id = :id AND stock >= q` — two shoppers can never buy the last item twice.

**Cache-aside:** product reads first look in Redis (`products:{id}`, valid 60 s); on a miss, read Postgres and
store in Redis. Changing stock deletes the cached copy.

**Replenishment:** every 15 s product-service tops low stock back up so the endless traffic never empties the shop.

**Start-up race fix:** two copies of a service starting together both ran `CREATE TABLE` and one crashed (seen
live). Now schema creation runs while holding a Postgres **advisory lock** — a named lock that only one
connection can hold at a time.

### 2.4 Observability built into every service
Every service exposes the **same metric names** so one query works for all:
- `http_requests_total{method, route, status_code}` — a **counter** (only goes up). Prometheus computes a *rate*
  from it (requests per second).
- `http_request_duration_seconds{method, route}` — a **histogram**: it counts requests into time buckets
  (≤5 ms, ≤10 ms, … ≤10 s); percentiles like p99 are estimated from the buckets.
- `http_requests_in_flight` — a **gauge** (goes up and down): requests being processed right now.
- `http_client_requests_total{target, status_code}` and `http_client_request_duration_seconds{target}` — what
  each service experiences when **it calls others**. This "caller-side view" is how AutoHeal sees a service that
  cannot report on itself (e.g. cut off from the network).
- `route` is the *template* (`/products/{product_id}`), never the raw path — raw paths would create a separate
  time series per product id (an "explosion of cardinality").
- Logs are one JSON object per line (`timestamp, service, level, message, …`) so they can be searched.

### 2.5 The gateway's two important engineering details
1. **Hard deadline.** Upstream calls use *undici* `fetch` with a 5-second timeout that also covers a stuck
   connection attempt. The previous library's timeout did not fire in that case, so a cut-off service made
   requests hang ~10 s and were never counted as errors (seen live).
2. **Connection recycling.** HTTP *keep-alive* reuses one network connection for many requests. Kubernetes
   balances **per connection**, so long-lived connections pin all traffic to whichever pod they first reached.
   A slow pod then received almost no traffic and took 60 s to detect. Recycling each connection after 25
   requests (and nginx after 50) spreads load again: detection dropped to ~15 s.

### 2.6 The traffic generator (fake shoppers)
Runs inside the cluster at **20 requests/second**, "open-loop" (it keeps the schedule even when the shop is slow,
so it doesn't hide slowness). Mix: 40 % view a product, 10 % view the catalogue, 25 % place an order, 15 % view
an order, 10 % view a payment. It exports `loadgen_requests_total{outcome}` and its latency — **what the users
actually experienced** — used to measure the real impact of every incident.

### 2.7 The AutoHeal API server (FastAPI)
- REST endpoints: status, current anomaly, full detection, metrics, topology, reasoning events, model card, agent
  status, campaigns and rounds; actions: start/stop a campaign, toggle autopilot, inject a fault manually.
- **WebSocket** `/ws/stream`: a permanent two-way connection; the server *pushes* one "tick" message every 5 s
  (so the browser does not have to keep asking).
- **Autopilot:** if an anomaly appears and no campaign is running, the server starts the healing pipeline itself.
- Bug found live: request-body classes defined inside a function were invisible to FastAPI because of postponed
  type annotations → moved to module level.

### 2.8 The dashboard (React)
- **React** builds the page from components that re-render when data changes; **Vite** bundles it;
  **Tailwind CSS** styles it with utility classes; **Recharts** draws charts; **d3** computes the graph layout.
- Panels: header (live/reconnecting, user requests/s, failure %, p99, last score, round/phase, autopilot,
  run/stop), anomaly score chart (each service's Isolation-Forest score against the threshold line), reasoning
  feed, health grid, decision trace (✓/✗ against what was really injected), dependency graph (d3 *force layout*:
  nodes repel, links pull; edge width = live requests/s; anomalous nodes pulse), LSTM forecast chart.
- **No fake data:** the original showed invented "MOCK" data when disconnected; this one says "not connected".
- Served by the API itself, using relative URLs (the original hard-coded a teammate's network IP).

### 2.9 The storefront
`http://127.0.0.1:30080/shop` — one plain HTML/JavaScript page served by the gateway: catalogue with stock,
**Buy** (runs the real saga), order/payment lookup, live service health chips, notification counters. Its own page
loads are excluded from metrics so browsing does not disturb the learned baseline.

---

## COMPONENT 3 — TELEMETRY & MACHINE-LEARNING DETECTION
### Owner: **Person 3**

### 3.1 Beginner: what "detecting an anomaly" means
We want a smoke alarm for each service: quiet when things are normal, loud when they are not — **without** being
told in advance what each failure looks like. The approach: learn what *normal* looks like for each service, then
flag behaviour that is far from it.

### 3.2 From raw metrics to features (telemetry)
Every 5 seconds AutoHeal asks Prometheus questions written in **PromQL** (Prometheus Query Language). Examples:
- `rate(http_requests_total[30s])` — "how many requests per second over the last 30 s".
- `histogram_quantile(0.99, sum by (le) (rate(http_request_duration_seconds_bucket[30s])))` — "the p99 latency".
- `sum by (service)` — add up all pods of a service.

The nine **features** per service:
| # | Feature | Meaning |
|---|---|---|
| 1 | request_rate | requests/s it served (notification: events/s) |
| 2 | error_rate | share of its responses that were 5xx |
| 3 | p99_latency_ms | its own slow-tail latency |
| 4 | inflight | requests in progress |
| 5 | cpu_cores | CPU per pod |
| 6 | cpu_throttle_ratio | share of time slices where the CPU limit stopped it |
| 7 | memory_mb | memory per pod |
| 8 | caller_error_rate | failures *its callers* see when calling it (gateway: real users) |
| 9 | caller_p99_ms | latency *its callers* see (gateway: real users) |

Plus **structural facts** from Kubernetes: which pods are Ready (by name), desired vs declared minimum
replicas, autoscaler limits, restarts, and whether Prometheus can still reach the pods.

Important rules:
- Missing traffic means **zero**, missing latency means **unknown** — never an invented "typical" value
  (the original did that and hid outages).
- CPU features use a **1-minute** window because the kubelet refreshes idle containers only every 10–15 s.
- Training and live detection use **identical** queries.

### 3.3 Normalisation: making services comparable
Payment normally takes ~250 ms; product ~15 ms. "300 ms" is fine for one and terrible for the other. So each
value is converted to a **z-score against that service's own normal**:

- **Median:** the middle value of the baseline (robust: one spike doesn't move it).
- **MAD (median absolute deviation):** the median distance from the median — a robust measure of spread.
  Multiplying by 1.4826 makes it comparable to a standard deviation.
- `z = (value − median) / scale`, where `scale = max(1.4826·MAD, floor)`.
- **Floors** stop near-constant features from exploding: e.g. error rate never varies in healthy traffic (MAD = 0),
  so a single error would be "infinite sigma"; the floor (2 percentage points) says "changes smaller than this
  are measurement noise". Floors: request rate 0.5 or 10 %, error 0.02, p99 15 ms or 15 %, inflight 1 or 25 %,
  CPU 0.01 or 20 %, throttle 0.05, memory 10 MB or 10 %, caller error 0.02, caller p99 15 ms or 15 %.
- z is clipped to ±25. **Harmful direction:** more latency/errors/CPU is bad; *less* traffic is bad; less latency is good.

### 3.4 Algorithm 1: Isolation Forest (IF)
**Intuition.** Imagine finding one odd marble in a jar by randomly cutting the jar. Normal marbles sit in a dense
cluster and need many cuts to separate; an odd marble far away is separated after a few cuts.

**How it works.**
1. Build a **tree**: pick a random feature and a random split value between its min and max; send points left or
   right; repeat until each point is alone (or a depth limit).
2. The **path length** = number of splits needed to isolate a point. Anomalies have short paths.
3. Build many trees (we use **200**, each from a random sample of up to **256** points) and average.
4. scikit-learn's `decision_function`: positive ≈ normal, lower/negative = more anomalous.

**Our setup.** Training vectors = all services' normalised baselines (earliest 80 % in time), plus **4 jittered
copies** (Gaussian noise σ = 0.75). Why jitter: a tree can never split on a feature that is constant, so without
it an error-rate explosion on a zero-error baseline would be invisible.

**Threshold calibration (advanced).** IF scores **saturate** outside the training range — a 3σ and a 20σ deviation
score the same because both land in the same outer leaf. So the threshold is placed between two measured
populations: the **clean floor** (0.1 % lowest score on healthy data) and the **weakest single-feature fault probe**
(each feature pushed to +4σ; take the least anomalous). Threshold = their midpoint. Final model: threshold
**0.1031**, false positives on held-out healthy data **0 %**, detection of single-feature 8σ probes **100 %**.

### 3.5 Algorithm 2: LSTM forecaster
**Neural network basics.** A neural network is a function with many adjustable numbers (weights), tuned by
**gradient descent** to reduce an error (the *loss*). An **RNN** reads a sequence step by step, keeping a memory.
An **LSTM** (Long Short-Term Memory) is an RNN with *gates* (input, forget, output) that decide what to remember,
so it handles longer patterns.

**Ours.**
- Input: the last **12** normalised feature vectors (60 s). Output: the next **12** (the coming 60 s).
- Architecture: LSTM (9 inputs → 48 hidden units, 1 layer) → small dense network → 12×9 outputs.
- **Residual trick:** the network predicts the *change* from the last observation, so its default is "things stay as they are".
- Training: MSE loss (mean squared error), **Adam** optimiser (learning rate 0.003), batches of 64, gradient
  clipping, up to 300 epochs, **early stopping** (stop when validation error hasn't improved for 20 epochs),
  validation on the last 20 % of each service's timeline.
- Measured against a naive "persistence" forecast (tomorrow = today): **30.5 % lower error**.
- Uses: (1) `predicted_score_60s` — the forecast is scored by the Isolation Forest ("will it look anomalous in a
  minute?"); (2) a **surprise score** — how far the newest observation is from what was predicted one step earlier.

### 3.6 The online detector (three voters + time logic)
Each service, each tick:
1. **Isolation Forest** votes if score < threshold and some feature is ≥ 3σ in a harmful direction.
2. **z-score rule** votes if any feature is ≥ **6σ** harmful.
3. **Structural rules** (facts from Kubernetes):
   - *all replicas down*;
   - *replicas lost* — **identity-based**: a pod that was Ready last tick is no longer Ready, and there was no
     scale-down, rollout or quarantine. (Kubernetes replaced a deleted pod in ~5 s — inside one tick — so
     counting pods missed it; comparing names catches it.)
   - *container restarted*; *capacity below declared minimum*; *metrics unreachable* (Prometheus can't scrape ≥ half the pods).

**Confirmation (debouncing).** Statistical votes need **2 of the last 3** windows; Kubernetes facts confirm
immediately (Kubernetes already debounces readiness). An anomaly **clears** after 3 clean windows.
**Episode memory:** the first specific classification, its evidence and the peak severity are kept until the
episode clears, so a later diagnosis still sees the incident.

**Severity (0–1)** combines how far below threshold the score is, `0.95·(1 − e^{−(z−3)/8})` for the worst
feature, and fixed weights for structural facts, combined as `1 − Π(1 − part)` (like independent probabilities).

**Classification** (first match wins): capacity below minimum → *replica exhaustion*; unreachable but running →
*network partition*; lost/down → *pod unready* (still running) or *pod crash*; throttle high → *CPU throttle*;
callers failing while traffic vanished and own latency normal → *network partition*; memory high → *OOM*;
latency high with few errors → *high latency*; errors high → *error spike*; else *unknown*.

### 3.7 Training safely
`.\nova.ps1 train` pulls the last 8–10 minutes from Prometheus, but **refuses** any window that contains chaos
activity (it waits until there has been clean traffic since the last fault + 1.5 min). Output files:
`normalizer.json`, `iforest.joblib`, `lstm_forecaster.pt`, `model_card.json` (all numbers above).

### 3.8 The Monitor
One loop, every 5 s: fetch telemetry → run the detector → push to the dashboard, autopilot and campaign →
append the measurements to `telemetry.jsonl` (for later retraining).

---

## COMPONENT 4 — DIAGNOSIS & SELF-HEALING
### Owner: **Person 4**

### 4.1 Beginner: why diagnosis is hard
When payment-service breaks, order-service (which calls it) and the gateway (which calls order-service) also look
broken. A naive system would "fix" the gateway. **Root-cause analysis (RCA)** finds the service where the trouble
*started*.

### 4.2 The dependency graph
```
api-gateway ──► product-service
     │   └────► order-service ──► product-service
     │                      └───► payment-service
     ├────────► payment-service
     └────────► notification-service      (order & payment also publish events to notification)
```
- **Upstream closure** of X = everyone who suffers if X fails (its callers, their callers…).
- **Downstream closure** of X = everything X depends on.
- Failures travel **upstream** (from callee to caller). The original project walked the wrong way.

### 4.3 RCA, step by step
1. **Candidates:** every confirmed anomalous service plus any deviating in the current window (a culprit's own
   signal can arrive one tick after its callers').
2. **Evidence from the cluster** ("what changed?" — most real incidents follow a change):
   | Evidence | Points |
   |---|---|
   | A NetworkPolicy that blocks all traffic to these pods | +3.0 |
   | Live CPU limit below half the declared value | +2.5 |
   | Autoscaler maximum below the declared minimum | +2.5 |
   | Pod events (Killing, BackOff, Unhealthy…), at most 3, max +1 total, excluding pods AutoHeal itself touched | ≤ +1.0 |
   | ERROR lines in the service's logs (last 60 s) | up to +1.5 |
3. **Scoring each candidate:**
   - +2 × severity;
   - −1.0 if its only symptom is *less traffic* (a victim of something upstream);
   - **caller-side only:** if its own latency/errors are normal but callers see it as slow, the problem is on the
     caller's side or the network: −1.5 for it, and +1.5 for each caller whose view shows **> 100 ms excess
     latency** over the callee's own time (found live: a slow order pod made healthy product-service look slow);
   - −1.5 if a failing dependency explains it, otherwise +1.0;
   - +0.3 per anomalous caller it explains; +0.75 if it was first (within 5 s); +0.75 for its own structural fault;
   - + evidence points.
4. **Confidence** from the gap between the best and second-best (0.55 + 0.4 × gap/3, capped 0.97).
5. **Refine the fault type** with evidence (a blocking NetworkPolicy ⇒ network partition, etc.).
6. Produce a narrative: who is the origin, who are upstream victims, who is starved downstream, and why.

### 4.4 The decision engine
**Playbook** (fault → primary fix, backup fix):
| Fault | Primary | Backup |
|---|---|---|
| pod crash | add capacity (hpa_scaleout) | rolling restart |
| pod unready | replace that pod (pod_restart) | rolling restart |
| CPU throttle / OOM | restore declared resources | rolling restart |
| network partition | remove the blocking policy | rolling restart |
| replica exhaustion | restore/raise autoscaler limits | restore resources |
| high latency | quarantine the slow replica (traffic_reroute) | rolling restart |
| error spike / unknown | rolling restart | add capacity |
| cache miss spike | flush the product cache | add capacity |

**Four guardrails (safety rules):**
- **G1 duplicate:** never two fixes on the same service at once (locks expire after 10 min if a process dies).
- **G2 replica safety:** never remove the last serving copy; replacing a copy that isn't serving is allowed.
- **G3 failure memory:** if this fix failed on this service in the last 5 minutes, try the backup first.
- **G4 cascade protection:** if two or more fixes are already running, only the most business-critical service proceeds.

**Confidence (learning from history):**
`confidence = smoothed_success × rca_confidence × (1 − 0.3 × blast_risk)`, where
`smoothed_success = (successes + 0.7·2) / (attempts + 2)` (a *Bayesian prior*: start by believing 70 % success
worth two attempts, then let real results dominate) and blast risk = number of upstream services / 4. Below 0.4,
the backup is used if it scores higher.

### 4.5 The seven fixes (remediators)
| Fix | What it really does |
|---|---|
| hpa_scaleout | Raise the autoscaler minimum to max(declared, ready)+1 and wait for those pods to be Ready. |
| resource_restore | Put CPU/memory back to the declared values — in place, no restart — and fix the template if it drifted. |
| network_policy_rollback | Delete policies that select this service and block all traffic (found by *effect*, so it would also undo a human mistake). |
| traffic_reroute | **Quarantine:** relabel the worst pod (`app=<svc>-quarantined`) — it instantly leaves the Service (no traffic) and its ReplicaSet (which starts a replacement); delete it after 5 s. Refuses if fewer than 2 copies are serving. |
| pod_restart | Delete the worst/unready pod; Kubernetes recreates it. |
| rolling_restart | Replace every pod gradually with zero downtime. |
| cache_flush | Delete `products:*` keys in Redis. |
"Worst pod" = a non-Ready pod, otherwise the highest `p99 + 2000·errors + 1000·throttle` from per-pod metrics.

### 4.6 The Healer: closing the loop
1. Wait one tick for evidence to settle; run RCA.
2. If the origin already recovered (Kubernetes self-healed), observe instead of acting.
3. Decide (respecting guardrails).
4. Apply the fix, then **verify independently**: the service has full Ready capacity **and** 5 consecutive real
   requests through nginx succeed in under 1 s.
5. If verification fails: **re-diagnose** with fresh evidence; if the origin changed, decide again; otherwise try the backup (max 3 attempts).
6. Wait until the whole system is back to normal; recovery time = the first clean window.
The same Healer powers **autopilot**, which heals faults AutoHeal did not cause.

---

## COMPONENT 5 — CHAOS, THE AI AGENT & ORCHESTRATION
### Owner: **Person 5**

### 5.1 Beginner: what chaos engineering is
Like a fire drill for software: create a realistic failure on purpose, in a controlled way, and observe whether
the system (and AutoHeal) copes. Rules of good chaos engineering, all implemented here: start from a healthy
"steady state", limit the blast radius, be able to abort, and always clean up.

### 5.2 The five fault injectors
| Fault | Mechanism (real, on Kubernetes) | What it simulates |
|---|---|---|
| **pod_deletion** | Delete a Ready pod instantly (grace period 0). | A machine crash / killed process. |
| **cpu_throttle** | **In-place resize** every pod's CPU limit to 25m (0.025 CPU) — Linux's *CFS quota* then pauses the process most of the time. | A bad resource change / noisy neighbour. |
| **network_partition** | Create a NetworkPolicy that blocks all in/out traffic for the service, then flush conntrack via the chaos agent. | A firewall mistake / network split. |
| **latency_injection** | Run `tc qdisc replace dev eth0 root netem delay 200ms 50ms distribution normal` in **one** pod. `tc` is Linux traffic control; *netem* adds delay to every outgoing packet. | A degraded node / network. |
| **replica_reduction** | Set the autoscaler to min = max = 1. | A bad scaling change removing redundancy. |
Each injector also has `compatible()` (can it be applied here?), `still_active()` (is the fault still physically
present?) and `reverse()` (idempotent cleanup — used only *after* recovery is measured).

Values were tuned from live evidence: 15m CPU caused an outage (40 % failures), not throttling → 25m;
400 ms delay made Kubernetes' readiness probe remove the pod (masking the fault) → 200 ± 50 ms.

### 5.3 The Chaos Planner agent (with an LLM)
**What an LLM is:** a Large Language Model — an AI trained on huge amounts of text that can follow instructions
and reason in language. We call it over the internet through an **API** using a key.

**Why not let the AI decide everything?** LLMs can invent things ("hallucinate"). So the code computes the facts
and limits the choice; the AI only picks from a validated list and explains why.

**Step 1 — candidates:** every (fault, service) pair that is applicable now and not already used in this campaign.
**Step 2 — facts per candidate:** services depending on it, services it depends on, business impact (payment 10,
gateway 9, order 8, product 6, notification 2), share of user traffic, **minutes since this exact fault was last
tried on this exact service** (from the history of all campaigns), times tried, last outcome.
**Step 3 — rule score:**
```
0.30 × staleness   (never tried = 1.0; else ln(1+hours)/ln(1+24), capped at 1 → fully "stale" after 24 h)
+ 0.20 × dependents/4
+ 0.15 × weakness  (undetected/failed 1.0, masked 0.8, misdiagnosed 0.7, SLA missed 0.6, fine 0)
+ 0.15 × impact/10
+ 0.10 × user share
+ 0.10 × dependencies/4
− 0.40 if this fault type was already used this campaign
− 0.25 if this service was already hit this campaign
```
**Step 4 — the LLM call (one per round):** the top 10 candidates with their facts are sent as JSON with
instructions (prefer never/long-untested pairs, critical services, past weak spots, variety). The model must reply
`{"candidate_id": n, "reason": "…"}` in **JSON mode** (the API forces valid JSON).
**Step 5 — validation and fallback:** the id must be in the list; if there is no key, a timeout, a rate limit
(HTTP 429), a retired model (HTTP 404) or a bad answer, the top rule-based pick is used — the campaign never breaks.
The dashboard shows who decided (LLM or rules) and why.

**Provider choice:** **Groq** — OpenAI-compatible and the most generous free tier (hundreds to thousands of
requests/day; we use 5 per campaign). Models tried in order: `openai/gpt-oss-120b` → `gpt-oss-20b` →
`qwen3.8-27b` (Groq retired the first choice, Llama 3.3 70B, during development — found live). Google Gemini is a
supported alternative. The key is stored outside the project (`llm.env`), typed with hidden input, with a daily cap of 500 calls.

### 5.4 The campaign loop (orchestrator), one round in detail
1. **PLANNING** — ask the Chaos Planner for (fault, service).
2. **PREFLIGHT / steady-state gate** — require 3 consecutive healthy ticks (≤ 180 s): Prometheus reachable, no
   anomalies anywhere, target at full capacity, load ≤ 1.8× normal. Compute the **blast radius**: dependent services
   and the share of users who could be affected; risk LOW/MEDIUM/HIGH.
3. **INJECT** the fault.
4. **DETECT** — wait up to 90 s for the detector. If nothing: report **UNDETECTED** (no faking).
5. **RECOVER** — run the Healer (Component 4). A **watchdog** aborts and reverts the fault if real users see more
   than 50 % failures for over 4 minutes.
6. **TEARDOWN** — check whether the fault is *still physically there*; if the system looked recovered anyway, the
   round is **MASKED** (symptoms gone, cause remains). Then revert leftovers and return the autoscaler to its
   declared limits.
7. **SCORE** — timings, user impact, diagnosis correctness against what was really injected.

### 5.5 Measuring and scoring
- **TTD** (time to detect) = detected − injected; **TTM** (time to mitigate) = verified fix − detected;
  **TTR** (time to recover) = system back to normal − detected.
- Targets — recovery: 90 s (pod, CPU, partition), 120 s (latency, replicas); detection: 25–35 s.
- **User impact:** failed / total synthetic-user requests during the incident (from the traffic generator).
- **Resilience score (0–100):** recovery SLA 35 + detection SLA 20 + fix effectiveness 20 (first fix 1.0, backup
  0.5, ×0.25 if masked) + diagnosis accuracy 15 (right service + right fault type) + user protection 10
  (`1 − 2 × average failure ratio`).
- Live result: **98.9 / 100**, all 5 detected (avg 8.9 s), all correctly diagnosed, all recovered (avg 36 s).

### 5.6 Narration and storage
- Every step produces a plain-English **event** built from live numbers (phases: PREFLIGHT, INJECT, DETECT, RCA,
  DECIDE, GUARDRAIL, REMEDIATE, VERIFY, RECOVERED, TEARDOWN, SUMMARY, AUTOPILOT…).
- Stored in **SQLite** (a database in a single file, `%LOCALAPPDATA%\AutoHeal\runtime\state\novasurge.db`, in WAL
  mode so the server can read while a campaign writes): campaigns, rounds, fix attempts (used for confidence),
  guardrail events, the reasoning feed, live status.
- Each campaign also writes `reports/<campaign>/` (rounds.json, scorecard.json, README.md) and updates `reports/LATEST.md`.

---

# PART C — HOW IT ALL FITS: ONE INCIDENT, END TO END

1. *Planner (P5):* rule scores rank "network_partition on product-service" high (never tried, two dependents);
   the LLM picks it: "high-impact, never tested, not yet used this campaign".
2. *Preflight (P5):* all healthy; blast radius: gateway and order-service, ~100 % of users.
3. *Inject (P5):* NetworkPolicy created; chaos agent (P1) flushes conntrack.
4. *Shop (P2):* gateway calls to product time out after 5 s → 504s; users start failing.
5. *Telemetry (P3):* product's caller error rate jumps (z = +25), Prometheus can't scrape it, its pods fail
   readiness → structural flags; confirmed in ~10 s.
6. *RCA (P4):* product scores highest (+3 NetworkPolicy evidence, structural fault, no failing dependency);
   gateway and order are upstream victims. Type: network partition, 95 % confidence.
7. *Decision (P4):* playbook → network_policy_rollback; guardrails pass; confidence 0.67.
8. *Fix and verify (P4):* policy deleted in 0.0 s; 5 probes through nginx succeed.
9. *Recovery (P4/P3):* all services normal 40 s after detection.
10. *Teardown and score (P5):* fault physically gone (not masked); SLA met; users saw ~20–26 % failures for ~18 s.
11. *Dashboard (P2):* the whole story streamed live; the decision trace row turns green with ✓✓.

---

# PART D — GLOSSARY OF ALGORITHMS AND TECHNIQUES

| Name | One-line explanation | Where |
|---|---|---|
| Rate over a window | (counter now − counter 30 s ago) / 30 s | PromQL features |
| Histogram quantile | Estimate p99 by interpolating within latency buckets | p99 features |
| Median / MAD / robust z-score | Outlier-resistant "how unusual is this" | Normalisation |
| Data augmentation (jitter) | Add noisy copies so a model sees spread on every feature | IF training |
| Isolation Forest | Random splits; anomalies isolate in few splits | Detector |
| Threshold calibration by probes | Place the cut-off between healthy scores and synthetic faults | Training |
| LSTM | Recurrent network with gates that remembers sequences | Forecaster |
| Residual forecasting | Predict changes, not absolute values | Forecaster |
| Early stopping | Stop training when validation error stops improving | Forecaster |
| Debouncing (2-of-3) | Require persistence before alarming | Detector |
| Identity diffing | Compare *which* pods were Ready between ticks | Detector |
| Graph closure (BFS) | Who depends on whom, transitively | RCA, planner |
| Evidence scoring | Weighted points from symptoms and changes | RCA |
| Bayesian smoothing | Start from a prior belief, update with outcomes | Confidence |
| Guardrails | Hard safety rules over decisions | Decision engine |
| Saga + compensation | Multi-service transaction with undo steps | Order flow |
| Advisory lock | Database-level mutual exclusion | Service start-up |
| Cache-aside | Read cache, fall back to DB, then fill cache | Product service |
| Content hashing | Fingerprint inputs to rebuild only what changed | Tooling |
| Adapter pattern | One interface, real and simulated backends | Cluster facade |
| Open-loop load | Requests on a fixed schedule regardless of slowness | Traffic generator |
| Connection recycling | Bound requests per keep-alive connection | Gateway, nginx |
| Conntrack flush | Force existing connections to be re-checked by the firewall | Partition fault |
| CFS quota | Linux CPU limiting by time slices | CPU throttle |
| netem | Linux packet delay emulation | Latency fault |
| LLM with constrained choice + JSON mode | AI picks from validated options in a strict format | Chaos Planner |
| Staleness (log-scaled recency) | Older-untested pairs gain priority, saturating at 24 h | Chaos Planner |
| WebSocket push | Server sends updates without polling | Dashboard |
| Force-directed layout | Nodes repel, links attract, to draw a graph | Dashboard |
