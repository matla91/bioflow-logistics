from baselhack.scenario import build
from baselhack.simulator.journey import simulate
from baselhack.storage import canonical


def test_same_seed_byte_identical_timeline():
    scenario = build("s3_lowriver_2026-10-01")
    assert canonical(simulate(scenario, scenario["seed"])) == canonical(
        simulate(scenario, scenario["seed"])
    )


def test_different_seed_changes_journey():
    scenario = build("s3_lowriver_2026-10-01")
    assert canonical(simulate(scenario, 1)) != canonical(simulate(scenario, 2))
