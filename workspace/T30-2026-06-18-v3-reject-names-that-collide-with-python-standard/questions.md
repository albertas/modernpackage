# Research Questions

## Context
Focus on the CLI argument-handling and name-processing code in
`modernpackage/main.py` and its tests in `tests/`. The relevant areas are how a
user-supplied package name is validated, how it is transformed into an
import-safe module name, and how validation failures are surfaced to the user.

## Questions
1. How is a user-supplied package name validated today — where does validation
   run in the argument-parsing flow, what rules are applied, and how are
   rejections reported back to the user?
2. How is the accepted package name transformed into the module/directory name
   that is later imported, and at what point in the flow does that
   transformation happen relative to validation?
3. What is the runtime relationship between the validated input name and the
   final on-disk module name (case handling, separator substitution), and where
   is each form consumed downstream (e.g. directory creation, `just init`)?
4. What patterns exist in the codebase for raising and presenting input errors
   versus runtime/subprocess errors, and how do exit codes correspond to each?
5. What does the existing test suite cover for name validation and module-name
   normalization, including how valid/invalid cases are exercised and asserted?
6. What is the project's targeted Python version and dependency baseline, and
   what standard-library facilities for enumerating module names are available
   under that version?
