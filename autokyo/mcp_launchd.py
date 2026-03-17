from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import plistlib
import platform
import re
import subprocess
import time
from typing import Sequence
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


DEFAULT_HTTP_HOST = "127.0.0.1"
DEFAULT_HTTP_PORT = 8765
DEFAULT_HTTP_WAIT_SECONDS = 10.0
DEFAULT_HTTP_POLL_INTERVAL_SECONDS = 0.25
LAUNCH_AGENT_LABEL_PREFIX = "io.github.plain127.autokyo.mcp"


@dataclass(frozen=True)
class LaunchAgentSpec:
    label: str
    plist_path: Path
    stdout_path: Path
    stderr_path: Path
    working_directory: Path
    command: tuple[str, ...]
    endpoint_url: str
    healthcheck_url: str


def build_launch_agent_spec(
    *,
    server_name: str,
    command: Sequence[str],
    host: str = DEFAULT_HTTP_HOST,
    port: int = DEFAULT_HTTP_PORT,
    working_directory: str | Path | None = None,
) -> LaunchAgentSpec:
    safe_name = _sanitize_launchd_component(server_name)
    label = f"{LAUNCH_AGENT_LABEL_PREFIX}.{safe_name}"
    launch_agents_dir = Path.home() / "Library" / "LaunchAgents"
    logs_dir = Path.home() / "Library" / "Logs" / "AutoKyo"
    working_dir = Path(working_directory).expanduser().resolve() if working_directory else Path.home()
    endpoint_url = f"http://{host}:{port}/mcp"
    healthcheck_url = f"http://{host}:{port}/healthz"
    return LaunchAgentSpec(
        label=label,
        plist_path=launch_agents_dir / f"{label}.plist",
        stdout_path=logs_dir / f"{label}.out.log",
        stderr_path=logs_dir / f"{label}.err.log",
        working_directory=working_dir,
        command=tuple(str(part) for part in command),
        endpoint_url=endpoint_url,
        healthcheck_url=healthcheck_url,
    )


def install_or_update_launch_agent(spec: LaunchAgentSpec) -> None:
    _require_macos()
    spec.plist_path.parent.mkdir(parents=True, exist_ok=True)
    spec.stdout_path.parent.mkdir(parents=True, exist_ok=True)
    spec.stderr_path.parent.mkdir(parents=True, exist_ok=True)
    spec.plist_path.write_bytes(_render_launch_agent_plist(spec))

    domain = _launchctl_domain()
    _run_launchctl(["launchctl", "bootout", f"{domain}/{spec.label}"], check=False)
    _run_launchctl(["launchctl", "bootout", domain, str(spec.plist_path)], check=False)
    _run_launchctl(["launchctl", "bootstrap", domain, str(spec.plist_path)], check=True)
    _run_launchctl(["launchctl", "enable", f"{domain}/{spec.label}"], check=False)
    _run_launchctl(["launchctl", "kickstart", "-k", f"{domain}/{spec.label}"], check=True)


def wait_for_http_health(
    url: str,
    *,
    timeout_seconds: float = DEFAULT_HTTP_WAIT_SECONDS,
    poll_interval_seconds: float = DEFAULT_HTTP_POLL_INTERVAL_SECONDS,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error = "no response received"

    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError(
                f"Timed out waiting for AutoKyo MCP HTTP server at {url}. Last error: {last_error}"
            )

        try:
            with urlopen(url, timeout=min(2.0, max(0.1, remaining))) as response:
                body = response.read().decode("utf-8", "replace").strip()
            if 200 <= response.status < 300 and body == "ok":
                return
            last_error = f"unexpected health response: status={response.status} body={body!r}"
        except HTTPError as exc:
            last_error = f"HTTP {exc.code}"
        except URLError as exc:
            last_error = str(exc.reason)
        except OSError as exc:
            last_error = str(exc)

        time.sleep(min(poll_interval_seconds, max(0.05, remaining)))


def _render_launch_agent_plist(spec: LaunchAgentSpec) -> bytes:
    payload = {
        "Label": spec.label,
        "ProgramArguments": list(spec.command),
        "WorkingDirectory": str(spec.working_directory),
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(spec.stdout_path),
        "StandardErrorPath": str(spec.stderr_path),
        "ProcessType": "Background",
    }
    return plistlib.dumps(payload, fmt=plistlib.FMT_XML, sort_keys=False)


def _run_launchctl(command: list[str], *, check: bool) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    if check and completed.returncode != 0:
        stderr = completed.stderr.strip()
        stdout = completed.stdout.strip()
        detail = stderr or stdout or "unknown launchctl error"
        raise RuntimeError(f"{' '.join(command)} failed: {detail}")
    return completed


def _launchctl_domain() -> str:
    return f"gui/{os.getuid()}"


def _require_macos() -> None:
    if platform.system() != "Darwin":
        raise RuntimeError("HTTP auto-start via launchd is only supported on macOS")


def _sanitize_launchd_component(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9.-]+", "-", value).strip("-.")
    return sanitized or "autokyo"
