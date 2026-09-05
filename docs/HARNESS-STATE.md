CURRENT_PHASE: 3B
STATUS: PAUSED_WIP
BASE_COMMIT: d27117e
LAST_GREEN_PHASE: 3A
LAST_GREEN_COMMIT: phase-2-green (Phase 3A is green but not independently committed)
CURRENT_WORK: Phase 3B Content Admin integration, partially implemented on wip/phase-3b.

DONE:
- Phase 3A backend, 19 directed tests, full regression and live inspect are green.
- Erome URL/inspect/import/acquire controls and frontend types are drafted and type-check.

TODO:
- Finish Phase 3B styles, deterministic fixture server and browser E2E.
- Run Phase 3 final build, E2E, regression and code review; then squash Phase 3 onto main.

BLOCKERS:
- Session intentionally paused for machine shutdown; no technical blocker.

NEXT:
- Resume wip/phase-3b at ContentManager; add deterministic worker-backed E2E harness.

IMPORTANT_NOTES:
- Reference Erome URL is HTTP 410; live replacement inspect passed with 15 items.
- No migration or new dependency is required. Do not start Phase 4A before Phase 3 is green.
