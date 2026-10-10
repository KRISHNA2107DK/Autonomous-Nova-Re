"""
Chaos campaign orchestrator.

Each round:
  1. STRATEGY  pick the target (or use the pinned one) with an auditable score
  2. PREFLIGHT steady-state gate + blast radius; waits for steady state, never
               injects into a degraded or unobservable system
  3. INJECT    real fault via the injector
  4. DETECT    wait for the live detector to confirm an anomaly (no synthetic
               fallback: an undetected fault is reported as UNDETECTED)
  5. HEAL      RCA -> decision + guardrails -> remediation (+ fallback) ->
               functional verification -> telemetry recovery (healer.Healer)
  6. TEARDOWN  idempotent reversal of any residual fault, autoscaler surge
               handed back, so the next round starts from the declared state
  7. SCORE     SLA (TTD/TTM/TTR), measured user impact, RCA ground-truth check

A watchdog aborts the experiment (immediate fault reversal) if synthetic users
see > 50% failures for longer than the abort window.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from novasurge import config, state_db, topology
from novasurge.blast_radius import preflight
from novasurge.chaos.injectors import REGISTRY as INJECTORS
from novasurge.chaos.injectors import Injection
from novasurge.chaos.planner import ChaosPlanner
from novasurge.chaos.strategy import select_target
from novasurge.healer import HealOptions, Healer
from novasurge.monitor import Monitor
from novasurge.reasoning import Narrator, detection_text, recovery_text
from novasurge.remediators import baseline_hpa
from novasurge.sla_tracker import evaluate_round, scorecard

log = logging.getLogger("novasurge.orchestrator")

# "injector": "auto" -> the Chaos Planner agent chooses both the fault and the service each round.
DEFAULT_PLAN = [{"injector": "auto", "target": "auto"} for _ in range(5)]

# One round per fault type in a fixed order (targets still chosen by the strategy).
FIXED_PLAN = [
    {"injector": "pod_deletion", "target": "auto"},
    {"injector": "cpu_throttle", "target": "auto"},
    {"injector": "network_partition", "target": "auto"},
    {"injector": "latency_injection", "target": "auto"},
    {"injector": "replica_reduction", "target": "auto"},
]


@dataclass
class CampaignOptions:
    steady_state_timeout_s: float = 180.0
    detect_timeout_s: float = 90.0
    teardown_settle_s: float = 10.0
    heal: HealOptions | None = None


def load_plan(path=None) -> list[dict]:
    path = path or config.CAMPAIGN_FILE
    if path and path.exists():
        data = json.loads(path.read_text())
        return data.get("rounds", data) if isinstance(data, dict) else data
    return list(DEFAULT_PLAN)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Campaign:
    def __init__(self, monitor: Monitor, cluster, plan: list[dict] | None = None,
                 options: CampaignOptions | None = None, mode: str = "live", echo: bool = True,
                 use_llm: bool = True):
        self.id = f"c-{_now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:4]}"
        self.monitor = monitor
        self.cluster = cluster
        self.plan = plan or load_plan()
        self.opts = options or CampaignOptions()
        self.mode = mode
        self.narrator = Narrator(self.id, echo=echo)
        self.rounds: list[dict] = []
        self.targeted: set[str] = set()
        self.chosen: list[tuple[str, str]] = []
        self.planner = ChaosPlanner(use_llm=use_llm)
        self.stop_requested = False

    # ── campaign ─────────────────────────────────────────────────────────────
    async def run(self) -> dict:
        state_db.create_campaign(self.id, self.mode, self.plan)
        state_db.clear_all_active()          # stale locks from a crashed previous run
        state_db.kv_set("campaign", {"id": self.id, "status": "RUNNING", "round": 0,
                                     "total_rounds": len(self.plan), "phase": "STARTING"})
        self.narrator.say("CAMPAIGN", f"Campaign {self.id} starting: {len(self.plan)} rounds "
                                      f"({', '.join(r.get('injector', 'auto') for r in self.plan)}).")
        if self.monitor.detector is None:
            raise RuntimeError(self.monitor.model_error or "detector unavailable")
        status = "COMPLETED"
        try:
            for i, spec in enumerate(self.plan, start=1):
                if self.stop_requested:
                    status = "STOPPED"
                    break
                rec = await self.run_round(i, spec)
                self.rounds.append(rec)
        except asyncio.CancelledError:
            status = "STOPPED"
            raise
        except Exception as exc:  # noqa: BLE001
            log.exception("campaign failed")
            status = "ERROR"
            self.narrator.say("FAILED", f"Campaign aborted by an internal error: {exc}")
        finally:
            report = scorecard(self.rounds)
            report["campaign_id"] = self.id
            state_db.finish_campaign(self.id, status, report)
            state_db.kv_set("campaign", {"id": self.id, "status": status, "round": len(self.rounds),
                                         "total_rounds": len(self.plan), "phase": "DONE"})
            self.monitor.context = {}
            self.narrator.round = None
            self.narrator.say("SUMMARY", f"Campaign {status.lower()}: resilience score "
                                         f"{report.get('resilience_score')}/100 — {report.get('verdict')}.",
                              data=report)
            _write_report(self.id, self.rounds, report)
        return report

    def _status(self, n: int, phase: str, **extra) -> None:
        self.monitor.context = {"campaign": self.id, "round": n, "phase": phase}
        state_db.kv_set("campaign", {"id": self.id, "status": "RUNNING", "round": n,
                                     "total_rounds": len(self.plan), "phase": phase, **extra})

    # ── round ────────────────────────────────────────────────────────────────
    async def run_round(self, n: int, spec: dict) -> dict:
        self.narrator.round = n
        plan = None
        if spec.get("injector", "auto") == "auto":
            self._status(n, "PLANNING")
            snap0, det0 = await self._fresh_tick()
            health = {s: (det0.services[s].status if det0 else "unknown") for s in topology.SERVICES}
            plan = await asyncio.to_thread(self.planner.decide, self.cluster, list(self.chosen), n,
                                           len(self.plan), health)
            if plan is None:
                self.narrator.say("STRATEGY", "Chaos Planner found no applicable (fault, service) pair; "
                                              "skipping round.")
                rec = {"round": n, "campaign_id": self.id, "injector": None, "target": None, "status": "SKIPPED"}
                state_db.save_round(self.id, rec)
                return rec
            who = f"LLM agent ({plan.model})" if plan.decided_by == "llm" else "rule-based planner"
            note = f" [LLM unavailable: {plan.fallback_reason}]" if plan.fallback_reason else ""
            self.narrator.say("STRATEGY", f"Chaos Planner — {who} chose {plan.injector} on {plan.target}: "
                                          f"{plan.reason}{note}", plan.target, plan.to_dict())
            spec = {"injector": plan.injector, "target": plan.target}
        injector_name = spec["injector"]
        mod = INJECTORS[injector_name]
        rec: dict = {"round": n, "campaign_id": self.id, "injector": injector_name, "planner": plan.to_dict() if plan else None,
                     "expected_signature": mod.EXPECTED_SIGNATURE, "requested_target": spec.get("target", "auto"),
                     "target": None, "status": "PENDING", "timeline": []}

        def mark(phase: str, **fields) -> None:
            rec["status"] = phase
            rec["timeline"].append({"at": _now().isoformat(), "phase": phase})
            rec.update(fields)
            self._status(n, phase, injector=injector_name, target=rec.get("target"))
            state_db.save_round(self.id, rec)

        mark("PREFLIGHT")
        snap, det = await self._fresh_tick()

        # 1. target
        baseline_rps = {s: self.monitor.detector.normalizer.baseline(s)["request_rate"] for s in topology.SERVICES}
        if spec.get("target", "auto") == "auto":
            target, scores = await asyncio.to_thread(select_target, mod, self.cluster, snap, baseline_rps,
                                                     self.targeted)
            rec["strategy"] = scores
            if target is None:
                self.narrator.say("STRATEGY", f"No service is eligible for {injector_name}; skipping round.")
                mark("SKIPPED")
                return rec
            best = scores[0]
            self.narrator.say("STRATEGY", f"{injector_name}: selected {target} (score {best['total']:.3f}: "
                                          f"blast {best['blast']}, impact {best['impact']}, users {best['users']}, "
                                          f"coverage penalty {best['coverage_penalty']}).", target,
                              {"scores": scores})
        else:
            target = spec["target"]
            ok, why = await asyncio.to_thread(mod.compatible, self.cluster, target)
            if not ok:
                self.narrator.say("STRATEGY", f"{injector_name} is not applicable to {target}: {why}.", target)
                mark("SKIPPED")
                return rec
        rec["target"] = target
        self.targeted.add(target)
        self.chosen.append((injector_name, target))

        # 2. steady-state gate
        pf = await self._steady_state_gate(target, injector_name, baseline_rps.get(target))
        rec["preflight"] = pf
        if pf["go_nogo"] != "GO":
            self.narrator.say("PREFLIGHT", f"NO-GO for {injector_name} on {target}: "
                                           f"{'; '.join(pf['nogo_reasons'])}. Round skipped.", target, pf)
            mark("SKIPPED_PREFLIGHT")
            return rec
        self.narrator.say("PREFLIGHT", f"GO: {target} at {pf['target_ready']} Ready, system "
                                       f"{pf['system_health_pct']:.0f}% healthy. Blast radius: "
                                       f"{len(pf['dependents'])} dependent service(s) "
                                       f"{pf['dependents'] or ''}, ~{pf['estimated_affected_users_pct']}% of users, "
                                       f"risk {pf['injection_risk']}.", target, pf)

        # 3. inject
        mark("INJECTING")
        injection: Injection = await asyncio.to_thread(mod.inject, self.cluster, target)
        rec["injection"] = injection.to_dict()
        if not injection.success:
            self.narrator.say("INJECT", f"Injection of {injector_name} into {target} failed: {injection.error}.",
                              target)
            mark("INJECTION_FAILED")
            return rec
        rec["injected_at"] = injection.injected_at
        self.narrator.say("INJECT", f"Injected {injector_name} into {target}: {mod.DESCRIPTION}"
                                    f"{' (' + injection.target + ')' if injection.target else ''}.", target,
                          injection.details)

        try:
            # 4. detect
            mark("DETECTING")
            detection = await self._wait_detection()
            if detection is None:
                self.narrator.say("DETECT", f"No anomaly confirmed within {self.opts.detect_timeout_s:.0f}s of "
                                            f"injecting {injector_name} into {target}. Reporting UNDETECTED.",
                                  target)
                mark("UNDETECTED")
            else:
                await self._detected_and_heal(rec, detection, n, target, mark)
        finally:
            # 6. teardown — always runs, even on errors/cancellation
            await self._teardown(rec, mod, injection)

        # 7. score
        rec["sla"] = evaluate_round(rec)
        end = datetime.fromisoformat(rec.get("recovered_at") or _now().isoformat()).timestamp()
        start = datetime.fromisoformat(rec["injected_at"]).timestamp()
        rec["user_impact"] = await asyncio.to_thread(self.monitor.telemetry.user_impact, start, end)
        if rec["status"] == "RECOVERED":
            self.narrator.say("RECOVERED", recovery_text(target, rec["sla"], rec["user_impact"]), target,
                              {"sla": rec["sla"], "user_impact": rec["user_impact"]})
        rca = rec.get("rca") or {}
        rec["diagnosis_correct"] = rca.get("origin") == target
        rec["classification_correct"] = rca.get("anomaly_type") == mod.EXPECTED_SIGNATURE
        state_db.save_round(self.id, rec)
        return rec

    async def _detected_and_heal(self, rec: dict, detection, n: int, target: str, mark) -> None:
        payload = detection.anomaly_payload()
        primary = detection.services[detection.primary]
        rec["detected_at"] = primary.confirmed_at or detection.timestamp.isoformat()
        rec["detection"] = payload
        ago = (datetime.fromisoformat(rec["detected_at"])
               - datetime.fromisoformat(rec["injected_at"])).total_seconds()
        self.narrator.say("DETECT", detection_text(payload, ago), payload["affected_service"], payload)

        # 5. heal, guarded by the user-impact watchdog
        mark("RECOVERING")
        healer = Healer(self.monitor, self.cluster, self.narrator, owner=self.id, campaign_id=self.id,
                        options=self.opts.heal)
        heal_task = asyncio.create_task(healer.heal(detection, n))
        watchdog = asyncio.create_task(self._watchdog(heal_task))
        try:
            outcome = await heal_task
        except asyncio.CancelledError:
            if self.stop_requested:
                raise
            outcome = None
        finally:
            watchdog.cancel()
        if outcome is None:
            rec["aborted"] = True
            self.narrator.say("FAILED", "Experiment ABORTED by the user-impact watchdog: reverting the "
                                        "fault immediately.", target)
            mark("ABORTED")
            return
        rec.update({"rca": outcome.rca, "initial_rca": outcome.initial_rca,
                    "decision": outcome.decision, "remediations": outcome.attempts,
                    "healed_by": outcome.healed_by, "mitigated_at": outcome.mitigated_at,
                    "recovered_at": outcome.recovered_at, "guardrails": outcome.guardrails})
        mark(outcome.status)

    # ── helpers ──────────────────────────────────────────────────────────────
    async def _fresh_tick(self):
        try:
            return await self.monitor.next_tick(timeout=30)
        except asyncio.TimeoutError:
            return self.monitor.snapshot, self.monitor.detection

    async def _steady_state_gate(self, target: str, injector: str, baseline_rps: float | None) -> dict:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.opts.steady_state_timeout_s
        announced = False
        clean_ticks = 0
        while True:
            snap, det = await self._fresh_tick()
            pf = preflight(target, injector, det, snap, baseline_rps)
            clean_ticks = clean_ticks + 1 if pf["go_nogo"] == "GO" else 0
            if clean_ticks >= 3:          # 15s of continuous steady state
                return pf
            if pf["go_nogo"] != "GO" and not announced:
                self.narrator.say("PREFLIGHT", f"Waiting for steady state before injecting: "
                                               f"{'; '.join(pf['nogo_reasons'])}.", target)
                announced = True
            if loop.time() >= deadline:
                if pf["go_nogo"] == "GO":
                    return pf
                pf["go_nogo"] = "NO-GO"
                return pf

    async def _wait_detection(self):
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.opts.detect_timeout_s
        while loop.time() < deadline:
            try:
                _, det = await self.monitor.next_tick(timeout=30)
            except asyncio.TimeoutError:
                continue
            if det is not None and det.primary:
                return det
        return None

    async def _watchdog(self, heal_task: asyncio.Task) -> None:
        opts = self.opts.heal or HealOptions()
        bad_since = None
        loop = asyncio.get_running_loop()
        while not heal_task.done():
            try:
                snap, _ = await self.monitor.next_tick(timeout=30)
            except asyncio.TimeoutError:
                continue
            ratio = (snap.user_sli or {}).get("failure_ratio") if snap else None
            if ratio is not None and ratio > opts.abort_failure_ratio:
                bad_since = bad_since or loop.time()
                if loop.time() - bad_since > opts.abort_after_s:
                    heal_task.cancel()
                    return
            else:
                bad_since = None

    async def _teardown(self, rec: dict, mod, injection: Injection) -> None:
        self._status(rec["round"], "TEARDOWN", injector=rec["injector"], target=rec.get("target"))
        notes = {}
        try:
            residual = await asyncio.to_thread(mod.still_active, self.cluster, injection)
            notes["fault_still_present"] = residual
            notes["reverse"] = await asyncio.to_thread(mod.reverse, self.cluster, injection)
        except Exception as exc:  # noqa: BLE001
            notes["reverse_error"] = str(exc)
        try:
            notes["autoscaler"] = await asyncio.to_thread(_restore_autoscaler, self.cluster, injection.service)
        except Exception as exc:  # noqa: BLE001
            notes["autoscaler_error"] = str(exc)
        state_db.clear_active(injection.service)
        rec["teardown"] = notes
        rec["fault_cleared"] = not notes.get("fault_still_present", False)
        if rec.get("status") == "RECOVERED" and not rec["fault_cleared"]:
            rec["status"] = "MASKED"
            self.narrator.say("TEARDOWN", f"Symptoms cleared but the injected fault was still present on "
                                          f"{injection.service}: recovery came from Kubernetes routing around it, "
                                          f"not from the remediation. Recorded as MASKED.", injection.service)
        residual_txt = ("the fault was still physically present and has now been reverted"
                        if notes.get("fault_still_present") else "no residual fault found")
        self.narrator.say("TEARDOWN", f"Round teardown for {injection.service}: {residual_txt}; "
                                      f"autoscaler returned to declared bounds.", injection.service, notes)
        await asyncio.sleep(self.opts.teardown_settle_s)


def _restore_autoscaler(cluster, service: str) -> dict:
    try:
        base = baseline_hpa(cluster, service)
    except Exception:  # noqa: BLE001 - service without HPA
        return {"skipped": True}
    hpa = cluster.get_hpa(f"{service}-hpa")
    if (hpa.min_replicas, hpa.max_replicas) != (base["minReplicas"], base["maxReplicas"]):
        cluster.patch_hpa(f"{service}-hpa", {"spec": base})
        return {"from": {"minReplicas": hpa.min_replicas, "maxReplicas": hpa.max_replicas}, "to": base}
    return {"unchanged": base}


def _write_report(campaign_id: str, rounds: list[dict], report: dict) -> None:
    """Write-once campaign artefacts into <repo>/reports/<campaign>/."""
    out = config.REPORTS_DIR / campaign_id
    try:
        out.mkdir(parents=True, exist_ok=True)
        (out / "rounds.json").write_text(json.dumps(rounds, indent=2, default=str))
        (out / "scorecard.json").write_text(json.dumps(report, indent=2, default=str))
        (out / "README.md").write_text(render_markdown(campaign_id, rounds, report), encoding="utf-8")
        latest = config.REPORTS_DIR / "LATEST.md"
        latest.write_text(render_markdown(campaign_id, rounds, report), encoding="utf-8")
    except OSError as exc:
        log.warning("could not write report: %s", exc)


def render_markdown(campaign_id: str, rounds: list[dict], report: dict) -> str:
    lines = [f"# NovaSurge campaign `{campaign_id}`", "",
             f"**Resilience score: {report.get('resilience_score')}/100** — {report.get('verdict')}", "",
             "| Component | Points |", "|---|---|"]
    for k, v in (report.get("components") or {}).items():
        lines.append(f"| {k.replace('_', ' ')} | {v} |")
    lines += ["", f"Mean time to detect: **{report.get('mean_ttd_seconds')}s** · mean time to recover: "
                  f"**{report.get('mean_ttr_seconds')}s** · RCA origin accuracy: "
                  f"**{report.get('rca_origin_accuracy', 0):.0%}** · fault classification accuracy: "
                  f"**{report.get('classification_accuracy', 0):.0%}** · mean user failure ratio during incidents: "
                  f"**{(report.get('mean_user_failure_ratio') or 0):.2%}**", "",
              "| # | Fault | Target | Detected as | RCA origin | Action | TTD | TTR | SLA | Users failed | Status |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rounds:
        sla = r.get("sla") or {}
        rca = r.get("rca") or {}
        acts = [a["remediator"] + ("✓" if a.get("verified") else "✗") for a in r.get("remediations") or []]
        ui = r.get("user_impact") or {}
        lines.append(
            f"| {r['round']} | {r.get('injector') or '—'} | {r.get('target')} | {rca.get('anomaly_type', '—')} | "
            f"{rca.get('origin', '—')} | {', '.join(acts) or '—'} | {sla.get('ttd_seconds', '—')}s | "
            f"{sla.get('ttr_seconds', '—')}s | {'MET' if sla.get('recovery_met') else 'MISS'} | "
            f"{(ui.get('failure_ratio') or 0):.1%} | {r.get('status')} |")
    return "\n".join(lines) + "\n"
