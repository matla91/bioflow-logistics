import type {
    BatchRecommendation,
    IncomingShipmentResult,
    ProductTemperatureEvidence,
    ProductionReadiness,
    StoredBatchAssessment,
} from '@/types/integration';

type Tone = 'neutral' | 'warning' | 'alert';

/** Format recorded quantities without turning absent evidence into zero. */
export function formatKg(value: number | null): string {
    return value === null || !Number.isFinite(value)
        ? 'Unavailable'
        : `${value.toFixed(1).replace(/\.0$/, '')} kg`;
}

// Selectively adapted from feat/dashboard-json-integration's logistics-display.ts:
// retain its minute/percent precision and small nonzero-value handling only.
/** Format observed/modelled minutes while keeping null distinct from zero. */
export function formatMinutes(value: number | null): string {
    if (value === null || !Number.isFinite(value)) return 'Unavailable';
    if (value > 0 && value < 0.1) return '<0.1 min';
    return `${value.toFixed(1).replace(/\.0$/, '')} min`;
}

/** Format a supplied probability; this never estimates a missing probability. */
export function formatProbability(value: number | null): string {
    if (value === null || !Number.isFinite(value)) return 'Unavailable';
    if (value > 0 && value < 0.001) return '<0.1%';
    return `${(value * 100).toFixed(1).replace(/\.0$/, '')}%`;
}

const baselDateOptions: Intl.DateTimeFormatOptions = {
    timeZone: 'Europe/Zurich',
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
    timeZoneName: 'longOffset',
};
const baselDateFormat = new Intl.DateTimeFormat('en-GB', {
    ...baselDateOptions,
    year: 'numeric',
});
const shortBaselDateFormat = new Intl.DateTimeFormat('en-GB', baselDateOptions);

/** Present the same instant in Basel, with its daylight-saving offset visible. */
export function formatBaselTime(value: string | null): string {
    if (value === null) return 'Unavailable';
    const date = new Date(value);
    if (!Number.isFinite(date.getTime())) return 'Unavailable';
    return `${baselDateFormat.format(date)} (Basel)`;
}

/** Compact card timestamp; use the full formatter for its audit/title text. */
export function formatBaselTimeShort(value: string | null): string {
    if (value === null) return 'Unavailable';
    const date = new Date(value);
    if (!Number.isFinite(date.getTime())) return 'Unavailable';
    return shortBaselDateFormat
        .format(date)
        .replace('GMT', 'UTC')
        .replace(/:00$/, '');
}

/** Shorten an identifier for navigation only; unknown identifiers stay intact. */
export function batchLabel(id: string): string {
    const suffix = /(?:^|-)batch-(\d+)$/i.exec(id);
    return suffix ? `Batch ${suffix[1]}` : id;
}

/** Shorten a shipment identifier without assigning it an operational meaning. */
export function shipmentLabel(id: string): string {
    const suffix = /(?:^|-)shipment-(\d+)$/i.exec(id);
    return suffix ? `Shipment ${suffix[1]}` : id;
}

/** Describe a passed charge deadline without reconstructing historical readiness. */
export function isRetrospective(record: StoredBatchAssessment): boolean {
    return (
        Date.parse(record.as_of) >=
        Date.parse(record.production_readiness.planned_charge_at)
    );
}

/** Label only the backend-selected action, including an unsupported null action. */
export function actionLabel(action: BatchRecommendation['action']): string {
    if (action === null) return 'No forward action';
    return {
        BUFFER: 'BUFFER · use reserved stock',
        EXPEDITE: 'Expedite shipment (EXPEDITE)',
        REROUTE: 'Reroute shipment (REROUTE)',
    }[action];
}

/** Use the supplied readiness enum, never derive readiness from quantities. */
export function productionStatusLabel(
    status: ProductionReadiness['status'],
): string {
    return {
        RESERVED_STOCK_SUFFICIENT: 'Released reservations cover demand',
        INCOMING_DEPENDENT: 'Incoming material needed',
        INSUFFICIENT_SUPPLY: 'Supply does not cover demand',
    }[status];
}

/** Distinguish observed arrivals, model outcomes and unavailable timing. */
export function incomingStatusLabel(
    status: IncomingShipmentResult['status'],
): string {
    return {
        ARRIVED: 'Arrived',
        MODELED: 'Timing modeled',
        UNAVAILABLE: 'Timing unavailable',
    }[status];
}

/** A logistics approval role is separate from the required human QA review. */
export function qaReviewLabel(required: boolean): string {
    return required ? 'Human QA review required' : 'QA review remains separate';
}

/** This contract permits no automated release authorization, including omission. */
export function qaReleaseLabel(
    authorized: BatchRecommendation['qa_release_authorized'],
): string {
    return authorized === false
        ? 'QA release authorized: No'
        : 'No QA release authorization supplied';
}

type TemperaturePresentation = {
    statusLabel: string;
    tone: Tone;
    excursionLabel: string;
    journeyLabel: string;
    limitation: string;
};

/** Relabel backend evidence states without testing a pharmaceutical release rule. */
export function temperaturePresentation(
    evidence: ProductTemperatureEvidence,
): TemperaturePresentation {
    const incomplete = !evidence.complete_journey;
    const missingReadings = evidence.reading_count === 0;
    const exceeded = evidence.status === 'OBSERVED_BUDGET_EXCEEDED';
    const unavailable = evidence.status === 'UNAVAILABLE';
    const statusLabel = exceeded
        ? 'Observed demo budget exceeded'
        : unavailable
          ? missingReadings
              ? 'Product-temperature evidence unavailable'
              : 'Usable excursion duration unavailable'
          : incomplete
            ? 'Partial temperature evidence'
            : 'Observed within demo budget';

    return {
        statusLabel,
        tone: exceeded
            ? 'alert'
            : unavailable || incomplete
              ? 'warning'
              : 'neutral',
        excursionLabel:
            evidence.observed_excursion_min === null
                ? missingReadings
                    ? '—'
                    : 'Unavailable'
                : `${formatMinutes(evidence.observed_excursion_min)} observed`,
        journeyLabel: incomplete ? 'Journey incomplete' : 'Journey complete',
        limitation: unavailable
            ? missingReadings
                ? 'No measurements: excursion is unknown, not zero.'
                : 'No usable excursion duration is available; gaps are not zero exposure.'
            : incomplete
              ? 'Observed excursion covers usable sampled intervals only; it does not establish whole-journey compliance.'
              : 'Demonstration limits are not pharmaceutical QA release criteria.',
    };
}

type AssessmentSummary = {
    headline: string;
    tone: Tone;
    detail: string;
    limitation: string;
    retrospective: boolean;
};

/** Highlight supplied evidence flags while preserving the saved recommendation. */
export function assessmentSummary(
    record: StoredBatchAssessment,
): AssessmentSummary {
    const retrospective = isRetrospective(record);
    if (retrospective) {
        return {
            headline: 'Retrospective assessment',
            tone: 'warning',
            detail:
                record.recommendation.action === null
                    ? 'Charge deadline already passed. No forward action is recorded; stock, arrival and sampled temperature evidence are retained.'
                    : 'Charge deadline already passed. The stored recommendation is retained as recorded.',
            limitation:
                'The persisted snapshot does not establish the exact historical QA or reservation state at charge time.',
            retrospective,
        };
    }

    const exceeded = record.product_temperature.some(
        (evidence) => evidence.status === 'OBSERVED_BUDGET_EXCEEDED',
    );
    const unavailable =
        record.product_temperature.length === 0 ||
        record.product_temperature.some(
            (evidence) => evidence.status === 'UNAVAILABLE',
        );
    const incomplete = record.product_temperature.some(
        (evidence) => !evidence.complete_journey,
    );
    const noReadings = record.product_temperature.every(
        (evidence) => evidence.reading_count === 0,
    );
    const stockShortfall =
        record.production_readiness.status !== 'RESERVED_STOCK_SUFFICIENT';

    return {
        headline: exceeded
            ? stockShortfall
                ? 'Stock shortfall · temperature review required'
                : 'Temperature evidence needs review'
            : unavailable
              ? noReadings
                  ? 'Evidence not yet available'
                  : 'Evidence unavailable'
              : incomplete
                ? 'Evidence incomplete'
                : stockShortfall
                  ? 'Incoming material needs review'
                  : 'Released reservations cover demand',
        tone: exceeded
            ? 'alert'
            : unavailable || incomplete || stockShortfall
              ? 'warning'
              : 'neutral',
        detail: exceeded
            ? 'Observed product-temperature excursion exceeds the demonstration budget. Human QA review remains separate from logistics approval.'
            : unavailable
              ? noReadings
                  ? 'Product-temperature readings are not available at this cutoff. Review incoming milestones and the saved timing reason.'
                  : 'Usable product-temperature excursion is unavailable. Review recorded gaps and incoming timing.'
              : incomplete
                ? 'Sampled intervals do not prove a compliant whole journey. Incoming material and human QA review remain separate.'
                : record.recommendation.reason,
        limitation: unavailable
            ? 'Missing evidence is unknown; it is not zero excursion or proof of a safe journey.'
            : incomplete
              ? 'The journey is not completely sampled; observed excursion is partial evidence.'
              : 'Recorded stock and logistics evidence do not authorize pharmaceutical QA release.',
        retrospective,
    };
}
