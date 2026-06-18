# Task

Define an explicit precedence order for the sources that supply package
metadata (author name, author email, description, license, repository URL) so
that when a value is available from more than one source the strongest source
wins, in the order CLI flag > environment variable > git config > per-user
config file. The goal is to make this ordering a single, clearly-defined and
consistently-applied rule rather than behaviour that is implied by the order of
scattered fallback checks, so the resolution is unambiguous, documented, and
verifiable across every field.
