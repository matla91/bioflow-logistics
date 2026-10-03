<?php

declare(strict_types=1);

namespace App\Data;

use Spatie\LaravelData\Data;

final class BriefingData extends Data
{
    /**
     * @param  'llm'|'template'  $source
     */
    public function __construct(
        public string $title,
        public string $summary,
        public string $glance,
        public string $source,
    ) {}
}
