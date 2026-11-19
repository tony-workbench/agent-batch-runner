# agent-batch-runner

A small harness that runs the Claude Agent SDK unattended over a table of tasks and produces one self-contained HTML learning page per task. Each task runs in its own process; the agent reads a few Markdown documents (rules, style guide, review checklist), writes the page with subagents, has it reviewed, and delivers it with a recorded hash.

## What you need

- Python 3.10 or newer
- An Anthropic API key in `ANTHROPIC_API_KEY`

## Steps

1. Create a virtual environment and install: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
2. Copy the example config: `cp config.example.json config.json`
3. Copy the example task table: `cp templates/tasks.example.json tasks.json`
4. Put your source material where each task's `evidence` points, and edit the three documents in `templates/` to describe your rules.
5. Run one task first: `MAX_TASKS=1 .venv/bin/python -m runner.batch` (with the key exported and the venv's `bin` first on `PATH`, or call `bin/start`).
6. Stop cleanly at any time: `touch .state/STOP`. Running tasks finish, then the wrap-up runs.

Test command (no API calls): `.venv/bin/python -m pytest -q`

## Docs

- [docs/harness.md](docs/harness.md): how the harness is built (processes, guard, subagents, timeouts)
- [docs/workflow.md](docs/workflow.md): what happens to one task, from claim to delivery
- [docs/documents-the-agent-reads.md](docs/documents-the-agent-reads.md): the Markdown files and the task table the agent reads, and how to write them
