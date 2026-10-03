# Local Codex explanation: frontend handoff

This describes the existing implementation in the local ML backup. These endpoints are implemented in `pipeline/baselhack/backup_api.py` in that copy; they are not present in the outer team scaffold. No streaming listener is required.

## Flow

Frontend → POST assessment → POST explanation → local signed-in `codex exec` → validate evidence selection → render immutable facts → return JSON.

The LLM orders evidence IDs by urgency. It does not write free-form factual claims or change the recommendation. The server renders evidence text from the verified assessment and adds the human-approval/QA reminder.

## Frontend integration

Use the local backend on `http://127.0.0.1:8001`, normally serving the built frontend from the same origin. No cross-origin browser configuration is currently provided; a separate frontend dev server should proxy `/api` and `/snapshots` to this backend.

1. Fetch an assessment with `POST /api/backup/assessment`:

```json
{
  "scenario_id": "s1_normal_2026-05-10",
  "observation_at": null,
  "injection": "none"
}
```

`observation_at` is a timezone-aware timestamp within the scene, or null for the default partial journey shortly before docking. Injection accepts `none`, `spike`, `frozen`, `gap`, or `delay`; these are synthetic demo controls. There is no variant parameter on these endpoints. The result is `BackupAssessment`, including `assessment_id`, arrival and QA statuses/probabilities, observations, evidence, recommendation and limitations.

2. On an explicit Explain button click, call `POST /api/backup/explain` with the same assessment inputs plus its returned ID:

```ts
import type { BackupAssessment, BackupExplanation } from "./interfaces";

async function post<T>(path: string, payload: unknown): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await response.json();
  if (!response.ok) {
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : `Request failed (${response.status})`,
    );
  }
  return body;
}

const query = {
  scenario_id: "s1_normal_2026-05-10",
  observation_at: null,
  injection: "none",
};
const assessment = await post<BackupAssessment>(
  "/api/backup/assessment", query,
);
const explanation = await post<BackupExplanation>(
  "/api/backup/explain",
  { ...query, assessment_id: assessment.assessment_id, use_llm: true },
);
```

The existing generated response contract is:

```ts
type BackupExplanation = {
  assessment_id: string;
  source: "codex" | "template";
  text: string;
  evidence_ids: string[];
  cached: boolean;
  detail: string;
};
```

Render `text` as text, and show `source`, `cached` and `detail` so the user can distinguish a live/cached Codex briefing from a template. `use_llm: false` produces the template immediately without consulting the Codex cache.

Disable the briefing button while pending. Reset the assessment and briefing when scene, cutoff or injection changes; ignore old responses using a request generation counter, as the existing `web/src/BackupConsole.tsx` does. Only display an explanation whose `assessment_id` matches the active assessment.

Error handling: HTTP 400 means invalid scene/time/injection or missing scene files; 422 means request validation failed; 409 means assessment evidence changed, so refresh the assessment. CLI absence, timeout, process failure or invalid structured output returns a successful `source: "template"` response with a fallback detail.

## Backend behavior

`backup_explain.py` locates the local Codex executable and uses the existing CLI login without reading or copying credentials. It runs `codex exec` with `--ignore-user-config`, `--ephemeral`, `--sandbox read-only`, `--skip-git-repo-check`, a temporary working directory, `--output-schema` and the prompt on stdin. The timeout is 45 seconds in `config/backup.yaml`.

Structured output must return the exact assessment ID and every evidence ID exactly once. A process-wide lock serializes explanations; successful selections are cached by SHA-256 of the complete assessment under `backup_artifacts/explanations/`. Cached text is re-rendered from the assessment. The 45-second timeout applies to the subprocess, not time waiting for the lock.

The optional live call needs Codex installed, signed in, and network access on the backend machine. The template works offline. This flow does not record action approval; the existing `/api/log` remains separate.

## Existing files to reuse

- `pipeline/baselhack/backup_api.py`: assessment/explanation/evaluation endpoints and local port 8001 server.
- `pipeline/baselhack/backup_explain.py`: CLI invocation, validation, cache and fallback.
- `pipeline/baselhack/interfaces.py`: canonical `BackupAssessment`, `BackupExplanation` and `ExplanationSelection` models.
- `web/src/interfaces.ts`: generated frontend types; do not hand-edit.
- `web/src/BackupConsole.tsx`: working request flow, loading states and stale-response protection.
- `config/backup.yaml`: timeout, port and synthetic-model settings.

To integrate into another checkout, port these dependencies together rather than adding frontend calls to endpoints that are absent there.
