from pathlib import Path

from agt_mcp.configuration.loader import load_configuration

ROOT = Path(__file__).resolve().parents[2]


def test_disabled_example_loads_offline_without_resolving_credentials():
    config = load_configuration(
        [
            ROOT / "config/server/local.example.yaml",
            ROOT / "config/server/observability.example.yaml",
        ],
        environ={},
    )
    source = config.observability.sources[0]
    assert not source.enabled and source.tls.verify
    assert source.credentials.reference == "PROMETHEUS_TOKEN"
    assert source.network_policy.allowed_hosts == ("prometheus.example",)


def test_required_docs_and_current_checkpoint():
    for path in (
        "docs/architecture/observability-correlation.md",
        "docs/security/observability-data-access.md",
        "docs/development/sprint-8-validation.md",
        "docs/development/diagnostic-scenario-harness.md",
        "docs/development/sprint-9-validation.md",
    ):
        assert (ROOT / path).is_file()
    state = (ROOT / "PROJECT_STATE.md").read_text(encoding="utf-8")
    assert "Sprint: 9" in state and "Impact: MEDIUM" in state
    assert "Base commit: 789dd79c95c374b3ab87f6a4e7b2320abb15dac5" in state
