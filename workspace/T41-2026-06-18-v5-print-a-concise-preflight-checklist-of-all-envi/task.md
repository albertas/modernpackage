# Task

Print a concise preflight checklist that surfaces every environment/precondition
check the `modernpackage` CLI runs before scaffolding (required tools on PATH,
target directory absent, template remote reachable, and any name validation), so
the user can see at a glance which checks ran and their outcome. This makes the
currently-silent preflight phase visible and sets up the follow-up work of
aborting early with a specific remediation hint when a check fails.
