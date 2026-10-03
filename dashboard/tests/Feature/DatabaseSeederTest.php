<?php

declare(strict_types=1);

use App\Enums\ShipmentAction;
use App\Enums\UserRole;
use App\Models\Shipment;
use App\Models\User;
use Database\Seeders\DatabaseSeeder;

test('the demo seed has one login per role and a mostly routine decided history', function () {
    $this->seed(DatabaseSeeder::class);

    expect(User::query()->pluck('role', 'email')->all())->toBe([
        'operator@example.com' => UserRole::Operator,
        'logistics@example.com' => UserRole::Logistics,
        'qa@example.com' => UserRole::Qa,
    ]);

    $history = Shipment::query()->closed()->with(['latestAssessment', 'decision'])->get();

    expect($history)->toHaveCount(20)
        ->and($history->every(fn (Shipment $shipment): bool => $shipment->decision !== null))->toBeTrue()
        ->and($history->filter(fn (Shipment $shipment): bool => $shipment->latestAssessment->recommended_action === ShipmentAction::RunAsPlanned))->toHaveCount(14)
        ->and(Shipment::query()->open()->whereNotNull('scenario')->pluck('scenario')->sort()->values()->all())->toBe(['s1', 's2', 's3']);
});
