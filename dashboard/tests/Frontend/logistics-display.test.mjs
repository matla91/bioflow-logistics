import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import {
    formatMinutes,
    formatPercent,
    humanizeAlternativeReason,
    humanizeCounterfactual,
    humanizeRecommendationReason,
    metricStatus,
    policyCriteria,
    recommendationSummary,
    scenarioStatus,
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

function metricPrefix(action) {
    return `${action}: production continuity 0.960, incoming on-time arrival 0.940, cold-chain exposure proxy risk 0.150, incoming mean lateness 2.0 min. `;
}

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

void test('scenario status has explicit labels and neutral unknown fallback', () => {
    assert.deepEqual(scenarioStatus('normal'), {
        label: 'NORMAL CONDITIONS',
        tone: 'neutral',
    });
    assert.deepEqual(scenarioStatus('disruption'), {
        label: 'DISRUPTION DETECTED',
        tone: 'warning',
    });
    assert.deepEqual(scenarioStatus('severe'), {
        label: 'SEVERE DISRUPTION',
        tone: 'alert',
    });
    for (const key of ['', 'unexpected', 'NORMAL']) {
        assert.deepEqual(scenarioStatus(key), {
            label: 'SCENARIO STATUS UNKNOWN',
            tone: 'neutral',
        });
    }
});

const expectedSummaries = {
    normal: 'No additional shipment intervention is needed; modeled stock covers production and incoming shipment criteria are met.',
    disruption:
        'EXPEDITE is selected to meet the production continuity target under the shipment policy.',
    severe: 'REROUTE is selected to meet the production continuity target under the shipment policy.',
};

for (const { scenario, result } of scenarios) {
    void test(`${scenario} describes the backend-selected action without changing the JSON`, () => {
        const snapshot = JSON.stringify(result);
        const selected = result.actions.find(
            (candidate) => candidate.action === result.recommendation.action,
        );
        assert.equal(
            recommendationSummary(result),
            expectedSummaries[scenario],
        );
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
        }
        assert.deepEqual(policyCriteria(result.recommendation.policy_detail), {
            productionContinuityTarget: 0.95,
            bufferOnTimeTarget: 0.9,
            bufferExposureCap: 0.1,
        });
        assert.equal(JSON.stringify(result), snapshot);
    });
}

void test('backend policy explanations retain criteria, thresholds and their order', () => {
    const { result: normal } = scenarios[0];
    const { result: disruption } = scenarios[1];
    const { result: severe } = scenarios[2];
    assert.equal(
        humanizeRecommendationReason(normal.recommendation.reason),
        'BUFFER meets the production continuity and arrival targets, and stays within the exposure proxy limit. Modeled stock coverage needs no additional shipment intervention.',
    );
    assert.equal(
        humanizeRecommendationReason(disruption.recommendation.reason),
        'EXPEDITE meets the 95% production continuity target. The shipment policy compares eligible interventions by lower exposure proxy, then lower incoming lateness, then higher on-time arrival.',
    );
    assert.equal(
        humanizeRecommendationReason(severe.recommendation.reason),
        'REROUTE meets the 95% production continuity target. The shipment policy compares eligible interventions by lower exposure proxy, then lower incoming lateness, then higher on-time arrival.',
    );
    assert.equal(
        humanizeAlternativeReason(normal.recommendation.why_not.EXPEDITE),
        'Not needed: BUFFER already satisfies all policy criteria without additional shipment intervention.',
    );
    assert.equal(
        humanizeAlternativeReason(disruption.recommendation.why_not.BUFFER),
        'Production continuity alone is insufficient: incoming on-time arrival is 27.9%, below the 90% target; the cold-chain exposure proxy is 76.6%, above the 10% limit.',
    );
    assert.equal(
        humanizeAlternativeReason(disruption.recommendation.why_not.REROUTE),
        'Projected production continuity is 41.3%, below the required 95% target.',
    );
    assert.equal(
        humanizeAlternativeReason(severe.recommendation.why_not.BUFFER),
        'Production continuity alone is insufficient: incoming on-time arrival is 0%, below the 90% target; the cold-chain exposure proxy is 100%, above the 10% limit.',
    );
});

void test('continuity-only and below-target modes retain unmet criteria and reassessment', () => {
    const continuityOnly = `${metricPrefix('BUFFER')}BUFFER meets the continuity target 0.950; no eligible shipment intervention meets that target. Incoming shipment criteria remain unmet despite the factory stock coverage.`;
    assert.equal(
        humanizeRecommendationReason(continuityOnly),
        'BUFFER meets the 95% production continuity target, but no eligible shipment intervention meets it. Incoming shipment criteria remain unmet despite modeled factory stock coverage.',
    );
    const belowTarget = `${metricPrefix('EXPEDITE')}No eligible action meets the continuity target 0.950. This action has the highest modeled continuity; ties favor lower exposure proxy, lower incoming lateness, then deterministic action priority. Reassessment is needed.`;
    assert.equal(
        humanizeRecommendationReason(belowTarget),
        "No eligible action meets the 95% production continuity target. EXPEDITE has the highest modeled continuity; ties favor lower exposure proxy, then lower incoming lateness, then the policy's action priority. Reassessment is needed.",
    );
    const result = structuredClone(scenarios[0].result);
    result.recommendation.reason = continuityOnly;
    assert.equal(
        recommendationSummary(result),
        humanizeRecommendationReason(continuityOnly),
    );
    result.recommendation.action = 'EXPEDITE';
    result.recommendation.reason = belowTarget;
    assert.equal(
        recommendationSummary(result),
        humanizeRecommendationReason(belowTarget),
    );
});

void test('alternative comparisons retain individual failures and tie criteria', () => {
    const cases = [
        [
            'BUFFER',
            'Factory continuity alone is insufficient: incoming on-time arrival 0.200 is below 0.900.',
            'Production continuity alone is insufficient: incoming on-time arrival is 20%, below the 90% target.',
        ],
        [
            'BUFFER',
            'Factory continuity alone is insufficient: cold-chain exposure proxy 0.800 exceeds 0.100.',
            'Production continuity alone is insufficient: the cold-chain exposure proxy is 80%, above the 10% limit.',
        ],
        [
            'REROUTE',
            "Its continuity is lower than EXPEDITE's 0.940; no eligible action meets the target.",
            "Projected production continuity is below EXPEDITE's 94%; no eligible action meets the target.",
        ],
        [
            'REROUTE',
            "Its exposure proxy risk 0.150 is higher than EXPEDITE's 0.020.",
            "The cold-chain exposure proxy is 15%, above EXPEDITE's 2%.",
        ],
        [
            'REROUTE',
            "Exposure proxies are tied; its incoming mean lateness 2.0 min is higher than EXPEDITE's 1.0 min.",
            "Exposure proxies are tied; mean incoming lateness is 2 min, above EXPEDITE's 1 min.",
        ],
        [
            'REROUTE',
            "Exposure and incoming lateness are tied; its on-time arrival 0.900 is lower than EXPEDITE's 0.940.",
            "Exposure proxies and incoming lateness are tied; on-time arrival is 90%, below EXPEDITE's 94%.",
        ],
        [
            'REROUTE',
            'Decision dimensions are tied; deterministic action priority chooses EXPEDITE.',
            "Compared decision criteria are tied; the policy's action priority selects EXPEDITE.",
        ],
    ];
    for (const [action, reason, expected] of cases) {
        assert.equal(
            humanizeAlternativeReason(metricPrefix(action) + reason),
            expected,
        );
    }
});

void test('summary uses a safe reason fallback if selected action or metrics disagree', () => {
    const result = structuredClone(scenarios[0].result);
    const reason = result.recommendation.reason;
    result.recommendation.action = 'REROUTE';
    assert.equal(
        recommendationSummary(result),
        humanizeRecommendationReason(reason),
    );
    assert.equal(result.recommendation.action, 'REROUTE');
    result.recommendation.action = 'BUFFER';
    result.actions[0].production_continuity_probability = 0.5;
    assert.equal(
        recommendationSummary(result),
        humanizeRecommendationReason(reason),
    );
    result.actions = [];
    assert.equal(
        recommendationSummary(result),
        humanizeRecommendationReason(reason),
    );
});

void test('unknown reason is not interpreted from action name, metrics or scenario', () => {
    const result = structuredClone(scenarios[0].result);
    result.recommendation.reason = 'Missing evidence requires operator review.';
    assert.equal(recommendationSummary(result), result.recommendation.reason);
    result.recommendation.action = 'REROUTE';
    assert.equal(recommendationSummary(result), result.recommendation.reason);
    result.recommendation.action = null;
    assert.equal(
        recommendationSummary(result),
        'Reassessment required. Missing evidence requires operator review.',
    );
});

void test('policy criteria parse only explicit complete current backend policy wording', () => {
    const detail = scenarios[0].result.recommendation.policy_detail;
    assert.deepEqual(
        policyCriteria(
            detail
                .replace('0.950', '0.800')
                .replace('0.900', '1.000')
                .replace('0.100', '0.000'),
        ),
        {
            productionContinuityTarget: 0.8,
            bufferOnTimeTarget: 1,
            bufferExposureCap: 0,
        },
    );
    for (const text of [
        '',
        'production continuity target 0.950',
        detail.replace('ASSUMED', 'REAL'),
        detail.replace('BUFFER incoming', 'All actions incoming'),
        detail.replace('0.950', '1.950'),
        detail.replace('0.100', '-0.100'),
        detail.replace('0.900', 'NaN'),
        detail.replace('EXPEDITE before REROUTE', 'REROUTE before EXPEDITE'),
        detail + ' Additional policy caveat.',
    ]) {
        assert.equal(policyCriteria(text), null);
    }
});

void test('metric hints compare raw values to explicit targets and include boundaries', () => {
    assert.deepEqual(metricStatus(0.95, 0.95, 'minimum'), {
        label: 'meets target',
        symbol: '✓',
        tone: 'positive',
    });
    assert.deepEqual(metricStatus(0.9501, 0.95, 'minimum'), {
        label: 'meets target',
        symbol: '✓',
        tone: 'positive',
    });
    assert.deepEqual(metricStatus(0.9499, 0.95, 'minimum'), {
        label: 'below target',
        symbol: '↓',
        tone: 'warning',
    });
    assert.deepEqual(metricStatus(0.1, 0.1, 'maximum'), {
        label: 'within limit',
        symbol: '✓',
        tone: 'positive',
    });
    assert.deepEqual(metricStatus(0.0999, 0.1, 'maximum'), {
        label: 'within limit',
        symbol: '✓',
        tone: 'positive',
    });
    assert.deepEqual(metricStatus(0.1001, 0.1, 'maximum'), {
        label: 'exceeds limit',
        symbol: '↑',
        tone: 'warning',
    });
    assert.deepEqual(metricStatus(0, 0, 'minimum'), {
        label: 'meets target',
        symbol: '✓',
        tone: 'positive',
    });
    for (const threshold of [
        null,
        undefined,
        Number.NaN,
        Number.POSITIVE_INFINITY,
    ]) {
        assert.equal(metricStatus(0.95, threshold, 'minimum'), null);
    }
    for (const value of [Number.NaN, Number.POSITIVE_INFINITY]) {
        assert.equal(metricStatus(value, 0.95, 'minimum'), null);
    }
});

void test('counterfactual direction preserves number strings, action and provenance', () => {
    const cases = [
        [
            'SIMULATED stock_available changed from 1 to 0 units: the paired model rerun selects EXPEDITE.',
            'If available factory stock fell from 1 to 0 units → EXPEDITE (SIMULATED)',
        ],
        [
            'SIMULATED planned_remaining_min changed from 80 to 120 min: the paired model rerun selects EXPEDITE.',
            'If remaining journey time increased from 80 to 120 min → EXPEDITE (SIMULATED)',
        ],
        [
            'SIMULATED protection_remaining_min changed from 080.50 to 120.00 min: the paired model rerun selects BUFFER.',
            'If remaining packaging protection increased from 080.50 to 120.00 min → BUFFER (SIMULATED)',
        ],
        [
            'ASSUMED expedite_transport_factor changed from 0.70 to 1.0 factor: the paired model rerun selects REROUTE.',
            'If assumed expedited transport factor increased from 0.70 to 1.0 → REROUTE (ASSUMED)',
        ],
        [
            'SIMULATED planned_remaining_min changed from 80 to 080.00 min: the paired model rerun selects BUFFER.',
            'If remaining journey time changed from 80 to 080.00 min → BUFFER (SIMULATED)',
        ],
        [
            'ASSUMED expedite_transport_factor changed from 1e-1 to 0.05 factor: the paired model rerun selects EXPEDITE.',
            'If assumed expedited transport factor fell from 1e-1 to 0.05 → EXPEDITE (ASSUMED)',
        ],
    ];
    for (const [input, expected] of cases) {
        assert.equal(humanizeCounterfactual(input), expected);
    }
});

void test('unexpected text stays raw without discarding backend meaning or caveats', () => {
    const inputs = [
        '',
        'Operator review: production continuity 0.950 is provisional.',
        'BUFFER: custom reasoning 0.950 min. Keep this caveat.',
        metricPrefix('BUFFER') + 'New backend reasoning. Keep this caveat.',
        metricPrefix('BUFFER') +
            'Factory continuity alone is insufficient: ; cold-chain exposure proxy 0.800 exceeds 0.100.',
        metricPrefix('BUFFER') +
            'Factory continuity alone is insufficient: incoming on-time arrival 0.200 is below 0.900; .',
        scenarios[0].result.recommendation.reason + ' Additional uncertainty.',
        scenarios[1].result.recommendation.why_not.BUFFER +
            ' Additional uncertainty.',
        'SIMULATED new_input changed from 80 to 120 min: the paired model rerun selects EXPEDITE.',
        'SIMULATED planned_remaining_min changed from 80 to 120 units: the paired model rerun selects EXPEDITE.',
        'ASSUMED planned_remaining_min changed from 80 to 120 min: the paired model rerun selects EXPEDITE.',
        'SIMULATED stock_available changed from 1 to 0 units: the paired model rerun selects EXPEDITE. A further caveat.',
        'SIMULATED planned_remaining_min changed from 80 to 1e309 min: the paired model rerun selects EXPEDITE.',
        'Ineligible: route restriction requires operator review.',
    ];
    for (const input of inputs) {
        assert.equal(humanizeRecommendationReason(input), input);
        assert.equal(humanizeAlternativeReason(input), input);
        assert.equal(humanizeCounterfactual(input), input);
    }
});
