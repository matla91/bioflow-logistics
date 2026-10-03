<?php

declare(strict_types=1);

namespace App\Data;

use Spatie\LaravelData\Data;

final class SignalData extends Data
{
    /**
     * @param  list<array{at: string, v: float}>  $points
     * @param  array{v: float, label: string}|null  $threshold
     */
    public function __construct(
        public string $title,
        public string $unit,
        public array $points,
        public ?array $threshold = null,
    ) {}
}
