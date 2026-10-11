"""
AutoHeal command line.

    python -m novasurge demo            everything: cluster -> models -> dashboard -> 5-round campaign
    python -m novasurge up              create/update the cluster and deploy ShopFusion (idempotent)
    python -m novasurge train           (re)train detection models on live baseline telemetry
    python -m novasurge serve           API + dashboard on http://127.0.0.1:8000 (autopilot on)
    python -m novasurge campaign        run a chaos campaign (uses the running server if there is one)
    python -m novasurge campaign --dry-run   same campaign against the built-in cluster simulator
    python -m novasurge inject <fault> <service>   inject one fault by hand (autopilot heals it)
    python -m novasurge revert          revert manual injections
    python -m novasurge status          health of every component
    python -m novasurge report          print the latest campaign report
    python -m novasurge logs            write incident logs (failures, remediations, reasoning) for every campaign
    python -m novasurge ledger          rebuild the incident ledger workbook + CSVs (reports/ledger/)
    python -m novasurge db-repair       rebuild a damaged state database (stop `serve` first)
    python -m novasurge down [--delete] pause the cluster (or delete it)
    python -m novasurge test            run the test-suite
    python -m novasurge dashboard-build rebuild the React dashboard
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
import time
import webbrowser

from novasurge import config

BASELINE_MINUTES = 8
WARMUP_MINUTES = 1
CHAOS_SETTLE_MINUTES = 1.5     # metrics windows + autoscaler settling after the last fault


def _utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def say(msg: str) -> None:
    print(f"[novasurge] {msg}", flush=True)


# ── commands ─────────────────────────────────────────────────────────────────
def cmd_up(args) -> None:
    from novasurge import infra
    infra.up(force_build=args.rebuild)
    if not args.skip_models:
        ensure_models()


def ensure_models(minutes: int = BASELINE_MINUTES) -> None:
    from novasurge.ml.train import models_present
    if models_present():
        say("detection models present (retrain any time with: python -m novasurge train)")
        return
    say("no trained models yet — training on live baseline telemetry")
    train_live(minutes, include_recorded=False, wait=True)


def clean_minutes_available() -> tuple[float, str]:
    """Minutes of steady traffic with no AutoHeal chaos/remediation activity in them."""
    from novasurge import infra, state_db
    traffic = infra.traffic_minutes_available()
    last = state_db.last_chaos_activity()
    if last is None:
        return traffic, "steady traffic"
    since_chaos = (time.time() - last.timestamp()) / 60.0 - CHAOS_SETTLE_MINUTES
    if since_chaos < traffic:
        return max(since_chaos, 0.0), "quiet time since the last chaos/remediation activity"
    return traffic, "steady traffic"


def train_live(minutes: int, include_recorded: bool, wait: bool) -> dict:
    from novasurge.ml.train import train
    need = minutes + WARMUP_MINUTES
    have, what = clean_minutes_available()
    if have < need:
        if not wait:
            raise SystemExit(f"only {have:.1f} min of {what}; need {need} (omit --no-wait to wait)")
        say(f"collecting a clean baseline: {have:.1f}/{need} min of {what} so far "
            f"(the in-cluster traffic generator keeps the shop busy; do not inject faults meanwhile)")
        while have < need:
            time.sleep(30)
            have, what = clean_minutes_available()
            say(f"  baseline {min(have, need):.1f}/{need} min")
    end = time.time()
    return train(start=end - minutes * 60, end=end, include_recorded=include_recorded)


def cmd_train(args) -> None:
    card = train_live(args.minutes, args.include_recorded, wait=not args.no_wait)
    say(f"threshold {card['iforest']['threshold']:.4f}, holdout false-positive rate "
        f"{card['iforest']['holdout_false_positive_rate']:.2%}, forecaster skill vs persistence "
        f"{card['forecaster']['skill_vs_persistence']:+.1%}")
    say("restart a running `serve` to load the new models")


def _server(autopilot: bool, port: int):
    import uvicorn
    from novasurge.api.server import create_app
    app = create_app(autopilot=autopilot)
    server = uvicorn.Server(uvicorn.Config(app, host=config.API_HOST, port=port, log_level="warning"))
    return app, server


def cmd_serve(args) -> None:
    _, server = _server(autopilot=not args.no_autopilot, port=args.port)
    url = f"http://{config.API_HOST}:{args.port}"
    say(f"dashboard + API on {url}  (autopilot {'off' if args.no_autopilot else 'on'}; Ctrl+C to stop)")
    if not args.no_browser:
        webbrowser.open(url)
    server.run()


def _api_up(url: str) -> bool:
    import httpx
    try:
        return httpx.get(f"{url}/api/health", timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


async def _tail_campaign(url: str, campaign_id: str, after: int) -> dict | None:
    import httpx
    async with httpx.AsyncClient(timeout=10) as client:
        while True:
            try:
                events = (await client.get(f"{url}/api/events", params={"after": after, "limit": 200})).json()
            except httpx.HTTPError:
                await asyncio.sleep(2)
                continue
            for ev in events:
                after = ev["id"]
                if ev.get("campaign_id") == campaign_id:
                    tag = f"R{ev['round']}" if ev.get("round") else "--"
                    print(f"  [{tag} {ev['phase']:<9}] {ev['message']}", flush=True)
            try:
                c = (await client.get(f"{url}/api/campaigns/{campaign_id}")).json()
                if c.get("status") not in (None, "RUNNING"):
                    return c
            except (httpx.HTTPError, ValueError):
                pass
            await asyncio.sleep(1.5)


def _print_scorecard(report: dict | None) -> None:
    if not report:
        return
    print()
    say(f"RESILIENCE SCORE {report.get('resilience_score')}/100 — {report.get('verdict')}")
    for k, v in (report.get("components") or {}).items():
        print(f"      {k:<26} {v}")
    print(f"      mean TTD {report.get('mean_ttd_seconds')}s · mean TTR {report.get('mean_ttr_seconds')}s · "
          f"RCA accuracy {report.get('rca_origin_accuracy', 0):.0%} · classification "
          f"{report.get('classification_accuracy', 0):.0%}")
    say(f"full report: {config.REPORTS_DIR / 'LATEST.md'}")
    cid = (report or {}).get("campaign_id")
    if cid:
        say(f"incident log (every failure, remediation and its reasoning): "
            f"{config.REPORTS_DIR / cid / 'INCIDENT-LOG.md'}")
    say(f"incident ledger (all incidents, all campaigns): "
        f"{config.REPORTS_DIR / 'ledger' / 'AUTOHEAL-INCIDENT-LEDGER.xlsx'}")


def _plan(args) -> list[dict]:
    from novasurge.orchestrator import FIXED_PLAN, load_plan
    if args.injector:
        return [{"injector": args.injector, "target": args.target or "auto"}]
    if getattr(args, "fixed", False):
        plan = list(FIXED_PLAN)
    else:
        plan = load_plan(config.REPO_ROOT / args.plan if args.plan else None)
    return plan[: args.rounds] if args.rounds else plan


def cmd_campaign(args) -> None:
    plan = _plan(args)
    if args.dry_run:
        report = asyncio.run(_run_simulated_campaign(plan, not args.no_llm))
        _print_scorecard(report)
        return
    url = config.API_URL
    if _api_up(url):
        import httpx
        say(f"submitting the campaign to the running AutoHeal server at {url} (watch the dashboard)")
        after = (httpx.get(f"{url}/api/events", params={"limit": 1}).json() or [{"id": 0}])[-1]["id"]
        resp = httpx.post(f"{url}/api/campaign/start", json={"plan": plan, "use_llm": not args.no_llm},
                          timeout=10)
        if resp.status_code != 200:
            raise SystemExit(f"server refused the campaign: {resp.text}")
        cid = resp.json()["campaign_id"]
        result = asyncio.run(_tail_campaign(url, cid, after))
        _print_scorecard((result or {}).get("report"))
        return
    report = asyncio.run(_run_local_campaign(plan, not args.no_llm))
    _print_scorecard(report)


async def _run_local_campaign(plan: list[dict], use_llm: bool = True) -> dict:
    from novasurge.cluster import get_cluster
    from novasurge.monitor import Monitor
    from novasurge.orchestrator import Campaign
    monitor = Monitor()
    if monitor.detector is None:
        raise SystemExit(monitor.model_error)
    await monitor.start()
    try:
        say("warming up the detector (LSTM needs 60s of history for forecasts; detection is live immediately)")
        for _ in range(3):
            await monitor.next_tick(timeout=30)
        return await Campaign(monitor, get_cluster(), plan=plan, use_llm=use_llm).run()
    finally:
        await monitor.stop()


async def _run_simulated_campaign(plan: list[dict], use_llm: bool = True) -> dict:
    from novasurge import sim
    say("DRY RUN — simulated cluster and telemetry; nothing touches Kubernetes")
    return await sim.run_campaign(plan, use_llm=use_llm)


def cmd_demo(args) -> None:
    from novasurge import infra
    infra.up(force_build=args.rebuild)
    ensure_models()
    if not (config.DASHBOARD_DIST / "index.html").exists():
        build_dashboard()
    asyncio.run(_demo(args))


async def _demo(args) -> None:
    import httpx
    app, server = _server(autopilot=True, port=config.API_PORT)
    task = asyncio.create_task(server.serve())
    while not server.started:
        if task.done():
            raise SystemExit(f"API server failed to start (port {config.API_PORT} in use?)")
        await asyncio.sleep(0.2)
    url = config.API_URL
    say(f"dashboard: {url}")
    if not args.no_browser:
        webbrowser.open(url)
    hub = app.state.hub
    say("warming up the detector")
    for _ in range(3):
        await hub.monitor.next_tick(timeout=30)
    plan = _plan(args)
    async with httpx.AsyncClient(timeout=10) as client:
        after = ((await client.get(f"{url}/api/events", params={"limit": 1})).json() or [{"id": 0}])[-1]["id"]
        resp = await client.post(f"{url}/api/campaign/start", json={"plan": plan, "use_llm": not args.no_llm})
        resp.raise_for_status()
        cid = resp.json()["campaign_id"]
    say(f"campaign {cid} started: {len(plan)} rounds")
    result = await _tail_campaign(url, cid, after)
    _print_scorecard((result or {}).get("report"))
    if args.exit_after:
        server.should_exit = True
        await task
        return
    say(f"campaign finished — dashboard still live at {url} with autopilot on (Ctrl+C to stop)")
    await task


def cmd_inject(args) -> None:
    from novasurge import state_db
    from novasurge.chaos.injectors import REGISTRY
    from novasurge.cluster import get_cluster
    mod = REGISTRY[args.injector]
    ok, why = mod.compatible(get_cluster(), args.service)
    if not ok:
        raise SystemExit(f"{args.injector} is not applicable to {args.service}: {why}")
    inj = mod.inject(get_cluster(), args.service)
    manual = state_db.kv_get("manual_injections", [])
    manual.append(inj.to_dict())
    state_db.kv_set("manual_injections", manual)
    say(f"injected: {json.dumps(inj.to_dict(), default=str)}")
    say("a running `serve` (autopilot on) will detect and heal it; `python -m novasurge revert` undoes it")


def cmd_revert(_args) -> None:
    from novasurge import state_db
    from novasurge.chaos.injectors import REGISTRY, Injection
    from novasurge.cluster import get_cluster
    manual = state_db.kv_get("manual_injections", [])
    for raw in manual:
        inj = Injection.from_dict(raw)
        try:
            say(f"reverting {inj.injector} on {inj.service}: {REGISTRY[inj.injector].reverse(get_cluster(), inj)}")
        except Exception as exc:  # noqa: BLE001
            say(f"could not revert {inj.injector} on {inj.service}: {exc}")
    state_db.kv_set("manual_injections", [])
    if not manual:
        say("no manual injections recorded")


def cmd_agent_key(args) -> None:
    import getpass
    from novasurge import llm
    key = getpass.getpass(f"Paste your {args.provider} API key (input hidden), then press Enter: ").strip()
    if not key:
        raise SystemExit("no key entered")
    llm.save_key(args.provider, key)
    say(f"saved to {llm.ENV_FILE} (outside the repository). Verify with: .\\nova.ps1 agent-test")


def cmd_agent_test(_args) -> None:
    from novasurge import llm
    from novasurge.chaos.planner import ChaosPlanner, build_candidates
    from novasurge.cluster import get_cluster
    cfg = llm.load_config()
    if cfg is None:
        raise SystemExit("no LLM key configured - run: .\\nova.ps1 agent-key groq")
    say(f"provider {cfg.provider}, model {cfg.model}, calls today {llm.usage_today()}/{cfg.daily_cap}")
    cands = build_candidates(get_cluster(), [])
    say(f"{len(cands)} applicable (fault, service) pairs; top rule-based pick: "
        f"{cands[0].injector} on {cands[0].service} (score {cands[0].rule_score:.3f})")
    d = ChaosPlanner(use_llm=True).decide(get_cluster(), [], 1, 5)
    if d.decided_by == "llm":
        say(f"LLM agent OK -> {d.injector} on {d.target}: {d.reason}")
    else:
        say(f"LLM call FAILED ({d.fallback_reason}); the rule-based fallback would choose {d.injector} on {d.target}")


def cmd_status(_args) -> None:
    import httpx
    from novasurge import infra, state_db
    from novasurge.ml.train import model_card_path, models_present
    print(f"  docker            {'running' if infra.docker_ok() else 'NOT RUNNING'}")
    exists = infra.docker_ok() and infra.cluster_exists()
    print(f"  kind cluster      {config.CLUSTER_NAME}: {'present' if exists else 'absent'}")
    if exists:
        out = infra.kubectl("get", "pods", "-A", "-l", "app", "--no-headers", check=False)
        lines = [ln.split() for ln in out.splitlines() if ln.strip()]
        ready = sum(1 for ln in lines if len(ln) > 3 and ln[3] == "Running" and ln[2].split("/")[0] == ln[2].split("/")[1])
        print(f"  pods              {ready}/{len(lines)} running and ready")
    for name, base, path in (("prometheus", config.PROMETHEUS_URL, "/-/ready"),
                             ("shopfusion", config.GATEWAY_URL, "/health"),
                             ("novasurge api", config.API_URL, "/api/health")):
        try:
            ok = httpx.get(base + path, timeout=3).status_code == 200
        except httpx.HTTPError:
            ok = False
        print(f"  {name:<17} {'up' if ok else 'down'}  ({base})")
    if models_present():
        card = json.loads(model_card_path().read_text())
        print(f"  models            trained {card['created_at'][:19]} on "
              f"{sum(card['data']['samples_per_service'].values())} samples; threshold "
              f"{card['iforest']['threshold']:.4f}")
    else:
        print("  models            not trained")
    c = state_db.latest_campaign()
    if c:
        score = (c.get("report") or {}).get("resilience_score")
        print(f"  last campaign     {c['id']} {c['status']} score={score}")


def cmd_report(_args) -> None:
    latest = config.REPORTS_DIR / "LATEST.md"
    print(latest.read_text(encoding="utf-8") if latest.exists() else "no campaign report yet")


def cmd_logs(args) -> None:
    """Incident logs: rebuild them for every campaign, or print one."""
    from novasurge import incident_log
    if args.campaign:
        cid = args.campaign
        if cid == "latest":
            dirs = sorted(d for d in config.REPORTS_DIR.iterdir()
                          if d.is_dir() and d.name.startswith("c-") and (d / "rounds.json").exists())
            if not dirs:
                print("no campaign reports yet")
                return
            cid = dirs[-1].name
        path = incident_log.write(cid)
        if not path:
            print(f"no report found for campaign {cid}")
            return
        print(path.read_text(encoding="utf-8"))
        say(f"saved to {path}")
        return
    written = incident_log.rebuild_all()
    for p in written:
        print(f"  {p}")
    say(f"{len(written)} incident log(s) written · live event files: reports/<campaign>/events.jsonl, "
        f"autopilot: reports/autopilot/<date>.jsonl")
    cmd_ledger(args)


def cmd_ledger(_args) -> None:
    """Rebuild the incident ledger: one workbook (+ CSVs) with every incident ever recorded."""
    from novasurge import ledger
    tables = ledger.collect()
    path = ledger.rebuild()
    if path is None:
        raise SystemExit("could not write the incident ledger (see the warning above)")
    say(f"incident ledger: {path}")
    say(f"  {len(tables['incidents'])} incidents · {len(tables['steps'])} remediation steps · "
        f"{len(tables['affected'])} affected-service rows · {len(tables['timeline'])} reasoning events · "
        f"{len(tables['campaigns'])} campaigns")
    say(f"  CSV copies in {path.parent}")


def cmd_db_repair(_args) -> None:
    """Rebuild the SQLite state database from every readable row plus the durable event files."""
    import re
    import shutil
    import sqlite3
    from datetime import datetime

    src = config.DB_PATH
    if not src.exists():
        raise SystemExit(f"no database at {src}")
    if _api_up(config.API_URL):
        raise SystemExit("AutoHeal is running: stop `serve` first (Ctrl+C in its terminal) and close any "
                         "DBeaver connection to novasurge.db, then run db-repair again")
    probe = src.with_name(src.name + ".lockcheck")
    try:
        src.rename(probe)          # Windows refuses this while any program holds the file open
        probe.rename(src)
    except PermissionError:
        raise SystemExit(f"{src.name} is open in another program (usually DBeaver): disconnect it there "
                         f"(right-click the connection → Disconnect) or close DBeaver, then run db-repair again")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = src.parent / f"corrupt-{stamp}"
    backup.mkdir()
    for f in src.parent.glob(src.name + "*"):
        if f.is_file():
            shutil.copy2(f, backup / f.name)
    say(f"backed up the current database to {backup}")

    old = sqlite3.connect(str(backup / src.name))
    new_path = src.with_name("novasurge.repaired.db")
    new_path.unlink(missing_ok=True)
    new = sqlite3.connect(str(new_path))
    schema = old.execute("SELECT type, name, sql FROM sqlite_master WHERE sql IS NOT NULL "
                         "AND name NOT LIKE 'sqlite_%' ORDER BY type = 'index'").fetchall()
    for _, _, sql in schema:
        new.execute(sql)
    tables = [n for t, n, _ in schema if t == "table"]

    def rows_of(table: str) -> tuple[list[str], list[tuple], int]:
        cols = [r[1] for r in old.execute(f'PRAGMA table_info("{table}")')]
        try:
            return cols, old.execute(f'SELECT {", ".join(cols)} FROM "{table}"').fetchall(), 0
        except sqlite3.DatabaseError:
            pass
        try:
            top = old.execute(f'SELECT max(rowid) FROM "{table}"').fetchone()[0] or 0
        except sqlite3.DatabaseError:
            top = 100000
        good, bad = [], 0
        for rid in range(1, top + 1):
            try:
                row = old.execute(f'SELECT {", ".join(cols)} FROM "{table}" WHERE rowid = ?', (rid,)).fetchone()
            except sqlite3.DatabaseError:
                bad += 1
                continue
            if row:
                good.append(row)
        return cols, good, bad

    for table in tables:
        cols, rows, bad = rows_of(table)
        if table == "events":
            continue
        new.executemany(f'INSERT INTO "{table}" ({", ".join(cols)}) VALUES ({", ".join("?" * len(cols))})', rows)
        say(f"  {table:<22} {len(rows)} rows recovered" + (f", {bad} unreadable" if bad else ""))

    # events: readable rows + every durable event file, de-duplicated, re-numbered in time order
    if "events" in tables:
        _, rows, bad = rows_of("events")
        merged: dict[tuple, tuple] = {}
        for _id, at, cid, rnd, phase, svc, msg, data in rows:
            merged[(str(at)[:19], phase, msg)] = (at, cid, rnd, phase, svc, msg, data)
        daily = re.compile(r"\d{4}-\d{2}-\d{2}\.jsonl$")
        files = list(config.REPORTS_DIR.glob("*/events.jsonl")) + [
            f for f in (config.REPORTS_DIR / "autopilot").glob("*.jsonl") if daily.match(f.name)]
        from_files = 0
        for f in files:
            for line in f.read_text(encoding="utf-8").splitlines():
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                key = (str(e.get("at"))[:19], e.get("phase"), e.get("message"))
                if key not in merged and e.get("at") and e.get("phase") and e.get("message"):
                    merged[key] = (e["at"], e.get("campaign_id"), e.get("round"), e["phase"], e.get("service"),
                                   e["message"], json.dumps(e["data"], default=str) if e.get("data") else None)
                    from_files += 1
        new.executemany("INSERT INTO events (at, campaign_id, round_num, phase, service, message, data) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)", sorted(merged.values(), key=lambda r: str(r[0])))
        say(f"  {'events':<22} {len(merged)} rows ({len(rows)} readable in the old database, "
            f"{bad} unreadable there, {from_files} restored from the durable event files)")
    # campaigns and rounds that only survive in reports/ (written after the database stopped keeping them)
    if {"campaigns", "rounds"} <= set(tables):
        known = {r[0] for r in new.execute("SELECT id FROM campaigns")}
        restored = 0
        for d in sorted(config.REPORTS_DIR.glob("c-*")):
            if d.name in known or not (d / "rounds.json").exists():
                continue
            try:
                rounds = json.loads((d / "rounds.json").read_text(encoding="utf-8"))
                card = json.loads((d / "scorecard.json").read_text(encoding="utf-8")) \
                    if (d / "scorecard.json").exists() else None
            except (OSError, json.JSONDecodeError):
                continue
            starts = sorted(t["at"] for r in rounds for t in r.get("timeline") or [])
            new.execute("INSERT INTO campaigns (id, started_at, finished_at, status, mode, plan, report) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (d.name, starts[0] if starts else "", (card or {}).get("generated_at"),
                         "COMPLETED" if card else "STOPPED", "live",
                         json.dumps([{"injector": r.get("injector"), "target": r.get("target")} for r in rounds]),
                         json.dumps(card) if card else None))
            for r in rounds:
                new.execute("INSERT OR IGNORE INTO rounds (campaign_id, round_num, injector, target, status, "
                            "updated_at, data) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (d.name, r.get("round"), r.get("injector"), r.get("target"), r.get("status"),
                             (r.get("timeline") or [{}])[-1].get("at") or "", json.dumps(r, default=str)))
            restored += 1
        if restored:
            say(f"  {'campaigns + rounds':<22} {restored} campaign(s) restored from reports/")
    new.commit()
    check = new.execute("PRAGMA integrity_check").fetchone()[0]
    new.close()
    old.close()
    if check != "ok":
        raise SystemExit(f"the rebuilt database failed its integrity check ({check}); the original is untouched")
    for f in src.parent.glob(src.name + "*"):
        if f.is_file():
            f.unlink()
    new_path.replace(src)
    say(f"database rebuilt and verified (integrity_check ok): {src}")


def cmd_down(args) -> None:
    from novasurge import infra
    if args.delete:
        say(f"deleting kind cluster '{config.CLUSTER_NAME}'")
        infra.delete_cluster()
    elif infra.cluster_exists():
        say("pausing the cluster (state kept; `up` resumes it in seconds)")
        infra.run(["docker", "stop", f"{config.CLUSTER_NAME}-control-plane"], quiet=True)


def build_dashboard() -> None:
    npm = shutil.which("npm")
    if not npm:
        raise SystemExit("Node.js/npm not found — install Node 20+ to build the dashboard (a prebuilt copy "
                         "ships in dashboard/dist)")
    src = config.REPO_ROOT / "dashboard"
    work = config.NOVASURGE_HOME / "dashboard-build"
    say(f"building the dashboard in {work} (outside the repo, so node_modules never lands in a synced folder)")
    work.mkdir(parents=True, exist_ok=True)
    for item in ("src", "public"):
        if (work / item).exists():
            shutil.rmtree(work / item)
        shutil.copytree(src / item, work / item)
    for f in ("index.html", "package.json", "package-lock.json", "vite.config.js", "tailwind.config.js",
              "postcss.config.js", "eslint.config.js"):
        if (src / f).exists():
            shutil.copy2(src / f, work / f)
    if not (work / "node_modules").exists():
        subprocess.run([npm, "ci", "--no-audit", "--no-fund"], cwd=work, check=True, shell=sys.platform == "win32")
    subprocess.run([npm, "run", "build"], cwd=work, check=True, shell=sys.platform == "win32")
    if config.DASHBOARD_DIST.exists():
        shutil.rmtree(config.DASHBOARD_DIST)
    shutil.copytree(work / "dist", config.DASHBOARD_DIST)
    say(f"dashboard built -> {config.DASHBOARD_DIST}")


def cmd_dashboard_build(_args) -> None:
    build_dashboard()


def cmd_test(args) -> None:
    import pytest
    raise SystemExit(pytest.main(["-q", str(config.REPO_ROOT / "tests"), *args.pytest_args]))


# ── parser ───────────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> None:
    _utf8_console()
    logging.basicConfig(level=os.environ.get("NOVASURGE_LOG", "WARNING"),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(prog="novasurge", description="Autonomous chaos engineering & self-healing")
    sub = p.add_subparsers(dest="command", required=True)

    def plan_args(sp):
        sp.add_argument("--rounds", type=int, help="only the first N rounds of the plan")
        sp.add_argument("--plan", help="campaign plan JSON (default config/campaign.json)")
        sp.add_argument("--injector", help="run a single round with this injector")
        sp.add_argument("--target", help="target service for --injector (default: strategy picks)")
        sp.add_argument("--fixed", action="store_true",
                        help="one round per fault type in a fixed order instead of the Chaos Planner agent")
        sp.add_argument("--no-llm", action="store_true", help="planner uses its rule-based score only")

    sp = sub.add_parser("up", help="create/update cluster and deploy")
    sp.add_argument("--rebuild", action="store_true", help="force rebuilding all images")
    sp.add_argument("--skip-models", action="store_true", help="do not train models if missing")
    sp.set_defaults(fn=cmd_up)

    sp = sub.add_parser("train", help="train detection models on live telemetry")
    sp.add_argument("--minutes", type=int, default=BASELINE_MINUTES)
    sp.add_argument("--include-recorded", action="store_true",
                    help="also train the forecaster on telemetry recorded during past campaigns")
    sp.add_argument("--no-wait", action="store_true")
    sp.set_defaults(fn=cmd_train)

    sp = sub.add_parser("serve", help="run API + dashboard")
    sp.add_argument("--port", type=int, default=config.API_PORT)
    sp.add_argument("--no-autopilot", action="store_true")
    sp.add_argument("--no-browser", action="store_true")
    sp.set_defaults(fn=cmd_serve)

    sp = sub.add_parser("campaign", help="run a chaos campaign")
    plan_args(sp)
    sp.add_argument("--dry-run", action="store_true", help="simulate (no cluster changes)")
    sp.set_defaults(fn=cmd_campaign)

    sp = sub.add_parser("demo", help="everything end-to-end")
    plan_args(sp)
    sp.add_argument("--rebuild", action="store_true")
    sp.add_argument("--no-browser", action="store_true")
    sp.add_argument("--exit-after", action="store_true", help="stop the server when the campaign ends")
    sp.set_defaults(fn=cmd_demo)

    sp = sub.add_parser("inject", help="inject one fault manually")
    sp.add_argument("injector", choices=["pod_deletion", "cpu_throttle", "network_partition",
                                         "latency_injection", "replica_reduction"])
    sp.add_argument("service")
    sp.set_defaults(fn=cmd_inject)

    sub.add_parser("revert", help="revert manual injections").set_defaults(fn=cmd_revert)
    sp = sub.add_parser("agent-key", help="store the LLM API key for the Chaos Planner agent")
    sp.add_argument("provider", choices=["groq", "gemini"])
    sp.set_defaults(fn=cmd_agent_key)
    sub.add_parser("agent-test", help="ask the Chaos Planner agent for one decision (1 API call)"
                   ).set_defaults(fn=cmd_agent_test)
    sub.add_parser("status", help="component health").set_defaults(fn=cmd_status)
    sub.add_parser("report", help="print latest campaign report").set_defaults(fn=cmd_report)
    sp = sub.add_parser("logs", help="incident logs: every injected failure, remediation and its reasoning")
    sp.add_argument("--campaign", help="print one campaign's log (a campaign id, or 'latest')")
    sp.set_defaults(fn=cmd_logs)
    sub.add_parser("ledger", help="rebuild the incident ledger workbook + CSVs (reports/ledger/)"
                   ).set_defaults(fn=cmd_ledger)
    sub.add_parser("db-repair", help="rebuild a damaged state database (stop `serve` first)"
                   ).set_defaults(fn=cmd_db_repair)
    sp = sub.add_parser("down", help="pause or delete the cluster")
    sp.add_argument("--delete", action="store_true")
    sp.set_defaults(fn=cmd_down)
    sub.add_parser("dashboard-build", help="rebuild the dashboard").set_defaults(fn=cmd_dashboard_build)
    sp = sub.add_parser("test", help="run tests")
    sp.add_argument("pytest_args", nargs="*")
    sp.set_defaults(fn=cmd_test)

    args = p.parse_args(argv)
    try:
        args.fn(args)
    except KeyboardInterrupt:
        say("interrupted")
    except Exception as exc:  # noqa: BLE001
        from novasurge.infra import InfraError
        if isinstance(exc, InfraError):
            say(f"ERROR: {exc}")
            raise SystemExit(1) from None
        raise
