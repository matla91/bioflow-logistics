# Decision rules

All numerical thresholds live in config/thresholds.yaml, config/material.yaml or config/site.yaml. No scene id selects a recommendation.

| Action | Recommend when | Reject when | Approver |
| --- | --- | --- | --- |
| RUN_AS_PLANNED | Miss-slot probability is low; excursion budget has configured headroom | Baseline is risky, suspended, or another candidate has lower expected delay | operator |
| EXPEDITE | Simulated faster same-route slot reduces expected delay for a late lot | Route itself is blocked, baseline is already timely, or no faster variant improves it | logistics |
| BUFFER | Stock covers a batch and baseline is late or risky | Stock is insufficient or the baseline already meets the slot safely | operator |
| REROUTE | Alternative truck route can meet the slot with no increased excursion risk | Its excursion risk is higher or slot-miss probability exceeds the configured low threshold | logistics |
| QUARANTINE | Measured simulated budget usage exceeds one, or simulated probability of exceeding it reaches the configured threshold | No measured/predicted exceedance above that threshold | QA |

Quarantine is checked first. Otherwise select the eligible action with minimum expected batch delay. Equal-delay ties preserve the table action order (RUN_AS_PLANNED, EXPEDITE, BUFFER, REROUTE, QUARANTINE). If there is no eligible action, fail for reassessment rather than invent a safe recommendation.

The quarantine probability cutoff is an ASSUMED demonstration policy. Exact 120-minute usage is not above the allowance; exceedance is strictly greater. Stock does not make an unsafe incoming lot safe: the quarantine check remains first. Baseline lot excursion probability remains visible for BUFFER, even though stock serves the batch.

The demo server enforces the required role label on log writes. Approve and override both require a reason; override additionally requires a chosen action. Any decision involving a quarantined lot requires QA. There is no production authentication or real lot-release workflow in this skeleton.
