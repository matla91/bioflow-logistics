import type { ActionKey, HumanDecision, Role } from './console';
import type { StoredLogisticsAssessment } from './integration';

// Laravel-owned human decisions are separate from the generated Python contracts.
export type IntegrationDecisions = Record<string, HumanDecision>;
export type IntegrationActionRoles = Record<ActionKey, Role>;
export type IntegrationDemoShipments = Partial<
    Record<StoredLogisticsAssessment['scenario'], string>
>;
