# Release commands

Run from repository root with the project virtual environment. Windows uses
`.venv/Scripts/python.exe`; Linux uses `.venv/bin/python`. No Bash-only helper.

```sh
python -m pip install -e '.[dev]'
python -m pip install setuptools==75.8.0 wheel==0.45.1
python scripts/release.py catalog
python scripts/release.py inventory
python scripts/release.py checkpoint
python -m pytest --scenario-acceptance --cov=agt_mcp --cov-fail-under=97
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m bandit -r src -q
python -m pip check
python scripts/release.py build
python scripts/release.py clean-install
```

`checkpoint` selects the release marker (configuration, deployment, security,
boundaries, MCP integrations and all diagnostic scenarios). Run focused tests
during changes and full regression only once at the final checkpoint. A failed
gate blocks release; do not weaken expectations. Build produces sdist, wheel and
dist/SHA256SUMS; output is local/ignored and nothing is published automatically.
Clean install creates/removes only its temporary venv, resolves constrained runtime
dependencies and invokes system_health from the installed wheel. It needs package
index access/cache; never reuses the development environment's site-packages.

Verify checksums with `Get-FileHash -Algorithm SHA256 dist/FILE` on PowerShell or
`sha256sum -c SHA256SUMS` after changing into `dist/` on Linux.
Archive artifacts/checksums with the final commit and trusted build provenance.
Checksums provide integrity, not authenticity; verify their origin separately.

Container build (replace placeholders with approved values):

```sh
docker build --build-arg PYTHON_IMAGE=python:3.12-slim@sha256:APPROVED_DIGEST --build-arg RELEASE_VERSION=1.0.0 --build-arg VCS_REF=COMMIT --build-arg SOURCE_URL=REPOSITORY_URL -t agt-mcp:1.0.0 .
python -m pytest -m real_lab --real-lab -q
```

Use project.version as RELEASE_VERSION; build fails on mismatch. Base image must
have an approved digest. SOURCE_URL/revision default to unknown if unavailable;
no unverified repository URL or license is invented. Pin updates require review;
archive resolved wheels for reproducibility. Linux-only constraints supplement the
existing Windows lock. Pinning is not a substitute for vulnerability monitoring.
Runtime install/run commands are in [installation](../installation/README.md).
