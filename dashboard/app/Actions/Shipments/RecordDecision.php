<?php

declare(strict_types=1);

namespace App\Actions\Shipments;

use App\Data\DecisionInputData;
use App\Enums\ShipmentAction;
use App\Enums\ShipmentStatus;
use App\Enums\UserRole;
use App\Enums\Verdict;
use App\Exceptions\DecisionNotAllowed;
use App\Models\Assessment;
use App\Models\Decision;
use App\Models\Shipment;
use App\Models\User;
use Illuminate\Support\Facades\DB;

final class RecordDecision
{
    /**
     * Record a person's approval or override and close the shipment.
     *
     * @throws DecisionNotAllowed
     */
    public function handle(Shipment $shipment, User $user, DecisionInputData $input): Decision
    {
        if (! $shipment->status->isOpen()) {
            throw new DecisionNotAllowed('This shipment already has a decision.');
        }

        $assessment = $shipment->latestAssessment;

        if ($assessment === null || $assessment->id !== $input->assessmentId) {
            throw new DecisionNotAllowed('A newer assessment is available. Reload before deciding.');
        }

        $isRecommended = $input->action === $assessment->recommended_action;

        if ($input->verdict === Verdict::Approve && ! $isRecommended) {
            throw new DecisionNotAllowed('Only the recommended action can be approved; choose Override for another action.');
        }

        if ($input->verdict === Verdict::Override && $isRecommended) {
            throw new DecisionNotAllowed('Choose a different action to override the recommendation.');
        }

        $requiredRole = $this->requiredRole($assessment, $input);

        if ($user->role !== $requiredRole) {
            throw new DecisionNotAllowed(sprintf('This decision needs %s approval.', $requiredRole->label()));
        }

        return DB::transaction(function () use ($shipment, $assessment, $user, $input): Decision {
            $decision = $shipment->decisions()->create([
                'assessment_id' => $assessment->id,
                'user_id' => $user->id,
                'role' => $user->role,
                'verdict' => $input->verdict,
                'action' => $input->action,
                'reason' => $input->reason,
                'snapshot_sha256' => $assessment->snapshot_sha256,
                'decided_at' => now(),
            ]);

            $shipment->update(['status' => ShipmentStatus::Closed]);

            return $decision;
        });
    }

    /**
     * Approvals need the recommendation's approver. Overrides need the chosen
     * action's approver, and only QA may override a quarantine recommendation.
     */
    private function requiredRole(Assessment $assessment, DecisionInputData $input): UserRole
    {
        if ($input->verdict === Verdict::Approve) {
            return $assessment->approver_role;
        }

        return $assessment->recommended_action === ShipmentAction::Quarantine
            ? UserRole::Qa
            : $input->action->approver();
    }
}
