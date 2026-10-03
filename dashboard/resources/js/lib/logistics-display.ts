import type {
    FrontendAction,
    LogisticsFrontendResult,
} from '@/types/integration';

/** Format a supplied reason probability while preserving small nonzero values. */
function formatPercent(value: number): string {
    if (value > 0 && value < 0.001) return '<0.1%';
    return `${(value * 100).toFixed(1).replace(/\.0$/, '')}%`;
}

/** Format a supplied reason delay without turning small delays into zero. */
function formatMinutes(value: number): string {
    if (value > 0 && value < 0.1) return '<0.1 min';
    return `${value.toFixed(1).replace(/\.0$/, '')} min`;
}

// Selectively reuse the existing scenario dashboard's display-only explanations.
/** Look up metrics for the backend-selected action without choosing an action. */
export function selectedActionResult(
    result: LogisticsFrontendResult,
): FrontendAction | null {
    return (
        result.actions.find(
            (candidate) => candidate.action === result.recommendation.action,
        ) ?? null
    );
}

type ScenarioStatus = {
    label: string;
    tone: 'neutral' | 'warning' | 'alert';
};

/** Describe the selected scenario without deriving a state from model metrics. */
export function scenarioStatus(key: string): ScenarioStatus {
    switch (key) {
        case 'normal':
            return { label: 'Normal scenario', tone: 'neutral' };
        case 'disruption':
            return { label: 'Disruption scenario', tone: 'warning' };
        case 'severe':
            return { label: 'Severe disruption scenario', tone: 'alert' };
        default:
            return { label: 'Unknown scenario', tone: 'neutral' };
    }
}

const numberPattern = '\\d+(?:\\.\\d+)?(?:e[+-]?\\d+)?';
const probabilityPattern = '(?:0(?:\\.\\d+)?|1(?:\\.0+)?)';
const actionPattern = '(?:BUFFER|EXPEDITE|REROUTE)';
const metricDumpPrefix = new RegExp(
    `^(${actionPattern}): production continuity (${numberPattern}), incoming on-time arrival (${numberPattern}), cold-chain exposure proxy risk (${numberPattern}), incoming mean lateness (${numberPattern}) min\\. (.+)$`,
);
const sufficientBufferConclusion =
    'BUFFER meets the continuity target and both incoming shipment criteria; the modeled stock coverage needs no additional shipment intervention.';
const interventionConclusion = new RegExp(
    `^It meets the production continuity target (${probabilityPattern}); eligible shipment interventions meeting that target are compared by lower exposure proxy, lower incoming lateness, then higher on-time arrival\\.$`,
);
const continuityBufferConclusion = new RegExp(
    `^BUFFER meets the continuity target (${probabilityPattern}); no eligible shipment intervention meets that target\\. Incoming shipment criteria remain unmet despite the factory stock coverage\\.$`,
);
const belowTargetConclusion = new RegExp(
    `^No eligible action meets the continuity target (${probabilityPattern})\\. This action has the highest modeled continuity; ties favor lower exposure proxy, lower incoming lateness, then deterministic action priority\\. Reassessment is needed\\.$`,
);

function selectionExplanation(
    action: string,
    conclusion: string,
): string | null {
    if (action === 'BUFFER' && conclusion === sufficientBufferConclusion) {
        return 'BUFFER meets the production continuity and arrival targets, and stays within the exposure proxy limit. Modeled stock coverage needs no additional shipment intervention.';
    }

    const intervention = interventionConclusion.exec(conclusion);
    if (action !== 'BUFFER' && intervention) {
        return `${action} meets the ${formatPercent(Number(intervention[1]))} production continuity target. The shipment policy compares eligible interventions by lower exposure proxy, then lower incoming lateness, then higher on-time arrival.`;
    }

    const continuityBuffer = continuityBufferConclusion.exec(conclusion);
    if (action === 'BUFFER' && continuityBuffer) {
        return `BUFFER meets the ${formatPercent(Number(continuityBuffer[1]))} production continuity target, but no eligible shipment intervention meets it. Incoming shipment criteria remain unmet despite modeled factory stock coverage.`;
    }

    const belowTarget = belowTargetConclusion.exec(conclusion);
    if (belowTarget) {
        return `No eligible action meets the ${formatPercent(Number(belowTarget[1]))} production continuity target. ${action} has the highest modeled continuity; ties favor lower exposure proxy, then lower incoming lateness, then the policy's action priority. Reassessment is needed.`;
    }

    return null;
}

const continuityFailure = new RegExp(
    `^Production continuity (${probabilityPattern}) is below the policy target (${probabilityPattern})\\.$`,
);
const bufferFailures = new RegExp(
    `^Factory continuity alone is insufficient: (?:incoming on-time arrival (${probabilityPattern}) is below (${probabilityPattern})(?:; cold-chain exposure proxy (${probabilityPattern}) exceeds (${probabilityPattern}))?|cold-chain exposure proxy (${probabilityPattern}) exceeds (${probabilityPattern}))\\.$`,
);
const lowerContinuity = new RegExp(
    `^Its continuity is lower than (${actionPattern})'s (${probabilityPattern}); no eligible action meets the target\\.$`,
);
const higherExposure = new RegExp(
    `^Its exposure proxy risk (${probabilityPattern}) is higher than (${actionPattern})'s (${probabilityPattern})\\.$`,
);
const higherLateness = new RegExp(
    `^Exposure proxies are tied; its incoming mean lateness (${numberPattern}) min is higher than (${actionPattern})'s (${numberPattern}) min\\.$`,
);
const lowerArrival = new RegExp(
    `^Exposure and incoming lateness are tied; its on-time arrival (${probabilityPattern}) is lower than (${actionPattern})'s (${probabilityPattern})\\.$`,
);
const tiedCriteria = new RegExp(
    `^Decision dimensions are tied; deterministic action priority chooses (${actionPattern})\\.$`,
);

function alternativeExplanation(
    action: string,
    conclusion: string,
): string | null {
    if (
        conclusion ===
        'BUFFER already meets all policy criteria without an additional intervention.'
    ) {
        return 'Not needed: BUFFER already satisfies all policy criteria without additional shipment intervention.';
    }

    const continuity = continuityFailure.exec(conclusion);
    if (continuity) {
        return `Projected production continuity is ${formatPercent(Number(continuity[1]))}, below the required ${formatPercent(Number(continuity[2]))} target.`;
    }

    const buffer = action === 'BUFFER' ? bufferFailures.exec(conclusion) : null;
    if (buffer) {
        const failures = [];
        const exposure = buffer[3] ?? buffer[5];
        const cap = buffer[4] ?? buffer[6];
        if (buffer[1]) {
            failures.push(
                `incoming on-time arrival is ${formatPercent(Number(buffer[1]))}, below the ${formatPercent(Number(buffer[2]))} target`,
            );
        }
        if (exposure) {
            failures.push(
                `the cold-chain exposure proxy is ${formatPercent(Number(exposure))}, above the ${formatPercent(Number(cap))} limit`,
            );
        }
        return `Production continuity alone is insufficient: ${failures.join('; ')}.`;
    }

    const lower = lowerContinuity.exec(conclusion);
    if (lower) {
        return `Projected production continuity is below ${lower[1]}'s ${formatPercent(Number(lower[2]))}; no eligible action meets the target.`;
    }
    const exposure = higherExposure.exec(conclusion);
    if (exposure) {
        return `The cold-chain exposure proxy is ${formatPercent(Number(exposure[1]))}, above ${exposure[2]}'s ${formatPercent(Number(exposure[3]))}.`;
    }
    const lateness = higherLateness.exec(conclusion);
    if (lateness) {
        return `Exposure proxies are tied; mean incoming lateness is ${formatMinutes(Number(lateness[1]))}, above ${lateness[2]}'s ${formatMinutes(Number(lateness[3]))}.`;
    }
    const arrival = lowerArrival.exec(conclusion);
    if (arrival) {
        return `Exposure proxies and incoming lateness are tied; on-time arrival is ${formatPercent(Number(arrival[1]))}, below ${arrival[2]}'s ${formatPercent(Number(arrival[3]))}.`;
    }
    const tied = tiedCriteria.exec(conclusion);
    return tied
        ? `Compared decision criteria are tied; the policy's action priority selects ${tied[1]}.`
        : null;
}

/** Humanize only complete, recognized backend explanations; retain raw fallback. */
export function humanizeRecommendationReason(text: string): string {
    const match = metricDumpPrefix.exec(text);
    return match ? (selectionExplanation(match[1], match[6]) ?? text) : text;
}

/** Preserve every supplied alternative criterion rather than rank actions. */
export function humanizeAlternativeReason(text: string): string {
    const match = metricDumpPrefix.exec(text);
    return match ? (alternativeExplanation(match[1], match[6]) ?? text) : text;
}

/** Summarize recognized backend selection reasons without computing a decision. */
export function recommendationSummary(result: LogisticsFrontendResult): string {
    const { action, reason } = result.recommendation;
    const fallback = humanizeRecommendationReason(reason);
    if (action === null) {
        return `Reassessment required. ${fallback}`;
    }

    const selected = selectedActionResult(result);
    const match = metricDumpPrefix.exec(reason);
    if (!selected || !match || match[1] !== action) {
        return fallback;
    }

    const suppliedMetrics = [
        selected.production_continuity_probability,
        selected.on_time_arrival_probability,
        selected.cold_chain_exposure_proxy_risk,
        selected.predicted_arrival_delay_min,
    ];
    if (
        !suppliedMetrics.every(
            (value, index) => value === Number(match[index + 2]),
        )
    ) {
        return fallback;
    }

    const conclusion = match[6];
    if (action === 'BUFFER' && conclusion === sufficientBufferConclusion) {
        return 'No additional shipment intervention is needed; modeled stock covers production and incoming shipment criteria are met.';
    }
    if (action !== 'BUFFER' && interventionConclusion.test(conclusion)) {
        return `${action} is selected to meet the production continuity target under the shipment policy.`;
    }
    return fallback;
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

const counterfactualPattern = new RegExp(
    `^(SIMULATED|ASSUMED) (stock_available|planned_remaining_min|protection_remaining_min|expedite_transport_factor) changed from (${numberPattern}) to (${numberPattern}) (units|min|factor): the paired model rerun selects (${actionPattern})\\.$`,
);

/** Relabel known paired model reruns, preserving number strings and provenance. */
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

    const previousValue = Number(previous);
    const nextValue = Number(next);
    if (!Number.isFinite(previousValue) || !Number.isFinite(nextValue)) {
        return text;
    }
    const direction =
        nextValue < previousValue
            ? 'fell'
            : nextValue > previousValue
              ? 'increased'
              : 'changed';
    const units = unit === 'factor' ? '' : ` ${unit}`;
    return `If ${description.label} ${direction} from ${previous} to ${next}${units} → ${action} (${kind})`;
}
