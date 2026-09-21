from pathlib import Path

from agt_mcp.cli import main

ROOT = Path(__file__).resolve().parents[2]


def test_offline_config_cli(capsys):
    args = ["validate-config"]
    for path in sorted((ROOT / "config").glob("*.example.yaml")):
        args.extend(["--file", str(path)])
    assert main(args) == 0
    assert "PASS" in capsys.readouterr().out


def test_offline_mapping_cli(capsys):
    for path in (ROOT / "mappings").rglob("*.yaml"):
        assert main(["validate-mapping", str(path)]) == 0
    assert "PASS" in capsys.readouterr().out


def test_cli_failure_hides_input(tmp_path, capsys):
    path = tmp_path / "invalid.yaml"
    path.write_text("application: {password: synthetic-sensitive-value}", encoding="utf-8")
    assert main(["validate-config", "--file", str(path)]) == 1
    output = capsys.readouterr().out
    assert "FAIL: configuration" in output
    assert "synthetic-sensitive-value" not in output


def test_cli_help(capsys):
    assert main([]) == 0
    assert "validate-config" in capsys.readouterr().out
