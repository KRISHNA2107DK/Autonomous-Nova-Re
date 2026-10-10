"""
cache_flush — drop the product cache (`products:*`) in Redis by exec-ing
redis-cli in the Redis pod (the cluster DNS name is not resolvable from the
host, which is why the original direct connection could never work). Pub/sub
channels and any other keys are left alone; FLUSHDB would be overkill.
"""

from __future__ import annotations

import time

from novasurge.remediators import RemediationContext, RemediationResult, now_iso

NAME = "cache_flush"
PATTERN = "products:*"
SCRIPT = ("n=0; for k in $(redis-cli --scan --pattern '" + PATTERN + "'); do "
          "redis-cli del \"$k\" >/dev/null; n=$((n+1)); done; echo $n")


async def remediate(service: str, ctx: RemediationContext) -> RemediationResult:
    started, t0 = now_iso(), time.monotonic()
    redis_pods = [p for p in ctx.cluster.list_pods("redis") if p.ready]
    if not redis_pods:
        return RemediationResult(NAME, service, False, "no Ready redis pod", started, now_iso(),
                                 time.monotonic() - t0)
    res = ctx.cluster.exec(redis_pods[0].name, ["sh", "-c", SCRIPT], timeout=30)
    flushed = int(res.stdout.strip().splitlines()[-1]) if res.ok and res.stdout.strip() else 0
    summary = (f"evicted {flushed} '{PATTERN}' keys from Redis" if res.ok
               else f"redis-cli failed: {res.stderr.strip()[:160]}")
    return RemediationResult(NAME, service, res.ok, summary, started, now_iso(), time.monotonic() - t0,
                             {"keys_flushed": flushed, "redis_pod": redis_pods[0].name, "pattern": PATTERN})
