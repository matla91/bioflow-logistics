<?php

declare(strict_types=1);

use App\Enums\ShipmentAction;
use App\Enums\Verdict;
use App\Models\Assessment;
use App\Models\Decision;
use App\Models\Shipment;
use App\Models\User;
use Inertia\Testing\AssertableInertia as Assert;

test('guests are redirected to the login page', function () {
    $this->get(route('shipments.index'))->assertRedirect(route('login'));
});

test('open shipments are listed as upcoming soonest first and decided ones as history newest first', function () {
    $later = Shipment::factory()->create(['charge_at' => now()->addDays(3)]);
    $sooner = Shipment::factory()->create(['charge_at' => now()->addDay()]);
    Assessment::factory()->for($sooner)->create(['recommended_action' => ShipmentAction::Expedite]);

    $older = Shipment::factory()->closed()->create(['charge_at' => now()->subDays(5)]);
    $newer = Shipment::factory()->closed()->create(['charge_at' => now()->subDay()]);
    $decider = User::factory()->create(['name' => 'Logistics Lead']);
    Decision::factory()
        ->for($decider)
        ->for(Assessment::factory()->for($newer))
        ->create(['verdict' => Verdict::Override, 'action' => ShipmentAction::Buffer]);

    $this->actingAs(User::factory()->create())
        ->get(route('shipments.index'))
        ->assertInertia(fn (Assert $page) => $page
            ->component('shipments/Index')
            ->where('upcoming.0.id', $sooner->id)
            ->where('upcoming.0.recommendedAction', 'EXPEDITE')
            ->where('upcoming.1.id', $later->id)
            ->where('history.0.id', $newer->id)
            ->where('history.0.decision.verdict', 'OVERRIDE')
            ->where('history.0.decision.action', 'BUFFER')
            ->where('history.0.decision.by', 'Logistics Lead')
            ->where('history.1.id', $older->id)
            ->where('history.1.decision', null),
        );
});
