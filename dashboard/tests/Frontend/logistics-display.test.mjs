import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import {
    humanizeAlternativeReason,
    humanizeCounterfactual,
    humanizeRecommendationReason,
    recommendationSummary,
    scenarioStatus,
    selectedActionResult,
} from '../../resources/js/lib/logistics-display.ts';

const scenarios = ['normal', 'disruption', 'severe'];
const records = scenarios.map((scenario) => ({
    scenario,
    result: JSON.parse(
        readFileSync(
            new URL(
                `../../../output/logistics-${scenario}.json`,
                import.meta.url,
            ),
            'utf8',
        ),
    ),
}));

function freezeEvidence(value) {
    if (value !== null && typeof value === 'object') {
        for (const child of Object.values(value)) freezeEvidence(child);
        Object.freeze(value);
    }
    return value;
}

void test('stored scenario fixtures supply BUFFER, EXPEDITE and REROUTE', () => {
    assert.deepEqual(
        records.map((record) => record.result.recommendation.action),
        ['BUFFER', 'EXPEDITE', 'REROUTE'],
    );
    for (const record of records) {
        assert.equal(
            selectedActionResult(record.result)?.action,
            record.result.recommendation.action,
        );
    }
});

void test('scenario labels describe selected scenarios without claiming a detected event', () => {
    assert.deepEqual(
        scenarios.map((scenario) => scenarioStatus(scenario).label),
        [
            'Normal scenario',
            'Disruption scenario',
            'Severe disruption scenario',
        ],
    );
    assert.deepEqual(scenarioStatus('unrecognized'), {
        label: 'Unknown scenario',
        tone: 'neutral',
    });
    for (const scenario of [...scenarios, 'unrecognized']) {
        assert.doesNotMatch(scenarioStatus(scenario).label, /detected/i);
    }
});

void test('action metrics follow the supplied recommendation even when scenario and metrics disagree', () => {
    for (const scenario of scenarios) {
        const record = structuredClone(records[0]);
        record.scenario = scenario;
        record.result.recommendation.action = 'REROUTE';
        for (const action of record.result.actions) {
            action.eligible = action.action !== 'REROUTE';
            action.production_continuity_probability =
                action.action === 'REROUTE' ? 0 : 1;
            action.on_time_arrival_probability =
                action.action === 'REROUTE' ? 0 : 1;
        }
        const selected = selectedActionResult(record.result);
        assert.equal(selected, record.result.actions[2]);
        assert.equal(selected.action, 'REROUTE');
        assert.equal(record.result.recommendation.action, 'REROUTE');
    }
});

void test('null recommendation and absent selected metrics stay absent', () => {
    const result = structuredClone(records[0].result);
    result.recommendation.action = null;
    result.recommendation.reason =
        'No eligible action. Operator reassessment needed.';
    assert.equal(selectedActionResult(result), null);
    assert.equal(
        recommendationSummary(result),
        'Reassessment required. No eligible action. Operator reassessment needed.',
    );
    result.recommendation.action = 'EXPEDITE';
    result.actions = result.actions.filter(
        (action) => action.action !== 'EXPEDITE',
    );
    assert.equal(selectedActionResult(result), null);
    assert.equal(result.recommendation.action, 'EXPEDITE');
    assert.equal(recommendationSummary(result), result.recommendation.reason);
});

void test('recognized supplied selection reasons produce concise summaries', () => {
    assert.equal(
        recommendationSummary(records[0].result),
        'No additional shipment intervention is needed; modeled stock covers production and incoming shipment criteria are met.',
    );
    for (const record of records.slice(1)) {
        assert.equal(
            recommendationSummary(record.result),
            `${record.result.recommendation.action} is selected to meet the production continuity target under the shipment policy.`,
        );
    }
    assert.match(
        humanizeRecommendationReason(records[1].result.recommendation.reason),
        /EXPEDITE meets the 95% production continuity target/,
    );
});

void test('unknown or partial backend reasons remain verbatim', () => {
    const reasons = [
        '',
        'Model evidence is insufficient; preserve this supplied explanation.',
        'EXPEDITE: production continuity 0.5, incoming on-time arrival 0.5',
        'REROUTE: production continuity 0.9, incoming on-time arrival 0.9, cold-chain exposure proxy risk 0.1, incoming mean lateness 1 min. A new backend policy explanation.',
    ];
    for (const reason of reasons) {
        assert.equal(humanizeRecommendationReason(reason), reason);
        assert.equal(humanizeAlternativeReason(reason), reason);
        const result = structuredClone(records[0].result);
        result.recommendation.reason = reason;
        assert.equal(recommendationSummary(result), reason);
    }
});

void test('alternative explanations preserve every supplied failed criterion', () => {
    const reason = records[1].result.recommendation.why_not.BUFFER;
    const display = humanizeAlternativeReason(reason);
    assert.match(
        display,
        /incoming on-time arrival is 27.9%, below the 90% target/,
    );
    assert.match(
        display,
        /cold-chain exposure proxy is 76.6%, above the 10% limit/,
    );
    const normalAlternative = humanizeAlternativeReason(
        records[0].result.recommendation.why_not.EXPEDITE,
    );
    assert.match(
        normalAlternative,
        /BUFFER already satisfies all policy criteria/,
    );
});

void test('paired rerun labels retain supplied values, action and provenance', () => {
    const supplied =
        'SIMULATED stock_available changed from 2 to 0 units: the paired model rerun selects EXPEDITE.';
    assert.equal(
        humanizeCounterfactual(supplied),
        'If available factory stock fell from 2 to 0 units → EXPEDITE (SIMULATED)',
    );
    const wrongProvenance = supplied.replace('SIMULATED', 'ASSUMED');
    assert.equal(humanizeCounterfactual(wrongProvenance), wrongProvenance);
    const unknown =
        'A backend-supplied sensitivity example with an unknown field.';
    assert.equal(humanizeCounterfactual(unknown), unknown);
});

void test('display functions never mutate recommendations, action metrics or evidence', () => {
    for (const fixture of records) {
        const record = freezeEvidence(structuredClone(fixture));
        const before = JSON.stringify(record);
        scenarioStatus(record.scenario);
        selectedActionResult(record.result);
        recommendationSummary(record.result);
        humanizeRecommendationReason(record.result.recommendation.reason);
        for (const reason of Object.values(
            record.result.recommendation.why_not,
        ))
            humanizeAlternativeReason(reason);
        for (const condition of record.result.recommendation.would_change_if)
            humanizeCounterfactual(condition);
        assert.equal(JSON.stringify(record), before);
        assert.deepEqual(
            record.result.recommendation,
            fixture.result.recommendation,
        );
    }
});
