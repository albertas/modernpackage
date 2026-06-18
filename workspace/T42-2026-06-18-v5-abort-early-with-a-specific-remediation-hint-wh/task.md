# Task

Make the scaffolding CLI abort early — before any clone or filesystem mutation —
whenever a precondition fails, and have each failure emit a specific, actionable
remediation hint telling the user exactly how to resolve it. This builds on the
existing preflight check sequence so that every precondition that can fail
(invalid name, missing tools, occupied target directory, unreachable template
remote) stops the run with a clear, distinct fix-it message rather than a generic
or late error.
