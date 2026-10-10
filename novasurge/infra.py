"""
Infrastructure lifecycle: tools, kind cluster, images, manifests, readiness.

Everything is idempotent and incremental so re-runs are fast:
  * tools are downloaded once (checksum-verified) into NOVASURGE_HOME/bin
  * the cluster is created only if missing
  * images are rebuilt only when the hash of their build inputs changed, loaded
    into kind only when the cluster has not seen that hash, and only the
    workloads whose image changed are restarted
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from novasurge import config

KIND_VERSION = "v0.33.0"
KUBECTL_VERSION = "v1.34.1"
IMAGE_TAG = "local"
STATE_FILE = config.NOVASURGE_HOME / "infra-state.json"

S = config.REPO_ROOT / "services"
IMAGES: dict[str, dict] = {
    "product-service": {"dockerfile": S / "python.Dockerfile", "context": S,
                        "args": {"SERVICE": "product-service", "PORT": "8001"},
                        "inputs": [S / "python.Dockerfile", S / "requirements-python.txt", S / "pycommon",
                                   S / "product-service"],
                        "workload": ("shopfusion", "deployment/product-service")},
    "order-service": {"dockerfile": S / "python.Dockerfile", "context": S,
                      "args": {"SERVICE": "order-service", "PORT": "8002"},
                      "inputs": [S / "python.Dockerfile", S / "requirements-python.txt", S / "pycommon",
                                 S / "order-service"],
                      "workload": ("shopfusion", "deployment/order-service")},
    "payment-service": {"dockerfile": S / "python.Dockerfile", "context": S,
                        "args": {"SERVICE": "payment-service", "PORT": "8003"},
                        "inputs": [S / "python.Dockerfile", S / "requirements-python.txt", S / "pycommon",
                                   S / "payment-service"],
                        "workload": ("shopfusion", "deployment/payment-service")},
    "api-gateway": {"dockerfile": S / "node.Dockerfile", "context": S,
                    "args": {"SERVICE": "api-gateway", "PORT": "3000"},
                    "inputs": [S / "node.Dockerfile", S / "api-gateway"],
                    "workload": ("shopfusion", "deployment/api-gateway")},
    "notification-service": {"dockerfile": S / "node.Dockerfile", "context": S,
                             "args": {"SERVICE": "notification-service", "PORT": "3001"},
                             "inputs": [S / "node.Dockerfile", S / "notification-service"],
                             "workload": ("shopfusion", "deployment/notification-service")},
    "traffic-generator": {"dockerfile": S / "traffic-generator" / "Dockerfile", "context": S / "traffic-generator",
                          "args": {}, "inputs": [S / "traffic-generator"],
                          "workload": ("novasurge-system", "deployment/traffic-generator")},
    "chaos-agent": {"dockerfile": S / "chaos-agent" / "Dockerfile", "context": S / "chaos-agent",
                    "args": {}, "inputs": [S / "chaos-agent"],
                    "workload": ("novasurge-system", "daemonset/chaos-agent")},
}

ROLLOUTS = [
    ("shopfusion", "statefulset/postgres"), ("shopfusion", "deployment/redis"),
    ("shopfusion", "deployment/product-service"), ("shopfusion", "deployment/order-service"),
    ("shopfusion", "deployment/payment-service"), ("shopfusion", "deployment/notification-service"),
    ("shopfusion", "deployment/api-gateway"), ("shopfusion", "deployment/nginx-gateway"),
    ("novasurge-system", "deployment/prometheus"), ("novasurge-system", "deployment/traffic-generator"),
    ("novasurge-system", "daemonset/chaos-agent"), ("kube-system", "deployment/metrics-server"),
]


class InfraError(RuntimeError):
    pass


def say(msg: str) -> None:
    print(f"[novasurge] {msg}", flush=True)


def run(cmd: list[str], check: bool = True, capture: bool = False, timeout: float | None = None,
        quiet: bool = False) -> subprocess.CompletedProcess:
    kwargs = {"text": True, "timeout": timeout}
    if capture or quiet:
        kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    proc = subprocess.run(cmd, **kwargs)  # noqa: S603 - fixed argv, no shell
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()[-800:] if (capture or quiet) else ""
        raise InfraError(f"command failed ({proc.returncode}): {' '.join(map(str, cmd))}\n{detail}")
    return proc


def _state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except (OSError, ValueError):
        return {}


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


# ── tools ────────────────────────────────────────────────────────────────────
def _exe(name: str) -> str:
    return f"{name}.exe" if sys.platform == "win32" else name


def _platform() -> tuple[str, str]:
    osname = {"win32": "windows", "darwin": "darwin"}.get(sys.platform, "linux")
    machine = os.environ.get("PROCESSOR_ARCHITECTURE", "") if sys.platform == "win32" else os.uname().machine
    arch = "arm64" if machine.lower() in {"arm64", "aarch64"} else "amd64"
    return osname, arch


def _download(url: str, dest: Path, sha256_url: str) -> None:
    say(f"downloading {url}")
    tmp = dest.with_suffix(".part")
    urllib.request.urlretrieve(url, tmp)  # noqa: S310 - fixed https URL
    expected = urllib.request.urlopen(sha256_url).read().decode().split()[0].strip()  # noqa: S310
    actual = hashlib.sha256(tmp.read_bytes()).hexdigest()
    if actual != expected:
        tmp.unlink(missing_ok=True)
        raise InfraError(f"checksum mismatch for {url}: expected {expected}, got {actual}")
    tmp.replace(dest)
    if sys.platform != "win32":
        dest.chmod(0o755)
    say(f"verified sha256 {actual[:16]}… -> {dest}")


def kind_bin() -> str:
    found = shutil.which("kind")
    if found:
        return found
    dest = config.TOOLS_DIR / _exe("kind")
    if not dest.exists():
        config.TOOLS_DIR.mkdir(parents=True, exist_ok=True)
        osname, arch = _platform()
        base = f"https://github.com/kubernetes-sigs/kind/releases/download/{KIND_VERSION}/kind-{osname}-{arch}"
        _download(base, dest, base + ".sha256sum")
    return str(dest)


def kubectl_bin() -> str:
    found = shutil.which("kubectl")
    if found:
        return found
    dest = config.TOOLS_DIR / _exe("kubectl")
    if not dest.exists():
        config.TOOLS_DIR.mkdir(parents=True, exist_ok=True)
        osname, arch = _platform()
        base = f"https://dl.k8s.io/release/{KUBECTL_VERSION}/bin/{osname}/{arch}/{_exe('kubectl')}"
        _download(base, dest, base + ".sha256")
    return str(dest)


def kubectl(*args: str, check: bool = True, capture: bool = True, timeout: float | None = 300) -> str:
    proc = run([kubectl_bin(), "--context", config.KUBE_CONTEXT, *args], check=check, capture=capture,
               timeout=timeout)
    return proc.stdout or ""


def docker_ok() -> bool:
    try:
        return run(["docker", "info", "--format", "{{.ServerVersion}}"], check=False, quiet=True,
                   timeout=30).returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def require_docker() -> None:
    if shutil.which("docker") is None:
        raise InfraError("Docker is not installed. Install Docker Desktop: https://www.docker.com/products/docker-desktop/")
    if not docker_ok():
        raise InfraError("Docker is installed but not running. Start Docker Desktop, wait until it says "
                         "'Engine running', then re-run this command.")


# ── cluster ──────────────────────────────────────────────────────────────────
def cluster_exists() -> bool:
    out = run([kind_bin(), "get", "clusters"], check=False, capture=True).stdout or ""
    return config.CLUSTER_NAME in out.split()


def cluster_id() -> str:
    """Identity of the current cluster incarnation (changes when it is recreated)."""
    proc = run(["docker", "inspect", "-f", "{{.Created}}", f"{config.CLUSTER_NAME}-control-plane"],
               check=False, capture=True)
    return (proc.stdout or "").strip()


def ensure_cluster() -> bool:
    """Returns True if a new cluster was created."""
    if cluster_exists():
        say(f"kind cluster '{config.CLUSTER_NAME}' already running")
        if not cluster_id():
            say("cluster node container is stopped; starting it")
            run(["docker", "start", f"{config.CLUSTER_NAME}-control-plane"])
            time.sleep(10)
        return False
    say(f"creating kind cluster '{config.CLUSTER_NAME}' (first run takes ~1-2 minutes)")
    run([kind_bin(), "create", "cluster", "--config", str(config.K8S_DIR / "kind-config.yaml"), "--wait", "180s"])
    return True


def delete_cluster() -> None:
    if cluster_exists():
        run([kind_bin(), "delete", "cluster", "--name", config.CLUSTER_NAME])


# ── images ───────────────────────────────────────────────────────────────────
def _hash_inputs(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for root in paths:
        files = [root] if root.is_file() else sorted(
            p for p in root.rglob("*") if p.is_file()
            and not any(part in {"__pycache__", "node_modules", ".pytest_cache"} for part in p.parts))
        for f in files:
            h.update(str(f.relative_to(config.REPO_ROOT)).replace("\\", "/").encode())
            h.update(f.read_bytes())
    return h.hexdigest()[:16]


def _image_exists(ref: str) -> bool:
    return run(["docker", "image", "inspect", ref], check=False, quiet=True).returncode == 0


def build_and_load_images(force: bool = False) -> list[str]:
    """Build changed images and load them into kind. Returns names whose image changed in the cluster."""
    state = _state()
    built = state.setdefault("built", {})
    cid = cluster_id()
    loaded = state.setdefault("loaded", {}).setdefault(cid, {})
    for stale in [k for k in state["loaded"] if k != cid]:
        state["loaded"].pop(stale)
    to_load, changed = [], []
    for name, spec in IMAGES.items():
        ref = f"novasurge/{name}:{IMAGE_TAG}"
        digest = _hash_inputs(spec["inputs"])
        if force or built.get(name) != digest or not _image_exists(ref):
            say(f"building image {ref}")
            cmd = ["docker", "build", "-q", "-f", str(spec["dockerfile"]), "-t", ref]
            for k, v in spec["args"].items():
                cmd += ["--build-arg", f"{k}={v}"]
            run(cmd + [str(spec["context"])], quiet=True)
            built[name] = digest
            _save_state(state)
        if loaded.get(name) != digest:
            to_load.append((name, ref, digest))
    if to_load:
        say(f"loading {len(to_load)} image(s) into the cluster: {', '.join(n for n, _, _ in to_load)}")
        run([kind_bin(), "load", "docker-image", "--name", config.CLUSTER_NAME, *[r for _, r, _ in to_load]],
            quiet=True)
        for name, _, digest in to_load:
            if name in loaded:
                changed.append(name)
            loaded[name] = digest
        _save_state(state)
    else:
        say("all images up to date in the cluster")
    return changed


# ── deploy ───────────────────────────────────────────────────────────────────
def ensure_db_secret() -> None:
    exists = run([kubectl_bin(), "--context", config.KUBE_CONTEXT, "-n", "shopfusion", "get", "secret",
                  "shopfusion-db"], check=False, quiet=True).returncode == 0
    if not exists:
        say("generating a random database password (Secret shopfusion/shopfusion-db)")
        kubectl("-n", "shopfusion", "create", "secret", "generic", "shopfusion-db",
                f"--from-literal=password={secrets.token_urlsafe(24)}")


def deploy(changed_images: list[str]) -> None:
    say("applying Kubernetes manifests")
    kubectl("apply", "-f", str(config.K8S_DIR / "base" / "00-namespaces.yaml"))
    ensure_db_secret()
    kubectl("apply", "-f", str(config.K8S_DIR / "base"))
    for name in changed_images:
        ns, workload = IMAGES[name]["workload"]
        say(f"restarting {workload} (new image)")
        kubectl("-n", ns, "rollout", "restart", workload, check=False)


def wait_rollouts(timeout: int = 300) -> None:
    say("waiting for workloads to become ready")
    deadline = time.monotonic() + timeout
    for ns, workload in ROLLOUTS:
        left = max(int(deadline - time.monotonic()), 10)
        proc = run([kubectl_bin(), "--context", config.KUBE_CONTEXT, "-n", ns, "rollout", "status", workload,
                    f"--timeout={left}s"], check=False, capture=True, timeout=left + 30)
        if proc.returncode != 0:
            raise InfraError(f"{workload} did not become ready: {(proc.stderr or proc.stdout).strip()[-400:]}")


def wait_http(url: str, timeout: float = 180, what: str = "") -> None:
    import httpx
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            r = httpx.get(url, timeout=3)
            if r.status_code < 500:
                return
            last = f"HTTP {r.status_code}"
        except httpx.HTTPError as exc:
            last = type(exc).__name__
        time.sleep(2)
    raise InfraError(f"{what or url} not reachable after {timeout:.0f}s ({last})")


def up(force_build: bool = False) -> None:
    require_docker()
    ensure_cluster()
    changed = build_and_load_images(force=force_build)
    deploy(changed)
    wait_rollouts()
    wait_http(f"{config.PROMETHEUS_URL}/-/ready", what="Prometheus")
    wait_http(f"{config.GATEWAY_URL}/products/1", what="ShopFusion (nginx -> gateway -> product-service)")
    say(f"ShopFusion is up: {config.GATEWAY_URL}   Prometheus: {config.PROMETHEUS_URL}")


def traffic_minutes_available(max_minutes: int = 60) -> float:
    """Minutes of continuous synthetic traffic currently stored in Prometheus."""
    import httpx
    end = time.time()
    start = end - max_minutes * 60
    try:
        r = httpx.get(f"{config.PROMETHEUS_URL}/api/v1/query_range", timeout=10, params={
            "query": "sum(rate(loadgen_requests_total[30s])) > 1", "start": start, "end": end, "step": 15})
        values = r.json()["data"]["result"]
    except (httpx.HTTPError, KeyError, ValueError):
        return 0.0
    if not values:
        return 0.0
    ts = [float(t) for t, _ in values[0]["values"]]
    run_start = ts[-1]
    for prev, cur in zip(reversed(ts[:-1]), reversed(ts[1:])):
        if cur - prev > 30:
            break
        run_start = prev
    return (end - run_start) / 60.0 if end - ts[-1] < 60 else 0.0
