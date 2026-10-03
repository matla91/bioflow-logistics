<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Actions\Shipments\BuildShipmentConsole;
use App\Actions\Shipments\ListShipments;
use App\Models\Shipment;
use Inertia\Inertia;
use Inertia\Response;

final class ShipmentController extends Controller
{
    /**
     * Show upcoming shipments and the decision history.
     */
    public function index(ListShipments $listShipments): Response
    {
        return Inertia::render('shipments/Index', $listShipments->handle());
    }

    /**
     * Show the operator console for one shipment.
     */
    public function show(Shipment $shipment, BuildShipmentConsole $buildConsole): Response
    {
        $assessment = $shipment->latestAssessment;

        abort_if($assessment === null, 404);

        return Inertia::render('shipments/Show', [
            'shipment' => $buildConsole->handle($shipment, $assessment),
        ]);
    }
}
