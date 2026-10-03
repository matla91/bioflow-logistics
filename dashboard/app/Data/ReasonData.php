<?php

declare(strict_types=1);

namespace App\Data;

use App\Enums\EvidenceKind;
use Spatie\LaravelData\Data;

final class ReasonData extends Data
{
    public function __construct(
        public int $n,
        public string $text,
        public EvidenceKind $kind,
        public string $source,
        public string $at,
        public ?string $signal = null,
    ) {}
}
