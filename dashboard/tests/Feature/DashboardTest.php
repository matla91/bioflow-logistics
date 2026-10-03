<?php

declare(strict_types=1);

use App\Enums\ShipmentAction;
use App\Enums\UserRole;
use App\Models\Assessment;
use App\Models\Shipment;
use App\Models\User;
use Inertia\Testing\AssertableInertia as Assert;

test('guests are redirected to the login page', function () {
    $response = $this->get(route('dashboard'));
    $response->assertRedirect(route('login'));
});

test('the overview counts open shipments and those needing the viewer\'s role', function () {
    Assessment::factory()->for(Shipment::factory())->create([
        'recommended_action' => ShipmentAction::Quarantine,
        'approver_role' => UserRole::Qa,
    ]);
    $routine = Assessment::factory()->for(Shipment::factory())->create();

    $this->actingAs(User::factory()->role(UserRole::Qa)->create())
        ->get(route('dashboard'))
        ->assertInertia(fn (Assert $page) => $page
            ->component('Dashboard')
            ->where('overview.open.open', 2)
            ->where('overview.open.needsYou', 1)
            ->has('overview.needsYou', 1)
            ->where('overview.nextCharges', fn ($items) => collect($items)->pluck('id')->contains($routine->shipment_id)),
        );
});
