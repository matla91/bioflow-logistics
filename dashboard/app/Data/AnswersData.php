<?php

declare(strict_types=1);

namespace App\Data;

use Spatie\LaravelData\Data;

final class AnswersData extends Data
{
    public function __construct(
        public AnswerData $arrival,
        public AnswerData $quality,
    ) {}
}
