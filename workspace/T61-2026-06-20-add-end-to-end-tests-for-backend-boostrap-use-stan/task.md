# Task

Add an end-to-end test for the backend scaffold, placed in a dedicated standalone
end-to-end tests directory (separate from the existing package unit-test layout).
The test scaffolds a backend application, brings it up against a real database,
and asserts the health-check endpoint reports database connectivity is working.

It then exercises a real schema change: introduce a `products` table, generate and
apply the migration through the scaffold's own Justfile migration target, and
verify the health check still passes after the database has been modified.
