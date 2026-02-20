"""LaunchAgent service management for claude-ai-skills.

Provides discovery, control, and log access for the project's
LaunchAgent-managed services (proxy, mcp, tunnel).
"""

from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path

LABEL_PREFIX = "com.joshuashew.claude-ai-skills"

SERVICES = {
    "proxy": {
        "label": f"{LABEL_PREFIX}.proxy",
        "description": "Flask credential proxy server",
    },
    "mcp": {
        "label": f"{LABEL_PREFIX}.mcp",
        "description": "MCP server (Streamable HTTP)",
    },
    "tunnel": {
        "label": f"{LABEL_PREFIX}.tunnel",
        "description": "Cloudflare Tunnel connector",
    },
}

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _expand(path_str: str) -> Path:
    return Path(path_str).expanduser()


def _tail(path: Path, n: int) -> list[str]:
    """Read the last n lines of a file without loading it all into memory."""
    buf_size = 8192
    lines: list[str] = []
    with path.open("rb") as f:
        f.seek(0, 2)  # seek to end
        remaining = f.tell()
        while remaining > 0 and len(lines) <= n:
            read_size = min(buf_size, remaining)
            remaining -= read_size
            f.seek(remaining)
            block = f.read(read_size).decode(errors="replace")
            lines = block.splitlines() + lines
        # If the file started with a partial first line from our block reads,
        # the split already handled it correctly.
    return lines[-n:] if len(lines) > n else lines


def label_to_name(label: str) -> str:
    """Extract short name from label ('com.joshuashew.claude-ai-skills.proxy' -> 'proxy')."""
    prefix = LABEL_PREFIX + "."
    if label.startswith(prefix):
        return label[len(prefix) :]
    return label


def name_to_label(name: str) -> str:
    if name in SERVICES:
        return SERVICES[name]["label"]
    return f"{LABEL_PREFIX}.{name}"


def log_paths_for_label(label: str) -> tuple[Path, Path]:
    """Return (stdout_log, stderr_log) paths for a label."""
    return (
        _expand(f"~/Library/Logs/{label}.log"),
        _expand(f"~/Library/Logs/{label}.error.log"),
    )


def plist_path_for_label(label: str) -> Path:
    return _expand(f"~/Library/LaunchAgents/{label}.plist")


def discover_services() -> dict[str, dict]:
    """Discover all claude-ai-skills services via launchctl + plist scan.

    Returns dict mapping short name to info dict with keys:
    label, description, loaded, running, pid, stdout_log, stderr_log
    """
    found: dict[str, dict] = {}

    # Scan launchctl list for loaded services
    try:
        result = subprocess.run(
            ["launchctl", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        for row in result.stdout.splitlines():
            parts = row.split("\t")
            if len(parts) >= 3:
                label = parts[2].strip()
                if label.startswith(LABEL_PREFIX + "."):
                    name = label_to_name(label)
                    pid = parts[0].strip()
                    stdout_log, stderr_log = log_paths_for_label(label)
                    found[name] = {
                        "label": label,
                        "description": SERVICES.get(name, {}).get("description", ""),
                        "loaded": True,
                        "running": pid != "-",
                        "pid": pid if pid != "-" else None,
                        "stdout_log": str(stdout_log),
                        "stderr_log": str(stderr_log),
                    }
    except (subprocess.TimeoutExpired, OSError):
        pass

    # Scan plist files for installed but unloaded services
    agents_dir = _expand("~/Library/LaunchAgents")
    if agents_dir.is_dir():
        for plist_file in agents_dir.glob(f"{LABEL_PREFIX}.*.plist"):
            label = plist_file.stem
            name = label_to_name(label)
            if name not in found:
                stdout_log, stderr_log = log_paths_for_label(label)
                found[name] = {
                    "label": label,
                    "description": SERVICES.get(name, {}).get("description", ""),
                    "loaded": False,
                    "running": False,
                    "pid": None,
                    "stdout_log": str(stdout_log),
                    "stderr_log": str(stderr_log),
                }

    return found


def get_service_status_text(name: str, info: dict) -> str:
    """Format a status block for a single service."""
    label = info["label"]
    desc = info.get("description", "")
    header = f"## {name}" + (f" — {desc}" if desc else "")
    lines = [header, f"Label: {label}"]

    if info.get("running"):
        lines.append(f"State: RUNNING (PID {info.get('pid', '?')})")
    elif info.get("loaded"):
        lines.append("State: NOT RUNNING (loaded but stopped)")
    else:
        lines.append("State: NOT LOADED (plist installed but not loaded)")

    # Recent stderr (last 10 lines)
    stderr_path = Path(info["stderr_log"])
    try:
        stderr_lines = _tail(stderr_path, 10)
        if stderr_lines:
            lines.append(f"\nRecent stderr ({stderr_path.name}):")
            lines.extend(f"  {strip_ansi(line)}" for line in stderr_lines)
    except OSError:
        pass

    # Recent stdout (last 5 lines)
    stdout_path = Path(info["stdout_log"])
    try:
        stdout_lines = _tail(stdout_path, 5)
        if stdout_lines:
            lines.append(f"\nRecent stdout ({stdout_path.name}):")
            lines.extend(f"  {line}" for line in stdout_lines)
    except OSError:
        pass

    return "\n".join(lines)


def run_launchctl(action: str, label: str) -> str:
    """Run a launchctl start/stop command. Returns status message."""
    try:
        result = subprocess.run(
            ["launchctl", action, label],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            return f"ERROR: launchctl {action} {label} failed (exit {result.returncode}): {stderr}"
        past = "Stopped" if action == "stop" else "Started"
        return f"{past} {label}."
    except subprocess.TimeoutExpired:
        return f"ERROR: launchctl {action} timed out for {label}."
    except OSError as e:
        return f"ERROR: Failed to run launchctl {action}: {e}"


def restart_service(label: str) -> str:
    """Stop then start a service."""
    stop_msg = run_launchctl("stop", label)
    time.sleep(1)
    start_msg = run_launchctl("start", label)
    return f"{stop_msg}\n{start_msg}"


def get_logs(label: str, lines: int = 20) -> dict[str, str]:
    """Read recent log lines for a service.

    Returns dict with 'stdout' and 'stderr' keys.
    """
    stdout_path, stderr_path = log_paths_for_label(label)
    result = {}

    for key, path in [("stderr", stderr_path), ("stdout", stdout_path)]:
        try:
            recent = _tail(path, lines)
            if key == "stderr":
                recent = [strip_ansi(line) for line in recent]
            result[key] = "\n".join(recent)
        except OSError:
            result[key] = f"(no log file at {path})"

    return result


def run_setup_script(project_dir: Path) -> dict:
    """Run the setup-launchagents.sh script.

    Returns dict with 'success' bool, 'stdout', and 'stderr'.
    """
    script = project_dir / "scripts" / "setup-launchagents.sh"
    if not script.exists():
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Setup script not found at {script}",
        }

    try:
        result = subprocess.run(
            ["bash", str(script)],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(project_dir),
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": "ERROR: Setup script timed out after 60 seconds.",
        }
    except OSError as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"ERROR: Failed to run setup script: {e}",
        }
