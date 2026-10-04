<?php

declare(strict_types=1);

namespace App\Actions\Integration;

use App\Data\IntegrationDecisionInputData;
use App\Enums\Verdict;
use App\Exceptions\DecisionNotAllowed;
use App\Models\IntegrationDecision;
use App\Models\User;
use Illuminate\Database\UniqueConstraintViolationException;

final class RecordIntegrationDecision
{
    public function __construct(private readonly ReadStoredAssessment $readAssessment) {}

    /** @throws DecisionNotAllowed */
    public function handle(string $assessmentId, User $user, IntegrationDecisionInputData $input): IntegrationDecision
    {
        $assessment = $this->readAssessment->handle($assessmentId);

        if (! $assessment->matches($input->identity)) {
            throw new DecisionNotAllowed('The assessment evidence or recommendation has changed. Reload before deciding.');
        }

        if ($assessment->identity['recommended_action'] === null || ! $assessment->isEligible($input->selectedAction)) {
            throw new DecisionNotAllowed('Choose an eligible action returned by this assessment. Reload before deciding.');
        }

        $recommended = $input->selectedAction->value === $assessment->identity['recommended_action'];
        if (($input->verdict === Verdict::Approve) !== $recommended) {
            throw new DecisionNotAllowed('Approve the recommended action, or override with a different eligible action.');
        }

        $role = $input->selectedAction->approver();
        if ($user->role !== $role) {
            throw new DecisionNotAllowed(sprintf('This decision needs %s approval.', $role->label()));
        }

        if (mb_trim($input->reason) === '') {
            throw new DecisionNotAllowed('A reason is required.');
        }

        try {
            return IntegrationDecision::query()->create([
                ...$assessment->identity,
                'verdict' => $input->verdict,
                'selected_action' => $input->selectedAction,
                'user_id' => $user->id,
                'role' => $user->role,
                'reason' => mb_trim($input->reason),
                'assessment_snapshot' => $assessment->snapshot,
                'decided_at' => now(),
            ]);
        } catch (UniqueConstraintViolationException) {
            throw new DecisionNotAllowed('A decision is already recorded for this assessment. Reload to review it.');
        }
    }
}
