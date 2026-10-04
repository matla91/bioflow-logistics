<?php

declare(strict_types=1);

use App\Enums\ShipmentAction;
use App\Enums\UserRole;
use App\Enums\Verdict;
use App\Models\Assessment;
use App\Models\Decision;
use App\Models\IntegrationDecision;
use App\Models\Shipment;
use App\Models\User;
use Illuminate\Http\Client\Factory;
use Illuminate\Http\Client\Request;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Facades\Http;
use Inertia\Testing\AssertableInertia as Assert;

beforeEach(function (): void {
    $this->withoutVite();
    Http::preventStrayRequests();
});

/** Test API records wrap the committed results without running any model. */
function integrationAssessment(string $scenario = 'normal', int $revision = 1): array
{
    $body = [
        'input_sha256' => hash('sha256', 'test-input-'.$scenario.'-'.$revision),
        'model_version' => 'logistics-monte-carlo-v1',
        'scenario' => $scenario,
        'result' => File::json(base_path('../output/logistics-'.$scenario.'.json')),
    ];

    return ['assessment_id' => hash('sha256', (string) json_encode($body)), ...$body];
}

function fakeIntegrationAssessments(array $records): void
{
    // Replace the remote state, rather than append lower-priority HTTP stubs.
    Http::swap(new Factory);
    Http::preventStrayRequests();
    $responses = [
        '*/api/integration/assessments' => Http::response($records),
        '*/api/integration/operations' => Http::response([]),
    ];
    foreach ($records as $record) {
        $responses['*/api/integration/assessments/'.$record['assessment_id']] = Http::response($record);
    }
    Http::fake($responses);
}

function integrationDecisionPayload(array $record, array $changes = []): array
{
    return [
        'assessment_id' => $record['assessment_id'],
        'input_sha256' => $record['input_sha256'],
        'model_version' => $record['model_version'],
        'scenario' => $record['scenario'],
        'external_shipment_id' => $record['result']['shipment_id'],
        'recommended_action' => $record['result']['recommendation']['action'],
        'verdict' => 'APPROVE',
        'selected_action' => $record['result']['recommendation']['action'],
        'reason' => 'Reviewed the stored evidence.',
        ...$changes,
    ];
}

function decideIntegration(array $record, UserRole $role = UserRole::Operator, array $changes = []): Illuminate\Testing\TestResponse
{
    return test()->actingAs(User::factory()->role($role)->create())
        ->from(route('integration'))
        ->post(route('integration.decisions.store', $record['assessment_id']), integrationDecisionPayload($record, $changes));
}

test('the recommendation is approved against the immutable Python identity', function (string $scenario, string $role): void {
    $record = integrationAssessment($scenario);
    fakeIntegrationAssessments([$record]);

    decideIntegration($record, UserRole::from($role))
        ->assertRedirect(route('integration'))->assertSessionHasNoErrors();

    $decision = IntegrationDecision::query()->sole();
    expect($decision->assessment_id)->toBe($record['assessment_id'])
        ->and($decision->input_sha256)->toBe($record['input_sha256'])
        ->and($decision->model_version)->toBe($record['model_version'])
        ->and($decision->scenario)->toBe($scenario)
        ->and($decision->external_shipment_id)->toBe($record['result']['shipment_id'])
        ->and($decision->recommended_action->value)->toBe($record['result']['recommendation']['action'])
        ->and($decision->selected_action)->toBe($decision->recommended_action)
        ->and($decision->verdict)->toBe(Verdict::Approve)
        ->and($decision->role->value)->toBe($role)
        ->and($decision->user_id)->toBe(auth()->id())
        ->and($decision->reason)->toBe('Reviewed the stored evidence.')
        ->and($decision->assessment_snapshot)->toEqual($record)
        ->and($decision->decided_at)->not->toBeNull()
        ->and(Shipment::query()->count())->toBe(0)
        ->and(Assessment::query()->count())->toBe(0)
        ->and(Decision::query()->count())->toBe(0);

    Http::assertSentCount(1);
    Http::assertSent(fn (Request $request): bool => $request->method() === 'GET'
        && str_ends_with($request->url(), '/api/integration/assessments/'.$record['assessment_id']));
})->with([
    ['normal', 'operator'], ['disruption', 'logistics'], ['severe', 'logistics'],
]);

test('eligible overrides preserve the model recommendation and use the selected action role', function (string $scenario, string $action, string $role): void {
    $record = integrationAssessment($scenario);
    fakeIntegrationAssessments([$record]);

    decideIntegration($record, UserRole::from($role), ['verdict' => 'OVERRIDE', 'selected_action' => $action])
        ->assertRedirect(route('integration'))->assertSessionHasNoErrors();

    $decision = IntegrationDecision::query()->sole();
    expect($decision->verdict)->toBe(Verdict::Override)
        ->and($decision->selected_action->value)->toBe($action)
        ->and($decision->recommended_action->value)->toBe($record['result']['recommendation']['action'])
        ->and($decision->assessment_snapshot)->toEqual($record);
})->with([
    ['normal', 'REROUTE', 'logistics'],
    ['disruption', 'BUFFER', 'operator'],
    ['disruption', 'REROUTE', 'logistics'],
]);

test('an integration decision requires a nonempty bounded reason', function (string $reason): void {
    $record = integrationAssessment();
    fakeIntegrationAssessments([$record]);

    decideIntegration($record, changes: ['reason' => $reason])->assertSessionHasErrors('reason');
    expect(IntegrationDecision::query()->count())->toBe(0);
    Http::assertNothingSent();
})->with(['empty' => [''], 'whitespace' => [" \n\t "], 'too long' => [str_repeat('r', 1001)]]);

test('another role cannot approve or override an integration action', function (string $scenario, string $role, array $changes): void {
    $record = integrationAssessment($scenario);
    fakeIntegrationAssessments([$record]);

    decideIntegration($record, UserRole::from($role), $changes)->assertSessionHasErrors('decision');
    expect(IntegrationDecision::query()->count())->toBe(0);
})->with([
    ['normal', 'logistics', []],
    ['disruption', 'operator', []],
    ['severe', 'operator', []],
    ['normal', 'qa', []],
    ['normal', 'operator', ['verdict' => 'OVERRIDE', 'selected_action' => 'REROUTE']],
]);

test('the acting user and role come from authentication rather than the payload', function (): void {
    $record = integrationAssessment();
    fakeIntegrationAssessments([$record]);
    decideIntegration($record, changes: ['user_id' => 9999, 'role' => 'qa'])->assertSessionHasNoErrors();
    $decision = IntegrationDecision::query()->sole();
    expect($decision->user_id)->toBe(auth()->id())->and($decision->role)->toBe(UserRole::Operator);
});

test('mismatched displayed evidence is rejected before persistence', function (string $field, string $value): void {
    $record = integrationAssessment();
    fakeIntegrationAssessments([$record]);

    decideIntegration($record, changes: [$field => $value])->assertSessionHasErrors('decision');
    expect(IntegrationDecision::query()->count())->toBe(0);
})->with([
    'assessment hash' => ['assessment_id', str_repeat('a', 64)],
    'input hash' => ['input_sha256', str_repeat('b', 64)],
    'model version' => ['model_version', 'another-model'],
    'scenario' => ['scenario', 'severe'],
    'external shipment' => ['external_shipment_id', 'another-shipment'],
    'recommendation' => ['recommended_action', 'REROUTE'],
]);

test('a changed server recommendation rejects the earlier displayed recommendation', function (): void {
    $displayed = integrationAssessment();
    $current = $displayed;
    $current['result']['recommendation']['action'] = 'REROUTE';
    fakeIntegrationAssessments([$current]);

    decideIntegration($displayed)->assertSessionHasErrors('decision');
    expect(IntegrationDecision::query()->count())->toBe(0);
});

test('a response with a different assessment hash is rejected', function (): void {
    $record = integrationAssessment();
    $other = integrationAssessment(revision: 2);
    Http::fake(['*/api/integration/assessments/'.$record['assessment_id'] => Http::response($other)]);
    decideIntegration($record)->assertSessionHasErrors('decision');
    expect(IntegrationDecision::query()->count())->toBe(0);
});

test('approve and override have distinct meanings', function (array $changes): void {
    $record = integrationAssessment();
    fakeIntegrationAssessments([$record]);
    decideIntegration($record, changes: $changes)->assertSessionHasErrors('decision');
    expect(IntegrationDecision::query()->count())->toBe(0);
})->with([
    [['verdict' => 'APPROVE', 'selected_action' => 'REROUTE']],
    [['verdict' => 'OVERRIDE', 'selected_action' => 'BUFFER']],
]);

test('unknown or non-logistics actions cannot be recorded', function (string $action, string $error): void {
    $record = integrationAssessment();
    fakeIntegrationAssessments([$record]);
    decideIntegration($record, changes: ['verdict' => 'OVERRIDE', 'selected_action' => $action])->assertSessionHasErrors($error);
    expect(IntegrationDecision::query()->count())->toBe(0);
})->with([
    ['UNKNOWN_ACTION', 'selected_action'],
    ['QUARANTINE', 'decision'],
    ['RUN_AS_PLANNED', 'decision'],
]);

test('an override must exist and be eligible in the returned action set', function (bool $present): void {
    $record = integrationAssessment();
    if ($present) {
        foreach ($record['result']['actions'] as &$action) {
            if ($action['action'] === 'REROUTE') {
                $action['eligible'] = false;
            }
        }
        unset($action);
    } else {
        $record['result']['actions'] = array_values(array_filter($record['result']['actions'], fn (array $action): bool => $action['action'] !== 'REROUTE'));
    }
    fakeIntegrationAssessments([$record]);
    decideIntegration($record, UserRole::Logistics, ['verdict' => 'OVERRIDE', 'selected_action' => 'REROUTE'])->assertSessionHasErrors('decision');
    expect(IntegrationDecision::query()->count())->toBe(0);
})->with([true, false]);

test('an unavailable missing or invalid API assessment fails closed', function (string $failure): void {
    $record = integrationAssessment();
    Http::fake(match ($failure) {
        'connection' => fn () => Http::failedConnection(),
        'missing' => ['*' => Http::response([], 404)],
        'error' => ['*' => Http::response([], 503)],
        'invalid' => ['*' => Http::response(['assessment_id' => $record['assessment_id']])],
        'null' => ['*' => Http::response('null')],
    });
    decideIntegration($record)->assertSessionHasErrors('decision');
    expect(IntegrationDecision::query()->count())->toBe(0);
})->with(['connection', 'missing', 'error', 'invalid', 'null']);

test('a null recommendation cannot be converted into an approval', function (): void {
    $displayed = integrationAssessment();
    $current = $displayed;
    $current['result']['recommendation']['action'] = null;
    fakeIntegrationAssessments([$current]);
    decideIntegration($displayed)->assertSessionHasErrors('decision');
    expect(IntegrationDecision::query()->count())->toBe(0);
});

test('submission failure remains visible when the integration page is unavailable', function (): void {
    $record = integrationAssessment();
    Http::fake(fn () => Http::failedConnection());
    $this->followingRedirects();
    decideIntegration($record)->assertInertia(fn (Assert $page) => $page
        ->where('unavailable', true)
        ->where('errors.decision', 'The stored assessment is unavailable. Reload before deciding.'));
    expect(IntegrationDecision::query()->count())->toBe(0);
});

test('a second decision cannot replace the evidence or reason of the first', function (): void {
    $record = integrationAssessment();
    fakeIntegrationAssessments([$record]);
    decideIntegration($record)->assertSessionHasNoErrors();
    $original = IntegrationDecision::query()->sole()->toArray();
    decideIntegration($record, changes: ['reason' => 'A replacement reason.'])->assertSessionHasErrors('decision');
    expect(IntegrationDecision::query()->sole()->toArray())->toBe($original);
});

test('scenario switching exposes only decisions keyed by exact assessment identity', function (): void {
    $normal = integrationAssessment();
    $disruption = integrationAssessment('disruption');
    $severe = integrationAssessment('severe');
    fakeIntegrationAssessments([$normal, $disruption, $severe]);
    decideIntegration($normal)->assertSessionHasNoErrors();

    $this->get(route('integration'))->assertInertia(fn (Assert $page) => $page
        ->component('Integration')->has('decisions', 1)
        ->where('decisions.'.$normal['assessment_id'].'.action', 'BUFFER')
        ->where('decisions.'.$normal['assessment_id'].'.verdict', 'APPROVE')
        ->missing('decisions.'.$disruption['assessment_id'])
        ->missing('decisions.'.$severe['assessment_id'])
        ->where('assessments.0.result.recommendation.action', 'BUFFER')
        ->where('assessments.1.result.recommendation.action', 'EXPEDITE')
        ->where('assessments.2.result.recommendation.action', 'REROUTE')
        ->where('actionRoles.BUFFER', 'operator')
        ->where('actionRoles.EXPEDITE', 'logistics')
        ->where('actionRoles.REROUTE', 'logistics'));
});

test('a new hash has no inherited decision and retains the old audit record', function (): void {
    $old = integrationAssessment();
    fakeIntegrationAssessments([$old]);
    decideIntegration($old)->assertSessionHasNoErrors();
    $new = integrationAssessment(revision: 2);
    fakeIntegrationAssessments([$new]);

    $this->get(route('integration'))->assertInertia(fn (Assert $page) => $page
        ->where('assessments.0.assessment_id', $new['assessment_id'])
        ->where('decisions', []));
    expect(IntegrationDecision::query()->sole()->assessment_id)->toBe($old['assessment_id']);
    decideIntegration($new)->assertSessionHasNoErrors();
    expect(IntegrationDecision::query()->count())->toBe(2);
});

test('the named demo decision can be reopened without touching any other record', function (string $scenario, string $role): void {
    $record = integrationAssessment($scenario);
    $other = integrationAssessment($scenario === 'normal' ? 'disruption' : 'normal');
    fakeIntegrationAssessments([$record, $other]);
    decideIntegration($other, ShipmentAction::from($other['result']['recommendation']['action'])->approver())->assertSessionHasNoErrors();
    decideIntegration($record, UserRole::from($role))->assertSessionHasNoErrors();
    $otherDecision = IntegrationDecision::query()->where('assessment_id', $other['assessment_id'])->sole()->toArray();

    $this->delete(route('integration.decisions.destroy', $record['assessment_id']))
        ->assertRedirect(route('integration'))->assertSessionHasNoErrors();
    expect(IntegrationDecision::query()->sole()->toArray())->toBe($otherDecision);
    decideIntegration($record, UserRole::from($role))->assertSessionHasNoErrors();
    Http::assertNotSent(fn (Request $request): bool => $request->method() !== 'GET');
})->with([['normal', 'operator'], ['disruption', 'logistics'], ['severe', 'logistics']]);

test('reopening requires the recorded role', function (): void {
    $record = integrationAssessment('severe');
    fakeIntegrationAssessments([$record]);
    decideIntegration($record, UserRole::Logistics)->assertSessionHasNoErrors();
    $this->actingAs(User::factory()->role(UserRole::Operator)->create())->from(route('integration'))
        ->delete(route('integration.decisions.destroy', $record['assessment_id']))->assertSessionHasErrors('decision');
    expect(IntegrationDecision::query()->count())->toBe(1);
});

test('a non-demo assessment cannot be reopened', function (bool $simulated, string $shipmentId): void {
    $record = integrationAssessment();
    $record['result']['simulated_shipment']['simulated'] = $simulated;
    $record['result']['shipment_id'] = $shipmentId;
    $record['result']['simulated_shipment']['shipment_id'] = $shipmentId;
    fakeIntegrationAssessments([$record]);
    decideIntegration($record)->assertSessionHasNoErrors();
    $this->from(route('integration'))->delete(route('integration.decisions.destroy', $record['assessment_id']))->assertSessionHasErrors('decision');
    expect(IntegrationDecision::query()->count())->toBe(1);
})->with([[false, 'SIM-BASEL-NORMAL'], [true, 'ANOTHER-SHIPMENT']]);

test('reopening fails closed if the source is unavailable or has changed', function (bool $unavailable): void {
    $record = integrationAssessment();
    fakeIntegrationAssessments([$record]);
    decideIntegration($record)->assertSessionHasNoErrors();
    if ($unavailable) {
        Http::swap(new Factory);
        Http::preventStrayRequests();
        Http::fake(fn () => Http::failedConnection());
    } else {
        $record['input_sha256'] = str_repeat('c', 64);
        fakeIntegrationAssessments([$record]);
    }
    $this->from(route('integration'))->delete(route('integration.decisions.destroy', $record['assessment_id']))->assertSessionHasErrors('decision');
    expect(IntegrationDecision::query()->count())->toBe(1);
})->with([true, false]);

test('integration decision endpoints require authentication and a hash identifier', function (): void {
    $record = integrationAssessment();
    $this->post(route('integration.decisions.store', $record['assessment_id']), integrationDecisionPayload($record))->assertRedirect(route('login'));
    $this->delete(route('integration.decisions.destroy', $record['assessment_id']))->assertRedirect(route('login'));
    $this->actingAs(User::factory()->create())->post('/integration/assessments/s1/decisions')->assertNotFound();
    Http::assertNothingSent();
});
