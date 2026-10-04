<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Actions\Integration\RecordIntegrationDecision;
use App\Actions\Integration\ReopenIntegrationDecision;
use App\Exceptions\DecisionNotAllowed;
use App\Http\Requests\StoreIntegrationDecisionRequest;
use App\Models\User;
use Illuminate\Container\Attributes\CurrentUser;
use Illuminate\Http\RedirectResponse;
use Inertia\Inertia;

final class IntegrationDecisionController extends Controller
{
    public function store(StoreIntegrationDecisionRequest $request, string $assessmentId, #[CurrentUser] User $user, RecordIntegrationDecision $recordDecision): RedirectResponse
    {
        try {
            $decision = $recordDecision->handle($assessmentId, $user, $request->toData());
        } catch (DecisionNotAllowed $exception) {
            return back()->withErrors(['decision' => $exception->getMessage()]);
        }

        Inertia::flash('toast', ['type' => 'success', 'message' => __(':verdict recorded: :action.', [
            'verdict' => ucfirst(mb_strtolower($decision->verdict->value)),
            'action' => $decision->selected_action->label(),
        ])]);

        return to_route('integration');
    }

    public function destroy(string $assessmentId, #[CurrentUser] User $user, ReopenIntegrationDecision $reopenDecision): RedirectResponse
    {
        try {
            $reopenDecision->handle($assessmentId, $user);
        } catch (DecisionNotAllowed $exception) {
            return back()->withErrors(['decision' => $exception->getMessage()]);
        }

        Inertia::flash('toast', ['type' => 'success', 'message' => __('Demo decision reopened.')]);

        return to_route('integration');
    }
}
