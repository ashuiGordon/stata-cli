"""Graph artifact storage and batch management."""

import json
import os
import shutil
import tempfile
import time
import uuid
from typing import Any, Dict, Iterable, List, Optional


DEFAULT_KEEP_BATCHES = 2
MANIFEST_FILENAME = "manifest.json"


def get_graphs_root(configured: Optional[str] = None) -> str:
    root = configured or os.environ.get("STATA_CLI_GRAPHS_DIR")
    if root:
        return os.path.abspath(root)
    return os.path.join(os.path.expanduser("~"), ".stata-cli", "graphs")


def ensure_graphs_root(graphs_root: str) -> str:
    os.makedirs(graphs_root, exist_ok=True)
    return os.path.abspath(graphs_root)


def create_batch_context(graphs_root: str, execution_id: Optional[str] = None) -> Dict[str, Any]:
    graphs_root = ensure_graphs_root(graphs_root)
    execution_id = execution_id or f"exec-{int(time.time() * 1000)}-{uuid.uuid4().hex[:8]}"
    batch_dir = os.path.join(graphs_root, execution_id)
    os.makedirs(batch_dir, exist_ok=True)
    return {
        "execution_id": execution_id,
        "batch_id": execution_id,
        "batch_dir": batch_dir,
        "graphs_root": graphs_root,
        "created_at": int(time.time() * 1000),
    }


def build_graph_record(
    batch_context: Dict[str, Any],
    name: str,
    file_path: str,
    order: int,
    fmt: str = "png",
) -> Dict[str, Any]:
    return {
        "name": name,
        "path": file_path.replace("\\", "/"),
        "filename": os.path.basename(file_path),
        "format": fmt,
        "order": order,
        "batchId": batch_context["batch_id"],
    }


def write_batch_manifest(batch_context: Dict[str, Any], graphs: List[Dict[str, Any]]) -> str:
    manifest = {
        "executionId": batch_context["execution_id"],
        "batchId": batch_context["batch_id"],
        "createdAt": batch_context["created_at"],
        "graphs": graphs,
    }
    path = os.path.join(batch_context["batch_dir"], MANIFEST_FILENAME)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    return path


def cleanup_graph_batches(
    graphs_root: str,
    keep_ids: Optional[Iterable[str]] = None,
    keep_latest: int = DEFAULT_KEEP_BATCHES,
) -> List[str]:
    if not os.path.isdir(graphs_root):
        return []
    protected = set(keep_ids or [])
    batch_dirs = sorted(
        (e.path for e in os.scandir(graphs_root) if e.is_dir()),
        key=lambda p: os.path.getmtime(p),
        reverse=True,
    )
    removed: list[str] = []
    for idx, bdir in enumerate(batch_dirs):
        bid = os.path.basename(bdir)
        if bid in protected or idx < keep_latest:
            continue
        try:
            shutil.rmtree(bdir, ignore_errors=True)
            removed.append(bid)
        except OSError:
            pass
    return removed
