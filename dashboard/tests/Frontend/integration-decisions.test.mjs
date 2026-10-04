import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import {
    decisionForAssessment,
    integrationDecisionOptions,
    isNamedIntegrationDemo,
} from '../../resources/js/lib/integration-decisions.ts';

const roles = {
    BUFFER: 'operator',
    EXPEDITE: 'logistics',
    REROUTE: 'logistics',
};
const fixtures = {
    normal: 'SIM-BASEL-NORMAL',
    disruption: 'SIM-BASEL-DISRUPTION',
    severe: 'SIM-BASEL-SEVERE',
};
const assessments = Object.keys(fixtures).map((scenario) => ({
    assessment_id: `${scenario}-assessment`,
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

void test('dialog options come only from supplied eligible actions and server role concepts', () => {
    for (const assessment of assessments) {
        const options = integrationDecisionOptions(assessment, roles);
        assert.deepEqual(
            options.map((option) => option.action),
            assessment.result.actions
                .filter((option) => option.eligible)
                .map((option) => option.action),
        );
        assert.equal(options.filter((option) => option.recommended).length, 1);
        assert.equal(
            options.find((option) => option.recommended).action,
            assessment.result.recommendation.action,
        );
        for (const option of options)
            assert.equal(option.requiredRole, roles[option.action]);
        assert.equal(
            options.some((option) => option.action === 'QUARANTINE'),
            false,
        );
    }
});

void test('absent and ineligible actions cannot be fabricated as alternatives', () => {
    const assessment = structuredClone(assessments[0]);
    assessment.result.actions = assessment.result.actions.filter(
        (option) => option.action !== 'EXPEDITE',
    );
    assessment.result.actions.find(
        (option) => option.action === 'REROUTE',
    ).eligible = false;
    assert.deepEqual(
        integrationDecisionOptions(assessment, roles).map(
            (option) => option.action,
        ),
        ['BUFFER'],
    );
});

void test('a persisted human choice never replaces the backend recommendation', () => {
    const assessment = structuredClone(assessments[0]);
    const decision = { verdict: 'OVERRIDE', action: 'REROUTE' };
    const before = JSON.stringify(assessment);
    assert.equal(
        decisionForAssessment(assessment, {
            [assessment.assessment_id]: decision,
        }),
        decision,
    );
    integrationDecisionOptions(assessment, roles);
    assert.equal(assessment.result.recommendation.action, 'BUFFER');
    assert.equal(JSON.stringify(assessment), before);
});

void test('scenario decisions are looked up exclusively by assessment hash', () => {
    const decision = { verdict: 'APPROVE', action: 'BUFFER' };
    const decisions = { [assessments[0].assessment_id]: decision };
    assert.equal(decisionForAssessment(assessments[0], decisions), decision);
    assert.equal(decisionForAssessment(assessments[1], decisions), null);
    assert.equal(decisionForAssessment(assessments[2], decisions), null);
    const newAssessment = { ...assessments[0], assessment_id: 'new-hash' };
    assert.equal(decisionForAssessment(newAssessment, decisions), null);
    assert.equal(decisions[assessments[0].assessment_id], decision);
});

void test('only the explicit named simulated fixtures offer demo reopen', () => {
    for (const assessment of assessments)
        assert.equal(isNamedIntegrationDemo(assessment, fixtures), true);
    const altered = structuredClone(assessments[0]);
    altered.result.simulated_shipment.simulated = false;
    assert.equal(isNamedIntegrationDemo(altered, fixtures), false);
    altered.result.simulated_shipment.simulated = true;
    altered.result.shipment_id = 'ANOTHER-SHIPMENT';
    altered.result.simulated_shipment.shipment_id = 'ANOTHER-SHIPMENT';
    assert.equal(isNamedIntegrationDemo(altered, fixtures), false);
    altered.result.shipment_id = fixtures.normal;
    assert.equal(isNamedIntegrationDemo(altered, fixtures), false);
});

void test('a null recommendation stays null and the helpers preserve evidence', () => {
    const assessment = structuredClone(assessments[0]);
    assessment.result.recommendation.action = null;
    const before = JSON.stringify(assessment);
    assert.equal(
        integrationDecisionOptions(assessment, roles).some(
            (option) => option.recommended,
        ),
        false,
    );
    decisionForAssessment(assessment, {});
    isNamedIntegrationDemo(assessment, fixtures);
    assert.equal(JSON.stringify(assessment), before);
});
