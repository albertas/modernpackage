# Task

Capture the stderr output from each subprocess call in `modernpackage/main.py`
instead of discarding it. The two `Popen` calls (`git clone` and `just init`)
currently only pipe stdout, so on failure the `RuntimeError` reports an exit
code but loses the underlying error text. Capturing stderr and including it in
the failure messages makes diagnosing subprocess failures possible.
