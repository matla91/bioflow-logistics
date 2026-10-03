<?php

declare(strict_types=1);

namespace App\Enums;

enum ShipmentStatus: string
{
    case InTransit = 'in_transit';
    case Suspended = 'suspended';
    case Arrived = 'arrived';
    case Closed = 'closed';

    public function isOpen(): bool
    {
        return $this !== self::Closed;
    }
}
