<?php

declare(strict_types=1);

namespace App\Data;

use Spatie\LaravelData\Data;

final class AnswerData extends Data
{
    /**
     * @param  'yes'|'no'|'at_risk'  $verdict
     */
    public function __construct(
        public string $question,
        public string $verdict,
        public string $detail,
    ) {}
}
