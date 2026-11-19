"""Shared task table: a JSON file with versioned claims, so parallel workers never overwrite each other.

Statuses: todo, in_progress, delivered, waiting_material, paused.
Only `deliver` can set `delivered`; it records the output file's sha256 so the final wrap-up can re-check it.

CLI (the agent calls these through Bash):
  python -m runner.tasks list [--status S] [--query TEXT]
  python -m runner.tasks show ID
  python -m runner.tasks update ID --expected-version N --actor NAME [--owner NAME] [--status S] [--note TEXT]
  python -m runner.tasks deliver ID --expected-version N --actor NAME --file OUTPUT.html
"""
import argparse
import fcntl
import hashlib
import json
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

from .config import load

STATUSES = {"todo", "in_progress", "delivered", "waiting_material", "paused"}


class VersionConflict(Exception):
    pass


@contextmanager
def _locked(path):
    lock = Path(str(path) + ".lock")
    with open(lock, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def _read(path):
    return json.loads(Path(path).read_text())


def _write(path, data):
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    os.replace(tmp, path)


def items(path):
    return {r["id"]: r for r in _read(path)["items"]}


def update(path, task_id, expected_version, actor, owner=None, status=None, note=None, extra=None):
    """Apply a change only if the row is still at `expected_version`; bump the version."""
    if status is not None and status not in STATUSES:
        raise ValueError(f"unknown status {status!r}")
    if status == "delivered" and not extra:
        raise ValueError("use deliver() to set delivered")
    with _locked(path):
        data = _read(path)
        row = next((r for r in data["items"] if r["id"] == task_id), None)
        if row is None:
            raise KeyError(task_id)
        if row["version"] != expected_version:
            raise VersionConflict(f"{task_id} is at version {row['version']}, not {expected_version}")
        if row.get("owner") and row["owner"] != actor:
            raise VersionConflict(f"{task_id} is owned by {row['owner']}")
        if owner is not None:
            row["owner"] = owner
        if status is not None:
            row["status"] = status
        if note is not None:
            row.setdefault("notes", []).append({"t": time.strftime("%Y-%m-%d %H:%M"), "by": actor, "text": note})
        row.update(extra or {})
        row["version"] += 1
        _write(path, data)
        return row


def deliver(path, task_id, expected_version, actor, output_file):
    out = Path(output_file)
    if not out.is_file() or out.stat().st_size == 0:
        raise ValueError(f"{out} is missing or empty")
    sha = hashlib.sha256(out.read_bytes()).hexdigest()
    return update(path, task_id, expected_version, actor, owner="", status="delivered",
                  note=f"delivered {out.name}", extra={"output": str(out), "sha256": sha})


def main(argv=None):
    ap = argparse.ArgumentParser(prog="runner.tasks")
    ap.add_argument("--config")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ls = sub.add_parser("list")
    ls.add_argument("--status")
    ls.add_argument("--query", default="")
    sub.add_parser("show").add_argument("id")
    for name in ("update", "deliver"):
        p = sub.add_parser(name)
        p.add_argument("id")
        p.add_argument("--expected-version", type=int, required=True)
        p.add_argument("--actor", required=True)
        if name == "update":
            p.add_argument("--owner")
            p.add_argument("--status")
            p.add_argument("--note")
        else:
            p.add_argument("--file", required=True)
    a = ap.parse_args(argv)
    table = load(a.config).task_table
    if a.cmd == "list":
        for r in items(table).values():
            if (not a.status or r["status"] == a.status) and a.query.lower() in (r["id"] + " " + r["title"]).lower():
                print(f"{r['id']}\t{r['status']}\tv{r['version']}\t{r.get('owner') or '-'}\t{r['title']}")
    elif a.cmd == "show":
        print(json.dumps(items(table)[a.id], indent=2, ensure_ascii=False))
    else:
        try:
            if a.cmd == "update":
                row = update(table, a.id, a.expected_version, a.actor, a.owner, a.status, a.note)
            else:
                row = deliver(table, a.id, a.expected_version, a.actor, a.file)
        except (VersionConflict, ValueError, KeyError) as e:
            print(f"refused: {e}", file=sys.stderr)
            return 1
        print(f"ok: {row['id']} is now {row['status']} at version {row['version']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
