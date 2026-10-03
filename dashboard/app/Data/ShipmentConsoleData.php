<?php

declare(strict_types=1);

namespace App\Data;

use App\Enums\ShipmentStatus;
use Spatie\LaravelData\Data;
use Spatie\LaravelData\DataCollection;

/**
 * Everything the operator console renders for one shipment.
 */
final class ShipmentConsoleData extends Data
{
    /**
     * @param  DataCollection<int, ReasonData>  $reasons
     * @param  DataCollection<int, ActionOptionData>  $options
     * @param  list<string>  $wouldChangeIf
     * @param  array{stops: list<array{id: string, label: string, position: float, state: string}>, progress: float}  $journey
     * @param  array{band: array{0: int, 1: int}, points: list<array{at: string, c: float}>, exposures: list<array{from: string, to: string, label: string}>}  $temperature
     * @param  array{usedFraction: float, budgetMin: int}  $budget
     * @param  array<string, mixed>  $signals
     * @param  list<ShipmentDecisionData>  $log
     */
    public function __construct(
        public int $id,
        public string $lot,
        public ?string $scenario,
        public bool $simulated,
        public string $reactor,
        public string $chargeAt,
        public string $asOf,
        public string $timezone,
        public ShipmentStatus $status,
        public int $assessmentId,
        public AnswersData $answers,
        public RecommendationData $recommendation,
        public DataCollection $reasons,
        public DataCollection $options,
        public array $wouldChangeIf,
        public array $journey,
        public array $temperature,
        public array $budget,
        public array $signals,
        public array $log,
    ) {}
}
