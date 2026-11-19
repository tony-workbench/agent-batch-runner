# Rules for every task

Purpose: the standing rules a worker reads before it starts any task. Edit this file to change behavior for all tasks.

## Boundaries
- Work only inside the folders the runner allows. Do not read secret files or print keys.
- Never ask the user questions. If you are blocked, set the task to `waiting_material` and say what is missing.
- Fetch missing sources once, save them under the task's source folder, and do not fetch them again.

## Quality
- Every number in the page comes from a recorded run or a cited source file.
- A runnable example is run for real, and its command and output are saved next to the page.
- Warnings and errors from runs stay in the record; explain them, do not hide them.

## Finishing
- Not finished until every not-done item is either done or explained in one line.
- A subagent's "done" is a claim: reopen the file and rerun the check.
- Verify the delivered file by its current hash, not by an earlier result.
