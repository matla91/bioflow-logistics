<?php

declare(strict_types=1);

use App\Models\User;
use Illuminate\Support\Facades\Http;
use Inertia\Testing\AssertableInertia as Assert;

test('integration page reads stored results without changing shipment decisions', function (): void {
    Http::fake([
        '*/api/integration/assessments' => Http::response([], 200),
        '*/api/integration/operations' => Http::response([], 200),
    ]);

    $this->actingAs(User::factory()->create())
        ->get('/integration')
        ->assertOk()
        ->assertInertia(fn (Assert $page) => $page
            ->component('Integration')
            ->has('assessments', 0)
            ->has('operations', 0)
            ->where('unavailable', false));

    Http::assertSentCount(2);
});

test('integration page shows unavailability when the engine cannot be reached', function (): void {
    Http::fake(fn () => Http::failedConnection());

    $this->actingAs(User::factory()->create())
        ->get('/integration')
        ->assertOk()
        ->assertInertia(fn (Assert $page) => $page
            ->component('Integration')
            ->where('unavailable', true));
});
