<?php

declare(strict_types=1);

use App\Enums\ShipmentAction;
use App\Enums\ShipmentStatus;
use App\Enums\UserRole;
use App\Enums\Verdict;
use App\Models\Assessment;
use App\Models\Decision;
use App\Models\Shipment;
use App\Models\User;
use Inertia\Testing\AssertableInertia as Assert;

function openShipment(ShipmentAction $recommended = ShipmentAction::RunAsPlanned): Assessment
{
    return Assessment::factory()->for(Shipment::factory())->create([
        'recommended_action' => $recommended,
        'approver_role' => $recommended->approver(),
    ]);
}

function decide(Assessment $assessment, UserRole $role, array $payload = []): Illuminate\Testing\TestResponse
{
    return test()->actingAs(User::factory()->role($role)->create())
        ->from(route('shipments.show', $assessment->shipment))
        ->post(route('shipments.decisions.store', $assessment->shipment), [
            'assessment_id' => $assessment->id,
            'verdict' => Verdict::Approve->value,
            'action' => $assessment->recommended_action->value,
            'reason' => 'Checked the evidence.',
            ...$payload,
        ]);
}

test('the console shows the latest assessment of a shipment', function () {
    $assessment = openShipment(ShipmentAction::Buffer);

    $this->actingAs(User::factory()->create())
        ->get(route('shipments.show', $assessment->shipment))
        ->assertInertia(fn (Assert $page) => $page
            ->component('shipments/Show')
            ->where('shipment.assessmentId', $assessment->id)
            ->where('shipment.recommendation.action', 'BUFFER')
            ->where('shipment.recommendation.approver', 'operator')
            ->where('shipment.log', []),
        );
});

test('the approver role can approve the recommendation, which closes the shipment', function () {
    $assessment = openShipment();

    decide($assessment, UserRole::Operator)
        ->assertRedirect(route('shipments.show', $assessment->shipment))
        ->assertSessionHasNoErrors();

    $decision = Decision::query()->sole();
    expect($decision->verdict)->toBe(Verdict::Approve)
        ->and($decision->action)->toBe(ShipmentAction::RunAsPlanned)
        ->and($decision->role)->toBe(UserRole::Operator)
        ->and($decision->snapshot_sha256)->toBe($assessment->snapshot_sha256)
        ->and($assessment->shipment->refresh()->status)->toBe(ShipmentStatus::Closed);
});

test('another role cannot approve the recommendation', function () {
    $assessment = openShipment(ShipmentAction::Quarantine);

    decide($assessment, UserRole::Operator)->assertSessionHasErrors(['decision' => 'This decision needs QA approval.']);

    expect(Decision::query()->count())->toBe(0)
        ->and($assessment->shipment->refresh()->status->isOpen())->toBeTrue();
});

test('an override needs the role responsible for the chosen action', function (string $role, string $recommended, string $chosen, bool $allowed) {
    $assessment = openShipment(ShipmentAction::from($recommended));

    $response = decide($assessment, UserRole::from($role), ['verdict' => Verdict::Override->value, 'action' => $chosen]);

    $allowed ? $response->assertSessionHasNoErrors() : $response->assertSessionHasErrors('decision');
    expect(Decision::query()->count())->toBe($allowed ? 1 : 0);
})->with([
    'operator overrides with buffer' => ['operator', 'RUN_AS_PLANNED', 'BUFFER', true],
    'operator cannot pick reroute' => ['operator', 'RUN_AS_PLANNED', 'REROUTE', false],
    'logistics picks reroute' => ['logistics', 'RUN_AS_PLANNED', 'REROUTE', true],
    'operator cannot release a quarantine' => ['operator', 'QUARANTINE', 'RUN_AS_PLANNED', false],
    'QA releases a quarantine' => ['qa', 'QUARANTINE', 'RUN_AS_PLANNED', true],
]);

test('approving a different action than recommended is rejected', function () {
    $assessment = openShipment();

    decide($assessment, UserRole::Operator, ['action' => ShipmentAction::Buffer->value])
        ->assertSessionHasErrors(['decision' => 'Only the recommended action can be approved; choose Override for another action.']);
});

test('a decision on an outdated assessment is rejected', function () {
    $stale = openShipment();
    Assessment::factory()->for($stale->shipment)->create(['assessed_at' => now()->addMinute()]);

    decide($stale, UserRole::Operator)->assertSessionHasErrors(['decision' => 'A newer assessment is available. Reload before deciding.']);
});

test('a shipment can only be decided once', function () {
    $assessment = openShipment();
    decide($assessment, UserRole::Operator)->assertSessionHasNoErrors();

    decide($assessment, UserRole::Operator)->assertSessionHasErrors(['decision' => 'This shipment already has a decision.']);

    expect(Decision::query()->count())->toBe(1);
});

test('a decision needs a reason', function () {
    decide(openShipment(), UserRole::Operator, ['reason' => ''])->assertSessionHasErrors('reason');

    expect(Decision::query()->count())->toBe(0);
});

test('a decided demo scene can be reopened', function () {
    $assessment = openShipment();
    $assessment->shipment->update(['scenario' => 's1', 'arrived_at' => now()]);
    decide($assessment, UserRole::Operator)->assertSessionHasNoErrors();

    $this->delete(route('shipments.decisions.destroy', $assessment->shipment))
        ->assertRedirect(route('shipments.show', $assessment->shipment));

    expect(Decision::query()->count())->toBe(0)
        ->and($assessment->shipment->refresh()->status)->toBe(ShipmentStatus::Arrived);
});

test('a real shipment cannot be reopened', function () {
    $assessment = openShipment();
    decide($assessment, UserRole::Operator)->assertSessionHasNoErrors();

    $this->from(route('shipments.show', $assessment->shipment))
        ->delete(route('shipments.decisions.destroy', $assessment->shipment))
        ->assertSessionHasErrors(['decision' => 'Only demo scenes can be reopened.']);

    expect(Decision::query()->count())->toBe(1);
});
