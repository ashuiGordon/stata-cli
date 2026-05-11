"""Stata execution engine wrapping PyStata."""

import io
import json
import os
import sys
import re
import time
import tempfile
import platform
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from .utils import join_line_continuations
from .graph_artifacts import (
    build_graph_record,
    cleanup_graph_batches,
    create_batch_context,
    ensure_graphs_root,
    get_graphs_root,
    write_batch_manifest,
)


@dataclass
class Result:
    """Outcome of a Stata command execution."""
    success: bool
    output: str
    error: str
    execution_time: float
    return_code: int = 0
    extra: dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


# ── Graph command regex for auto-naming ──────────────────────────────────

_GRAPH_CMD_RE = re.compile(
    r"^(\s*)(scatter|histogram|twoway|kdensity|graph\s+"
    r"(?:bar|box|dot|pie|matrix|hbar|hbox|combine))\s+(.*)$",
    re.IGNORECASE,
)
_GRAPH_NAME_RE = re.compile(r"\bname\s*\(", re.IGNORECASE)
_EXISTING_GRAPHN_RE = re.compile(r"\bname\s*\(\s*graph(\d+)", re.IGNORECASE)


class StataEngine:
    """Thin wrapper around PyStata for single-process command execution."""

    def __init__(self, stata_path: str, edition: str = "mp", graphs_dir: Optional[str] = None):
        self.stata_path = stata_path
        self.edition = edition.lower()
        self.graphs_dir = graphs_dir or get_graphs_root()
        self._stata = None
        self._stlib = None
        self._initialized = False
        self._stop_sent = False

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return

        os.environ["SYSDIR_STATA"] = self.stata_path

        from .utils import get_pystata_path

        pystata_dir = get_pystata_path(self.stata_path)
        if pystata_dir and pystata_dir not in sys.path:
            sys.path.insert(0, pystata_dir)
        utilities_parent = os.path.join(self.stata_path, "utilities")
        if os.path.isdir(utilities_parent) and utilities_parent not in sys.path:
            sys.path.insert(0, utilities_parent)

        if platform.system() == "Darwin":
            os.environ["_JAVA_OPTIONS"] = "-Djava.awt.headless=true"

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            from pystata import config  # type: ignore[import-untyped]
            config.init(self.edition)
        finally:
            sys.stdout = old_stdout

        from pystata import stata as stata_module  # type: ignore[import-untyped]

        self._stata = stata_module

        try:
            from pystata.config import stlib as stlib_module  # type: ignore[import-untyped]
            self._stlib = stlib_module
        except Exception:
            self._stlib = None

        self._initialized = True

    # ── public API ────────────────────────────────────────────────────────

    def run(self, code: str, timeout: float = 600.0) -> Result:
        """Execute a Stata code string and return captured output."""
        self._ensure_initialized()
        code = join_line_continuations(code)
        self._stop_sent = False

        self._reset_graph_tracking()

        log_file = os.path.join(
            tempfile.gettempdir(),
            f"stata_cli_{os.getpid()}_{int(time.time() * 1000)}.log",
        )
        log_file_stata = log_file.replace("\\", "/")

        wrapped = (
            f'capture log close _all\n'
            f'log using "{log_file_stata}", replace text\n'
            f'{code}\n'
            f'capture log close _all\n'
        )

        start = time.time()
        try:
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                self._stata.run(wrapped, echo=True, inline=False)
            finally:
                captured_stdout = sys.stdout.getvalue()
                sys.stdout = old_stdout

            output = self._read_log(log_file) or captured_stdout
            elapsed = time.time() - start

            output = _deduplicate_breaks(output)

            graphs = self._detect_and_export_graphs()
            extra: dict = {}
            if graphs:
                extra["graphs"] = graphs

            if "--Break--" in output:
                return Result(False, output, "Execution cancelled", elapsed, return_code=1, extra=extra)

            rc = _extract_return_code(output)
            if rc:
                return Result(False, output, "", elapsed, return_code=rc, extra=extra)

            return Result(True, output, "", elapsed, return_code=0, extra=extra)

        except Exception as exc:
            elapsed = time.time() - start
            error_str = str(exc)
            if "--Break--" in error_str:
                return Result(False, "", "Execution cancelled", elapsed, return_code=1)
            rc = _extract_return_code(error_str)
            return Result(False, error_str, "", elapsed, return_code=rc or 1)
        finally:
            self._remove(log_file)

    def run_file(self, path: str, timeout: float = 600.0) -> Result:
        """Execute a .do file with graph auto-naming and ``///`` preprocessing."""
        path = os.path.abspath(path)
        if not os.path.isfile(path):
            return Result(False, "", f"File not found: {path}", 0.0)

        preprocessed = self._preprocess_do_file(path)
        file_dir = os.path.dirname(path)
        stata_path = preprocessed.replace("\\", "/")
        code = f'cd "{file_dir}"\ndo "{stata_path}"'
        try:
            return self.run(code, timeout=timeout)
        finally:
            if preprocessed != path:
                self._remove(preprocessed)

    def get_data(self, if_condition: Optional[str] = None, max_rows: int = 10000) -> Dict[str, Any]:
        """Return the current dataset as a dict (columns, data, dtypes, row counts)."""
        self._ensure_initialized()
        try:
            import sfi  # type: ignore[import-untyped]
            import numpy as np  # type: ignore[import-untyped]
        except ImportError as exc:
            return {"status": "error", "error": f"Missing dependency: {exc}"}

        total_obs = sfi.Data.getObsTotal()
        if total_obs == 0:
            return {
                "status": "success", "data": [], "columns": [], "dtypes": {},
                "rows": 0, "total_rows": 0, "displayed_rows": 0, "max_rows": max_rows,
            }

        max_rows = max(100, max_rows)
        frame_name = f"_stata_cli_flt_{os.getpid()}"

        try:
            if if_condition:
                self._stata.run(f"capture frame drop {frame_name}", inline=False, echo=False)
                self._stata.run(f"frame copy `c(frame)' {frame_name}", inline=False, echo=False)
                self._stata.run(f"frame {frame_name}: quietly gen long _orig_obs = _n - 1", inline=False, echo=False)
                self._stata.run(f"frame {frame_name}: quietly keep if {if_condition}", inline=False, echo=False)

                df = self._stata.pdataframe_from_frame(frame_name)
                filtered_obs = len(df) if df is not None else 0
                if filtered_obs > max_rows:
                    df = df.head(max_rows)

                orig_index = df["_orig_obs"].tolist() if df is not None and not df.empty else []
                if df is not None and "_orig_obs" in df.columns:
                    df = df.drop(columns=["_orig_obs"])

                total_matching = filtered_obs
                displayed = min(filtered_obs, max_rows)
            else:
                total_matching = total_obs
                displayed = min(total_obs, max_rows)
                if total_obs > max_rows:
                    df = self._stata.pdataframe_from_data(obs=range(max_rows))
                else:
                    df = self._stata.pdataframe_from_data()
                orig_index = list(range(len(df))) if df is not None else []

            if df is None or df.empty:
                return {
                    "status": "success", "data": [], "columns": [], "dtypes": {},
                    "rows": 0, "total_rows": total_matching, "displayed_rows": 0, "max_rows": max_rows,
                }

            df_clean = df.replace({np.nan: None})
            return {
                "status": "success",
                "data": df_clean.values.tolist(),
                "columns": df_clean.columns.tolist(),
                "dtypes": {col: str(df[col].dtype) for col in df.columns},
                "rows": len(df),
                "index": orig_index,
                "total_rows": total_matching,
                "displayed_rows": displayed,
                "max_rows": max_rows,
            }
        except Exception as exc:
            return {"status": "error", "error": str(exc)}
        finally:
            if if_condition:
                try:
                    self._stata.run(f"capture frame drop {frame_name}", inline=False, echo=False)
                except Exception:
                    pass

    def help(self, topic: str) -> Result:
        """Return Stata help text for *topic*."""
        self._ensure_initialized()
        topic = topic.strip().lstrip("#").replace(" ", "_").split(",")[0].strip()
        if not topic or not re.match(r"^[a-zA-Z0-9_.\-]+$", topic):
            return Result(False, "", "Invalid topic name", 0.0)

        first_letter = topic[0].lower()
        sysdirs = ["base", "plus", "site", "personal", "stata", "oldplace"]
        fallback_blocks = ""
        for sd in sysdirs:
            for ext in ["sthlp", "hlp"]:
                fallback_blocks += (
                    f'if "`_helpfn\'" == "" {{\n'
                    f'    capture confirm file "`c(sysdir_{sd})\'{first_letter}/{topic}.{ext}"\n'
                    f'    if _rc == 0 local _helpfn "`c(sysdir_{sd})\'{first_letter}/{topic}.{ext}"\n'
                    f'}}\n'
                )

        stata_code = (
            f'quietly set more off\n'
            f'local _stata_help_old_linesize = c(linesize)\n'
            f'quietly set linesize 255\n'
            f'local _helpfn ""\n'
            f'capture findfile {topic}.sthlp\n'
            f'if _rc == 0 local _helpfn "`r(fn)\'"\n'
            f'if "`_helpfn\'" == "" {{\n'
            f'    capture findfile {topic}.hlp\n'
            f'    if _rc == 0 local _helpfn "`r(fn)\'"\n'
            f'}}\n'
            f'{fallback_blocks}'
            f'if "`_helpfn\'" != "" {{\n'
            f'    type "`_helpfn\'", starbang\n'
            f'}}\n'
            f'else {{\n'
            f'    display as error "help file not found for: {topic}"\n'
            f'}}\n'
            f'quietly set linesize `_stata_help_old_linesize\'\n'
        )

        result = self.run(stata_code)

        if result.output:
            from .output_filter import clean_log_wrapper, apply_compact_filter
            from .smcl_parser import smcl_to_text
            output = clean_log_wrapper(result.output)
            output = apply_compact_filter(output, filter_command_echo=True)
            output = smcl_to_text(output)
            result.output = output

        return result

    def stop(self) -> bool:
        """Interrupt a running Stata command. Returns True if signal sent."""
        if self._stop_sent or self._stlib is None:
            return False
        self._stop_sent = True
        try:
            self._stlib.StataSO_SetBreak()
            return True
        except Exception:
            return False

    def close(self) -> None:
        """Cleanup placeholder."""

    # ── graph detection ──────────────────────────────────────────────────

    def _reset_graph_tracking(self) -> None:
        if self._stlib is None:
            return
        try:
            from pystata.config import get_encode_str  # type: ignore[import-untyped]
            self._stlib.StataSO_Execute(get_encode_str("qui _gr_list off"), False)
            self._stlib.StataSO_Execute(get_encode_str("qui _gr_list on"), False)
        except Exception:
            pass

    def _detect_and_export_graphs(self) -> List[Dict[str, Any]]:
        if self._stlib is None:
            return []
        try:
            import sfi  # type: ignore[import-untyped]
            from pystata.config import get_encode_str  # type: ignore[import-untyped]

            self._stlib.StataSO_Execute(get_encode_str("qui _gr_list list"), False)
            gnamelist = sfi.Macro.getGlobal("r(_grlist)")
            if not gnamelist or not gnamelist.strip():
                return []

            graph_names = gnamelist.strip().split()
            graphs_root = ensure_graphs_root(self.graphs_dir)
            batch = create_batch_context(graphs_root)
            graphs: List[Dict[str, Any]] = []

            for order, gname in enumerate(graph_names):
                try:
                    self._stlib.StataSO_Execute(
                        get_encode_str(f"quietly graph display {gname}"), False
                    )
                    graph_file = os.path.join(batch["batch_dir"], f"{gname}.png")
                    graph_file_stata = graph_file.replace("\\", "/")
                    export_cmd = (
                        f'quietly graph export "{graph_file_stata}", '
                        f"name({gname}) replace width(800) height(600)"
                    )
                    rc = self._stlib.StataSO_Execute(get_encode_str(export_cmd), False)
                    if rc != 0:
                        continue
                    if os.path.isfile(graph_file) and os.path.getsize(graph_file) > 0:
                        graphs.append(build_graph_record(batch, gname, graph_file, order))
                except Exception:
                    continue

            if graphs:
                write_batch_manifest(batch, graphs)
                cleanup_graph_batches(graphs_root, keep_ids=[batch["batch_id"]])

            return graphs
        except Exception:
            return []

    # ── do-file preprocessing ────────────────────────────────────────────

    @staticmethod
    def _preprocess_do_file(path: str) -> str:
        """Join ``///`` continuations and auto-name unnamed graph commands.

        Returns the path to a temp file (or the original if no changes needed).
        """
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read()

            joined_lines = join_line_continuations(content).splitlines()

            existing_nums: set[int] = set()
            for line in joined_lines:
                for m in _EXISTING_GRAPHN_RE.findall(line):
                    try:
                        existing_nums.add(int(m))
                    except ValueError:
                        pass

            counter = max(existing_nums) if existing_nums else 0
            modified = False
            out_lines: list[str] = []

            for line in joined_lines:
                gm = _GRAPH_CMD_RE.match(line)
                if gm and not _GRAPH_NAME_RE.search(gm.group(3)):
                    indent, cmd, rest = gm.group(1), gm.group(2), gm.group(3)
                    counter += 1
                    name_opt = f"name(graph{counter}, replace)"
                    if "," in rest:
                        rest = rest.replace(",", f", {name_opt}", 1)
                    else:
                        rest = rest.rstrip() + f", {name_opt}"
                    out_lines.append(f"{indent}{cmd} {rest}")
                    modified = True
                else:
                    out_lines.append(line)

            if not modified:
                return path

            tmp = tempfile.NamedTemporaryFile(suffix=".do", delete=False, mode="w", encoding="utf-8")
            tmp.write("\n".join(out_lines) + "\n")
            tmp.close()
            return tmp.name
        except Exception:
            return path

    # ── internals ─────────────────────────────────────────────────────────

    @staticmethod
    def _read_log(path: str) -> str:
        if not os.path.isfile(path):
            return ""
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                return fh.read()
        except OSError:
            return ""

    @staticmethod
    def _remove(path: str) -> None:
        try:
            if os.path.isfile(path):
                os.unlink(path)
        except OSError:
            pass


def _deduplicate_breaks(output: str) -> str:
    if not output or "--Break--" not in output:
        return output
    return re.sub(
        r"(--Break--\s*\n\s*r\(1\);\s*\n?)+",
        "--Break--\nr(1);\n",
        output,
    )


_STATA_ERROR_RE = re.compile(r"^r\((\d+)\);\s*$", re.MULTILINE)


def _extract_return_code(output: str) -> int:
    """Extract the last Stata return code from output. 0 if none found."""
    matches = _STATA_ERROR_RE.findall(output)
    return int(matches[-1]) if matches else 0
