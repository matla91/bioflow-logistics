import type { LogisticsFrontendResult } from '@/types/logistics';

/** Format an existing probability for display without implying false zeroes. */
export function formatPercent(value: number): string {
    if (value > 0 && value < 0.001) {
        return '<0.1%';
    }

    return `${(value * 100).toFixed(1).replace(/\.0$/, '')}%`;
}

/** Format existing minute values, keeping zero distinct from small delays. */
export function formatMinutes(value: number): string {
    if (value > 0 && value < 0.1) {
        return '<0.1 min';
    }

    return `${value.toFixed(1).replace(/\.0$/, '')} min`;
}

const metricDumpPrefix =
    /^(?:BUFFER|EXPEDITE|REROUTE): production continuity \d+(?:\.\d+)?(?:e[+-]?\d+)?, incoming on-time arrival \d+(?:\.\d+)?(?:e[+-]?\d+)?, cold-chain exposure proxy risk \d+(?:\.\d+)?(?:e[+-]?\d+)?, incoming mean lateness \d+(?:\.\d+)?(?:e[+-]?\d+)? min\. (.+)$/;

const probabilityPattern = '(?:0(?:\\.\\d+)?|1(?:\\.0+)?)';
const probabilityComparison = new RegExp(
    `(\\b(?:incoming on-time arrival|cold-chain exposure proxy(?: risk)?) )(${probabilityPattern})( (?:is below|exceeds) )(${probabilityPattern})(?=[.;\\s]|$)`,
    'g',
);
const namedProbability = new RegExp(
    `(\\b(?:production continuity(?: target)?|incoming on-time arrival|cold-chain exposure proxy(?: risk| cap)?|policy target) )(${probabilityPattern})(?=[.;\\s]|$)`,
    'gi',
);

function humanizePolicyConclusion(text: string): string {
    const match = metricDumpPrefix.exec(text);

    // Only remove the known generated dump; unfamiliar backend text stays intact.
    if (!match) {
        return text;
    }

    return match[1]
        .replace(
            probabilityComparison,
            (_match, label, value, comparison, target) =>
                `${label}${formatPercent(Number(value))}${comparison}${formatPercent(Number(target))}`,
        )
        .replace(
            namedProbability,
            (_match, label, value) => `${label}${formatPercent(Number(value))}`,
        );
}

/** Keep the backend policy explanation, formatting its known numerical text. */
export function humanizeRecommendationReason(text: string): string {
    return humanizePolicyConclusion(text);
}

/** Preserve the supplied alternative explanation rather than rank actions. */
export function humanizeAlternativeReason(text: string): string {
    return humanizePolicyConclusion(text);
}

/** Describe only the backend-selected action and its supplied simulation values. */
export function recommendationSummary(result: LogisticsFrontendResult): string {
    const action = result.recommendation.action;

    if (action === null) {
        return `Reassessment required. ${humanizeRecommendationReason(result.recommendation.reason)}`;
    }

    const selected = result.actions.find(
        (candidate) => candidate.action === action,
    );

    if (!selected) {
        return `In the simulation, ${action} is recommended. ${humanizeRecommendationReason(result.recommendation.reason)}`;
    }

    return `In the simulation, ${action} has ${formatPercent(selected.production_continuity_probability)} production continuity and ${formatPercent(selected.on_time_arrival_probability)} on-time arrival, with ${formatMinutes(selected.predicted_arrival_delay_min)} expected incoming delay.`;
}

const counterfactualLabels: Record<
    string,
    { label: string; unit: string; kind: string }
> = {
    stock_available: {
        label: 'available factory stock',
        unit: 'units',
        kind: 'SIMULATED',
    },
    planned_remaining_min: {
        label: 'remaining journey time',
        unit: 'min',
        kind: 'SIMULATED',
    },
    protection_remaining_min: {
        label: 'remaining packaging protection',
        unit: 'min',
        kind: 'SIMULATED',
    },
    expedite_transport_factor: {
        label: 'assumed expedited transport factor',
        unit: 'factor',
        kind: 'ASSUMED',
    },
};

const counterfactualPattern =
    /^(SIMULATED|ASSUMED) (stock_available|planned_remaining_min|protection_remaining_min|expedite_transport_factor) changed from (\d+(?:\.\d+)?(?:e[+-]?\d+)?) to (\d+(?:\.\d+)?(?:e[+-]?\d+)?) (units|min|factor): the paired model rerun selects (BUFFER|EXPEDITE|REROUTE)\.$/;

/** Relabel known paired model reruns, preserving numbers, action and provenance. */
export function humanizeCounterfactual(text: string): string {
    const match = counterfactualPattern.exec(text);

    if (!match) {
        return text;
    }

    const [, kind, field, previous, next, unit, action] = match;
    const description = counterfactualLabels[field];

    if (description.kind !== kind || description.unit !== unit) {
        return text;
    }

    const units = unit === 'factor' ? '' : ` ${unit}`;

    return `If ${description.label} changed from ${previous} to ${next}${units} → ${action} (${kind})`;
}
