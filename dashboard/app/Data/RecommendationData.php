<?php

declare(strict_types=1);

namespace App\Data;

use App\Enums\ShipmentAction;
use App\Enums\UserRole;
use Spatie\LaravelData\Data;

final class RecommendationData extends Data
{
    public function __construct(
        public ShipmentAction $action,
        public string $title,
        public string $summary,
        public string $glance,
        public UserRole $approver,
    ) {}
}
