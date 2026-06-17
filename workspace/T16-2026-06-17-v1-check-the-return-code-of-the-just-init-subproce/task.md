# Task

In `init_new_package()` (`modernpackage/main.py`), the `just init` subprocess
currently discards its output and never checks its exit status, so a failed
rewrite leaves the new package in a broken state silently. Inspect the
subprocess return code after `communicate()` and raise a `RuntimeError` when it
is non-zero, mirroring the `git clone` check added in T15, so `just init`
failures are surfaced as hard errors.
