"""Provider semantics, lane integrity, complete pagination and offline failures."""

from datetime import datetime, timedelta, timezone

import httpx
import pytest

from baselhack.ingestion import IngestionError, rhine, traffic, weather
from baselhack.ingestion.common import basel_records

UTC = timezone.utc
AT = datetime(2026, 9, 30, 12, tzinfo=UTC)


def traffic_lane(lane=1, total=766, **changes):
    return {
        "zst_id": 402,
        "datetimefrom": "2026-09-30T11:00:00+00:00",
        "datetimeto": "2026-09-30T12:00:00+00:00",
        "directionname": f"direction {lane}",
        "lanecode": lane,
        "valuesapproved": 1,
        "total": total,
        **changes,
    }


def hourly_csv(rows):
    return (
        "station_abbr;reference_timestamp;tre200h0;rre150h0;fkl010h0;ure200h0;note\n"
        + "\n".join(rows)
    )


def test_traffic_sums_distinct_lanes_after_deduplicating_identical_repeats():
    first, second = traffic_lane(), traffic_lane(2, 496)
    rows = traffic.parse_records([second, first, first.copy()])
    assert len(rows) == 1
    assert rows[0].vehicle_count == 1262
    assert rows[0].interval_end == AT
    assert rows[0].station_id == "402"


@pytest.mark.parametrize(
    ("bad_lane", "message"),
    [
        (traffic_lane(2, None), "Missing traffic total"),
        (traffic_lane(2, 496, valuesapproved=0), "partial station totals"),
        (traffic_lane(2, 496, valuesapproved=None), "partial station totals"),
        (traffic_lane(2, -3), "nonnegative"),
        (traffic_lane(2, 1.5), "vehicle count"),
        (traffic_lane(2, float("nan")), "finite"),
        (traffic_lane(2, 496, directionname=None), "identifiers"),
    ],
)
def test_traffic_never_returns_partial_or_invalid_station_count(bad_lane, message):
    with pytest.raises(IngestionError, match=message):
        traffic.parse_records([traffic_lane(), bad_lane])


def test_conflicting_duplicate_lane_is_rejected():
    with pytest.raises(IngestionError, match="Conflicting duplicate"):
        traffic.parse_records([traffic_lane(), traffic_lane(total=999)])


def test_missing_lane_from_one_hour_does_not_create_a_partial_station_total():
    with pytest.raises(IngestionError, match="Incomplete or changing"):
        traffic.parse_records(
            [
                traffic_lane(),
                traffic_lane(2, 496),
                traffic_lane(
                    datetimefrom="2026-09-30T12:00:00+00:00",
                    datetimeto="2026-09-30T13:00:00+00:00",
                ),
            ]
        )


def test_traffic_preserves_both_dst_fallback_hours_as_different_instants():
    rows = traffic.parse_records(
        [
            traffic_lane(
                datetimefrom="2026-10-25T02:00:00+02:00",
                datetimeto="2026-10-25T02:00:00+01:00",
            ),
            traffic_lane(
                datetimefrom="2026-10-25T02:00:00+01:00",
                datetimeto="2026-10-25T03:00:00+01:00",
            ),
        ]
    )
    assert len(rows) == 2
    assert rows[1].interval_start - rows[0].interval_start == timedelta(hours=1)


def test_rhine_maps_the_verified_units_and_datum_without_creating_readings():
    rows = rhine.parse_records(
        [
            {"timestamp": AT.isoformat(), "pegelhoehe": 481.5, "abfluss": 365.218},
            {
                "timestamp": (AT - timedelta(minutes=5)).isoformat(),
                "pegel": 244.812,
                "pegelhoehe": 481.2,
                "abfluss": None,
            },
        ]
    )
    assert rows[0].discharge_m3_s is None
    assert rows[1].level_masl == pytest.approx(244.815)
    assert rows[1].discharge_m3_s == 365.218
    assert rows[1].station_id == "2289"


@pytest.mark.parametrize(
    "row",
    [
        {"timestamp": AT.isoformat()},
        {"timestamp": AT.isoformat(), "abfluss": -1},
        {"timestamp": AT.isoformat(), "pegel": 244.8, "pegelhoehe": 1},
        {"timestamp": "2026-09-30T12:00:00", "pegel": 244.8},
    ],
)
def test_rhine_rejects_missing_data_bad_units_and_naive_timestamps(row):
    with pytest.raises(IngestionError):
        rhine.parse_records([row])


def test_conflicting_rhine_timestamp_is_rejected():
    with pytest.raises(IngestionError, match="Conflicting Rhine"):
        rhine.parse_records(
            [
                {"timestamp": AT.isoformat(), "pegel": 244.8},
                {"timestamp": AT.isoformat(), "pegel": 244.9},
            ]
        )


def test_weather_keeps_utc_interval_ending_and_optional_missing_fields():
    rows = weather.parse_csv(
        hourly_csv(
            [
                "BAS;30.09.2026 12:00;26.4;0;0.8;41.1;météo",
                "BAS;30.09.2026 11:00;25.1;;;;météo",
                "BAS;30.09.2026 10:00;;;;;météo",
            ]
        )
    )
    assert len(rows) == 2
    assert rows[0].precipitation_mm is None
    assert rows[0].wind_speed_m_s is None
    assert rows[0].relative_humidity_pct is None
    assert rows[1].t == AT  # Not shifted to local time or the next hour.
    assert rows[1].air_temperature_c == 26.4
    assert rows[1].wind_speed_m_s == 0.8


def test_weather_whitespace_fields_are_missing_not_invented_zeroes():
    rows = weather.parse_csv(hourly_csv(["BAS;30.09.2026 12:00;26.4; ;\t; ;"]))
    assert rows[0].precipitation_mm is None
    assert rows[0].wind_speed_m_s is None
    assert rows[0].relative_humidity_pct is None


def test_weather_rejects_wrong_station_and_wrong_timestamp():
    with pytest.raises(IngestionError, match="BAS"):
        weather.parse_csv(hourly_csv(["BER;30.09.2026 12:00;26.4;;;;"]))
    with pytest.raises(IngestionError, match="end on the hour"):
        weather.parse_csv(hourly_csv(["BAS;30.09.2026 12:30;26.4;;;;"]))


def test_complete_rhine_download_follows_every_page_in_order():
    records = [
        {"timestamp": (AT + timedelta(minutes=5 * i)).isoformat(), "pegel": 244.8}
        for i in range(205)
    ]
    offsets = []

    def handler(request):
        offset = int(request.url.params["offset"])
        offsets.append(offset)
        assert request.url.params["order_by"] == "timestamp asc"
        return httpx.Response(
            200,
            json={
                "total_count": len(records),
                "results": records[offset : offset + 100],
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        rows, source = rhine.download(AT, AT + timedelta(hours=18), client=client)
    assert offsets == [0, 100, 200]
    assert len(rows) == 205
    assert source.dataset == "100089"
    assert source.licence == "CC0 1.0"
    assert source.real_data is True
    assert len(source.sha256) == 64


@pytest.mark.parametrize("second_response", ["offline", "empty", "changed"])
def test_pagination_failure_never_returns_the_successful_first_page(second_response):
    def handler(request):
        offset = int(request.url.params["offset"])
        if offset == 0:
            return httpx.Response(200, json={"total_count": 101, "results": [{}] * 100})
        if second_response == "offline":
            raise httpx.ConnectError("offline", request=request)
        return httpx.Response(
            200,
            json={
                "total_count": 102 if second_response == "changed" else 101,
                "results": [],
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(IngestionError):
            basel_records("100089", "bounded", "timestamp asc", client=client)


def test_oversized_ods_query_fails_with_a_useful_window_instruction():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"total_count": 10001, "results": []})
    )
    with httpx.Client(transport=transport) as client:
        with pytest.raises(IngestionError, match="narrow the date window"):
            basel_records("100006", "bounded", "datetimefrom asc", client=client)


def test_repeated_page_cannot_silently_replace_history_with_deduplicated_rows():
    page = [{"value": i} for i in range(100)]
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"total_count": 200, "results": page})
    )
    with httpx.Client(transport=transport) as client:
        with pytest.raises(IngestionError, match="repeated an earlier page"):
            basel_records("100006", "bounded", "datetimefrom asc", client=client)


def test_traffic_download_selects_stations_and_only_completed_intervals():
    def handler(request):
        where = request.url.params["where"]
        assert "zst_id = 402" in where
        assert "datetimeto <=" in where
        return httpx.Response(
            200,
            json={"total_count": 2, "results": [traffic_lane(), traffic_lane(2, 496)]},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        rows, source = traffic.download(
            AT - timedelta(hours=1), AT, [402], client=client
        )
    assert rows[0].vehicle_count == 1262
    assert source.dataset == "100006"
    assert "CC BY" in source.licence


def test_weather_download_decodes_cp1252_and_filters_future_rows():
    text = hourly_csv(
        [
            "BAS;30.09.2026 12:00;26.4;0;0.8;41.1;météo",
            "BAS;30.09.2026 13:00;28.0;0;0.8;41.1;météo",
        ]
    )

    def handler(request):
        assert request.url.path.endswith("ogd-smn_bas_h_recent.csv")
        return httpx.Response(200, content=text.encode("cp1252"))

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        rows, source = weather.download(
            AT - timedelta(hours=1),
            AT,
            client=client,
            now=datetime(2026, 10, 3, tzinfo=UTC),
        )
    assert len(rows) == 1
    assert rows[0].t == AT
    assert source.provider == "MeteoSwiss"


def test_weather_current_day_combines_recent_and_now_with_latest_revision():
    urls = []

    def handler(request):
        urls.append(request.url.path)
        temperature = "26.4" if "recent" in request.url.path else "26.5"
        return httpx.Response(
            200,
            content=hourly_csv([f"BAS;30.09.2026 12:00;{temperature};;;;"]).encode(),
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        rows, _ = weather.download(
            AT - timedelta(hours=1), AT, client=client, now=AT + timedelta(hours=1)
        )
    assert len(urls) == 2
    assert len(rows) == 1
    assert rows[0].air_temperature_c == 26.5


def test_weather_historical_request_uses_the_correct_decade_file():
    start = datetime(2025, 12, 20, tzinfo=UTC)

    def handler(request):
        assert request.url.path.endswith("ogd-smn_bas_h_historical_2020-2029.csv")
        return httpx.Response(
            200, content=hourly_csv(["BAS;20.12.2025 01:00;5.1;;;;"]).encode()
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        rows, _ = weather.download(
            start,
            start + timedelta(hours=2),
            client=client,
            now=datetime(2026, 10, 3, tzinfo=UTC),
        )
    assert rows[0].air_temperature_c == 5.1


def test_weather_current_day_validation_handles_february_29():
    at = datetime(2024, 2, 29, 12, tzinfo=UTC)
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, content=hourly_csv(["BAS;29.02.2024 12:00;5.1;;;;"]).encode()
        )
    )
    with httpx.Client(transport=transport) as client:
        rows, _ = weather.download(
            at - timedelta(hours=1), at, client=client, now=at + timedelta(hours=1)
        )
    assert rows[0].t == at


def test_download_rejects_naive_window_before_any_request():
    with pytest.raises(IngestionError, match="explicit UTC offset"):
        rhine.download(datetime(2026, 9, 30), AT)
