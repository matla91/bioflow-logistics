<?php

declare(strict_types=1);

use App\Models\User;
use Illuminate\Http\Client\Request;
use Illuminate\Support\Facades\Http;
use Inertia\Testing\AssertableInertia as Assert;

beforeEach(function (): void {
    $this->withoutVite();
    Http::preventStrayRequests();
});

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

test('batch assessment page requires authentication and is read only', function (): void {
    Http::fake();

    $this->get(route('integration.batches'))->assertRedirect(route('login'));
    $this->actingAs(User::factory()->create())
        ->post(route('integration.batches'))->assertStatus(405);

    Http::assertNothingSent();
});

test('batch assessment page defaults to the first sorted batch and preserves stored evidence', function (): void {
    $first = storedBatchAssessment(0);
    $second = storedBatchAssessment(1);
    Http::fake([
        '*/api/integration/batch-assessments' => Http::response([$second, $first, $first]),
        '*/api/integration/batches/'.$first['batch_id'].'/assessments/latest*' => Http::response($first),
    ]);

    $this->actingAs(User::factory()->create())
        ->get(route('integration.batches'))
        ->assertOk()
        ->assertInertia(fn (Assert $page) => $page
            ->component('BatchAssessment')
            ->has('batches', 2)
            ->where('batches.0.id', $first['batch_id'])
            ->where('batches.0.label', 'Batch 001')
            ->where('batches.1.id', $second['batch_id'])
            ->where('selectedBatchId', $first['batch_id'])
            ->where('assessment', $first)
            ->where('assessment.model_version', 'batch-stored-evidence-v2')
            ->where('assessment.recommendation.action', null)
            ->where('assessment.product_temperature.0.observed_excursion_min', 99.49666380275252)
            ->where('unavailable', false)
            ->where('missing', false));

    Http::assertSentCount(2);
    Http::assertSent(fn (Request $request): bool => $request->method() === 'GET'
        && parse_url($request->url(), PHP_URL_PATH) === '/api/integration/batches/'.$first['batch_id'].'/assessments/latest'
        && $request['dataset_id'] === $first['dataset_id']);
    Http::assertNotSent(fn (Request $request): bool => $request->method() !== 'GET');
});

test('batch selection fetches its latest stored assessment with the matching dataset', function (): void {
    $first = storedBatchAssessment(0);
    $selected = storedBatchAssessment(1);
    $selected['dataset_id'] = 'selected-dataset';
    Http::fake([
        '*/api/integration/batch-assessments' => Http::response([$first, $selected]),
        '*/api/integration/batches/'.$selected['batch_id'].'/assessments/latest*' => Http::response($selected),
    ]);

    $this->actingAs(User::factory()->create())
        ->get(route('integration.batches', ['batch_id' => $selected['batch_id']]))
        ->assertOk()
        ->assertInertia(fn (Assert $page) => $page
            ->component('BatchAssessment')
            ->where('selectedBatchId', $selected['batch_id'])
            ->where('assessment', $selected)
            ->where('assessment.recommendation.action', null)
            ->where('assessment.production_readiness.released_reserved_quantity_kg', 30)
            ->where('assessment.production_readiness.reservation_shortfall_kg', 20)
            ->where('unavailable', false)
            ->where('missing', false));

    Http::assertSentCount(2);
    Http::assertSent(fn (Request $request): bool => $request->method() === 'GET'
        && parse_url($request->url(), PHP_URL_PATH) === '/api/integration/batches/'.$selected['batch_id'].'/assessments/latest'
        && $request['dataset_id'] === 'selected-dataset');
});

test('batch assessment boundary preserves null excursion and missing timing values', function (): void {
    $selected = storedBatchAssessment(3);
    Http::fake([
        '*/api/integration/batch-assessments' => Http::response([$selected]),
        '*/api/integration/batches/'.$selected['batch_id'].'/assessments/latest*' => Http::response($selected),
    ]);

    $this->actingAs(User::factory()->create())
        ->get(route('integration.batches'))
        ->assertInertia(fn (Assert $page) => $page
            ->component('BatchAssessment')
            ->where('assessment', $selected)
            ->where('assessment.product_temperature.0.observed_excursion_min', null)
            ->where('assessment.incoming_shipments.0.on_time_arrival_probability', null)
            ->where('assessment.incoming_shipments.0.eta_p50', null)
            ->where('assessment.incoming_shipments.0.eta_p90', null));
});

test('an empty stored batch list has no fabricated assessment', function (): void {
    Http::fake(['*/api/integration/batch-assessments' => Http::response([])]);

    $this->actingAs(User::factory()->create())
        ->get(route('integration.batches'))
        ->assertOk()
        ->assertInertia(fn (Assert $page) => $page
            ->component('BatchAssessment')
            ->has('batches', 0)
            ->where('assessment', null)
            ->where('selectedBatchId', null)
            ->where('unavailable', false)
            ->where('missing', false));

    Http::assertSentCount(1);
});

test('an unknown selected batch is missing rather than replaced by a demo batch', function (): void {
    Http::fake(['*/api/integration/batch-assessments' => Http::response([storedBatchAssessment(0)])]);

    $this->actingAs(User::factory()->create())
        ->get(route('integration.batches', ['batch_id' => 'unknown-batch']))
        ->assertOk()
        ->assertInertia(fn (Assert $page) => $page
            ->component('BatchAssessment')
            ->has('batches', 1)
            ->where('assessment', null)
            ->where('selectedBatchId', 'unknown-batch')
            ->where('unavailable', false)
            ->where('missing', true));

    Http::assertSentCount(1);
});

test('a missing latest assessment is distinct from an unavailable engine', function (): void {
    $selected = storedBatchAssessment(0);
    Http::fake([
        '*/api/integration/batch-assessments' => Http::response([$selected]),
        '*/api/integration/batches/'.$selected['batch_id'].'/assessments/latest*' => Http::response(['detail' => 'No applicable batch assessment found'], 404),
    ]);

    $this->actingAs(User::factory()->create())
        ->get(route('integration.batches'))
        ->assertOk()
        ->assertInertia(fn (Assert $page) => $page
            ->component('BatchAssessment')
            ->has('batches', 1)
            ->where('assessment', null)
            ->where('selectedBatchId', $selected['batch_id'])
            ->where('unavailable', false)
            ->where('missing', true));

    Http::assertSentCount(2);
});

test('batch assessment page gracefully handles an engine connection outage', function (): void {
    Http::fake(fn () => Http::failedConnection());

    $this->actingAs(User::factory()->create())
        ->get(route('integration.batches', ['batch_id' => 'requested-batch']))
        ->assertOk()
        ->assertInertia(fn (Assert $page) => $page
            ->component('BatchAssessment')
            ->has('batches', 0)
            ->where('assessment', null)
            ->where('selectedBatchId', 'requested-batch')
            ->where('unavailable', true)
            ->where('missing', false));
});

test('a batch list server error is an engine outage rather than missing evidence', function (): void {
    Http::fake(['*/api/integration/batch-assessments' => Http::response([], 500)]);

    $this->actingAs(User::factory()->create())
        ->get(route('integration.batches'))
        ->assertOk()
        ->assertInertia(fn (Assert $page) => $page
            ->component('BatchAssessment')
            ->where('assessment', null)
            ->where('unavailable', true)
            ->where('missing', false));
});

test('a latest assessment server error keeps the batch selector available', function (): void {
    $selected = storedBatchAssessment(0);
    Http::fake([
        '*/api/integration/batch-assessments' => Http::response([$selected]),
        '*/api/integration/batches/'.$selected['batch_id'].'/assessments/latest*' => Http::response([], 500),
    ]);

    $this->actingAs(User::factory()->create())
        ->get(route('integration.batches'))
        ->assertOk()
        ->assertInertia(fn (Assert $page) => $page
            ->component('BatchAssessment')
            ->has('batches', 1)
            ->where('assessment', null)
            ->where('selectedBatchId', $selected['batch_id'])
            ->where('unavailable', true)
            ->where('missing', false));
});

/** @return array<string, mixed> */
function storedBatchAssessment(int $index): array
{
    $records = json_decode(file_get_contents(base_path('../output/batch-assessments-demo.json')), true, 512, JSON_THROW_ON_ERROR);

    return json_decode(json_encode($records[$index], JSON_THROW_ON_ERROR), true, 512, JSON_THROW_ON_ERROR);
}
