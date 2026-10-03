<?php

declare(strict_types=1);

namespace App\Data;

use Spatie\LaravelData\Data;

final class ShipmentOverviewData extends Data
{
    /**
     * @param  array{open: int, needsYou: int, suspended: int, atRisk: int}  $open
     * @param  array{days: int, decided: int, overrides: int, onTime: int, withinBudget: int}  $recent
     * @param  array<string, int>  $decisionsByAction
     * @param  list<ShipmentListItemData>  $needsYou
     * @param  list<ShipmentListItemData>  $nextCharges
     */
    public function __construct(
        public array $open,
        public array $recent,
        public array $decisionsByAction,
        public array $needsYou,
        public array $nextCharges,
    ) {}
}
