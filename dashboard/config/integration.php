<?php

declare(strict_types=1);

return [
    'url' => env('DATA_ENGINE_URL', 'http://127.0.0.1:8002'),
    // External identifiers from scenarios/logistics/*.json; no Laravel shipment linkage.
    'demo_shipments' => [
        'normal' => 'SIM-BASEL-NORMAL',
        'disruption' => 'SIM-BASEL-DISRUPTION',
        'severe' => 'SIM-BASEL-SEVERE',
    ],
];
