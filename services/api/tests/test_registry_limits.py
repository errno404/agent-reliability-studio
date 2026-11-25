import pytest
from app.registry import UnknownAgent, resolve


@pytest.mark.parametrize(
    "spec",
    [
        "live:research:v1?model=opus",
        "live:research:v1?budget=50",
        "live:research:v1?timeout=99999",
        "live:research:v1?budget=abc",
    ],
)
def test_live_spec_options_are_clamped_server_side(spec):
    with pytest.raises(UnknownAgent):
        resolve(spec)


def test_live_spec_defaults_resolve():
    r = resolve("live:research:v1?model=haiku&budget=0.25")
    assert r.execution_kind == "live" and r.config["per_run_budget_usd"] == 0.25
