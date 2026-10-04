<?php

declare(strict_types=1);

namespace App\Actions\Integration;

use App\Exceptions\DecisionNotAllowed;
use App\Models\IntegrationDecision;
use App\Models\User;
use Illuminate\Support\Facades\DB;

final class ReopenIntegrationDecision
{
    public function __construct(private readonly ReadStoredAssessment $readAssessment) {}

    /** @throws DecisionNotAllowed */
    public function handle(string $assessmentId, User $user): void
    {
        $assessment = $this->readAssessment->handle($assessmentId);

        if (! $assessment->demo) {
            throw new DecisionNotAllowed('Only the named simulated logistics demo decisions can be reopened.');
        }

        DB::transaction(function () use ($assessmentId, $assessment, $user): void {
            $decision = IntegrationDecision::query()->where('assessment_id', $assessmentId)->lockForUpdate()->firstOrFail();

            if (! $assessment->matches($decision->getAttributes())) {
                throw new DecisionNotAllowed('The recorded assessment evidence has changed. Reload before reopening.');
            }

            if ($user->role !== $decision->role) {
                throw new DecisionNotAllowed(sprintf('Reopening this decision needs the %s role.', $decision->role->label()));
            }

            $decision->delete();
        });
    }
}
