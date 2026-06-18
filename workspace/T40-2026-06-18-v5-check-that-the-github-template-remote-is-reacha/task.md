# Task

Add a pre-flight reachability check that confirms the GitHub template remote
can be reached before the scaffolder attempts to clone it. The goal is to fail
fast with a clear, actionable message when the remote is unreachable (network
down, host unresolved, repository missing/private) instead of surfacing a raw
git clone failure partway through scaffolding.
