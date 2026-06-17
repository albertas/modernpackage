# Task

When a scaffolding step (`git clone` or `just init`) fails, present the captured
stderr to the user as a clean, readable message instead of a raw Python
traceback. The stderr is already captured and attached to the raised
`RuntimeError` (from T17); this task ensures the user actually sees it.
