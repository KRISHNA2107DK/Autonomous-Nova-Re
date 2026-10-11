"""
Healer — diagnose -> decide -> remediate -> verify -> confirm recovery.

Shared by campaign rounds (orchestrator) and autopilot (API), so an anomaly is
handled identically whether AutoHeal injected it or it happened on its own.

Verification is independent of the remediator's own report:
  * functional — the deployment is at full Ready capacity (>= declared minimum)
    and N consecutive real user-path probes through nginx succeed fast
  * recovered  — the detector sees the whole system back inside its normal
    band; recovery time is stamped at the *first* clean window of that streak
If the primary action does not verifiably restore service, the fallback runs.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from novasurge import state_db
from novasurge.decision_engine import decide
from novasurge.ml.detector import DetectionResult
from novasurge.monitor import Monitor
from novasurge.rca import RcaResult, analyze
from novasurge.reasoning import Narrator, remediation_text
from novasurge.remediators import REGISTRY, RemediationContext

log = logging.getLogger("novasurge.healer")


@dataclass
class HealOptions:
    verify_timeout_s: float = 75.0
    probe_successes: int = 5
    probe_interval_s: float = 1.0
    recovery_timeout_s: float = 150.0
    remediation_timeout_s: float = 120.0
    poll_s: float = 2.0
    abort_failure_ratio: float = 0.5
    abort_after_s: float = 240.0


@dataclass
class HealOutcome:
    status: str = "FAILED"            # RECOVERED | MITIGATED | FAILED | NO_ACTION
    rca: dict | None = None           # final diagnosis acted upon
    initial_rca: dict | None = None   # first diagnosis (before any re-diagnosis)
    decision: dict | None = None
    attempts: list[dict] = field(default_factory=list)
    healed_by: str | None = None      # primary | fallback | self-healing
    mitigated_at: str | None = None
    recovered_at: str | None = None
    guardrails: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


SETTLE_TICKS = 1
MAX_ATTEMPTS = 3


def _iso(dt: datetime | None = None) -> str:
    return (dt or datetime.now(timezone.utc)).isoformat()


def _plan_steps(decision, role: str, reason: str) -> list[tuple[str, str, str]]:
    """(action, role, why) for the decided action and its fallback."""
    steps = []
    if decision.action:
        steps.append((decision.action, role, reason))
    if decision.fallback:
        steps.append((decision.fallback, "fallback",
                      f"Playbook fallback for {decision.anomaly_type} if {decision.action} cannot be verified."))
    return steps


class Healer:
    def __init__(self, monitor: Monitor, cluster, narrator: Narrator, owner: str,
                 campaign_id: str | None = None, options: HealOptions | None = None):
        self.monitor = monitor
        self.cluster = cluster
        self.narrator = narrator
        self.owner = owner
        self.campaign_id = campaign_id
        self.opts = options or HealOptions()

    # ── entry point ──────────────────────────────────────────────────────────
    async def heal(self, detection: DetectionResult, round_num: int | None = None) -> HealOutcome:
        out = HealOutcome()
        # Evidence-settling tick: in a cascade the culprit can trail its callers by one window.
        await self._wait_ticks(SETTLE_TICKS)
        detection = self.monitor.detection or detection
        rca: RcaResult | None = await asyncio.to_thread(analyze, detection, self.cluster,
                                                        self.monitor.telemetry)
        if rca is None:
            out.status = "NO_ACTION"
            return out
        out.rca = rca.to_dict()
        out.initial_rca = out.rca
        self.narrator.say("RCA", rca.narrative, rca.origin, {"candidates": rca.candidates,
                                                               "call_path": rca.call_path})

        origin = rca.origin
        det = self.monitor.detection or detection
        if not det.services[origin].confirmed and not det.services[origin].window_anomalous:
            self.narrator.say("DECIDE", f"{origin} returned to normal on its own before any action "
                                        f"(Kubernetes self-healing); observing instead of intervening.", origin)
            out.healed_by = "self-healing"
            out.mitigated_at = _iso()
            out.recovered_at = await self._wait_recovered()
            out.status = "RECOVERED" if out.recovered_at else "MITIGATED"
            return out

        decision = await self._decide(origin, rca, round_num)
        out.decision = decision.to_dict()
        out.guardrails = [asdict(g) for g in decision.guardrails]
        if not decision.actionable:
            self.narrator.say("FAILED", f"Remediation of {origin} could not proceed: {decision.action}.", origin)
            return out

        # Each queued step carries why it is being tried, so the incident ledger can show the full chain.
        queue = _plan_steps(decision, "primary", " ".join(decision.reasoning))
        tried: set[tuple[str, str]] = set()
        for attempt_no in range(MAX_ATTEMPTS):
            queue = [q for q in queue if (origin, q[0]) not in tried]
            if not queue:
                break
            action, role, why = queue.pop(0)
            tried.add((origin, action))
            ok, at = await self._attempt(origin, action, rca, round_num, out,
                                         {"step": attempt_no + 1, "role": role, "reason": why})
            if ok:
                out.healed_by = "primary" if attempt_no == 0 else "fallback"
                out.mitigated_at = at
                break
            # Re-diagnose with fresh evidence before escalating: the picture may have changed.
            fresh = await asyncio.to_thread(analyze, self.monitor.detection or detection, self.cluster,
                                            self.monitor.telemetry)
            if fresh is not None and fresh.origin != origin:
                self.narrator.say("RCA", f"Re-diagnosis after {action} failed to restore {origin}: "
                                         f"{fresh.narrative}", fresh.origin)
                origin, rca = fresh.origin, fresh
                out.rca = rca.to_dict()
                decision = await self._decide(origin, rca, round_num)
                out.decision = decision.to_dict()
                out.guardrails += [asdict(g) for g in decision.guardrails]
                if not decision.actionable:
                    break
                queue = _plan_steps(decision, "re-diagnosis",
                                    f"{action} did not restore the previous origin; re-diagnosis moved the root "
                                    f"cause to {origin}. " + " ".join(decision.reasoning))
            elif queue:
                queue[0] = (queue[0][0], "fallback",
                            f"{action} did not verifiably restore {origin} and re-diagnosis still points at "
                            f"{origin}; escalating to the playbook fallback {queue[0][0]}.")
                self.narrator.say("DECIDE", f"{action} did not restore {origin}; escalating to fallback "
                                            f"{queue[0][0]}.", origin)
        if not out.healed_by:
            self.narrator.say("FAILED", f"All remediation options exhausted without verified recovery "
                                        f"(last diagnosis: {origin}).", origin)
            out.status = "FAILED"
            return out

        out.recovered_at = await self._wait_recovered()
        out.status = "RECOVERED" if out.recovered_at else "MITIGATED"
        return out

    # ── steps ────────────────────────────────────────────────────────────────
    async def _decide(self, origin: str, rca: RcaResult, round_num: int | None):
        for _ in range(6):
            det = self.monitor.detection
            st = self.monitor.snapshot.services[origin] if self.monitor.snapshot else None
            severity = det.services[origin].severity if det else 0.5
            decision = await asyncio.to_thread(
                decide, origin, rca.anomaly_type, severity, rca.confidence,
                st.ready_replicas if st else 0, owner=self.owner, campaign_id=self.campaign_id,
                round_num=round_num,
                unready_replicas=max(len(st.pod_names) - len(st.ready_pods), 0) if st else 0)
            for g in decision.guardrails:
                self.narrator.say("GUARDRAIL", f"{g.id} {g.outcome}: {g.detail}", origin)
            self.narrator.say("DECIDE", " ".join(decision.reasoning[-2:]) if decision.actionable
                              else decision.reasoning[-1], origin, decision.to_dict())
            if decision.action == "BLOCKED":
                await self._wait_ticks(4)
                continue
            if decision.action == "DEFERRED":
                await asyncio.sleep(30)
                continue
            return decision
        return decision

    async def _attempt(self, origin: str, action: str, rca: RcaResult, round_num: int | None,
                       out: HealOutcome, step: dict) -> tuple[bool, str | None]:
        fn = REGISTRY[action]
        anomaly_type = rca.anomaly_type
        ctx = RemediationContext(self.cluster, self.monitor.telemetry,
                                 timeout_s=self.opts.remediation_timeout_s, poll_s=self.opts.poll_s)
        meta = step | {"diagnosis": {"origin": origin, "anomaly_type": anomaly_type,
                                     "confidence": rca.confidence}}
        state_db.mark_active(origin, action, self.owner)
        rem_id = state_db.record_remediation_attempt(self.campaign_id, round_num, origin, anomaly_type, action)
        self.narrator.say("REMEDIATE", f"Executing {action} on {origin} (step {step['step']}, {step['role']}).",
                          origin, meta)
        started = _iso()
        try:
            result = await fn(origin, ctx)
            self.narrator.say("REMEDIATE", remediation_text(result.to_dict()), origin, result.to_dict())
            verified, at = (await self._verify_functional(origin)) if result.success else (False, None)
            attempt = result.to_dict() | {"verified": verified, "verified_at": at} | meta
            out.attempts.append(attempt)
            state_db.complete_remediation(rem_id, verified, result.duration_s,
                                          None if verified else result.summary)
            return verified, at
        except Exception as exc:  # noqa: BLE001 - a crashing remediator is a failed attempt
            log.exception("remediator %s crashed", action)
            out.attempts.append({"remediator": action, "service": origin, "success": False,
                                 "summary": f"crashed: {exc}", "verified": False, "started_at": started,
                                 "completed_at": _iso()} | meta)
            state_db.complete_remediation(rem_id, False, 0.0, f"crashed: {exc}")
            self.narrator.say("FAILED", f"{action} crashed: {exc}", origin)
            return False, None
        finally:
            state_db.clear_active(origin)

    async def _verify_functional(self, service: str) -> tuple[bool, str | None]:
        """Full Ready capacity + N consecutive fast user-path probes."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.opts.verify_timeout_s
        streak, first_ok_at = 0, None
        while loop.time() < deadline:
            snap = self.monitor.snapshot
            st = snap.services.get(service) if snap else None
            capacity_ok = bool(st and st.desired_replicas and st.ready_replicas >= max(
                st.desired_replicas, st.baseline_min_replicas))
            probe = await asyncio.to_thread(self.monitor.telemetry.probe, service)
            if capacity_ok and probe["ok"]:
                streak += 1
                first_ok_at = first_ok_at or _iso()
                if streak >= self.opts.probe_successes:
                    self.narrator.say("VERIFY", f"{service} verified functional: {st.ready_replicas}/"
                                                f"{st.desired_replicas} replicas Ready and {streak} consecutive "
                                                f"user-path probes OK (last {probe['latency_ms']:.0f}ms).", service)
                    return True, first_ok_at
            else:
                streak, first_ok_at = 0, None
            await asyncio.sleep(self.opts.probe_interval_s)
        self.narrator.say("VERIFY", f"{service} failed functional verification within "
                                    f"{self.opts.verify_timeout_s:.0f}s.", service)
        return False, None

    async def _wait_recovered(self) -> str | None:
        """System-wide: no confirmed anomalies. Returns the first clean window's timestamp."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.opts.recovery_timeout_s
        clean_since: str | None = None
        while loop.time() < deadline:
            try:
                snap, det = await self.monitor.next_tick(timeout=30)
            except asyncio.TimeoutError:
                continue
            if det is None:
                continue
            any_window = any(d.window_anomalous for d in det.services.values())
            if any_window:
                clean_since = None
            elif clean_since is None:
                clean_since = snap.timestamp.isoformat()
            if not det.anomalous and clean_since:
                return clean_since
        return None

    async def _wait_ticks(self, n: int) -> None:
        for _ in range(n):
            try:
                await self.monitor.next_tick(timeout=30)
            except asyncio.TimeoutError:
                return
