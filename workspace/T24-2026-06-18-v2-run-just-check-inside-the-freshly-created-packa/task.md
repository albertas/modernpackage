# Task

After `modernpackage` scaffolds a new package (git clone + `just init`), run
`just check` inside the freshly created package directory so the generated
project is verified to be in a working, lint/type/test-clean state immediately
after scaffolding.

The invocation itself is the scope of this task. Reporting whether the check
passed/failed, exiting non-zero on failure, and adding an e2e assertion are
tracked as separate sibling V2 backlog tasks and are out of scope here.
