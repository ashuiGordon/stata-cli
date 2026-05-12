"""Platform detection and Stata path auto-discovery."""

from __future__ import annotations

import os
import platform


PLATFORM = platform.system()
IS_WINDOWS = PLATFORM == "Windows"
IS_MACOS = PLATFORM == "Darwin"
IS_LINUX = PLATFORM == "Linux"


def detect_stata_path() -> str | None:
    """Auto-detect the Stata installation directory.

    Checks, in order:
    1. STATA_PATH environment variable
    2. Platform-specific default locations
    """
    env_path = os.environ.get("STATA_PATH")
    if env_path and os.path.exists(env_path):
        return env_path

    if IS_MACOS:
        for candidate in [
            "/Applications/Stata",
            "/Applications/StataNow",
            "/Applications/Stata18",
            "/Applications/Stata17",
        ]:
            if os.path.exists(candidate):
                return candidate

    elif IS_WINDOWS:
        for version in ["18", "17", "16"]:
            for prefix in [r"C:\Program Files\Stata", r"C:\Program Files (x86)\Stata"]:
                candidate = prefix + version
                if os.path.exists(candidate):
                    return candidate

    elif IS_LINUX:
        for candidate in ["/usr/local/stata18", "/usr/local/stata17", "/usr/local/stata"]:
            if os.path.exists(candidate):
                return candidate

    return None


def get_pystata_path(stata_path: str) -> str | None:
    """Return the pystata utilities directory inside a Stata installation."""
    utilities = os.path.join(stata_path, "utilities")
    pystata = os.path.join(utilities, "pystata")
    if os.path.isdir(pystata):
        return pystata
    if os.path.isdir(utilities):
        return utilities
    return None


def normalize_path(path: str) -> str:
    """Normalize a file path for the current platform."""
    if not path:
        return path
    normalized = os.path.normpath(path)
    if IS_WINDOWS and "/" in normalized:
        normalized = normalized.replace("/", "\\")
    return normalized


def join_line_continuations(code: str) -> str:
    """Join Stata ``///`` line continuations into single logical lines."""
    raw_lines = code.splitlines()
    joined: list[str] = []
    current = ""
    for raw_line in raw_lines:
        stripped = raw_line.rstrip()
        if stripped.endswith("///"):
            current += stripped[:-3].rstrip() + " "
        else:
            current += raw_line
            joined.append(current)
            current = ""
    if current:
        joined.append(current)
    return "\n".join(joined)
