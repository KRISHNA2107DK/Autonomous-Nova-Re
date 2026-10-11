# AutoHeal — What It Is, How It Works, and What It Is Good For

## 1. The problem

Modern applications are built from many small services that call each other. When one of them slows down,
crashes, loses its network or runs out of capacity, the effect spreads to everything that depends on it, and
the users notice. Two questions matter to any team running such a system:

1. **Will we survive the failures we have not seen yet?** You only find out by causing failures on purpose in a
   controlled way — this is called *chaos engineering*.
2. **When something breaks, how fast can we find the cause and fix it?** Usually a human is paged, looks at
   dashboards, guesses the cause and applies a fix. That takes minutes to hours.

AutoHeal does both, automatically: it breaks a real application on purpose, notices the problem by itself, works
out what caused it, fixes it, checks that the fix really worked, explains every step in plain English, and grades
its own performance.

## 2. What is inside

- **ShopFusion — the shop being tested.** A small online store made of five services: a gateway that receives every
  request, a product catalogue, an order service, a payment service and a notification service, plus a
  database, a cache and a web server in front. A built-in "traffic generator" acts as 20 shoppers per second
  browsing and buying, so there is always real activity — and it records what those shoppers experience.
- **Kubernetes** — the system that runs and manages these services on your computer (inside Docker), restarting
  them, scaling them and routing traffic.
- **Prometheus** — collects measurements from every service every 5 seconds: how many requests, how many fail,
  how slow they are, how much CPU and memory they use.
- **AutoHeal** — the brain. It reads those measurements, decides when something is wrong, finds the cause, and
  acts through Kubernetes.
- **A live dashboard** in the browser that shows everything as it happens.

## 3. How a round works (the loop)

1. **Choose an experiment.** A *Chaos Planner* agent decides which failure to cause and in which service. It looks
   at how many other services depend on each one, how important it is to the business, how much of the users'
   traffic goes through it, how long ago that exact failure was last tried on that service, and how well the
   system coped last time. An AI language model (through a free API) makes the final choice from a short,
   validated list and explains why; if the AI is unavailable, a scoring rule decides instead.
2. **Safety check.** Before breaking anything, AutoHeal confirms the system is healthy and observable and
   estimates the "blast radius" — which services and what share of users could be affected. It never injects
   into an already-unhealthy system.
3. **Break something for real.** One of five failures: kill a running copy of a service; starve a service of CPU;
   cut a service off the network; make one copy of a service slow; take away a service's ability to scale.
4. **Notice it.** Every 5 seconds a detector compares each service's current behaviour with what is normal *for
   that service*, using machine learning (an Isolation Forest, which spots unusual combinations of measurements),
   simple statistical rules, and facts reported by Kubernetes (for example "a working copy disappeared").
   A second model (an LSTM neural network) forecasts the next 60 seconds.
5. **Find the cause.** When several services look unhealthy at once, AutoHeal works out which one started it,
   using the map of which service calls which, which one went wrong first, and what changed in the system recently
   (for example a new network rule or a reduced CPU limit).
6. **Decide and act.** It picks the fix from a playbook (add capacity, restore the correct CPU limit, remove the
   blocking network rule, take a slow copy out of rotation, restart safely…), checked by four safety rules, and
   applies it.
7. **Prove it worked.** It sends real shopper requests through the front door and checks capacity. If the fix did
   not work, it re-examines the evidence and tries the backup fix.
8. **Clean up and grade.** It confirms the injected failure is physically gone, restores the declared settings,
   and scores the round: how fast it detected, how fast it recovered, whether the diagnosis was right (it knows
   what it injected, so this is checked against the truth), and how many shoppers' requests failed.

Every step is narrated in plain English on the dashboard and stored in a report.

## 4. What it achieved

In the final live 5-round run on a laptop:

| Measure | Result |
|---|---|
| Resilience score | 98.9 / 100 |
| Failures detected | 5 of 5, in 5–15 seconds (average 8.9 s) |
| Root cause identified correctly | 5 of 5 |
| Fault type identified correctly | 5 of 5 |
| Back to normal | 20–50 seconds after detection (average 36 s) |
| Fixes that worked first time | 5 of 5 |

The only points lost were for user impact when the front gateway itself was cut off — every shopper is affected
until the fix lands (about 18 seconds) — and the score counts that honestly.

## 5. Benefits

- **Finds weaknesses before real incidents do**, in a controlled, reversible way, with safety checks and an
  automatic abort if users are hurt too much.
- **Reduces time to recover** from minutes or hours (a person being paged) to seconds.
- **Explains itself.** Every detection, diagnosis and decision is written in plain language with the numbers
  behind it — useful for trust, auditing and learning.
- **Honest self-assessment.** Results such as "undetected", "masked" (symptoms gone but cause still there) or
  "failed" are reported as such; the score is measured, not claimed.
- **Learns from history.** Confidence in each fix grows or shrinks with its track record, and the Chaos Planner
  prioritises experiments that have not been tried recently or that went badly last time.
- **Works without a cloud.** Everything runs on one machine; the AI agent needs only a free API key and makes one
  request per round, and the system keeps working without it.
- **Heals more than its own experiments.** With autopilot on, a failure caused by anything else is handled the same way.
- **Fast to re-run.** After the first setup, it is ready in about a minute; a campaign takes about 10 minutes.

## 6. Limitations

- **Laptop scale.** One Kubernetes node and a small shop; real production systems are larger and noisier.
- **What "normal" means is learned from about 10 minutes of simulated shoppers.** Real systems would need days of
  real traffic and periodic retraining as behaviour changes.
- **Five kinds of failure.** Others (disk full, database failure, memory leaks, DNS problems, bad deployments) are
  not injected, although some are recognised.
- **The forecaster is cautious.** Trained mostly on healthy data, it predicts "staying the same / returning to
  normal" better than the onset of a new problem.
- **The service map is written by hand.** It is accurate for this shop but would have to be discovered
  automatically in a larger system.
- **Fixes are playbook-based.** AutoHeal chooses among known fixes; it cannot invent a new kind of fix, and some
  problems (for example a code bug) need a human.
- **The AI agent depends on an external free service** whose models and limits can change; AutoHeal falls back to
  its own scoring when the service is unavailable.
- **It runs with full rights to the local cluster.** A least-privilege role is documented for running it inside a
  real cluster.

## 7. Who it is for

- **Platform and reliability teams** wanting to test resilience continuously and shorten recovery times.
- **Developers** wanting to see how their service behaves when its neighbours fail.
- **Students and evaluators** wanting a complete, working, explainable example of chaos engineering, anomaly
  detection, root-cause analysis and self-healing on Kubernetes.

## 8. In one sentence

AutoHeal is a self-driving reliability engineer for a Kubernetes application: it deliberately causes realistic
failures, detects them with models trained on the application's own behaviour, finds the true cause, repairs it,
proves the repair, explains every decision, and grades itself against the truth.
