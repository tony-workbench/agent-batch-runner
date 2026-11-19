"""Coordinator: picks tasks, runs one worker process per task, enforces timeouts, wraps up.

Stop it without losing work by creating the STOP file in the state directory (or typing `stop`):
no new task starts and running tasks finish.
"""
import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from . import tasks
from .config import load


def pick_next(table, cfg, fails, busy, heavy_running):
    """First `todo` task without an owner, in file order (or in the order file), skipping failed and busy ones."""
    heavy = re.compile(cfg["heavy_pattern"], re.I)
    order_file = cfg.root / "order.json"
    order = json.loads(order_file.read_text()) if order_file.exists() else []
    rows = [r for r in table.values() if r["status"] == "todo" and not r.get("owner")
            and r["id"] not in busy and fails.get(r["id"], 0) < cfg["max_failures_per_task"]]
    rows.sort(key=lambda r: order.index(r["id"]) if r["id"] in order else len(order))
    for r in rows:
        if heavy_running and heavy.search(r["title"]):
            continue
        return r
    return None


def verify_delivered(table):
    """Return [(id, problem)] for delivered rows whose file is missing or changed since delivery."""
    bad = []
    for r in table.values():
        if r["status"] != "delivered":
            continue
        p = Path(r.get("output", ""))
        if not p.is_file():
            bad.append((r["id"], "output file missing"))
        elif hashlib.sha256(p.read_bytes()).hexdigest() != r.get("sha256"):
            bad.append((r["id"], "file changed after delivery"))
    return bad


class Batch:
    def __init__(self, cfg, config_path):
        self.cfg, self.config_path = cfg, config_path
        self.stop_file = cfg.state_dir / "STOP"
        self.log_file = cfg.state_dir / "batch.log"
        self.running, self.fails = {}, {}
        self.workers = cfg["workers"]
        self.bad_streak = 0

    def log(self, msg):
        line = f"[{datetime.now():%m-%d %H:%M:%S}] {msg}"
        print(line, flush=True)
        with self.log_file.open("a") as f:
            f.write(line + "\n")

    def watch(self, task_id, proc, started):
        """Return True when the worker must be killed: past its time and idle, or past the hard maximum."""
        cfg = self.cfg
        now = time.time()
        progress = cfg.state_dir / f"{task_id}.progress"
        last = progress.stat().st_mtime if progress.exists() else started
        limit = started + cfg["base_seconds"]
        while limit <= now and now - last < cfg["idle_seconds"] and now - started < cfg["max_seconds"]:
            limit += cfg["extend_seconds"]
        return now > limit or now - started >= cfg["max_seconds"]

    def reap(self):
        table = tasks.items(self.cfg.task_table)
        for tid, (proc, started) in list(self.running.items()):
            if proc.poll() is None:
                if self.watch(tid, proc, started):
                    self.log(f"{tid} timed out, terminating")
                    proc.terminate()
                continue
            del self.running[tid]
            row = table[tid]
            self.log(f"finished {tid}: status={row['status']} exit={proc.returncode}")
            good = row["status"] in ("delivered", "waiting_material", "paused")
            self.bad_streak = 0 if good else self.bad_streak + 1
            if self.bad_streak >= self.cfg["throttle_after_bad_ends"] and self.workers > 1:
                self.workers -= 1
                self.bad_streak = 0
                self.log(f"too many abnormal ends, workers reduced to {self.workers}")
            if row["status"] == "in_progress":
                self.fails[tid] = self.fails.get(tid, 0) + 1
                tasks.update(self.cfg.task_table, tid, row["version"], row.get("owner") or tid, owner="", status="todo",
                             note="run ended without a result, released for retry")

    def start(self, row):
        self.log(f"start {row['id']} {row['title']}")
        module = os.environ.get("RUNNER_WORKER", "runner.worker")
        env = {**os.environ, "RUNNER_CONFIG": str(self.config_path)}
        proc = subprocess.Popen([sys.executable, "-m", module, row["id"], str(self.config_path)], cwd=str(self.cfg.root), env=env)
        self.running[row["id"]] = (proc, time.time())

    def wrapup(self):
        table = tasks.items(self.cfg.task_table)
        bad = verify_delivered(table)
        done = sum(1 for r in table.values() if r["status"] == "delivered")
        out = [f"# Wrap-up {datetime.now():%Y-%m-%d %H:%M}", "", f"{done} delivered, {len(bad)} with problems.", ""]
        out += [f"- {i}: {why}" for i, why in bad]
        reports = self.cfg.output_dir.parent / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        (reports / "summary.md").write_text("\n".join(out) + "\n")
        self.log(f"wrap-up: {done} delivered, {len(bad)} problems")

    async def run(self, max_tasks=0):
        self.cfg.state_dir.mkdir(parents=True, exist_ok=True)
        self.stop_file.unlink(missing_ok=True)
        started = 0
        try:
            while True:
                self.reap()
                stopping = self.stop_file.exists() or (max_tasks and started >= max_tasks)
                if stopping and not self.running:
                    break
                if not stopping and len(self.running) < self.workers:
                    table = tasks.items(self.cfg.task_table)
                    heavy = re.compile(self.cfg["heavy_pattern"], re.I)
                    heavy_running = any(heavy.search(table[t]["title"]) for t in self.running)
                    row = pick_next(table, self.cfg, self.fails, set(self.running), heavy_running)
                    if row is None and not self.running:
                        self.log("nothing left to do")
                        break
                    if row is not None:
                        self.start(row)
                        started += 1
                        await asyncio.sleep(5)
                        continue
                await asyncio.sleep(10)
        finally:
            self.wrapup()


def main(argv=None):
    config_path = Path(os.environ.get("RUNNER_CONFIG", "config.json")).resolve()
    cfg = load(config_path)
    max_tasks = int(os.environ.get("MAX_TASKS", "0"))
    asyncio.run(Batch(cfg, config_path).run(max_tasks))


if __name__ == "__main__":
    main()
