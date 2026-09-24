import pytest
from pydantic import ValidationError

from agt_mcp.configuration.probes import EnvironmentPolicy, ProbesConfig
from agt_mcp.probes.models import Endpoint, ProbePlan, ProbeTarget, ProbeType
from agt_mcp.probes.planner import target_from
from agt_mcp.probes.policy import ProbePolicy
from tests.correlation_support import NOW
from tests.probe_support import config, plan


@pytest.mark.parametrize(
    "host",
    [
        "http://169.254.169.254",
        "https://user:password@host",
        "user@host",
        "host/path",
        "host\\evil",
        "host\n",
        "2130706433",
        "127.1",
        "0177.0.0.1",
        "0x7f000001",
        "a..b",
        "-host",
        "a" * 64 + ".example",
        "fe80::1%eth0",
        "[::1]",
    ],
)
def test_invalid_target_host(host):
    with pytest.raises(ValidationError):
        config(host)


@pytest.mark.parametrize(
    "path",
    [
        "//evil",
        "/../x",
        "/%2fetc",
        "/?token=secret",
        "/x#fragment",
        "/x\r\nHost:evil",
        "https://evil",
    ],
)
def test_path_cannot_change_target_or_carry_credentials(path):
    with pytest.raises(ValidationError):
        config().endpoints[0].model_validate({**config().endpoints[0].model_dump(), "path": path})


@pytest.mark.parametrize(
    "address",
    [
        "169.254.169.254",
        "169.254.170.2",
        "100.100.100.200",
        "fd00:ec2::254",
        "0.0.0.0",
        "::",
        "224.0.0.1",
        "ff02::1",
        "255.255.255.255",
        "10.20.255.255",
        "172.16.0.1",
        "8.8.8.8",
        "garbage",
        "::ffff:169.254.169.254",
    ],
)
def test_unsafe_dns_answers_are_blocked(address):
    cfg = config()
    assert ProbePolicy(cfg).addresses(target_from(cfg.endpoints[0], NOW), (address,)) != "ALLOWED"


@pytest.mark.parametrize("address", ["10.20.1.2", "127.0.0.1", "::1", "::ffff:127.0.0.1"])
def test_approved_corporate_and_harness_networks(address):
    cfg = config()
    assert ProbePolicy(cfg).addresses(target_from(cfg.endpoints[0], NOW), (address,)) == "ALLOWED"


@pytest.mark.parametrize("address", ["127.0.0.1", "::1", "10.1.1.1", "169.254.1.2"])
def test_broad_network_is_not_explicit_private_permission(address):
    cfg = config()
    policy = cfg.policy.environments[0].model_copy(
        update={"allowed_networks": ("0.0.0.0/0", "::/0")}
    )
    cfg = cfg.model_copy(
        update={"policy": cfg.policy.model_copy(update={"environments": (policy,)})}
    )
    assert ProbePolicy(cfg).addresses(target_from(cfg.endpoints[0], NOW), (address,)) != "ALLOWED"


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"environment_id": "other"}, "ENVIRONMENT_DENIED"),
        ({"host": "evil.example"}, "TARGET_ORIGIN_DENIED"),
        ({"port": 22}, "TARGET_ORIGIN_DENIED"),
        ({"resource_id": "other"}, "TARGET_ORIGIN_DENIED"),
    ],
)
def test_caller_cannot_forge_target(change, reason):
    cfg = config()
    target = target_from(cfg.endpoints[0], NOW).model_copy(update=change)
    assert ProbePolicy(cfg).target(target, "demo", ProbeType.TLS, 3) == reason


@pytest.mark.parametrize(
    "case",
    [
        "source",
        "checksum",
        "reference",
        "host",
        "port",
        "protocol",
        "missing_policy",
        "timeout",
        "type",
        "denied_network",
        "empty_dns",
        "many_dns",
    ],
)
def test_fail_closed_policy(case):
    cfg = config()
    target = target_from(cfg.endpoints[0], NOW)
    if case in {"source", "checksum", "reference"}:
        field = {
            "source": "source_id",
            "checksum": "content_sha256",
            "reference": "source_reference",
        }[case]
        target = target.model_copy(
            update={"provenance": target.provenance.model_copy(update={field: "wrong"})}
        )
    p = cfg.policy.environments[0]
    changes = {
        "host": {"allowed_hosts": ()},
        "port": {"allowed_ports": ()},
        "protocol": {"allowed_protocols": ()},
        "denied_network": {"denied_networks": ("10.20.0.0/16",)},
    }
    if case in changes:
        cfg = cfg.model_copy(
            update={
                "policy": cfg.policy.model_copy(
                    update={"environments": (p.model_copy(update=changes[case]),)}
                )
            }
        )
    if case == "missing_policy":
        cfg = ProbesConfig(endpoints=cfg.endpoints)
    policy = ProbePolicy(cfg)
    if case in {"denied_network", "empty_dns", "many_dns"}:
        addresses = (
            ()
            if case == "empty_dns"
            else ("10.20.1.2",) * 20
            if case == "many_dns"
            else ("10.20.1.2",)
        )
        assert policy.addresses(target, addresses) != "ALLOWED"
    else:
        assert (
            policy.target(
                target,
                "demo",
                ProbeType.HTTP if case == "type" else ProbeType.TLS,
                50 if case == "timeout" else 3,
            )
            != "ALLOWED"
        )


def test_defaults_and_configuration_validation():
    assert not ProbesConfig().enabled and ProbesConfig().execution_mode == "plan_only"
    with pytest.raises(ValidationError):
        config(endpoints=(config().endpoints[0],) * 2)
    with pytest.raises(ValidationError):
        EnvironmentPolicy(environment_id="demo", allowed_ports=(0,))
    with pytest.raises(ValidationError):
        EnvironmentPolicy(environment_id="demo", allowed_networks=("bad",))
    cfg = config()
    with pytest.raises(ValidationError):
        config(policy={"environments": [cfg.policy.environments[0]] * 2})
    target = target_from(cfg.endpoints[0], NOW)
    with pytest.raises(ValidationError):
        ProbeTarget.model_validate(
            target.model_copy(update={"environment_id": "other"}).model_dump()
        )
    p = plan()
    with pytest.raises(ValidationError):
        ProbePlan.model_validate(p.model_copy(update={"environment_id": "other"}).model_dump())
    with pytest.raises(ValidationError):
        ProbePlan.model_validate(p.model_copy(update={"requests": p.requests * 2}).model_dump())
    assert Endpoint.hostname("EXAMPLE.COM.") == "example.com"
