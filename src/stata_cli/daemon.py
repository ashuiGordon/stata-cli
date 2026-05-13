"""Stata CLI daemon — keeps PyStata alive across invocations.

Server: long-running background process with a StataEngine.
Client: thin JSON-over-socket connector used by CLI commands.
"""

import json
import os
import platform
import selectors
import signal
import socket
import struct
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

_STATE_DIR = os.path.join(os.path.expanduser("~"), ".stata-cli")
_PID_FILE = os.path.join(_STATE_DIR, "daemon.pid")
_SOCK_FILE = os.path.join(_STATE_DIR, "daemon.sock")
_IS_WINDOWS = platform.system() == "Windows"
_DEFAULT_PORT = 4718
_IDLE_TIMEOUT = 3600  # 1 hour


# ── wire protocol: 4-byte big-endian length prefix + JSON ────────────────

def _send_msg(sock: socket.socket, obj: Any) -> None:
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    sock.sendall(struct.pack(">I", len(data)) + data)


def _recv_msg(sock: socket.socket) -> Optional[Dict]:
    header = b""
    while len(header) < 4:
        chunk = sock.recv(4 - len(header))
        if not chunk:
            return None
        header += chunk
    length = struct.unpack(">I", header)[0]
    buf = b""
    while len(buf) < length:
        chunk = sock.recv(min(length - len(buf), 65536))
        if not chunk:
            return None
        buf += chunk
    return json.loads(buf.decode("utf-8"))


# ═══════════════════════════════════════════════════════════════════════════
# SERVER
# ═══════════════════════════════════════════════════════════════════════════

class DaemonServer:
    """Single-threaded daemon that wraps a StataEngine."""

    def __init__(self, stata_path: str, edition: str = "mp",
                 graphs_dir: Optional[str] = None, idle_timeout: float = _IDLE_TIMEOUT):
        self.stata_path = stata_path
        self.edition = edition
        self.graphs_dir = graphs_dir
        self.idle_timeout = idle_timeout
        self._engine = None
        self._running = False
        self._start_time = time.time()
        self._last_activity = time.time()

    def serve(self) -> None:
        """Start listening and processing commands."""
        from .engine import StataEngine

        self._engine = StataEngine(self.stata_path, self.edition, graphs_dir=self.graphs_dir)
        self._engine._ensure_initialized()

        os.makedirs(_STATE_DIR, exist_ok=True)

        sock = self._create_listener()
        self._write_pid()
        self._running = True

        signal.signal(signal.SIGTERM, lambda *_: self._shutdown())
        signal.signal(signal.SIGINT, lambda *_: self._shutdown())

        sel = selectors.DefaultSelector()
        sel.register(sock, selectors.EVENT_READ)

        try:
            while self._running:
                events = sel.select(timeout=30.0)
                if not events:
                    if self.idle_timeout > 0 and (time.time() - self._last_activity) > self.idle_timeout:
                        break
                    continue
                for key, _ in events:
                    conn, _ = sock.accept()
                    try:
                        self._handle_connection(conn)
                    except Exception:
                        try:
                            _send_msg(conn, {"status": "error", "error": "Internal daemon error"})
                        except Exception:
                            pass
                    finally:
                        conn.close()
        finally:
            sel.close()
            sock.close()
            self._cleanup()

    def _create_listener(self) -> socket.socket:
        if _IS_WINDOWS:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", _DEFAULT_PORT))
        else:
            if os.path.exists(_SOCK_FILE):
                os.unlink(_SOCK_FILE)
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.bind(_SOCK_FILE)
        sock.listen(4)
        sock.setblocking(False)
        return sock

    def _handle_connection(self, conn: socket.socket) -> None:
        conn.settimeout(600.0)
        msg = _recv_msg(conn)
        if not msg:
            return

        self._last_activity = time.time()
        cmd_type = msg.get("type", "")
        payload = msg.get("payload", {})

        if cmd_type == "execute":
            result = self._engine.run(
                payload.get("code", ""),
                timeout=payload.get("timeout", 600.0),
            )
            _send_msg(conn, self._result_to_dict(result))

        elif cmd_type == "execute_file":
            result = self._engine.run_file(
                payload.get("path", ""),
                timeout=payload.get("timeout", 600.0),
            )
            _send_msg(conn, self._result_to_dict(result))

        elif cmd_type == "get_data":
            data = self._engine.get_data(
                if_condition=payload.get("if_condition"),
                max_rows=payload.get("max_rows", 10000),
            )
            _send_msg(conn, data)

        elif cmd_type == "help":
            result = self._engine.help(payload.get("topic", ""))
            _send_msg(conn, self._result_to_dict(result))

        elif cmd_type == "stop":
            ok = self._engine.stop()
            _send_msg(conn, {"status": "ok" if ok else "no_op"})

        elif cmd_type == "get_return":
            data = self._engine.get_return(rtype=payload.get("rtype", "r"))
            _send_msg(conn, data)

        elif cmd_type == "get_vars":
            data = self._engine.get_vars()
            _send_msg(conn, data)

        elif cmd_type == "get_matrix":
            data = self._engine.get_matrix(payload.get("name", ""))
            _send_msg(conn, data)

        elif cmd_type == "get_labels":
            data = self._engine.get_labels(
                name=payload.get("name"),
                var=payload.get("var"),
            )
            _send_msg(conn, data)

        elif cmd_type == "get_macro":
            data = self._engine.get_macro(payload.get("name", ""))
            _send_msg(conn, data)

        elif cmd_type == "set_macro":
            data = self._engine.set_macro(payload.get("name", ""), payload.get("value", ""))
            _send_msg(conn, data)

        elif cmd_type == "get_frames":
            data = self._engine.get_frames()
            _send_msg(conn, data)

        elif cmd_type == "status":
            _send_msg(conn, {
                "status": "ok",
                "pid": os.getpid(),
                "uptime": time.time() - self._start_time,
                "idle": time.time() - self._last_activity,
                "stata_path": self.stata_path,
                "edition": self.edition,
            })

        elif cmd_type == "shutdown":
            _send_msg(conn, {"status": "ok"})
            self._running = False

        else:
            _send_msg(conn, {"status": "error", "error": f"Unknown command: {cmd_type}"})

    @staticmethod
    def _result_to_dict(result) -> Dict[str, Any]:
        from dataclasses import asdict
        return asdict(result)

    def _write_pid(self) -> None:
        addr = f"127.0.0.1:{_DEFAULT_PORT}" if _IS_WINDOWS else _SOCK_FILE
        with open(_PID_FILE, "w") as fh:
            json.dump({"pid": os.getpid(), "address": addr, "started": time.time()}, fh)

    def _cleanup(self) -> None:
        try:
            os.unlink(_PID_FILE)
        except OSError:
            pass
        if not _IS_WINDOWS:
            try:
                os.unlink(_SOCK_FILE)
            except OSError:
                pass

    def _shutdown(self) -> None:
        self._running = False


def run_daemon_server(stata_path: str, edition: str = "mp",
                      graphs_dir: Optional[str] = None, idle_timeout: float = _IDLE_TIMEOUT) -> None:
    """Entry point called in the daemon subprocess."""
    server = DaemonServer(stata_path, edition, graphs_dir=graphs_dir, idle_timeout=idle_timeout)
    server.serve()


# ═══════════════════════════════════════════════════════════════════════════
# CLIENT
# ═══════════════════════════════════════════════════════════════════════════

class DaemonClient:
    """Connects to a running daemon over the Unix socket / TCP port."""

    def __init__(self) -> None:
        self._sock: Optional[socket.socket] = None

    def is_running(self) -> bool:
        if not os.path.isfile(_PID_FILE):
            return False
        try:
            with open(_PID_FILE) as fh:
                info = json.load(fh)
            pid = info["pid"]
            os.kill(pid, 0)
            return True
        except (OSError, KeyError, json.JSONDecodeError):
            return False

    def connect(self) -> bool:
        try:
            info = self._read_pid()
            if not info:
                return False
            if _IS_WINDOWS:
                parts = info["address"].split(":")
                self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._sock.connect((parts[0], int(parts[1])))
            else:
                self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self._sock.connect(info["address"])
            self._sock.settimeout(600.0)
            return True
        except (OSError, KeyError):
            self._sock = None
            return False

    def send(self, cmd_type: str, payload: Optional[Dict] = None) -> Dict[str, Any]:
        if self._sock is None:
            raise RuntimeError("Not connected")
        _send_msg(self._sock, {"type": cmd_type, "payload": payload or {}})
        resp = _recv_msg(self._sock)
        return resp or {"status": "error", "error": "No response from daemon"}

    def close(self) -> None:
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def _read_pid(self) -> Optional[Dict]:
        if not os.path.isfile(_PID_FILE):
            return None
        try:
            with open(_PID_FILE) as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError):
            return None


def start_daemon(stata_path: str, edition: str = "mp",
                 graphs_dir: Optional[str] = None, idle_timeout: float = _IDLE_TIMEOUT) -> bool:
    """Launch daemon as a detached background process. Returns True on success."""
    client = DaemonClient()
    if client.is_running():
        return True

    os.makedirs(_STATE_DIR, exist_ok=True)
    log_file = os.path.join(_STATE_DIR, "daemon.log")

    args = [
        sys.executable, "-m", "stata_cli.daemon",
        "--stata-path", stata_path,
        "--edition", edition,
        "--idle-timeout", str(int(idle_timeout)),
    ]
    if graphs_dir:
        args += ["--graphs-dir", graphs_dir]

    with open(log_file, "a") as log:
        if _IS_WINDOWS:
            subprocess.Popen(
                args, stdout=log, stderr=log,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
            )
        else:
            subprocess.Popen(
                args, stdout=log, stderr=log,
                start_new_session=True,
            )

    for _ in range(60):
        time.sleep(0.5)
        if client.is_running():
            return True
    return False


def stop_daemon() -> bool:
    """Ask the daemon to shut down gracefully."""
    client = DaemonClient()
    if not client.is_running():
        return True
    if client.connect():
        try:
            client.send("shutdown")
        except Exception:
            pass
        client.close()
    for _ in range(20):
        time.sleep(0.25)
        if not client.is_running():
            return True
    # Force kill
    try:
        with open(_PID_FILE) as fh:
            pid = json.load(fh)["pid"]
        os.kill(pid, signal.SIGKILL if not _IS_WINDOWS else signal.SIGTERM)
    except Exception:
        pass
    return True


def daemon_status() -> Optional[Dict[str, Any]]:
    """Query the running daemon's status. Returns None if not running."""
    client = DaemonClient()
    if not client.is_running():
        return None
    if not client.connect():
        return None
    try:
        return client.send("status")
    except Exception:
        return None
    finally:
        client.close()


# ── Allow running as ``python -m stata_cli.daemon`` ──────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--stata-path", required=True)
    parser.add_argument("--edition", default="mp")
    parser.add_argument("--graphs-dir", default=None)
    parser.add_argument("--idle-timeout", type=float, default=_IDLE_TIMEOUT)
    args = parser.parse_args()
    run_daemon_server(args.stata_path, args.edition, args.graphs_dir, args.idle_timeout)
