<?php

declare(strict_types=1);

namespace App\Enums;

enum EvidenceKind: string
{
    case Real = 'real';
    case Simulated = 'simulated';
    case Unverified = 'unverified';
}
