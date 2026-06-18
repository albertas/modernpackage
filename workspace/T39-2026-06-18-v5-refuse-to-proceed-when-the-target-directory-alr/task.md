# Task

Add a preflight check to the `modernpackage` scaffolder that refuses to proceed
when the target directory for the new package already exists, failing fast with
a clear, actionable error before any cloning or filesystem work begins. This
prevents accidentally writing into or colliding with an existing directory and
joins the other V5 preflight checks (e.g. the git/just/uv PATH check from T38).
