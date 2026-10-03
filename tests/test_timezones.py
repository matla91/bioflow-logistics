from datetime import datetime

import pytest
from baselhack.simulator.journey import ambient_at
from baselhack.storage import read_json


def test_exact_utc_hour_and_offset_equivalence():
    scenario = read_json("snapshots/s2_heat_2026-07-30/scenario.json")
    local = datetime.fromisoformat("2026-07-30T16:35:12.123+02:00")
    utc = datetime.fromisoformat("2026-07-30T14:00:00+00:00")
    assert ambient_at(scenario, "basel", local) == ambient_at(scenario, "basel", utc)
    assert ambient_at(scenario, "basel", utc) > 35


def test_missing_hour_fails_without_default():
    scenario = {"ambient": {"basel": []}, "overrides": {}}
    with pytest.raises(ValueError, match="exact UTC hour"):
        ambient_at(
            scenario, "basel", datetime.fromisoformat("2026-07-30T14:00:00+00:00")
        )
