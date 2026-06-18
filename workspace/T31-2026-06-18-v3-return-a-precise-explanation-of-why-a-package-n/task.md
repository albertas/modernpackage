# Task

When `modernpackage` refuses a package name, it should return a precise
explanation of *why* the name was refused (for example: the specific
disallowed character, a leading/trailing separator, an empty value, or a
standard-library collision) instead of a generic "Invalid package name"
message. The goal is to give users an actionable reason they can immediately
act on when correcting their package name.
