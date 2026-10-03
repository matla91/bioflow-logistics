<?php

declare(strict_types=1);

namespace App\Enums;

enum UserRole: string
{
    case Operator = 'operator';
    case Logistics = 'logistics';
    case Qa = 'qa';

    public function label(): string
    {
        return match ($this) {
            self::Operator => 'Operator',
            self::Logistics => 'Logistics',
            self::Qa => 'QA',
        };
    }
}
