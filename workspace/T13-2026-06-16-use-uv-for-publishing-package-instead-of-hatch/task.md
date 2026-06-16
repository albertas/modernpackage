# Task

Replace `hatch` with `uv` as the tool used to build and publish the package to a
package index. The publishing flow (currently `hatch build` + `hatch publish`)
should run through `uv` instead, and `hatch`-specific configuration and
dependencies should be updated or removed accordingly so the project no longer
relies on the `hatch` CLI for releasing.
