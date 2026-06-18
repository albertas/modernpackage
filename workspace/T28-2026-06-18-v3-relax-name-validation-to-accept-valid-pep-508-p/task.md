# Task

Relax the CLI package-name validation so it accepts any valid PEP 508 / PyPI
distribution name — including names containing hyphens (`-`), underscores (`_`),
and dots (`.`) between alphanumeric characters — instead of only strictly
alphanumeric names. This lets users scaffold packages with conventional
distribution names like `my-package` while still rejecting genuinely invalid
names.
