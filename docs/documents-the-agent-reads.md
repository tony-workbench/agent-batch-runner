# Documents the agent reads

Purpose: which files drive a run and how to write them. The harness does not care what they are about; it only passes them to the agent.

## The task table (`tasks.json`)

Read and written through `python -m runner.tasks`. One row per page to produce. Put the title, the output path, and the folders with source material (`evidence`) in each row. See `templates/tasks.example.json`.

## The rules documents (`docs_dir`, listed in `rules_docs`)

The worker reads these in full before every task. Keep each short, one purpose per file, each fact once.

| File | Holds | Example in `templates/` |
|---|---|---|
| `RULES.md` | standing rules: boundaries, quality bar, definition of finished | `RULES.md` |
| `STYLE_GUIDE.md` | what the HTML page must contain and look like, and the self-checks to run | `STYLE_GUIDE.md` |
| `REVIEW_CHECKLIST.md` | what the reviewer checks and how findings are classified | `REVIEW_CHECKLIST.md` |

Add more files by listing them in `rules_docs`. To change behavior for all tasks, edit these files; the next task picks them up.

## Source material

Folders named in each row's `evidence`: lecture notes, papers, slides, transcripts, assignments. The worker reads them and, if they are not enough, fetches more once and saves it there.

## Optional files

- `order.json`: a list of task ids that sets the order; anything not listed follows in file order.

## Files the harness writes

- `.state/<id>.log` blocked tool calls; `.state/<id>.progress` touched on every message (used for the idle check); `.state/usage.jsonl` cost estimates; `.state/batch.log` coordinator events.
- `reports/<id>.md` per-task report; `reports/summary.md` wrap-up.
