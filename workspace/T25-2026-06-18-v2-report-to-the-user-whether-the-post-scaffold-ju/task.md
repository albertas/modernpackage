# Task

After scaffolding a new package, `modernpackage` runs `just check` inside it but
currently discards the result without telling the user the outcome. Report to
the user whether that post-scaffold `just check` passed or failed, so they know
immediately whether the freshly created package is valid.

Scope is limited to user-facing reporting; changing the process exit code when
`just check` fails is tracked as a separate backlog task and is out of scope here.
