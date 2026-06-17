# Task

Make the `modernpackage` CLI exit with a non-zero status code whenever a
scaffolding step (git clone or `just init`) fails. Today `main()` catches the
`RuntimeError` raised on failure, prints it to stderr, and returns normally —
so the process still exits 0, which hides the failure from shells and CI. This
change ensures a failed scaffold is reflected in the process exit status.
