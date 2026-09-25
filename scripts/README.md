# Release helpers

`python scripts/release.py checkpoint` runs the consolidated offline release marker.
`catalog` and `inventory` generate tool and installed-dependency/license documentation.
`build` produces local source/wheel artifacts and SHA256SUMS under ignored dist/.
`clean-install` creates a temporary isolated environment, installs constrained runtime
requirements and runs scripts/smoke_installed.py; package index/cache access is needed.
Only that temporary environment is cleaned up. No publication, Git tag, cluster
provisioning or remediation is performed. See [commands](../docs/release/commands.md).
