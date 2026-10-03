<?php

declare(strict_types=1);

namespace App\Enums;

enum ShipmentAction: string
{
    case RunAsPlanned = 'RUN_AS_PLANNED';
    case Expedite = 'EXPEDITE';
    case Buffer = 'BUFFER';
    case Reroute = 'REROUTE';
    case Quarantine = 'QUARANTINE';

    public function label(): string
    {
        return match ($this) {
            self::RunAsPlanned => 'Run as planned',
            self::Expedite => 'Expedite',
            self::Buffer => 'Buffer',
            self::Reroute => 'Reroute',
            self::Quarantine => 'Quarantine',
        };
    }

    /**
     * The role that must approve this action.
     */
    public function approver(): UserRole
    {
        return match ($this) {
            self::Quarantine => UserRole::Qa,
            self::Expedite, self::Reroute => UserRole::Logistics,
            self::RunAsPlanned, self::Buffer => UserRole::Operator,
        };
    }
}
