# Human decisions on stored logistics assessments

On `feat/demo-polish`, `/integration` ends each named logistics recommendation with **Approve** and **Override recommendation**. Python owns the stored recommendation, eligibility, probabilities and evidence. Laravel records a separate human decision; neither button modifies a model result or the engine database. Batch assessments and the existing shipment decision workflow retain their own behavior.

## External identity and persistence

The Laravel `integration_decisions` table has a unique external `assessment_id`, not a foreign key to Laravel shipments or assessments. It stores the Python `input_sha256`, `model_version`, `scenario`, external shipment ID and recommended action, plus the human verdict, selected action, authenticated user ID and role, required reason, decision time and Laravel timestamps. `assessment_snapshot` retains the complete API response as JSON for audit, including the returned action set and provenance. Evidence hashes are retained verbatim, never recomputed from Laravel's JSON serialization.

Normal, Disruption and Severe refer to the existing Python fixtures `SIM-BASEL-NORMAL`, `SIM-BASEL-DISRUPTION` and `SIM-BASEL-SEVERE`. None is linked to the unrelated Laravel `s1`, `s2` or `s3` scenes. A decision belongs only to its exact external hash. A new hash starts without a human decision; older records remain stored audit history. The API exposes immutable records, not a unique latest revision ordering for equal scenario cutoffs, so the page retains explicit stored-record selection rather than guessing revision recency.

## Submission validation

The authenticated POST route is `/integration/assessments/{assessmentId}/decisions`. Laravel freshly GETs `/api/integration/assessments/{assessment_id}` from the configured integration service. It verifies the response hash matches the route and compares all displayed identity fields with the fresh response: assessment hash, input hash, model version, scenario, external shipment ID and recommendation. A missing, malformed, changed or unavailable record fails closed with a reload message.

The chosen action must be present and eligible in the returned action set. APPROVE selects the recommendation; OVERRIDE selects a different eligible action. Both require a nonempty reason of at most 1,000 characters. User ID, role, selected-action eligibility and model truth are not accepted from Vue. A database uniqueness constraint prevents concurrent or repeated submissions from replacing an existing decision.

BUFFER requires Operator; EXPEDITE and REROUTE require Logistics, reusing `ShipmentAction::approver()`. Overrides require the selected action's role. The Python logistics contract has no QA disposition action; ambient exposure remains a proxy and never becomes `p_excursion` or QA release authorization.

## Presentation and rehearsal

The model action and explanation stay visible above the human-decision area. After submission, the page displays the chosen human action, approve/override status, actor, role and Basel-local timestamp. The existing verdict dialog and decision-log presentation are shared with the shipment console, without fabricating shipment simulation metrics. Alternative buttons use only eligible actions supplied in the selected Python record.

Scenario switching keys both the persisted-decision lookup and the decision panel by `assessment_id`. Switching destroys an unfinished dialog and reason draft. Persistence is read from Laravel after submission and survives a full reload; no local Vue decision state substitutes for it.

The authenticated DELETE route on the same URL offers **Reopen demo decision** only for the known fixture external IDs listed in `dashboard/config/integration.php`, with matching named scenario and an explicit simulated-shipment flag. The server rechecks the source identity and requires the recorded decision's role. Reset deletes only that Laravel human decision. It cannot modify or delete any Python evidence, another scenario's decision, or a shipment-console decision. Reopening removes that demo decision's trace by design; ordinary records cannot use this rehearsal operation.

## Run and check

Apply the additive migration to the **Laravel** database, then rebuild the dashboard:

```sh
cd dashboard
pixi run php artisan migrate
npm run build
pixi run php artisan test --compact tests/Feature/IntegrationDecisionTest.php tests/Feature/IntegrationTest.php tests/Feature/ShipmentDecisionTest.php
node --test tests/Frontend/*.test.mjs
npm run types:check
```

Keep the integration read API running. Approve Normal as the demo Operator and Disruption/Severe as the demo Logistics user. Reset with the same role to rehearse again. This records a demonstration decision on a historical simulated scenario, not execution of a transport action or pharmaceutical QA release.
