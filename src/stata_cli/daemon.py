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
_IS_WINDOWS = platform.system() == "Windows"
_DEFAULT_PORT = 4718
_IDLE_TIMEOUT = 3600  # 1 hour


def _pid_file(session: str = "default") -> str:
    return os.path.join(_STATE_DIR, f"daemon-{session}.pid")


def _sock_file(session: str = "default") -> str:
    return os.path.join(_STATE_DIR, f"daemon-{session}.sock")


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
                 graphs_dir: Optional[str] = None, idle_timeout: float = _IDLE_TIMEOUT,
                 session: str = "default"):
        self.stata_path = stata_path
        self.edition = edition
        self.graphs_dir = graphs_dir
        self.idle_timeout = idle_timeout
        self.session = session
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
        self._port = sock.getsockname()[1] if _IS_WINDOWS else 0
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
            port = self._find_free_port()
            sock.bind(("127.0.0.1", port))
        else:
            sock_path = _sock_file(self.session)
            if os.path.exists(sock_path):
                os.unlink(sock_path)
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.bind(sock_path)
        sock.listen(4)
        sock.setblocking(False)
        return sock

    @staticmethod
    def _find_free_port() -> int:
        for port in range(_DEFAULT_PORT, _DEFAULT_PORT + 200):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s.bind(("127.0.0.1", port))
                s.close()
                return port
            except OSError:
                s.close()
                continue
        raise RuntimeError("No free port found")

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
        sock_path = _sock_file(self.session)
        addr = f"127.0.0.1:{self._port}" if _IS_WINDOWS else sock_path
        with open(_pid_file(self.session), "w") as fh:
            json.dump({"pid": os.getpid(), "address": addr, "started": time.time(), "session": self.session}, fh)

    def _cleanup(self) -> None:
        try:
            os.unlink(_pid_file(self.session))
        except OSError:
            pass
        if not _IS_WINDOWS:
            try:
                os.unlink(_sock_file(self.session))
            except OSError:
                pass

    def _shutdown(self) -> None:
        self._running = False


def run_daemon_server(stata_path: str, edition: str = "mp",
                      graphs_dir: Optional[str] = None, idle_timeout: float = _IDLE_TIMEOUT,
                      session: str = "default") -> None:
    """Entry point called in the daemon subprocess."""
    server = DaemonServer(stata_path, edition, graphs_dir=graphs_dir, idle_timeout=idle_timeout, session=session)
    server.serve()


# ═══════════════════════════════════════════════════════════════════════════
# CLIENT
# ═══════════════════════════════════════════════════════════════════════════

class DaemonClient:
    """Connects to a running daemon over the Unix socket / TCP port."""

    def __init__(self, session: str = "default") -> None:
        self.session = session
        self._sock: Optional[socket.socket] = None

    def is_running(self) -> bool:
        pid_path = _pid_file(self.session)
        if not os.path.isfile(pid_path):
            return False
        try:
            with open(pid_path) as fh:
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
        pid_path = _pid_file(self.session)
        if not os.path.isfile(pid_path):
            return None
        try:
            with open(pid_path) as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError):
            return None


def start_daemon(stata_path: str, edition: str = "mp",
                 graphs_dir: Optional[str] = None, idle_timeout: float = _IDLE_TIMEOUT,
                 session: str = "default") -> bool:
    """Launch daemon as a detached background process. Returns True on success."""
    client = DaemonClient(session)
    if client.is_running():
        return True

    os.makedirs(_STATE_DIR, exist_ok=True)
    log_file = os.path.join(_STATE_DIR, f"daemon-{session}.log")

    args = [
        sys.executable, "-m", "stata_cli.daemon",
        "--stata-path", stata_path,
        "--edition", edition,
        "--idle-timeout", str(int(idle_timeout)),
        "--session", session,
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


def stop_daemon(session: str = "default") -> bool:
    """Ask the daemon to shut down gracefully."""
    client = DaemonClient(session)
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
        with open(_pid_file(session)) as fh:
            pid = json.load(fh)["pid"]
        os.kill(pid, signal.SIGKILL if not _IS_WINDOWS else signal.SIGTERM)
    except Exception:
        pass
    return True


def stop_all_daemons() -> int:
    """Stop all running daemon sessions. Returns count stopped."""
    import glob
    count = 0
    for pid_path in glob.glob(os.path.join(_STATE_DIR, "daemon-*.pid")):
        name = os.path.basename(pid_path)
        session = name[len("daemon-"):-len(".pid")]
        stop_daemon(session)
        count += 1
    return count


def list_sessions() -> list:
    """Return list of running session info dicts."""
    import glob
    sessions = []
    for pid_path in glob.glob(os.path.join(_STATE_DIR, "daemon-*.pid")):
        name = os.path.basename(pid_path)
        session = name[len("daemon-"):-len(".pid")]
        client = DaemonClient(session)
        if not client.is_running():
            continue
        info = {"session": session}
        if client.connect():
            try:
                status = client.send("status")
                info.update(status)
            except Exception:
                pass
            client.close()
        sessions.append(info)
    return sessions


def daemon_status(session: str = "default") -> Optional[Dict[str, Any]]:
    """Query a running daemon's status. Returns None if not running."""
    client = DaemonClient(session)
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
    parser.add_argument("--session", default="default")
    args = parser.parse_args()
    run_daemon_server(args.stata_path, args.edition, args.graphs_dir, args.idle_timeout, session=args.session)
