<?php

declare(strict_types=1);

namespace App\Actions\Shipments;

use App\Data\RecommendationData;
use App\Data\ShipmentConsoleData;
use App\Data\ShipmentDecisionData;
use App\Enums\ShipmentStatus;
use App\Models\Assessment;
use App\Models\Shipment;
use App\Models\ShipmentObservation;
use Illuminate\Support\Collection;
use Illuminate\Support\Str;

final class BuildShipmentConsole
{
    private const int EXCURSION_BUDGET_MIN = 120;

    /**
     * Fixed stops on the Rotterdam → R2 route, by share of the journey.
     *
     * @var list<array{id: string, label: string, position: float}>
     */
    private const array STOPS = [
        ['id' => 'rtm', 'label' => 'Rotterdam', 'position' => 0.0],
        ['id' => 'barge', 'label' => 'Barge', 'position' => 0.28],
        ['id' => 'kaub', 'label' => 'Kaub', 'position' => 0.5],
        ['id' => 'basel', 'label' => 'Basel', 'position' => 0.78],
        ['id' => 'r2', 'label' => 'R2', 'position' => 1.0],
    ];

    public function handle(Shipment $shipment, Assessment $assessment): ShipmentConsoleData
    {
        $shipment->loadMissing(['observations', 'decisions.user']);
        $briefing = $assessment->briefing;

        return new ShipmentConsoleData(
            id: $shipment->id,
            lot: $shipment->lot,
            scenario: $shipment->scenario,
            simulated: $shipment->simulated,
            reactor: $shipment->reactor,
            chargeAt: $shipment->charge_at->toIso8601String(),
            asOf: $assessment->assessed_at->toIso8601String(),
            timezone: $shipment->timezone,
            status: $shipment->status,
            assessmentId: $assessment->id,
            answers: $assessment->answers,
            recommendation: new RecommendationData(
                action: $assessment->recommended_action,
                title: $briefing === null ? $assessment->recommended_action->label() : $briefing->title,
                summary: $briefing->summary ?? '',
                glance: $briefing->glance ?? '',
                approver: $assessment->approver_role,
            ),
            reasons: $assessment->reasons,
            options: $assessment->options,
            wouldChangeIf: $assessment->would_change_if,
            journey: [
                'stops' => $this->stops($shipment),
                'progress' => $shipment->route_progress,
            ],
            temperature: [
                'band' => [2, 8],
                'points' => array_values($shipment->observations->map(fn (ShipmentObservation $o): array => [
                    'at' => $o->observed_at->toIso8601String(),
                    'c' => $o->product_temp_c,
                ])->all()),
                'exposures' => $this->exposures($shipment->observations),
            ],
            budget: ['usedFraction' => $assessment->budget_used, 'budgetMin' => self::EXCURSION_BUDGET_MIN],
            signals: $assessment->signals ?? [],
            log: array_values($shipment->decisions->map(ShipmentDecisionData::fromModel(...))->all()),
        );
    }

    /**
     * @return list<array{id: string, label: string, position: float, state: string}>
     */
    private function stops(Shipment $shipment): array
    {
        return array_map(function (array $stop) use ($shipment): array {
            $atStop = abs($stop['position'] - $shipment->route_progress) < 0.01;

            $state = match (true) {
                $atStop && $shipment->status === ShipmentStatus::Suspended => 'blocked',
                $atStop => 'current',
                $stop['position'] < $shipment->route_progress => 'done',
                default => 'pending',
            };

            return [...$stop, 'state' => $state];
        }, self::STOPS);
    }

    /**
     * Group consecutive unrefrigerated readings into exposed handovers.
     *
     * @param  Collection<int, ShipmentObservation>  $observations
     * @return list<array{from: string, to: string, label: string}>
     */
    private function exposures(Collection $observations): array
    {
        $exposures = [];
        $run = [];

        foreach ([...$observations->all(), null] as $observation) {
            if ($observation instanceof ShipmentObservation && ! $observation->refrigerated) {
                $run[] = $observation;

                continue;
            }

            if ($run !== []) {
                $exposures[] = [
                    'from' => $run[0]->observed_at->toIso8601String(),
                    'to' => $run[array_key_last($run)]->observed_at->toIso8601String(),
                    'label' => Str::headline($run[0]->segment),
                ];
                $run = [];
            }
        }

        return $exposures;
    }
}
