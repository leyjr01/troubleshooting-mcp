from pathlib import Path

from agt_mcp.configuration.loader import load_configuration
from agt_mcp.mapping.schema import load_mapping

ROOT = Path(__file__).resolve().parents[2]


def test_compact_checkpoint_and_permanent_instructions():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    state = (ROOT / "PROJECT_STATE.md").read_text(encoding="utf-8")
    assert len(agents.splitlines()) <= 120
    assert len(state.splitlines()) <= 250
    assert "Read PROJECT_STATE.md first" in agents
    assert "## SPRINT CHECKPOINT" in state
    checkpoint = state.split("## SPRINT CHECKPOINT", 1)[1]
    assert len(checkpoint.splitlines()) <= 60
    for field in ("Commit:", "Status:", "Tests:", "Next:"):
        assert field in checkpoint


def test_knowledge_configuration_examples():
    for name in ("local-git", "official-docs", "incident-source"):
        configuration = load_configuration(
            [
                ROOT / "config/server/local.example.yaml",
                ROOT / f"config/knowledge/{name}.example.yaml",
            ],
            environ={},
        )
        assert len(configuration.knowledge_sources) == 1
        assert not configuration.knowledge_sources[0].enabled
    assert (
        load_mapping(ROOT / "config/knowledge/incident-mapping.example.yaml").entity == "Incident"
    )
