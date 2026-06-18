# Task

Reject package names whose resulting import module name would collide with a
Python standard-library module (e.g. `json`, `os`, `email`). The goal is to stop
the scaffolder from creating packages that shadow stdlib modules, which would
break imports in the generated project. Validation should fail clearly before any
scaffolding work begins.
