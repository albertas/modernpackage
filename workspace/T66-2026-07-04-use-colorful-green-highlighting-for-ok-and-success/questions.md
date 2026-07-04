# Research Questions

## Context
Focus on the command-line output layer in `modernpackage/main.py` — the
`_format_*` / `_print_*` helper functions, the preflight-check flow, and the
package-initialization command. Also look at dependency configuration in
`pyproject.toml` and the corresponding tests under `tests/`.

## Questions
1. How does the CLI currently produce terminal output — which functions build
   output strings, which functions print them, and is any styling, ANSI escape
   code, or color library involved today?

2. What is the complete sequence of messages emitted during package
   initialization (from preflight checks through the post-scaffold summary and
   next-steps hint), including which are separate `print` calls and how blank
   lines / section separation are currently handled?

3. Where in the output strings do affirmative status words appear (for example
   `[ok]` markers, "passed", "success", "valid"), and how are the corresponding
   negative/failure markers (for example `[FAIL]`) constructed?

4. How are the output-formatting helpers (`_format_check_line`,
   `_format_init_summary`, `_format_next_commands`, `_format_dry_run_plan`)
   tested, and what exact string content do those tests assert on?

5. What are the project's runtime dependencies and dependency-management
   conventions (per `pyproject.toml`), and does any code detect whether stdout
   is a TTY or otherwise gate behavior on interactive vs piped output?

6. What lint/format/type rules apply to `main.py` output code (for example the
   `# noqa: T201` markers on `print`) that constrain how output is written?
