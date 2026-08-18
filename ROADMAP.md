# Product Roadmap

## Product Goal

Imperator Fitness Coach will be a private, local first strength and fitness engine that can guide one exercise at a time, preserve exact workout results, explain progression decisions, and remain useful without Hermes, a browser, a wearable, or network access.

The intended user outcome is consistent, measurable progress toward user selected strength, power, muscle, work capacity, and adherence goals without invented health claims or universal load prescriptions.

## Architecture Decision

The core remains an independent Python engine with SQLite storage and a supported command line interface.

1. The engine owns programs, exercises, sessions, calibration, goals, progression, records, summaries, safety wording, migrations, export, and exact deletion.
2. The CLI, private Hermes skill, any future Dashboard plugin, any future MCP server, and any provider integration remain thin adapters over the engine.
3. Adapters must not access SQLite directly or duplicate fitness rules.
4. No public network service, cloud account, telemetry, or third party service is required for core workouts.
5. The existing `fitness.py` entry point remains compatible while engine logic moves into an importable package.

## Supported Training Modes

The first structured release will include three versioned program families.

1. Bodyweight
2. Dumbbell only
3. Barbell plus dumbbell

Each program defines exercise order, sets, repetition or duration ranges, rest guidance, substitutions, required equipment, progression rules, and a stable template version. Historical sessions retain a snapshot so later template edits cannot rewrite past training.

## Starting Load and Difficulty Calibration

The project will not publish one universal starting weight for dumbbells or barbells. A universal number would be inaccurate across exercises, equipment, training histories, and users.

Starting difficulty will be determined separately for each exercise through a conservative user controlled calibration.

1. Record available equipment, units, and load increments.
2. Select an unloaded movement, bodyweight variation, or user selected light practice load.
3. Record completed repetitions, technique confidence, and optional effort or repetitions in reserve.
4. Allow the user to stop, reduce, repeat, or accept the result.
5. Store whether a dumbbell value means each hand or total load.
6. Select only a load or variation that the available equipment can produce.
7. Preserve the inputs and reason for every accepted starting target.

Bodyweight calibration changes leverage, assistance, range of motion, tempo, pauses, repetitions, or variation before requiring external load.

## Goals

Goals are explicit, measurable, user selected, and separate from medical outcomes.

Initial goal types will include:

1. Weekly session consistency
2. Program completion
3. Exercise repetition capacity
4. Exercise load progression
5. Bodyweight variation progression
6. Work capacity
7. User selected exercise milestones

Each goal stores a baseline, target, unit, status, and optional target date. The engine reports observed progress and does not guarantee strength gain, weight change, recovery, or health outcomes.

## Workout Workflow

The primary workflow supports exercise by exercise coaching.

1. Start or resume the next scheduled session.
2. Show the current exercise with its target and instructions.
3. Record each completed set with repetitions or duration, external load when applicable, load semantics, and optional effort.
4. Skip, substitute, stop, or abandon without fabricating completion.
5. Derive the next exercise from ordered session state.
6. Complete the session transactionally so interruption does not corrupt progress.
7. Produce an explainable recommendation for the next applicable session.
8. Require user acceptance before changing future targets.

## Progression Rules

Progression will be deterministic, conservative, versioned, and explainable.

1. Hold when evidence is incomplete.
2. Advance only after the configured success criteria are satisfied.
3. Use available equipment increments only.
4. Support repetition range progression for loaded exercises.
5. Support variation progression for bodyweight exercises.
6. Preserve skipped exercises, substitutions, rejected recommendations, and user overrides.
7. Never increase load solely because time passed, a single session succeeded, or wearable data changed.
8. Never infer missing effort, pain, recovery, or completion data.

## Progress Records and Summaries

The engine will derive progress from completed immutable set results.

Planned outputs include:

1. Planned compared with completed sets
2. Repetitions, duration, and external load history
3. Training volume where the measurement is meaningful
4. Session and program adherence
5. Goal status
6. Personal records tied to their source session and set
7. Progression decisions with their inputs and rationale
8. Plain language observations that distinguish fact from inference

Exports use a documented schema version and retain provenance. Private databases, exports, programs, and workout history remain under `~/.hermes/private/fitness` and must never be committed.

## Interface Decision

### Current interface

The CLI remains the primary supported interface while the structured engine is built. The private `imperator-fitness-check-in` Hermes skill may invoke the CLI but is not contained in this repository.

### Dashboard and visual progress

A standalone web application is not justified yet. It would add browser security, authentication, privacy, dependency, and maintenance obligations before structured longitudinal data exists.

After the engine and query contract are stable, an optional native Hermes Dashboard plugin may provide visual history and workout controls. It must remain local, inherit host protection, and call the engine rather than duplicate logic or storage.

### MCP and API

MCP and HTTP API surfaces are deferred until a real independent process or external client requires a transport contract. Any future surface must be narrow, versioned, authenticated where applicable, local by default, and unable to bypass confirmation or privacy controls.

## Accessible Progress Visualization Contract

Charts are supplementary. The canonical information remains plain language summaries and semantic data tables.

Every future graph must provide:

1. A visible title describing the metric, unit, period, sample count, and missing data treatment
2. A plain language observation generated from the same filtered dataset
3. An adjacent semantic table with caption and scoped headers
4. Exact date, value, unit, source record, and relevant exercise or body area
5. Keyboard access to every action without requiring hover, drag, or precision pointing
6. Visible focus and predictable focus return
7. Text, shape, pattern, line style, or direct labels so color is never the only distinction
8. Support for Windows forced colors and high contrast
9. Reflow at 200 and 400 percent zoom and at a 320 CSS pixel viewport
10. Immediate equivalent content with nonessential motion disabled when reduced motion is requested
11. Complete empty, sparse, loading, error, missing data, and unavailable states
12. Manual verification with a screen reader, keyboard, forced colors, zoom, and reduced motion in addition to automated checks

Charts must not convert missing values to zero, invent trend lines from fewer than three relevant observations, imply causation, use inaccessible canvas only output, make every point a tab stop, or hide the equivalent table in a special accessibility mode.

## Private Data and Safety

1. The application is a descriptive fitness record and planning tool, not diagnosis, treatment, rehabilitation, injury clearance, or emergency care.
2. Personal workout data stays local unless the user explicitly exports it.
3. Database directories use private permissions and exports are treated as sensitive.
4. Deletion requires an exact identifier, dependency preview where applicable, and explicit confirmation.
5. Migrations are versioned, transactional, backed up through the SQLite backup API, and verified before acceptance.
6. No adapter may expose private record text in URLs, telemetry, logs, public repositories, or unauthenticated endpoints.

## WHOOP Integration

WHOOP support is planned only after structured programs, sessions, progression, and data lifecycle controls are stable.

1. WHOOP is an optional provider adapter behind a provider neutral interface.
2. Credentials remain outside the repository.
3. Provider data retains source, observation time, import time, and synchronization state.
4. Raw provider data remains separate from user authored workout records and is minimized.
5. The engine continues working when WHOOP is disconnected, stale, rate limited, or unavailable.
6. WHOOP observations may add context but must not automatically prescribe loads, diagnose readiness, block a workout, or override the user's report and choices.
7. Authorization, revocation, deletion, retry, pagination, duplicate handling, and credential redaction require tests before release.

## Delivery Sequence

### Phase 0: Preserve current behavior

Characterize the existing database and commands. Lock exact source preservation, permission, urgent phrase, export, summary, and exact deletion behavior with regression tests.

### Phase 1: Establish engine boundaries

Create an importable package for domain rules, services, storage, migrations, and adapters. Keep `fitness.py` as a compatible entry point.

### Phase 2: Add migration authority

Baseline the existing schema, add transactional versioned migrations, and prove rollback, integrity, and legacy data preservation.

### Phase 3: Add equipment and program catalogs

Implement the three equipment modes, exercise variants, requirements, substitutions, and versioned templates.

### Phase 4: Add onboarding, calibration, and goals

Implement equipment inventory, exercise specific starting difficulty calibration, explicit goals, and accepted starting targets.

### Phase 5: Add durable workout sessions

Implement start, resume, current exercise, set recording, skip, substitute, stop, completion, and crash safe continuation.

### Phase 6: Add progression and records

Implement versioned progression policies, user accepted recommendations, goal status, personal records, and conservative summaries.

### Phase 7: Complete private data lifecycle

Add versioned full export, migration verification, dependency aware exact deletion, backup, and restore validation.

### Phase 8: Add an accessible Dashboard interface if justified

Implement only after the engine query contract and longitudinal data are stable. Verify complete equivalence between charts, summaries, tables, and source records.

### Phase 9: Add WHOOP through an optional adapter

Keep provider failure isolated and preserve offline operation.

### Phase 10: Consider MCP or an API only for a proven consumer

Do not add a transport merely because one is available.

## Explicit Non Goals

The project will not add universal starting weights, medical screening, diagnosis, treatment advice, automatic readiness claims, cloud accounts, social feeds, public leaderboards, nutrition prescriptions, opaque wellness scores, or silent program changes.
