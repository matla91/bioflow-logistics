# Data sources and verification

Central collection stores normalized observations and their source metadata in local SQLite; see [DATA_ENGINE.md](DATA_ENGINE.md). The operational fixture in `output/operations-demo.json` is entirely synthetic. Its schedules, quantities, thermal constants and QA states come from `config/operations_demo.yaml`; they are demonstration assumptions, not provider measurements or release policy.

Retrieved 2–3 October 2026. Raw downloads stay in ignored data/raw/. Small scene evidence is in committed data/cache/. Real observations are never fabricated. Provider timestamps and values are preserved; sampling and simulated overrides are labelled.

| Source | Endpoint / use | Caveat |
| --- | --- | --- |
| WSV PEGELONLINE | https://www.pegelonline.wsv.de/webservices/rest-api/v2/stations/KAUB/W/measurements.json?start=P31D | W in gauge cm, negative datum readings are possible; 31-day window |
| WSV discharge | Same path with Q, including Mainz/Koblenz neighbours | Q in m³/s; optional anomaly check requires aligned evidence |
| Basel-Rheinhalle | Same paths with station Basel-Rheinhalle | TODO(verify): actual Basel navigation high-water stop |
| MeteoSwiss BAS | https://data.geo.admin.ch/ch.meteoschweiz.ogd-smn/bas/ogd-smn_bas_h_recent.csv | Semicolon, latin-1, tre200h0 hourly mean; reference timestamps UTC, not Swiss local time |
| MeteoSwiss historical | https://data.geo.admin.ch/ch.meteoschweiz.ogd-smn/bas/ogd-smn_bas_h_historical_2020-2029.csv | Currently ends 2025; current-year observations are in recent |
| MeteoSwiss daily | https://data.geo.admin.ch/ch.meteoschweiz.ogd-smn/bas/ogd-smn_bas_d_recent.csv | tre200dx confirms 39.7 °C on 30 July 2026; daily max is not an hourly ambient |
| Open-Meteo archive | https://archive-api.open-meteo.com/v1/archive with Rotterdam 51.92, 4.48, hourly temperature_2m, timezone UTC | Weather reanalysis, not a physical station measurement |
| Basel counts | https://data.bs.ch/api/explore/v2.1/catalog/datasets/100006/records | Fields verified: zst_id, sitename, datetimefrom, total, lw, hourfrom; first page is a sample, not full history |
| Basel speeds | Same API, dataset 100356 | TODO(verify): speed mapping and coverage |
| Basel locations | Same API, dataset 100038 | Select active Rhine-port/A2 stations; first displayed A2 station was out of service, so it must not be picked blindly |

Downloaded Kaub window begins 2 September, not the requested 1 September. Its highest reading is 64 cm; it confirms −6 cm at 1 October 02:45 +02:00. The requested cache filename is retained, while its metadata records actual 2 September coverage and the unavailable 1 September observation; no value is invented. As v1.1 authorizes, the normal scene uses a separately labelled simulated normal river sensitivity value. An explicit July request returned no observations; the normal and heat scenes' 150 cm sensitivity settings is **simulated**, kept outside rhine.kaub_cm, and cannot be presented as July river evidence.

[MeteoSwiss format documentation](https://opendatadocs.meteoswiss.ch/de/general/download) establishes UTC timestamps and hourly interval-ending semantics. [WSV API documentation](https://m.pegelonline.wsv.de/webservice/dokuRestapi) documents rolling coverage and gauge units. Long river history may be available via WSV HyDAS or FOEN; TODO(verify): obtain, audit and evaluate it before claiming forecast quality.

ASSUMED river bands, neutral traffic factor, thermal response, excursion budget, action variants and stock are model parameters. Production limits require the challenge pack, stability evidence and QA review. No dataset licence is replaced by the code licence; TODO(verify): document provider redistribution terms before public upload. Existing scene caches are preserved on repeated fetch; review raw/window files before intentionally updating evidence.


## Licences and publication gates

Verified 3 October against provider pages and dataset metadata:

| Provider | Licence and attribution | Evidence |
| --- | --- | --- |
| MeteoSwiss | CC BY 4.0; Source: MeteoSwiss, with no endorsement implied | [Official terms](https://opendatadocs.meteoswiss.ch/general/terms-of-use) |
| Open-Meteo | API data CC BY 4.0; Weather data by Open-Meteo.com, link licence and note processing | [Provider repository data licence](https://github.com/open-meteo/open-meteo#data-license), [API terms](https://open-meteo.com/en/terms) |
| PEGELONLINE | DL-DE-Zero-2.0; source still recorded for provenance | [Official terms](https://m.pegelonline.wsv.de/gast/nutzungsbedingungen) |
| Basel 100006 / 100356 | CC BY 4.0, Amt für Mobilität; no endorsement implied | [Count metadata](https://data.bs.ch/api/explore/v2.1/catalog/datasets/100006), [Speed metadata](https://data.bs.ch/api/explore/v2.1/catalog/datasets/100356) |
| Basel 100038 | CC BY 4.0 + OpenStreetMap; Geodaten Kanton Basel-Stadt | [Station metadata](https://data.bs.ch/api/explore/v2.1/catalog/datasets/100038); TODO(verify): OpenStreetMap-derived geometry conditions before redistributing those geometries |

Cache files retain observation values but trim provider datasets; calculated shipment/temperature histories are explicitly simulated. UI credits MeteoSwiss and Open-Meteo. No station geometry is currently committed. Raw traffic data stays ignored. Source data keeps provider terms; MIT applies to project code only. TODO(verify): organiser acceptance of MIT, and supplementary OpenStreetMap geometry conditions if those data are published. The licence gate remains failing for the unresolved condition, not for sources already verified above.

## Basel snapshot demo evidence

`data/cache/logistics_basel.json` contains only normalized **real observations**,
retrieved 3 October 2026 directly from the following providers. Every source
retains its exact query URL, retrieval timestamp, licence and SHA-256. ODS hashes
cover canonical raw records combined across pages; MeteoSwiss hashes cover the
downloaded CSV bytes. The stored subset is smaller than those upstream downloads.

| Provider | Observations used | Attribution and semantics |
| --- | --- | --- |
| [Basel 100089 metadata](https://data.bs.ch/api/explore/v2.1/catalog/datasets/100089) | 145 five-minute level/discharge readings, 30 September 00:00–12:00 UTC | BAFU via Open Data Basel-Stadt, CC0 1.0. FOEN station 2289. `pegel` is metres above sea level; `pegelhoehe` is cm above a 240 m datum; `abfluss` is m³/s. This is distinct from the older PEGELONLINE caches. |
| [Basel 100006 metadata](https://data.bs.ch/api/explore/v2.1/catalog/datasets/100006) | Station 402, Hochbergerstrasse 55: 13 earlier Wednesdays, 1 July–23 September, plus 30 September's complete local 13:00–14:00 interval | Amt für Mobilität, CC BY 4.0. Two approved lane/direction counts are summed per UTC interval. Latest station sum is 1262 vehicles. The single selected station is a demonstration signal; route representativeness is unvalidated. |
| [MeteoSwiss BAS hourly CSV](https://data.geo.admin.ch/ch.meteoschweiz.ogd-smn/bas/ogd-smn_bas_h_recent.csv) | Seven hourly interval endings, 30 September 06:00–12:00 UTC | Source: MeteoSwiss, CC BY 4.0. Latest ambient mean 26.4 °C. `tre200h0` °C, `rre150h0` mm, `fkl010h0` m/s, `ure200h0` %. [Format documentation](https://opendatadocs.meteoswiss.ch/general/download) specifies semicolon, Windows-1252, UTC interval endings, and blank missing values. |

The traffic subset intentionally covers only one local weekday/hour cell; it is
not a baseline for all stations and hours. Mean and sample standard deviation
are learned from distinct earlier local dates; the target date and future values
are excluded. DST repeated hours remain distinct UTC intervals, then average into
one daily sample. Approved replacement counts may be used as provider values;
unapproved, missing, conflicting or visibly incomplete lane groups fail ingestion.
Entirely absent lanes cannot be proven complete without a station coverage audit.

Rhine slopes use the preceding six-hour subset, not the whole cached day. BAS
observations identify the end of an hourly interval. No forecast or product
temperature is inferred from them. The cache was retrieved after the scenario
date; historical publication availability and provider revisions are unknown,
so this is a retrospective demonstration, not a real-time backtest.

`scenarios/logistics_demo.json`, `scenarios/logistics/`, `config/logistics.yaml`
and `config/logistics_scenarios/` contain **simulated or assumed** inputs
exclusively. They include shipment/stock, packaging autonomy,
route durations, action effects, minute coefficients and proxy thresholds.
The exposure budget is not a pharmaceutical stability limit. The reproducible
demo uses this fixed historical cache; refresh writes another file and never
rewrites the bundled evidence. Provider provenance/attribution travels in every
output JSON object: the primary contract carries concise provenance while full
URLs, retrieval times, licences and hashes remain in detailed output. No official
Rhine/BAFU forecast feed is integrated by the contract refinement. Its future
adapter accepts identified, validity-bounded official input; without that input,
navigation state and delay remain explicitly ASSUMED. State bands apply to modelled
delay minutes, never purported official water-level or discharge thresholds.
