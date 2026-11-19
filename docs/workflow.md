# Workflow for one task

Purpose: the steps the worker follows, in order. The task prompt in `runner/prompts.py` states the same steps.

1. **Read the documents.** The worker reads every file named in `rules_docs` in full, from the documents folder.
2. **Self-check.** Are the sources present and enough to write the page? If not, it fetches what it can once and saves it. If still not enough, it sets the row to `waiting_material` with a note saying what is missing, writes its report, and stops. It does not write an empty page.
3. **Claim.** `show` the row, then `update --expected-version <v> --owner <id> --status in_progress`.
4. **Write in blocks.** Writer subagents each write one block, started together. Blocks are assembled into the page.
5. **Check.** The style guide's checks run on the assembled file.
6. **Review.** One reviewer subagent reads the whole page and writes `must`, `should` and `nit` findings to a review file. It never edits the page.
7. **Fix.** The worker fixes every must and should, reruns the checks, and compares file hashes so an old result cannot pass a new file.
8. **Deliver.** `deliver --file <output>` stores the output path and sha256 and sets `delivered`.
9. **Report.** A one-page report: what was produced, sources, checks, review findings and handling, decisions, what was not done and why.
10. **Do not finish early.** Before stopping, list everything not done or not verified. Do what affects the reader; give one line of reason for the rest. Re-read the row and the documents and check the delivered file by its current hash.

If the worker is blocked, it decides by the rules and records the decision in the report; it never asks the user.
