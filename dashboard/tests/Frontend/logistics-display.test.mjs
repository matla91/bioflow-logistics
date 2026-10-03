import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import {
    formatMinutes,
    formatPercent,
    humanizeAlternativeReason,
    humanizeCounterfactual,
    humanizeRecommendationReason,
    recommendationSummary,
} from '../../resources/js/lib/logistics-display.ts';

const scenarios = ['normal', 'disruption', 'severe'].map((scenario) => ({
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

void test('probabilities and minutes use concise formatting without false zeroes', () => {
    assert.equal(formatPercent(1), '100%');
    assert.equal(formatPercent(0.9968), '99.7%');
    assert.equal(formatPercent(0.9663), '96.6%');
    assert.equal(formatPercent(0), '0%');
    assert.equal(formatPercent(0.0001), '<0.1%');
    assert.equal(formatPercent(0.001), '0.1%');
    assert.equal(formatMinutes(0), '0 min');
    assert.equal(formatMinutes(0.017895175758668502), '<0.1 min');
    assert.equal(formatMinutes(0.0999), '<0.1 min');
    assert.equal(formatMinutes(0.1), '0.1 min');
    assert.equal(formatMinutes(0.2778887828557802), '0.3 min');
    assert.equal(formatMinutes(6), '6 min');
});

for (const { scenario, result } of scenarios) {
    void test(`${scenario} uses backend-selected action without changing the JSON`, () => {
        const snapshot = JSON.stringify(result);
        const selected = result.actions.find(
            (candidate) => candidate.action === result.recommendation.action,
        );
        const summary = recommendationSummary(result);

        assert.ok(summary.startsWith(`In the simulation, ${selected.action} `));
        assert.ok(
            summary.includes(
                formatPercent(selected.production_continuity_probability),
            ),
        );
        assert.ok(
            summary.includes(
                formatPercent(selected.on_time_arrival_probability),
            ),
        );
        assert.ok(
            summary.includes(
                formatMinutes(selected.predicted_arrival_delay_min),
            ),
        );
        assert.ok(summary.includes('expected incoming delay'));
        assert.ok(!summary.includes('0.950'));
        assert.ok(
            !humanizeRecommendationReason(
                result.recommendation.reason,
            ).startsWith(`${selected.action}: production continuity`),
        );

        for (const explanation of Object.values(
            result.recommendation.why_not,
        )) {
            assert.ok(
                !humanizeAlternativeReason(explanation).includes(
                    'incoming mean lateness',
                ),
            );
        }

        for (const condition of result.recommendation.would_change_if) {
            const humanized = humanizeCounterfactual(condition);
            assert.ok(humanized.startsWith('If '));
            assert.ok(humanized.endsWith('(SIMULATED)'));
            assert.ok(!humanized.includes('planned_remaining_min'));
            assert.ok(!humanized.includes('production coverage'));
        }

        assert.equal(JSON.stringify(result), snapshot);
    });
}

void test('backend policy conclusions survive with percentage targets', () => {
    const { result: normal } = scenarios[0];
    const { result: disruption } = scenarios[1];
    const { result: severe } = scenarios[2];

    assert.equal(
        humanizeRecommendationReason(normal.recommendation.reason),
        'BUFFER meets the continuity target and both incoming shipment criteria; the modeled stock coverage needs no additional shipment intervention.',
    );
    assert.equal(
        humanizeRecommendationReason(disruption.recommendation.reason),
        'It meets the production continuity target 95%; eligible shipment interventions meeting that target are compared by lower exposure proxy, lower incoming lateness, then higher on-time arrival.',
    );
    assert.equal(
        humanizeAlternativeReason(disruption.recommendation.why_not.BUFFER),
        'Factory continuity alone is insufficient: incoming on-time arrival 27.9% is below 90%; cold-chain exposure proxy 76.6% exceeds 10%.',
    );
    assert.equal(
        humanizeAlternativeReason(disruption.recommendation.why_not.REROUTE),
        'Production continuity 41.3% is below the policy target 95%.',
    );
    assert.equal(
        humanizeAlternativeReason(severe.recommendation.why_not.BUFFER),
        'Factory continuity alone is insufficient: incoming on-time arrival 0% is below 90%; cold-chain exposure proxy 100% exceeds 10%.',
    );
});

void test('summary uses supplied action even when another action has higher metrics', () => {
    const result = structuredClone(scenarios[0].result);
    result.recommendation.action = 'REROUTE';

    assert.equal(
        recommendationSummary(result),
        'In the simulation, REROUTE has 76.9% production continuity and 76.9% on-time arrival, with 2.9 min expected incoming delay.',
    );
});

void test('missing selected action and reassessment preserve the supplied reason', () => {
    const result = structuredClone(scenarios[0].result);
    result.actions = [];
    result.recommendation.reason = 'Missing evidence requires operator review.';

    assert.equal(
        recommendationSummary(result),
        'In the simulation, BUFFER is recommended. Missing evidence requires operator review.',
    );

    result.recommendation.action = null;
    assert.equal(
        recommendationSummary(result),
        'Reassessment required. Missing evidence requires operator review.',
    );
});

void test('known counterfactuals retain number strings, semantics and provenance', () => {
    assert.equal(
        humanizeCounterfactual(
            'SIMULATED stock_available changed from 1 to 0 units: the paired model rerun selects EXPEDITE.',
        ),
        'If available factory stock changed from 1 to 0 units → EXPEDITE (SIMULATED)',
    );
    assert.equal(
        humanizeCounterfactual(
            'SIMULATED planned_remaining_min changed from 80 to 120 min: the paired model rerun selects EXPEDITE.',
        ),
        'If remaining journey time changed from 80 to 120 min → EXPEDITE (SIMULATED)',
    );
    assert.equal(
        humanizeCounterfactual(
            'SIMULATED protection_remaining_min changed from 080.50 to 120.00 min: the paired model rerun selects BUFFER.',
        ),
        'If remaining packaging protection changed from 080.50 to 120.00 min → BUFFER (SIMULATED)',
    );
    assert.equal(
        humanizeCounterfactual(
            'ASSUMED expedite_transport_factor changed from 0.70 to 1.0 factor: the paired model rerun selects REROUTE.',
        ),
        'If assumed expedited transport factor changed from 0.70 to 1.0 → REROUTE (ASSUMED)',
    );
});

void test('unexpected text falls back unchanged without discarding backend meaning', () => {
    const inputs = [
        '',
        'Operator review: production continuity 0.950 is provisional.',
        'BUFFER: custom reasoning 0.950 min. Keep this caveat.',
        'SIMULATED new_input changed from 80 to 120 min: the paired model rerun selects EXPEDITE.',
        'SIMULATED planned_remaining_min changed from 80 to 120 units: the paired model rerun selects EXPEDITE.',
        'ASSUMED planned_remaining_min changed from 80 to 120 min: the paired model rerun selects EXPEDITE.',
        'SIMULATED stock_available changed from 1 to 0 units: the paired model rerun selects EXPEDITE. A further caveat.',
    ];

    for (const input of inputs) {
        assert.equal(humanizeRecommendationReason(input), input);
        assert.equal(humanizeAlternativeReason(input), input);
        assert.equal(humanizeCounterfactual(input), input);
    }
});
