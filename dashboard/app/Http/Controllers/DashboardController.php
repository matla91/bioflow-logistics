<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Inertia\Inertia;
use Inertia\Response;
use JsonException;

final class DashboardController extends Controller
{
    /**
     * Show the hackathon decision dashboard backed by the logistics JSON contract.
     */
    public function __invoke(Request $request): Response
    {
        $requested = $request->string('scenario')->toString();
        $scenario = in_array($requested, ['normal', 'disruption', 'severe'], true)
            ? $requested
            : 'normal';

        $path = dirname(base_path())
            .DIRECTORY_SEPARATOR.'output'
            .DIRECTORY_SEPARATOR."logistics-{$scenario}.json";

        abort_unless(is_file($path), 503, "Logistics demo output is missing: {$path}");

        $contents = file_get_contents($path);
        abort_if($contents === false, 500, 'Unable to read logistics demo output.');

        try {
            $logistics = json_decode($contents, true, 512, JSON_THROW_ON_ERROR);
        } catch (JsonException) {
            abort(500, 'Logistics demo output is invalid JSON.');
        }

        return Inertia::render('Dashboard', [
            'scenario' => $scenario,
            'logistics' => $logistics,
        ]);
    }
}
