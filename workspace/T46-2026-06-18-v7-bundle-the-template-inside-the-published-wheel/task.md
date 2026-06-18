# Task

Bundle the project template inside the published wheel so the `modernpackage`
CLI can scaffold a new package from template files shipped with the installed
package instead of cloning them over the network from GitHub. This removes the
runtime dependency on a reachable remote and makes scaffolding work offline,
while keeping the resulting package identical to what the clone-based flow
produced.
