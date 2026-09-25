from pathlib import Path

import yaml

from agt_mcp.configuration.probes import ProbesConfig

ROOT = Path(__file__).resolve().parents[2]


def test_probe_example_is_disabled_and_valid():
    data = yaml.safe_load((ROOT / "config/server/probes.example.yaml").read_text(encoding="utf-8"))
    config = ProbesConfig.model_validate(data["probes"])
    assert not config.enabled and config.execution_mode == "plan_only"
    assert config.policy.environments and config.endpoints


def test_sprint_checkpoint_and_architecture_docs():
    state = (ROOT / "PROJECT_STATE.md").read_text(encoding="utf-8-sig")
    checkpoint = state.split("## SPRINT CHECKPOINT")[1]
    assert "Sprint: 9" in checkpoint
    assert "789dd79c95c374b3ab87f6a4e7b2320abb15dac5" in checkpoint
    assert len(checkpoint.splitlines()) < 60
    for file in (
        "docs/architecture/virtual-trace-probes.md",
        "docs/security/probe-safety.md",
        "docs/adr/0019-virtual-trace-and-safe-probe-architecture.md",
    ):
        assert (ROOT / file).exists()
