import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import {
    actionLabel,
    assessmentSummary,
    batchLabel,
    formatBaselTime,
    formatBaselTimeShort,
    formatKg,
    formatMinutes,
    formatProbability,
    incomingStatusLabel,
    isRetrospective,
    productionStatusLabel,
    qaReleaseLabel,
    qaReviewLabel,
    shipmentLabel,
    temperaturePresentation,
} from '../../resources/js/lib/batch-display.ts';

const assessments = JSON.parse(
    readFileSync(
        new URL('../../../output/batch-assessments-demo.json', import.meta.url),
        'utf8',
    ),
);

function freezeEvidence(value) {
    if (value !== null && typeof value === 'object') {
        for (const child of Object.values(value)) freezeEvidence(child);
        Object.freeze(value);
    }
    return value;
}

void test('formatting preserves zero, small nonzero values and absent evidence', () => {
    assert.equal(formatKg(0), '0 kg');
    assert.equal(formatKg(30), '30 kg');
    assert.equal(formatKg(20.25), '20.3 kg');
    assert.equal(formatKg(null), 'Unavailable');
    assert.equal(formatMinutes(0), '0 min');
    assert.equal(formatMinutes(0.017895), '<0.1 min');
    assert.equal(formatMinutes(99.49666380275252), '99.5 min');
    assert.equal(formatMinutes(null), 'Unavailable');
    assert.equal(formatProbability(0), '0%');
    assert.equal(formatProbability(1), '100%');
    assert.equal(formatProbability(0.9663), '96.6%');
    assert.equal(formatProbability(0.0001), '<0.1%');
    assert.equal(formatProbability(null), 'Unavailable');
});

void test('timestamps retain the instant and show the Basel summer/winter offset', () => {
    assert.equal(
        formatBaselTime('2026-10-03T12:00:00Z'),
        '3 Oct 2026, 14:00 GMT+02:00 (Basel)',
    );
    assert.equal(
        formatBaselTime('2026-01-03T12:00:00Z'),
        '3 Jan 2026, 13:00 GMT+01:00 (Basel)',
    );
    assert.equal(
        formatBaselTime('2026-10-03T14:00:00+02:00'),
        formatBaselTime('2026-10-03T12:00:00Z'),
    );
    assert.equal(formatBaselTime(null), 'Unavailable');
    assert.equal(formatBaselTime('invalid timestamp'), 'Unavailable');
    assert.equal(
        formatBaselTimeShort('2026-10-03T12:00:00Z'),
        '3 Oct, 14:00 UTC+02',
    );
    assert.equal(
        formatBaselTimeShort('2026-01-03T12:00:00Z'),
        '3 Jan, 13:00 UTC+01',
    );
    assert.equal(formatBaselTimeShort(null), 'Unavailable');
    assert.equal(formatBaselTimeShort('invalid timestamp'), 'Unavailable');
});

void test('identifiers are used only for display labels', () => {
    assert.equal(batchLabel(assessments[0].batch_id), 'Batch 001');
    assert.equal(shipmentLabel(assessments[0].shipment_ids[0]), 'Shipment 001');
    assert.equal(batchLabel('custom-batch'), 'custom-batch');
    assert.equal(shipmentLabel('custom-shipment'), 'custom-shipment');
    for (const record of assessments) {
        const relabeled = structuredClone(record);
        relabeled.batch_id = 'custom-batch';
        relabeled.shipment_ids = ['custom-shipment'];
        for (const shipment of relabeled.incoming_shipments) {
            shipment.shipment_id = 'custom-shipment';
        }
        for (const evidence of relabeled.product_temperature) {
            evidence.shipment_id = 'custom-shipment';
        }
        assert.deepEqual(
            assessmentSummary(relabeled),
            assessmentSummary(record),
        );
    }
});

void test('the v2 retrospective fixture retains its null action and recorded evidence', () => {
    const record = freezeEvidence(structuredClone(assessments[0]));
    const before = JSON.stringify(record);
    assert.equal(record.model_version, 'batch-stored-evidence-v2');
    assert.equal(record.recommendation.action, null);
    assert.equal(
        actionLabel(record.recommendation.action),
        'No forward action',
    );
    assert.equal(isRetrospective(record), true);
    const summary = assessmentSummary(record);
    assert.equal(summary.headline, 'Retrospective assessment');
    assert.match(summary.detail, /Charge deadline already passed/);
    assert.match(summary.detail, /No forward action is recorded/);
    assert.match(summary.detail, /temperature evidence are retained/);
    assert.match(summary.limitation, /historical QA or reservation state/);
    assert.equal(
        formatKg(record.production_readiness.released_reserved_quantity_kg),
        '50 kg',
    );
    assert.equal(
        incomingStatusLabel(record.incoming_shipments[0].status),
        'Arrived',
    );
    assert.equal(
        temperaturePresentation(record.product_temperature[0]).excursionLabel,
        '99.5 min observed',
    );
    assert.equal(JSON.stringify(record), before);
});

void test('supplied action labels preserve null and every supported logistics action', () => {
    assert.equal(actionLabel(null), 'No forward action');
    assert.equal(actionLabel('BUFFER'), 'BUFFER · use reserved stock');
    assert.equal(actionLabel('EXPEDITE'), 'Expedite shipment (EXPEDITE)');
    assert.equal(actionLabel('REROUTE'), 'Reroute shipment (REROUTE)');
});

void test('the deadline boundary controls retrospective presentation, not the batch identifier', () => {
    const record = structuredClone(assessments[2]);
    record.as_of = record.production_readiness.planned_charge_at;
    assert.equal(isRetrospective(record), true);
    record.as_of = new Date(Date.parse(record.as_of) - 1).toISOString();
    assert.equal(isRetrospective(record), false);
});

void test('batch 002 preserves 30 kg released reservations and 20 kg shortfall/dependency', () => {
    const record = assessments[1];
    const readiness = record.production_readiness;
    assert.equal(formatKg(readiness.required_quantity_kg), '50 kg');
    assert.equal(formatKg(readiness.released_reserved_quantity_kg), '30 kg');
    assert.equal(formatKg(readiness.reservation_shortfall_kg), '20 kg');
    assert.equal(formatKg(readiness.incoming_dependency_kg), '20 kg');
    assert.equal(formatKg(readiness.uncovered_quantity_kg), '0 kg');
    assert.equal(
        productionStatusLabel(readiness.status),
        'Incoming material needed',
    );
    assert.equal(
        assessmentSummary(record).headline,
        'Stock shortfall · temperature review required',
    );
    assert.equal(assessmentSummary(record).tone, 'alert');
    assert.equal(
        temperaturePresentation(record.product_temperature[0]).statusLabel,
        'Observed demo budget exceeded',
    );
    assert.equal(
        temperaturePresentation(record.product_temperature[0]).excursionLabel,
        '147.7 min observed',
    );
});

void test('batch 003 shows zero observed excursion together with an incomplete journey', () => {
    const record = assessments[2];
    const temperature = temperaturePresentation(record.product_temperature[0]);
    assert.equal(assessmentSummary(record).headline, 'Evidence incomplete');
    assert.equal(temperature.statusLabel, 'Partial temperature evidence');
    assert.equal(temperature.excursionLabel, '0 min observed');
    assert.equal(temperature.journeyLabel, 'Journey incomplete');
    assert.match(temperature.limitation, /usable sampled intervals only/);
    assert.match(
        temperature.limitation,
        /does not establish whole-journey compliance/,
    );
});

void test('batch 004 exposes absent measurements without presenting a false zero', () => {
    const record = assessments[3];
    const temperature = temperaturePresentation(record.product_temperature[0]);
    assert.equal(
        assessmentSummary(record).headline,
        'Evidence not yet available',
    );
    assert.equal(
        temperature.statusLabel,
        'Product-temperature evidence unavailable',
    );
    assert.equal(temperature.excursionLabel, '—');
    assert.equal(temperature.journeyLabel, 'Journey incomplete');
    assert.match(temperature.limitation, /unknown, not zero/);
    assert.equal(
        formatMinutes(record.product_temperature[0].reported_excursion_min),
        'Unavailable',
    );
});

void test('unusable intervals with readings keep null excursion unavailable', () => {
    const evidence = freezeEvidence({
        ...structuredClone(assessments[2].product_temperature[0]),
        status: 'UNAVAILABLE',
        reading_count: 2,
        observed_excursion_min: null,
        unobserved_interval_min: 180,
    });
    const before = JSON.stringify(evidence);
    const temperature = temperaturePresentation(evidence);
    assert.equal(temperature.excursionLabel, 'Unavailable');
    assert.equal(
        temperature.statusLabel,
        'Usable excursion duration unavailable',
    );
    assert.match(temperature.limitation, /gaps are not zero exposure/);
    assert.equal(JSON.stringify(evidence), before);
    const record = structuredClone(assessments[2]);
    record.product_temperature = [evidence];
    assert.equal(assessmentSummary(record).headline, 'Evidence unavailable');
});

void test('source-reported excursion never replaces a null, zero or positive observed duration', () => {
    const cases = [
        {
            reading_count: 0,
            status: 'UNAVAILABLE',
            observed_excursion_min: null,
            reported_excursion_min: 240,
            label: '—',
        },
        {
            reading_count: 2,
            status: 'UNAVAILABLE',
            observed_excursion_min: null,
            reported_excursion_min: 240,
            label: 'Unavailable',
        },
        {
            reading_count: 25,
            status: 'OBSERVED_WITHIN_BUDGET',
            observed_excursion_min: 0,
            reported_excursion_min: 240,
            label: '0 min observed',
        },
        {
            reading_count: 25,
            status: 'OBSERVED_WITHIN_BUDGET',
            observed_excursion_min: 99.49666380275252,
            reported_excursion_min: 240,
            label: '99.5 min observed',
        },
    ];
    for (const { label, ...fields } of cases) {
        const evidence = freezeEvidence({
            ...structuredClone(assessments[2].product_temperature[0]),
            ...fields,
        });
        const before = JSON.stringify(evidence);
        const presentation = temperaturePresentation(evidence);
        assert.equal(presentation.excursionLabel, label);
        assert.equal(presentation.journeyLabel, 'Journey incomplete');
        assert.equal(JSON.stringify(evidence), before);
    }
});

void test('temperature and production labels use backend states rather than new thresholds', () => {
    const exceeded = structuredClone(assessments[1].product_temperature[0]);
    exceeded.observed_excursion_min = 0;
    assert.equal(
        temperaturePresentation(exceeded).statusLabel,
        'Observed demo budget exceeded',
    );
    const within = structuredClone(assessments[0].product_temperature[0]);
    within.observed_excursion_min = 999;
    assert.equal(
        temperaturePresentation(within).statusLabel,
        'Last product reading outside range',
    );
    const record = structuredClone(assessments[1]);
    record.production_readiness.reservation_shortfall_kg = 0;
    record.production_readiness.released_reserved_quantity_kg = 999;
    assert.match(assessmentSummary(record).headline, /Stock shortfall/);
    assert.equal(
        productionStatusLabel('INSUFFICIENT_SUPPLY'),
        'Supply does not cover demand',
    );
});

void test('QA review is primary even when observed excursion is below the demo budget', () => {
    const evidence = freezeEvidence(
        structuredClone(assessments[0].product_temperature[0]),
    );
    const before = JSON.stringify(evidence);
    const display = temperaturePresentation(evidence, true);
    assert.equal(display.statusLabel, 'Human QA review required');
    assert.equal(display.tone, 'warning');
    assert.equal(display.excursionLabel, '99.5 min observed');
    assert.equal(display.budgetLabel, 'Below 120 min demo excursion budget');
    assert.equal(display.lastReadingLabel, '10.9 °C — outside 2–8 °C range');
    assert.equal(display.journeyLabel, 'Journey complete');
    assert.equal(JSON.stringify(evidence), before);
    const relabeled = {
        ...evidence,
        shipment_id: 'another-shipment',
        budget_min: 99.49666380275252,
    };
    assert.equal(
        temperaturePresentation(relabeled, true).budgetLabel,
        'At 99.5 min demo excursion budget',
    );
    assert.equal(
        temperaturePresentation({ ...evidence, budget_min: 90 }, true)
            .budgetLabel,
        'Above 90 min demo excursion budget',
    );
});

void test('partial and missing temperature evidence cannot imply QA clearance', () => {
    const partial = temperaturePresentation(
        assessments[2].product_temperature[0],
        true,
    );
    assert.equal(partial.statusLabel, 'Human QA review required');
    assert.equal(partial.excursionLabel, '0 min observed');
    assert.equal(
        partial.budgetLabel,
        'Below 120 min demo excursion budget · sampled intervals only',
    );
    assert.equal(partial.journeyLabel, 'Journey incomplete');
    assert.match(
        partial.limitation,
        /does not establish whole-journey compliance/,
    );
    const absent = temperaturePresentation(
        assessments[3].product_temperature[0],
        true,
    );
    assert.equal(
        absent.statusLabel,
        'Product-temperature evidence unavailable',
    );
    assert.equal(absent.excursionLabel, '—');
    assert.equal(absent.lastReadingLabel, 'Unavailable');
    assert.match(absent.budgetLabel, /comparison unavailable/);
    const unknownRange = {
        ...assessments[2].product_temperature[0],
        last_product_outside_range: null,
    };
    assert.equal(
        temperaturePresentation(unknownRange).lastReadingLabel,
        '5.0 °C — range comparison unavailable',
    );
    const complete = {
        ...assessments[2].product_temperature[0],
        complete_journey: true,
    };
    assert.equal(
        temperaturePresentation(complete, false).statusLabel,
        'Sampled temperature evidence available',
    );
});

void test('missing timing probabilities and ETAs remain unavailable with their backend reason', () => {
    for (const record of assessments.slice(1)) {
        const shipment = record.incoming_shipments[0];
        assert.equal(
            incomingStatusLabel(shipment.status),
            'Timing unavailable',
        );
        assert.equal(
            formatProbability(shipment.on_time_arrival_probability),
            'Unavailable',
        );
        assert.equal(
            formatProbability(shipment.cold_chain_exposure_proxy_risk),
            'Unavailable',
        );
        assert.equal(formatBaselTime(shipment.eta_p50), 'Unavailable');
        assert.equal(formatBaselTime(shipment.eta_p90), 'Unavailable');
        assert.ok(shipment.reason.length > 0);
        assert.equal(
            actionLabel(record.recommendation.action),
            'No forward action',
        );
    }
    assert.equal(incomingStatusLabel('MODELED'), 'Timing modeled');
});

void test('QA review stays distinct from logistics approval and release is never authorized', () => {
    for (const record of assessments) {
        assert.equal(
            qaReviewLabel(record.recommendation.qa_review_required),
            'Human QA review required',
        );
        assert.equal(
            qaReleaseLabel(record.recommendation.qa_release_authorized),
            'QA release authorized: No',
        );
        for (const temperature of record.product_temperature) {
            assert.equal(
                qaReleaseLabel(temperature.qa_release_authorized),
                'QA release authorized: No',
            );
        }
    }
    assert.equal(qaReviewLabel(false), 'QA review remains separate');
    assert.equal(
        qaReleaseLabel(undefined),
        'No QA release authorization supplied',
    );
    assert.equal(
        assessments[0].recommendation.requires_approval_by,
        'logistics',
    );
    assert.equal(
        assessments[1].recommendation.requires_approval_by,
        'logistics',
    );
});

void test('presentation does not mutate recommendations, alternatives or any evidence', () => {
    for (const fixture of assessments) {
        const record = freezeEvidence(structuredClone(fixture));
        const before = JSON.stringify(record);
        assessmentSummary(record);
        isRetrospective(record);
        actionLabel(record.recommendation.action);
        productionStatusLabel(record.production_readiness.status);
        for (const evidence of record.product_temperature)
            temperaturePresentation(evidence);
        assert.equal(JSON.stringify(record), before);
        assert.deepEqual(record.recommendation, fixture.recommendation);
    }
});
