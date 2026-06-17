# Task

The `init_new_package` function in `modernpackage/main.py` runs `git clone` via
`Popen` but ignores its exit status, so a failed clone silently proceeds to run
`just init` on a missing or incomplete directory. Check the git clone
subprocess return code and treat any non-zero code as a failure so the flow
stops with a clear error instead of continuing.
