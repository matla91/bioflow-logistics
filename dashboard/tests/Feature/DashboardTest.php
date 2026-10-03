<?php

declare(strict_types=1);

use App\Models\User;
use Inertia\Testing\AssertableInertia as Assert;

test('guests are redirected to the login page', function () {
    $response = $this->get(route('dashboard'));
    $response->assertRedirect(route('login'));
});

test('the dashboard loads the normal logistics JSON by default', function () {
    $this->actingAs(User::factory()->create())
        ->get(route('dashboard'))
        ->assertInertia(fn (Assert $page) => $page
            ->component('Dashboard')
            ->where('scenario', 'normal')
            ->where('logistics.shipment_id', 'SIM-BASEL-NORMAL')
            ->where('logistics.recommendation.action', 'BUFFER')
            ->has('logistics.actions', 3)
            ->has('logistics.data_provenance')
            ->has('logistics.limitations'),
        );
});

test('the dashboard can switch to the severe scenario', function () {
    $this->actingAs(User::factory()->create())
        ->get(route('dashboard', ['scenario' => 'severe']))
        ->assertInertia(fn (Assert $page) => $page
            ->component('Dashboard')
            ->where('scenario', 'severe')
            ->where('logistics.recommendation.action', 'REROUTE'),
        );
});
