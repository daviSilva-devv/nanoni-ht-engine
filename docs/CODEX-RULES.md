# Codex Rules

1. Read `BASE-OFICIAL.md` before implementation work.
2. Work on one phase/gate at a time.
3. Do not hardcode commercial names, prices, topics or CTAs into business logic.
4. Do not replace a generic configuration entity with an `if niche == ...` branch.
5. Do not couple a provider SDK directly to Order/Access code; implement the provider interface.
6. Do not make a webhook perform Telegram membership changes inline. Enqueue/fulfill through Access.
7. Do not delete a failed operation. Persist error + state + alert when appropriate.
8. Do not purge local media until remote persistence/publication is confirmed.
9. Do not make Redis mandatory in V1.
10. Do not add open-ended conversational AI in V1.
11. Do not implement protected-content bypass. Helper functionality is assisted/local import only.
12. Every schema change requires an Alembic migration and a test or explicit migration check.
13. Every new state transition must update transition tests.
14. New ideas outside the requested gate go to `BACKLOG.md`.
15. Finish a phase with: tests, migration check, files changed, gate pass/fail, real blockers only.
