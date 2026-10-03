<?php

declare(strict_types=1);

namespace Database\Seeders;

use App\Enums\EvidenceKind;
use App\Enums\ShipmentAction;
use App\Enums\ShipmentStatus;
use App\Enums\UserRole;
use App\Enums\Verdict;
use App\Models\Assessment;
use App\Models\Decision;
use App\Models\Shipment;
use App\Models\User;
use Carbon\CarbonImmutable;
use Illuminate\Database\Seeder;
use Illuminate\Support\Facades\File;

/**
 * Seeds the three hand-built demo scenes (from the dashboard-v0 snapshots),
 * a decided history and a few in-transit shipments sampled from the ML
 * team's simulated training set (docs/simulated_shipments_3000.csv).
 */
final class ShipmentSeeder extends Seeder
{
    private const string TIMEZONE = 'Europe/Zurich';

    private const string MATERIAL = '2–8 °C pharma intermediate';

    /**
     * Route segments indexed by the ML feature `segment_code`.
     */
    private const array SEGMENTS = [
        'sea', 'repack_rtm', 'truck_to_barge', 'transfer',
        'barge', 'unload_basel', 'truck_to_site', 'dock',
    ];

    /**
     * History positions (0 = yesterday) of the non-routine outcomes, so
     * they are spread through the list instead of clustered.
     */
    private const array EXCEPTION_SLOTS = [2, 6, 9, 13, 16, 19];

    /** @var array<string, User> */
    private array $usersByRole = [];

    public function run(): void
    {
        foreach (UserRole::cases() as $role) {
            $this->usersByRole[$role->value] = User::query()->where('role', $role)->firstOrFail();
        }

        Shipment::query()->delete();

        /** @var list<array<string, mixed>> $scenes */
        $scenes = File::json(database_path('seeders/data/demo_scenes.json'));
        foreach ($scenes as $scene) {
            $this->seedScene($scene);
        }

        /** @var array{history: list<array<string, mixed>>, in_transit: list<array<string, mixed>>} $simulated */
        $simulated = File::json(database_path('seeders/data/simulated_shipments.json'));
        $this->seedHistory($simulated['history']);
        $this->seedInTransit($simulated['in_transit']);
    }

    /**
     * @param  array<string, mixed>  $scene
     */
    private function seedScene(array $scene): void
    {
        $chargeAt = CarbonImmutable::parse($scene['chargeAt'])->utc();
        $now = CarbonImmutable::parse($scene['now'])->utc();
        $stops = collect($scene['journey']['stops']);
        $blocked = $stops->firstWhere('state', 'blocked');

        $shipment = Shipment::query()->create([
            'lot' => 'SIM-'.$chargeAt->tz(self::TIMEZONE)->format('y-md').'-'.mb_strtoupper((string) $scene['id']),
            'scenario' => $scene['id'],
            'simulated' => true,
            'material' => self::MATERIAL,
            'origin' => 'Shanghai',
            'reactor' => $scene['reactor'],
            'timezone' => $scene['timezone'],
            'departed_at' => $chargeAt->subDays(40),
            'charge_at' => $chargeAt,
            'arrived_at' => $blocked === null ? $now->subHours(2) : null,
            'status' => $blocked === null ? ShipmentStatus::Arrived : ShipmentStatus::Suspended,
            'current_segment' => $blocked === null ? 'dock' : 'barge',
            'route_progress' => $scene['journey']['progress'],
        ]);

        $exposures = collect($scene['temperature']['exposures']);
        $shipment->observations()->createMany(collect($scene['temperature']['points'])->map(function (array $point) use ($exposures): array {
            $at = CarbonImmutable::parse($point['at'])->utc();
            $exposure = $exposures->first(fn (array $e): bool => $at->betweenIncluded($e['from'], $e['to']));

            return [
                'observed_at' => $at,
                'segment' => $exposure === null ? 'barge' : mb_strtolower(str_replace(' ', '_', (string) $exposure['label'])),
                'route_progress' => 0,
                'refrigerated' => $exposure === null,
                'product_temp_c' => $point['c'],
            ];
        })->all());

        $baseline = collect($scene['options'])->firstWhere('action', ShipmentAction::RunAsPlanned->value);
        $recommendation = $scene['recommendation'];

        $this->createAssessment($shipment, [
            'assessed_at' => $now,
            'model' => 'dashboard-v0 decision_analysis (2,000 runs)',
            'p_miss_slot' => $baseline['pMissSlot'],
            'p_excursion' => $baseline['pExcursion'],
            'budget_used' => $scene['budget']['usedFraction'],
            'recommended_action' => $recommendation['action'],
            'approver_role' => $recommendation['approver'],
            'answers' => $scene['answers'],
            'options' => $scene['options'],
            'reasons' => $scene['reasons'],
            'would_change_if' => $scene['wouldChangeIf'],
            'signals' => $scene['signals'],
            'briefing' => [
                'title' => $recommendation['title'],
                'summary' => $recommendation['summary'],
                'glance' => $recommendation['glance'],
                'source' => 'template',
            ],
        ]);
    }

    /**
     * @param  list<array<string, mixed>>  $history
     */
    private function seedHistory(array $history): void
    {
        $routine = array_values(array_filter($history, fn (array $h): bool => $h['outcome'] === ShipmentAction::RunAsPlanned->value));
        $exceptions = array_values(array_filter($history, fn (array $h): bool => $h['outcome'] !== ShipmentAction::RunAsPlanned->value));
        $today = CarbonImmutable::now(self::TIMEZONE)->startOfDay();

        foreach (range(0, count($history) - 1) as $daysAgo) {
            $entry = in_array($daysAgo, self::EXCEPTION_SLOTS, true) && $exceptions !== []
                ? array_shift($exceptions)
                : array_shift($routine) ?? array_shift($exceptions);

            $chargeAt = $today->subDays($daysAgo + 1)->setTime(6, 0)->utc();
            $action = ShipmentAction::from($entry['outcome']);
            $final = $entry['final'];

            $shipment = $this->createSimulatedShipment($entry, $chargeAt, $entry['observations'], ShipmentStatus::Closed);
            $assessment = $this->createAssessment($shipment, $this->simulatedAssessment($chargeAt->subHours(3), $action, $final));

            $this->recordDecision($shipment, $assessment, $daysAgo === 4
                ? [Verdict::Override, ShipmentAction::Buffer, 'R2 restart overran by 3 h; kept this lot in cold store and charged from stock.']
                : [Verdict::Approve, $action, $this->approvalReason($action)]);
        }
    }

    /**
     * @param  list<array<string, mixed>>  $inTransit
     */
    private function seedInTransit(array $inTransit): void
    {
        $outlookActions = [
            'on_track' => ShipmentAction::RunAsPlanned,
            'late_cold' => ShipmentAction::Expedite,
            'warm' => ShipmentAction::RunAsPlanned,
        ];

        foreach ($inTransit as $i => $entry) {
            $observations = array_values(array_filter($entry['observations'], fn (array $o): bool => $o['time_to_slot_min'] > 0));
            $last = end($observations);
            $lastObservedAt = CarbonImmutable::now()->subMinutes(20 + $i * 7);
            $chargeAt = $lastObservedAt->tz(self::TIMEZONE)->addMinutes((int) $last['time_to_slot_min'])->addDays($i)->setTime(6, 0)->utc();

            $shipment = $this->createSimulatedShipment($entry, $chargeAt, $observations, ShipmentStatus::InTransit, $lastObservedAt);

            $final = [...$last, 'on_time' => $entry['outlook'] === 'late_cold' ? 0 : 1, 'qa_budget_exceeded' => 0];
            $this->createAssessment($shipment, $this->simulatedAssessment(
                $lastObservedAt,
                $outlookActions[$entry['outlook']],
                $final,
                atRisk: $entry['outlook'] === 'warm',
            ));
        }
    }

    /**
     * @param  array<string, mixed>  $entry
     * @param  list<array<string, mixed>>  $observations
     * @param  ?CarbonImmutable  $lastObservedAt  defaults to the time implied by the last observation's time to slot
     */
    private function createSimulatedShipment(array $entry, CarbonImmutable $chargeAt, array $observations, ShipmentStatus $status, ?CarbonImmutable $lastObservedAt = null): Shipment
    {
        $last = end($observations);
        $lastObservedAt ??= $chargeAt->subMinutes((int) $last['time_to_slot_min']);
        $closed = $status === ShipmentStatus::Closed;

        $shipment = Shipment::query()->create([
            'lot' => 'SIM-'.$chargeAt->tz(self::TIMEZONE)->format('y-md'),
            'external_ref' => $entry['external_ref'],
            'simulated' => true,
            'material' => self::MATERIAL,
            'origin' => 'Shanghai',
            'reactor' => 'R2',
            'departed_at' => $chargeAt->subDays(40),
            'charge_at' => $chargeAt,
            'eta' => $closed ? null : $lastObservedAt->addMinutes((int) ($last['remaining_min'] ?? 0)),
            'arrived_at' => $closed ? $lastObservedAt->addMinutes((int) ($last['remaining_min'] ?? 0)) : null,
            'status' => $status,
            'current_segment' => $closed ? 'dock' : self::SEGMENTS[(int) $last['segment_code']],
            'route_progress' => $closed ? 1 : $last['route_progress'],
        ]);

        $shipment->observations()->createMany(array_map(fn (array $o): array => [
            'observed_at' => $lastObservedAt->subMinutes((int) ($o['time_to_slot_min'] - $last['time_to_slot_min'])),
            'segment' => self::SEGMENTS[(int) $o['segment_code']],
            'route_progress' => $o['route_progress'],
            'refrigerated' => (bool) $o['refrigerated'],
            'product_temp_c' => $o['current_temp_c'],
            'ambient_c' => $o['ambient_c'],
            'river_level_cm' => $o['river_route_level_cm'],
            'excursion_min' => $o['excursion_min'],
            'budget_used' => $o['budget_used'],
        ], $observations));

        return $shipment;
    }

    /**
     * Shape an assessment from the simulated labels, mimicking the decision rules.
     *
     * @param  array<string, mixed>  $final
     * @return array<string, mixed>
     */
    private function simulatedAssessment(CarbonImmutable $assessedAt, ShipmentAction $recommended, array $final, bool $atRisk = false): array
    {
        $river = (float) $final['river_route_level_cm'];
        $budget = (float) $final['budget_used'];
        $onTime = (bool) $final['on_time'];
        $budgetExceeded = (bool) $final['qa_budget_exceeded'];

        $pMiss = $onTime ? 0.03 : ($river < 50 ? 1.0 : 0.72);
        $pExcursion = $budgetExceeded ? 0.88 : ($atRisk ? 0.35 : 0.02);
        $budgetPct = (int) round($budget * 100);

        $options = array_map(fn (ShipmentAction $action): array => [
            'action' => $action->value,
            'label' => $action->label(),
            ...$this->optionFigures($action, $pMiss, $pExcursion),
            'recommended' => $action === $recommended,
            'note' => $action === $recommended ? 'Lowest expected delay' : $this->rejectionNote($action, $recommended),
        ], ShipmentAction::cases());

        return [
            'assessed_at' => $assessedAt,
            'model' => 'risk-model simulated',
            'p_miss_slot' => $pMiss,
            'p_excursion' => $pExcursion,
            'budget_used' => $budget,
            'recommended_action' => $recommended,
            'approver_role' => $recommended->approver(),
            'answers' => [
                'arrival' => [
                    'question' => 'Will it be here?',
                    'verdict' => $onTime ? 'yes' : 'no',
                    'detail' => $onTime ? 'On schedule · '.round($pMiss * 100).'% chance of missing the slot' : 'Late · '.round($pMiss * 100).'% chance of missing the slot',
                ],
                'quality' => [
                    'question' => 'Still good to use?',
                    'verdict' => $budgetExceeded ? 'no' : ($atRisk ? 'at_risk' : 'yes'),
                    'detail' => $budgetPct.'% of 120-min excursion budget used',
                ],
            ],
            'options' => $options,
            'reasons' => [
                ['n' => 1, 'text' => sprintf('River at %d cm on the barge route', $river), 'kind' => EvidenceKind::Simulated, 'source' => 'Simulated route level', 'at' => $assessedAt->toIso8601String()],
                ['n' => 2, 'text' => sprintf('%d%% chance of missing the slot', round($pMiss * 100)), 'kind' => EvidenceKind::Simulated, 'source' => 'Risk model', 'at' => $assessedAt->toIso8601String()],
                ['n' => 3, 'text' => sprintf('%d%% of excursion budget used', $budgetPct), 'kind' => EvidenceKind::Simulated, 'source' => 'Shipment observations', 'at' => $assessedAt->toIso8601String()],
            ],
            'would_change_if' => ['River level changes', 'Handover exposure changes', 'Cold-store stock changes'],
            'briefing' => [
                'title' => $recommended->label(),
                'summary' => sprintf('%s recommended: %d%% chance of missing the slot and %d%% of the excursion budget used.', $recommended->label(), round($pMiss * 100), $budgetPct),
                'glance' => $recommended->label().'.',
                'source' => 'template',
            ],
        ];
    }

    /**
     * @return array{pMissSlot: float, expDelayMin: float, pExcursion: float, stockAfter: int}
     */
    private function optionFigures(ShipmentAction $action, float $pMiss, float $pExcursion): array
    {
        $baselineDelay = $pMiss >= 1.0 ? 10080.0 : round($pMiss * 600);

        return match ($action) {
            ShipmentAction::RunAsPlanned => ['pMissSlot' => $pMiss, 'expDelayMin' => $baselineDelay, 'pExcursion' => $pExcursion, 'stockAfter' => 2],
            ShipmentAction::Expedite => ['pMissSlot' => $pMiss >= 1.0 ? 1.0 : round($pMiss * 0.1, 2), 'expDelayMin' => $pMiss >= 1.0 ? $baselineDelay : 0.0, 'pExcursion' => $pExcursion, 'stockAfter' => 2],
            ShipmentAction::Buffer => ['pMissSlot' => 0.0, 'expDelayMin' => 0.0, 'pExcursion' => $pExcursion, 'stockAfter' => 1],
            ShipmentAction::Reroute => ['pMissSlot' => min(1.0, round($pMiss * 0.4, 2)), 'expDelayMin' => round($baselineDelay * 0.3), 'pExcursion' => min(1.0, round($pExcursion + 0.05, 2)), 'stockAfter' => 2],
            ShipmentAction::Quarantine => ['pMissSlot' => 0.0, 'expDelayMin' => 0.0, 'pExcursion' => $pExcursion, 'stockAfter' => 1],
        };
    }

    private function rejectionNote(ShipmentAction $action, ShipmentAction $recommended): string
    {
        if ($recommended === ShipmentAction::Quarantine) {
            return 'Excursion limit exceeded';
        }

        return match ($action) {
            ShipmentAction::RunAsPlanned => 'Misses the slot',
            ShipmentAction::Expedite => 'No faster slot helps',
            ShipmentAction::Buffer => 'Would spend stock for nothing',
            ShipmentAction::Reroute => 'Adds excursion risk',
            ShipmentAction::Quarantine => 'No excursion · QA only',
        };
    }

    /**
     * @param  array<string, mixed>  $attributes
     */
    private function createAssessment(Shipment $shipment, array $attributes): Assessment
    {
        return $shipment->assessments()->create([
            ...$attributes,
            'snapshot_sha256' => hash('sha256', (string) json_encode([$shipment->lot, $attributes])),
        ]);
    }

    /**
     * @param  array{0: Verdict, 1: ShipmentAction, 2: string}  $decision
     */
    private function recordDecision(Shipment $shipment, Assessment $assessment, array $decision): void
    {
        [$verdict, $action, $reason] = $decision;
        $role = $verdict === Verdict::Override ? $action->approver() : $assessment->approver_role;

        Decision::query()->create([
            'shipment_id' => $shipment->id,
            'assessment_id' => $assessment->id,
            'user_id' => $this->usersByRole[$role->value]->id,
            'role' => $role,
            'verdict' => $verdict,
            'action' => $action,
            'reason' => $reason,
            'snapshot_sha256' => $assessment->snapshot_sha256,
            'decided_at' => $assessment->assessed_at->addMinutes(12),
        ]);
    }

    private function approvalReason(ShipmentAction $action): string
    {
        return match ($action) {
            ShipmentAction::RunAsPlanned => 'On time and in band.',
            ShipmentAction::Expedite => 'Booked the earlier barge slot.',
            ShipmentAction::Buffer => 'Barge held at Kaub; charged from cold-store stock.',
            ShipmentAction::Reroute => 'Switched the last leg to truck.',
            ShipmentAction::Quarantine => 'Excursion over budget; lot held for QA review.',
        };
    }
}
