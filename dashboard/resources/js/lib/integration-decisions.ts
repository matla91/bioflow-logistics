import type { DecisionOption, HumanDecision } from '../types/console';
import type { StoredLogisticsAssessment } from '../types/integration';
import type {
    IntegrationActionRoles,
    IntegrationDecisions,
    IntegrationDemoShipments,
} from '../types/integration-decisions';

export function integrationDecisionOptions(
    assessment: StoredLogisticsAssessment,
    roles: IntegrationActionRoles,
): DecisionOption[] {
    return assessment.result.actions
        .filter((option) => option.eligible)
        .map((option) => ({
            action: option.action,
            label: option.action,
            recommended:
                option.action === assessment.result.recommendation.action,
            requiredRole: roles[option.action],
        }));
}

export function decisionForAssessment(
    assessment: StoredLogisticsAssessment,
    decisions: IntegrationDecisions,
): HumanDecision | null {
    return decisions[assessment.assessment_id] ?? null;
}

export function isNamedIntegrationDemo(
    assessment: StoredLogisticsAssessment,
    fixtures: IntegrationDemoShipments,
): boolean {
    return (
        assessment.result.simulated_shipment.simulated === true &&
        assessment.result.simulated_shipment.shipment_id ===
            assessment.result.shipment_id &&
        fixtures[assessment.scenario] === assessment.result.shipment_id
    );
}
