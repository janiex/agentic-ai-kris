#!/usr/bin/env python3
"""Cross-platform launcher / lifecycle manager for the Chainlit app.

Works identically on Linux, macOS, and Windows (pure standard library):

    python run.py [start] [--watch]   start the chat UI (foreground)
    python run.py stop                stop a server running on $PORT
    python run.py status              report whether the server is up
    python run.py restart [--watch]   stop, then start

The port is taken from the PORT environment variable (default 8000):

    PORT=8600 python run.py start

`start` is the default when no command is given, so a bare `python run.py`
behaves as before. On Unix, `./run.sh <command>` forwards to this script.
"""
from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PIDFILE = ROOT / ".run.pid"          # records "<pid> <port>" for the running server


# ── helpers ──────────────────────────────────────────────────────────────────
def _port() -> int:
    try:
        return int(os.environ.get("PORT", "8000"))
    except ValueError:
        return 8000


def _is_up(port: int, host: str = "127.0.0.1") -> bool:
    """True if something is accepting TCP connections on the port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def _pids_on_port(port: int) -> list[int]:
    """Best-effort discovery of PIDs listening on `port` (lsof / netstat)."""
    pids: set[int] = set()
    try:
        if sys.platform.startswith("win"):
            out = subprocess.run(
                ["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True
            ).stdout
            for line in out.splitlines():
                parts = line.split()
                if (
                    len(parts) >= 5
                    and parts[0].upper() == "TCP"
                    and f":{port}" in parts[1]
                    and parts[-2].upper() == "LISTENING"
                    and parts[-1].isdigit()
                ):
                    pids.add(int(parts[-1]))
        else:
            out = subprocess.run(
                ["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"],
                capture_output=True, text=True,
            ).stdout
            for tok in out.split():
                if tok.strip().isdigit():
                    pids.add(int(tok.strip()))
    except FileNotFoundError:
        pass  # no lsof/netstat — fall back to the pidfile
    return sorted(pids)


def _pidfile_pid() -> int | None:
    try:
        pid, port = PIDFILE.read_text().split()
        if int(port) == _port():
            return int(pid)
    except (OSError, ValueError):
        pass
    return None


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _terminate(pid: int, timeout: float = 6.0) -> bool:
    """Graceful stop: SIGTERM then SIGKILL (taskkill /T /F on Windows)."""
    if sys.platform.startswith("win"):
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
        return True
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return True  # already gone
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not _alive(pid):
            return True
        time.sleep(0.2)
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass
    return not _alive(pid)


# ── commands ─────────────────────────────────────────────────────────────────
def cmd_start(extra: list[str]) -> int:
    port = _port()
    if _is_up(port):
        print(
            f"⚠️  Port {port} is already in use. Run 'python run.py stop' first, "
            f"or start with a different PORT."
        )
        return 1
    cmd = [sys.executable, "-m", "chainlit", "run", str(ROOT / "app.py"),
           "--port", str(port)]
    if "--watch" in extra:
        cmd.append("-w")
    print(f"▶ Starting agentic-ai-kris on http://localhost:{port}  (Ctrl+C to stop)")
    proc = subprocess.Popen(cmd)
    PIDFILE.write_text(f"{proc.pid} {port}")
    try:
        return proc.wait()
    except KeyboardInterrupt:
        _terminate(proc.pid)
        return 0
    finally:
        PIDFILE.unlink(missing_ok=True)


def cmd_stop() -> int:
    port = _port()
    targets = set(_pids_on_port(port))
    pf = _pidfile_pid()
    if pf and _alive(pf):
        targets.add(pf)

    if not targets:
        if _is_up(port):
            print(
                f"⚠️  Port {port} is in use but the PID couldn't be determined "
                f"(no lsof/netstat). Stop the process manually."
            )
            return 1
        print(f"○ Nothing to stop — no server on port {port}.")
        PIDFILE.unlink(missing_ok=True)
        return 0

    ok = True
    for pid in sorted(targets):
        done = _terminate(pid)
        print(("✓ stopped" if done else "✗ could not stop") + f" PID {pid}")
        ok = ok and done
    PIDFILE.unlink(missing_ok=True)

    time.sleep(0.3)
    if _is_up(port):
        print(f"⚠️  Port {port} still in use after stop.")
        return 1
    print(f"■ agentic-ai-kris stopped (port {port}).")
    return 0 if ok else 1


def cmd_status() -> int:
    port = _port()
    if _is_up(port):
        pids = _pids_on_port(port)
        if not pids and _pidfile_pid():
            pids = [_pidfile_pid()]  # type: ignore[list-item]
        pid_s = ", ".join(str(p) for p in pids if p) or "unknown"
        print(f"● running — http://localhost:{port}  (PID {pid_s})")
        return 0
    print(f"○ stopped — nothing listening on port {port}")
    return 1


def cmd_restart(extra: list[str]) -> int:
    cmd_stop()
    return cmd_start(extra)


def main() -> int:
    args = sys.argv[1:]
    command = "start"
    if args and not args[0].startswith("-"):
        command = args.pop(0)

    if command in ("start", "up"):
        return cmd_start(args)
    if command in ("stop", "down"):
        return cmd_stop()
    if command == "status":
        return cmd_status()
    if command == "restart":
        return cmd_restart(args)

    print(f"Unknown command: {command!r}. Use: start | stop | status | restart.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
