# Scheduler coverage scoping — `vera/scheduler.py` (#46)

Scoping note gathered 2026-10-22 at HEAD `34451fd1` by the daily
improvement loop, following the eos #148 scoping pattern: evidence
first, decomposition second, no test code in the scoping commit.
This is the last named 0% block from the 2026-10-19 coverage
measurement of the `vera/` package.

## The module, measured

- One class, `ProactiveScheduler` (~40 methods, 990 lines,
  37,811 B). Re-measured today with the CI invocation's coverage
  setup: **583 statements, 234 branches** — identical to the
  2026-10-19 count, so the block has not drifted. Import alone
  covers 5.75%; everything else needs tests.
- **All state is files.** Every worker reads/writes JSON under the
  module constant `DATA_DIR` (`vera/scheduler.py:23`,
  `Path(__file__).resolve().parent.parent / "data"`): reminders,
  calendar, portfolio, todos, scheduled tasks/posts, finance,
  wellness, Jira scan state, channel monitor, mood history.
  `DATA_DIR` is a module-level `Path` — patchable in tests.
- **Every external dependency is an in-function import.** The
  stub set is per-worker, which — not line count — is what makes
  this module multi-slice:
  - `from config import settings` (absolute import, *not*
    `vera.config`) inside `start()` and most `_run_*` wrappers —
    a test must stub `sys.modules["config"]`.
  - `vera.monitoring.metrics` inside `_run_with_metrics`.
  - `yfinance` inside `_check_stock_alerts` (line 237).
  - Per-agent tool imports (`vera.brain.agents.*`,
    `vera.messaging`, `vera.emotional.*`) inside the job-scan /
    planner / digest / Jira / channel / mood workers.
- The uniform shape is `*_loop()` wrappers (infinite
  `while self._running` + `_run_with_metrics` +
  `asyncio.sleep`) over `_check_*()` / `_run_*()` workers.

## (a) Slice decomposition — four independently landable slices

Each slice is one day-sized test landing, Refs #46, never Closes.
Every slice must be green on its own; no slice depends on a later
one's stubs.

- **S1 — lifecycle + dispatch core.** `__init__`,
  `add_notification_handler` / `remove_notification_handler`
  (including the `ValueError` path for an absent handler),
  `_notify` (including a handler that raises — the remaining
  handlers must still fire, per the current code's semantics,
  which the test pins as-is), `_run_with_metrics` success and
  re-raise paths, and `start()` / `stop()` with
  `sys.modules["config"]` stubbed: all loops disabled first,
  then selectively enabled one at a time. Stub set: `config`,
  `vera.monitoring.metrics`. **First landing (earliest
  2026-10-23).**
- **S2 — file-state checkers with no third-party imports.**
  `_check_reminders`, `_check_upcoming_events`,
  `_check_scheduled_tasks`, `_check_scheduled_posts`,
  `_check_spending_alerts`, `_check_break_needed`, against a tmp
  `DATA_DIR`: due / not-due / dismissed / malformed-JSON /
  missing-file cases, with **write-back assertions** — these
  workers mutate the JSON files they read, and the tests assert
  the *current* mutation semantics; they do not redesign them.
  Stub set: none beyond the `DATA_DIR` patch and a recording
  notification handler.
- **S3 — settings-gated run wrappers.** `_run_job_scan`
  (including its result cap), `_run_morning_plan`, `_run_digest`,
  `_run_daily_review` (ticket scan), `_run_channel_monitor`,
  `_run_mood_check`, and `_send_daily_briefing`, with their
  agent / messaging / emotional imports stubbed in
  `sys.modules` per-worker. Stub set: the largest of the four —
  which is why it is third, after S1's `config` stub pattern
  exists to copy.
- **S4 — `_check_stock_alerts` last.** The `yfinance` import is
  the heaviest stub in the module; isolating it means its
  awkwardness cannot block S1–S3. Stub set: `yfinance` plus the
  portfolio JSON under a tmp `DATA_DIR`.

## (b) The loop-wrapper question

The `*_loop()` bodies are near-identical infinite loops. Testing
position: **test the workers, not the loops.** Cover one loop
iteration per family only where it is free — by flipping
`self._running` after the first pass or stubbing
`asyncio.sleep` to raise/cancel — and do **not** refactor the
loops to make them testable inside a coverage slice. A loop
refactor is its own issue, proposed on its own merits.

## (c) Async test idiom — resolved

`pyproject.toml` sets `asyncio_mode = "auto"` (line 93) and CI
installs `pytest-asyncio`, so plain `async def test_*` functions
run without markers or new dependencies — the idiom the health
slice's tests already rely on. S1's `start()` test can be written
under it as-is.

## (d) Coverage-config governance — which file governs: resolved; which number: #60

Two configs disagreed: `.coveragerc` says `fail_under = 10`,
`pyproject.toml` `[tool.coverage.report]` says `fail_under = 45`.
The CI workflow's invocation (`pytest tests/unit/ --cov=.`,
no `--cov-config`) was run empirically on 2026-10-22: the
failure message quotes **10.0%** — `.coveragerc` governs and the
pyproject number is shadowed dead config. Filed as **#60** for
the maintainers' decision on the single intended number and
file. Until #60 is resolved: **no ratchet change and no
"fix" of either number inside any scheduler slice.**

## (e) Sequencing + go/no-go

**GO.** Order: S1 → S2 → S3 → S4, one per day at the earliest.
Each slice Refs #46, never Closes — #46's terms are
ratchet-to-100 across the package, and scheduler at 100% still
leaves the providers/perception modules #46's own body names.
No slice imports the real `config` settings or any real agent
tool; pinning a behaviour this note has not recorded as a quirk
is out of scope for the slice that notices it — file it, then
pin it.

Refs #46. Governance question: #60. Matrix/floor inconsistency
(3.10 vs >=3.11) is #59 — scheduler tests inherit its interim
skip discipline until it is decided.
