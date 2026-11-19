# Harness design

Purpose: how the runner is built and why each part exists.

## Processes

- `runner/batch.py` is the coordinator. It never calls the model. It picks tasks, starts one `runner/worker.py` process per task, watches them, and writes the wrap-up.
- `runner/worker.py` runs one task through `claude_agent_sdk.query` with a task prompt. One process per task keeps SDK global state, crashes and memory from leaking between tasks.
- `runner/tasks.py` is the shared task table (a JSON file). It is also the command-line tool the agent calls through Bash to claim, update and deliver a task.

## Task selection

- Rows with status `todo`, no owner, and fewer than `max_failures_per_task` failed runs are candidates.
- Order follows `order.json` (a list of ids, optional), then file order.
- Tasks whose title matches `heavy_pattern` (for example GPU or Docker work) run one at a time; light tasks fill the other worker slots.
- After `throttle_after_bad_ends` consecutive abnormal ends the coordinator lowers the worker count by one. A worker that ends with the task still `in_progress` is released back to `todo` and counted as a failure.

## Task table

A JSON file with `items`. Each row has `id`, `title`, `status`, `owner`, `version`, `path` (output file), `evidence` (source folders) and `notes`.

- Statuses: `todo`, `in_progress`, `delivered`, `waiting_material`, `paused`.
- Every change names the version it was read at. A stale version is refused, so parallel workers never overwrite each other. A row with an owner can only be changed by that owner.
- `delivered` can only be set by `deliver`, which stores the output path and its sha256.

## Guard

A `PreToolUse` hook calls `runner/guard.py` for every tool call, including subagents' calls:

- Write and Edit only inside the write roots (project root, output folder, state folder, temp).
- Read, Glob and Grep only inside the read roots (write roots, the documents folder, system folders, and any extra roots from the config). Secret-looking file names are never readable.
- Bash is checked by its command text: no `sudo`, keychain, system-settings or bulk-kill commands; write targets and read targets must be inside the roots.
- Every `mcp__*` tool is refused, so mail, calendar and other connectors cannot be used.

The guard reads command text only. A path built inside a script is not seen, so it is a seatbelt, not a sandbox. Add a real sandbox if the work is not trusted.

## Subagents

| Name | Job | Tools |
|---|---|---|
| `source` | read and summarize source material | all except Agent |
| `writer` | write one block of the page, self-check that block | all except Agent |
| `reviewer` | read-only independent review, writes only the review file | no Edit |

The main agent coordinates: it starts all writers in one message, assembles the page, starts the reviewer, fixes the findings, and verifies.

## Time limits

- A task gets `base_seconds`. At the deadline, if the worker touched its progress file within `idle_seconds`, the deadline moves out by `extend_seconds`, up to `max_seconds`. Otherwise the worker is terminated.
- The progress file is touched on every tool result and every streamed message.

## Wrap-up

When no task is left, the STOP file exists, or `MAX_TASKS` is reached, the coordinator re-hashes every delivered output and writes `reports/summary.md` with the count and any file that is missing or changed since delivery. Each worker also writes its own one-page report to `reports/<id>.md`.

## Cost

The SDK's `total_cost_usd` is an estimate. Per-task estimates are appended to `.state/usage.jsonl`; compare them with your billing before relying on them.
