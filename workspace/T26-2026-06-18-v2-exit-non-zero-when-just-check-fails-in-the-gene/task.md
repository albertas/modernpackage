# Task

Make the `modernpackage` CLI exit with a non-zero status code when the
post-scaffold `just check` fails inside the freshly created package. Today the
CLI already runs `just check` (T24) and prints whether it passed or failed
(T25), but it still exits 0 even on failure, so callers and CI cannot detect the
problem. This change propagates the `just check` failure into the process exit
code while preserving the existing pass/fail reporting.
