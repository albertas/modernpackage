# Research Questions

## Context
Focus on the `modernpackage/main.py` CLI scaffolder, the `backend_template/`
directory it injects, and the `docs/` reference material (especially
`fastapi_backend.md` and `reactjs_frontend.md`). The relevant flows are CLI
argument parsing, optional template injection, dependency/Justfile/dry-run
wiring, and how generated-package quality gates are satisfied.

## Questions
1. How is an optional store-true CLI flag with an alias defined, parsed, and
   threaded from `parse_args` through `main` into `init_new_package`, and where
   does its boolean value influence scaffolding behavior?
2. How does the existing template-injection path work end-to-end — how is the
   `backend_template/` tree located, copied into a freshly cloned package,
   staged for `just init`, and what makes its injection conditional and absent
   by default?
3. How are extra runtime/dev dependencies, Justfile recipes, and dry-run plan
   lines added to a generated package when an optional feature flag is set, and
   how are those additions kept out of the default scaffold?
4. What does the `backend_template/` provide at runtime — particularly the
   FastAPI application factory, health endpoints, and any OpenAPI/schema
   surface — and how is its test suite structured to satisfy the generated
   package's `just check` coverage gate?
5. What does `docs/reactjs_frontend.md` document regarding project structure,
   Vite, unit testing, and backend API schema synchronization, and what
   concrete tooling/commands does it recommend?
6. How do `just check`, `just init`, and the generated package's `Justfile` and
   `pyproject.toml` define and run quality gates today, and what mechanisms
   exist (or would be needed) to invoke a non-Python (Node-based) test/build
   step from that flow?
7. How are the CLI's behaviors verified in `tests/` — what patterns exist for
   mocking the clone/subprocess seams and asserting which files, dependencies,
   and recipes are injected for a given flag?
