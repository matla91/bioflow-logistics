<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Actions\Shipments\SummarizeShipments;
use App\Models\User;
use Illuminate\Container\Attributes\CurrentUser;
use Inertia\Inertia;
use Inertia\Response;

final class DashboardController extends Controller
{
    /**
     * Show the overview of all shipments.
     */
    public function __invoke(#[CurrentUser] User $user, SummarizeShipments $summarizeShipments): Response
    {
        return Inertia::render('Dashboard', [
            'overview' => $summarizeShipments->handle($user),
        ]);
    }
}
