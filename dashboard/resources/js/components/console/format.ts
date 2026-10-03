import type { ActionKey, Role } from '@/types/console';

export const actionLabels: Record<ActionKey, string> = {
    RUN_AS_PLANNED: 'Run as planned',
    EXPEDITE: 'Expedite',
    BUFFER: 'Buffer',
    REROUTE: 'Reroute',
    QUARANTINE: 'Quarantine',
};

export const roleLabels: Record<Role, string> = {
    operator: 'Operator',
    logistics: 'Logistics',
    qa: 'QA',
};

export function formatTime(iso: string, timeZone: string): string {
    return new Intl.DateTimeFormat('en-GB', {
        hour: '2-digit',
        minute: '2-digit',
        timeZone,
    }).format(new Date(iso));
}

export function formatDateTime(iso: string, timeZone: string): string {
    return new Intl.DateTimeFormat('en-GB', {
        day: 'numeric',
        month: 'short',
        hour: '2-digit',
        minute: '2-digit',
        timeZone,
    }).format(new Date(iso));
}

export function formatPercent(fraction: number): string {
    const pct = fraction * 100;

    return `${pct > 0 && pct < 1 ? pct.toFixed(1) : Math.round(pct)}%`;
}

export function formatDelay(minutes: number): string {
    if (minutes <= 0) {
        return 'none';
    }

    if (minutes >= 1440) {
        return `${Math.round(minutes / 1440)} d`;
    }

    if (minutes >= 60) {
        return `${Math.round(minutes / 60)} h`;
    }

    return `${Math.round(minutes)} min`;
}

export function formatCountdown(fromIso: string, toIso: string): string {
    const minutes = Math.max(
        0,
        Math.round(
            (new Date(toIso).getTime() - new Date(fromIso).getTime()) / 60_000,
        ),
    );
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;

    return h > 0 ? `${h}h ${m}m` : `${m}m`;
}
