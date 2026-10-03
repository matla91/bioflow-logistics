<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Actions\Shipments\RecordDecision;
use App\Actions\Shipments\ReopenDemoShipment;
use App\Exceptions\DecisionNotAllowed;
use App\Http\Requests\StoreDecisionRequest;
use App\Models\Shipment;
use App\Models\User;
use Illuminate\Container\Attributes\CurrentUser;
use Illuminate\Http\RedirectResponse;
use Inertia\Inertia;

final class ShipmentDecisionController extends Controller
{
    /**
     * Approve or override the shipment's current recommendation.
     */
    public function store(StoreDecisionRequest $request, Shipment $shipment, #[CurrentUser] User $user, RecordDecision $recordDecision): RedirectResponse
    {
        try {
            $decision = $recordDecision->handle($shipment, $user, $request->toData());
        } catch (DecisionNotAllowed $decisionNotAllowed) {
            return back()->withErrors(['decision' => $decisionNotAllowed->getMessage()]);
        }

        Inertia::flash('toast', ['type' => 'success', 'message' => __(':verdict recorded: :action.', [
            'verdict' => ucfirst(mb_strtolower($decision->verdict->value)),
            'action' => $decision->action->label(),
        ])]);

        return to_route('shipments.show', $shipment);
    }

    /**
     * Reopen a demo scene so the decision can be rehearsed again.
     */
    public function destroy(Shipment $shipment, ReopenDemoShipment $reopenDemoShipment): RedirectResponse
    {
        try {
            $reopenDemoShipment->handle($shipment);
        } catch (DecisionNotAllowed $decisionNotAllowed) {
            return back()->withErrors(['decision' => $decisionNotAllowed->getMessage()]);
        }

        Inertia::flash('toast', ['type' => 'success', 'message' => __('Demo scene reopened.')]);

        return to_route('shipments.show', $shipment);
    }
}
