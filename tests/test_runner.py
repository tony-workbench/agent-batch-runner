import json
from pathlib import Path

import pytest

from runner import guard, tasks, batch
from runner.config import load


@pytest.fixture
def project(tmp_path):
    (tmp_path / "output").mkdir()
    (tmp_path / "config.json").write_text(json.dumps({"root": ".", "docs_dir": "docs-for-agents"}))
    rows = [
        {"id": "a", "title": "Plain lesson", "status": "todo", "owner": "", "version": 1, "path": "output/a.html"},
        {"id": "b", "title": "GPU training lesson", "status": "todo", "owner": "", "version": 1, "path": "output/b.html"},
    ]
    (tmp_path / "tasks.json").write_text(json.dumps({"items": rows}))
    return load(tmp_path / "config.json")


def test_version_conflict(project):
    row = tasks.update(project.task_table, "a", 1, "w1", owner="w1", status="in_progress")
    assert row["version"] == 2
    with pytest.raises(tasks.VersionConflict):
        tasks.update(project.task_table, "a", 1, "w1", note="stale")
    with pytest.raises(tasks.VersionConflict):
        tasks.update(project.task_table, "a", 2, "w2", note="not the owner")


def test_delivered_only_through_deliver(project):
    with pytest.raises(ValueError):
        tasks.update(project.task_table, "a", 1, "w1", status="delivered")
    out = project.output_dir / "a.html"
    out.write_text("<title>a</title>")
    row = tasks.deliver(project.task_table, "a", 1, "w1", out)
    assert row["status"] == "delivered" and len(row["sha256"]) == 64


def test_wrapup_detects_changed_file(project):
    out = project.output_dir / "a.html"
    out.write_text("<title>a</title>")
    tasks.deliver(project.task_table, "a", 1, "w1", out)
    assert batch.verify_delivered(tasks.items(project.task_table)) == []
    out.write_text("<title>changed</title>")
    assert batch.verify_delivered(tasks.items(project.task_table)) == [("a", "file changed after delivery")]


def test_pick_next_runs_one_heavy_task_at_a_time(project):
    table = tasks.items(project.task_table)
    assert batch.pick_next(table, project, {}, set(), heavy_running=False)["id"] == "a"
    assert batch.pick_next(table, project, {}, {"a"}, heavy_running=False)["id"] == "b"
    assert batch.pick_next(table, project, {}, {"a"}, heavy_running=True) is None
    assert batch.pick_next(table, project, {"a": 2}, set(), heavy_running=False)["id"] == "b"


def test_guard(project):
    r, w = project.read_roots, project.write_roots
    assert guard.check("Write", {"file_path": str(project.output_dir / "x.html")}, r, w) is None
    assert guard.check("Write", {"file_path": "/etc/passwd"}, r, w)
    assert guard.check("Read", {"file_path": str(project.root / ".env")}, r, w)
    assert guard.check("mcp__mail__send", {}, r, w)
    assert guard.check("Bash", {"command": "sudo ls"}, r, w)
    assert guard.check("Bash", {"command": "echo hi > /etc/hosts"}, r, w)
    assert guard.check("Bash", {"command": f"echo hi > {project.output_dir}/x.txt"}, r, w) is None
    assert guard.check("Bash", {"command": "rm -rf ~"}, r, w)


def test_batch_smoke_with_stub_worker(project, tmp_path, monkeypatch):
    """The coordinator starts a worker per task, wraps up, and releases a task whose worker ended without a result."""
    import asyncio
    import sys
    stub = tmp_path / "stub_worker.py"
    stub.write_text(
        "import sys\n"
        "from runner import tasks\n"
        "from runner.config import load\n"
        "cfg = load(sys.argv[2])\n"
        "row = tasks.items(cfg.task_table)[sys.argv[1]]\n"
        "row = tasks.update(cfg.task_table, row['id'], row['version'], row['id'], owner=row['id'], status='in_progress')\n"
        "if row['id'] == 'a':\n"
        "    out = cfg.output_dir / 'a.html'; out.write_text('<title>a</title>')\n"
        "    tasks.deliver(cfg.task_table, 'a', row['version'], 'a', out)\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv("RUNNER_WORKER", "stub_worker")
    monkeypatch.setenv("PYTHONPATH", f"{tmp_path}:{Path(__file__).resolve().parents[1]}")
    monkeypatch.chdir(project.root)
    b = batch.Batch(project, project.root / "config.json")
    real_sleep = asyncio.sleep

    async def fast_sleep(seconds):
        await real_sleep(0.05)

    monkeypatch.setattr(asyncio, "sleep", fast_sleep)
    asyncio.run(b.run(max_tasks=2))
    rows = tasks.items(project.task_table)
    assert rows["a"]["status"] == "delivered"
    assert rows["b"]["status"] == "todo" and b.fails["b"] == 1
    assert (project.output_dir.parent / "reports" / "summary.md").read_text().startswith("# Wrap-up")

