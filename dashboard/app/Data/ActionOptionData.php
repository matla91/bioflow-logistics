<?php

declare(strict_types=1);

namespace App\Data;

use App\Enums\ShipmentAction;
use Spatie\LaravelData\Data;

final class ActionOptionData extends Data
{
    public function __construct(
        public ShipmentAction $action,
        public string $label,
        public float $pMissSlot,
        public float $expDelayMin,
        public float $pExcursion,
        public int $stockAfter,
        public bool $recommended,
        public string $note,
    ) {}
}
