# Style guide for the generated page

Purpose: what the HTML learning page must look like and which self-checks must pass.

## Page
- One self-contained `.html` file: inline CSS, no external scripts, readable on a phone.
- Structure: goal, prerequisites, short explanation blocks, worked example, exercise with answer, summary.
- Figures are inline SVG or embedded images with a caption that says what to look at.
- No placeholder text, no "TODO", no links to local absolute paths.

## Checks (run before review)
- The file parses as HTML and has a `<title>`.
- No text from the banned list: `TODO`, `lorem`, absolute local paths.
- Every code block that claims output matches a saved run record.
