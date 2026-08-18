# Imperator Fitness Coach

A dependency free, private Python CLI for recording fitness check ins, listing source entries, producing conservative summaries, exporting JSON, and safely deleting one exact entry with explicit confirmation.

## Product and Integration Boundary

Imperator Fitness Coach is a standalone local fitness engine and command line interface. It is not a Hermes plugin.

### Current implemented capability

The public repository currently owns deterministic check in parsing, the private local SQLite storage contract, recent entry listing, conservative summaries, JSON export, urgent phrase warnings, and exact confirmed deletion.

The active Hermes integration is an external private skill named `imperator-fitness-check-in`. The skill invokes this CLI. This repository does not contain, install, configure, or publish that skill.

### Planned engine capability

The public engine should own structured programs, workout session selection, exercise results, progression rules, personal records, and training summaries. These capabilities are planned and are not implemented by the current schema, CLI, or tests.

Private workout history, health information, database files, exports, and program files stay under `~/.hermes/private/fitness` and must never be committed.

A future native Dashboard plugin is optional and deferred. If built, it must be a thin interface over this engine. It must not duplicate fitness rules or storage.

---

## Value and Features

- **Private by default:** All data stays local in a strict-mode SQLite database; nothing leaves your device unless you export it.
- **No runtime dependencies:** The CLI uses only the Python standard library and makes no network or third-party service calls. GitHub CI uses the standard checkout and Python setup actions.
- **Deterministic parsing:** Extracts only explicit fields via regex/phrases—not fuzzy inference.
- **CLI-first:** Simple interface for quick entry, review, and export.
- **Strong safety rails:** Emergency-language only triggers local professional help prompt; deletion requires exact ID and `--confirm`.

---

## Features Overview

- Log a parsed fitness check-in with optional timestamp and details (activity, duration, energy, soreness, sleep, hydration, notes)
- List recent entries from a time window
- Summarize observations for trends (requires 3+ points)
- Export recorded data as machine-readable JSON
- Delete one entry by exact ID only (with forced confirmation)
- No bulk deletion, no unsolicited advice, no data inference

## Requirements

- Python 3.13 is verified. Python 3.11+ with SQLite 3.37+ is expected because the schema uses SQLite `STRICT` tables and JSON validation.
- No third-party Python packages are required.

---

## Architecture and Flow

**How it works behind the scenes:**

1. **CLI entry:** `python3 fitness.py [command]` (see usage)
2. **Parsing:** Static regex/phrase-matching to extract only explicit fields (activity, energy, soreness, sleep, food/hydration, notes)
3. **Safety check:** Emergency-language scanner detects critical symptoms ("can't breathe", "chest pain", certain stroke symptoms, etc.)—shows an urgent prompt to seek local professional help if matched (does not provide diagnosis/treatment or cover all emergencies)
4. **Local storage:** All data is written to a local SQLite database (`STRICT` table, WAL journaling, mode 0700/0600)
5. **Data management:** Entries can be listed, summarized, exported, or deleted—each via CLI
6. **Permanent deletion:** Only exact, confirmed IDs accepted—no partial matching or bulk delete ever

### Mermaid Flowchart
```mermaid
flowchart TD
    Input[Log check-in via CLI]
    Parse[Parse explicit fields]
    Safety[Emergency-language scan]
    Store[Insert into local SQLite DB (STRICT, WAL)]
    Warn[Show URGENT prompt (if triggered)]
    List[List entries]
    Summarize[Summarize trends]
    Export[Export all as JSON]
    Delete[Delete 1 entry by full ID w/ confirm]

    Input --> Parse --> Safety --> Store
    Safety -- if critical --> Warn
    Store --> List
    Store --> Summarize
    Store --> Export
    Store --> Delete
```

### Accessible Step-by-Step Flow
1. User enters check-in at CLI
2. Text is parsed using regex/static phrase matching (no ML, no inference)
3. Emergency-language phrases are checked; trigger shows a warning to seek local help (no treatment provided, limited coverage)
4. Parsed and source text is stored locally to SQLite (STRICT, WAL, safe permissions)
5. Entries can be listed, summarized, exported, or deleted on command
6. Summaries require at least 3 points, only describe explicit directional energy, never infer causes
7. Deletion requires full exact ID and --confirm; never deletes partial/wildcards, never bulk

---

## Safety and Privacy Boundaries

- This tool is a descriptive personal record, **not a diagnosis, treatment service, or substitute for medical care**.
- Only explicitly stated, narrow fields are extracted; does **not** infer conditions or causes.
- Recognized emergency-language patterns produce an urgent prompt to contact local emergency services, never treatment advice. Pattern matching is intentionally limited and cannot detect every emergency.
- Health entries are stored in a local SQLite database, directory-mode `0700`, file `0600`. Database and exports may be exposed by backups, malware, or improper sharing—**do not commit, paste, sync, or share unintentionally**.
- Database permissions are best-effort local; OS, admin, and backup hygiene remain user's responsibility.

---

## Usage and Commands

**See all options:**
```sh
python3 fitness.py --help
```

**Log a check-in with optional timestamp:**
```sh
python3 fitness.py log \
  --text "Walked 20 minutes. Energy 3/5." \
  --at "2026-08-14T18:30:00-07:00"
```

**List check-ins (last 7 days):**
```sh
python3 fitness.py recent --days 7
```

**Summarize observations (needs 3+ check-ins):**
```sh
python3 fitness.py summary --days 30
```

**Export all to JSON:**
```sh
python3 fitness.py export-json > fitness-export.json
```
Treat the export as private data—remove securely if no longer needed.

**Delete one entry by ID and confirm:**
```sh
python3 fitness.py delete-entry --id FULL_ENTRY_ID --confirm
```
No partial or unknown IDs are deleted. The current implementation has no bulk-delete command. Deletion is permanent unless a backup exists.

---

## Data Path and Storage

- Default DB: `~/.hermes/private/fitness/fitness.sqlite3`
- For tests or alt locations, set `FITNESS_DB_PATH`:
```sh
FITNESS_DB_PATH=/custom/fitness.sqlite3 python3 fitness.py recent --days 7
```
- The application enables WAL mode and uses `STRICT` typing, non-empty source-text validation, valid-JSON validation, and an urgent flag constrained to `0` or `1`.

To inspect a database without changing it:

```sh
FITNESS_DB_PATH=/private/path/fitness.sqlite3 python3 - <<'PY'
import os, sqlite3
con = sqlite3.connect(f"file:{os.environ['FITNESS_DB_PATH']}?mode=ro", uri=True)
print(con.execute("PRAGMA quick_check").fetchone()[0])
print(con.execute("PRAGMA integrity_check").fetchone()[0])
PY
```

---

## Verification and Test Strategy

- All code is governed by in-tree Python unit tests, run locally on Python 3.13 and in CI on Python 3.11 and 3.13
- Test coverage includes CLI behaviour, parsing, database safety, permission rails, deletion, and regression cases
- The CLI uses no network or third-party services; tests use temporary local SQLite files
- Verification commands (from repo root):
```sh
python3 -m py_compile fitness.py tests/test_fitness.py
python3 -m unittest discover -s tests -v
```

---

## Backup, Rollback, and Maintenance

**Backup:**
1. Stop all commands using the database
2. Use Python's backup API for safe copying:
```sh
FITNESS_DB_PATH=/private.sqlite3 FITNESS_BACKUP_PATH=/backup.sqlite3 python3 - <<'PY'
import os, sqlite3
with sqlite3.connect(os.environ["FITNESS_DB_PATH"]) as src:
    with sqlite3.connect(os.environ["FITNESS_BACKUP_PATH"]) as dst:
        src.backup(dst)
PY
```

**Rollback:**
- Revert code via git; restore backed up DB if needed (replace only when no process is using it; verify with integrity check)
- Future schema changes require a reviewed migration, a verified backup, and a tested rollback path

---

## Troubleshooting

- Errors on startup: verify Python/SQLite version
- Parsing looks odd: refer to parsing logic and unit tests
- Path/data not found: check `FITNESS_DB_PATH`, paths, permissions
- Test issues: always run the full suite; do not publish failing/unverified code

---

## Maintenance and Extension Points

- Entrypoint: `fitness.py` (modular, single file)
- Extend fields: update regex parser, schema, tests
- Update safety rails and emergency-language matchers only with caution, medical input, and added tests—never remove deletion confirmation
- All new features must retain strict privacy, local storage, and permission boundaries

---

## Deferred UI

A graphical interface is deferred. This CLI and local contract are currently maintained and supported. Contributions should follow all safety, privacy, and testing rails as detailed above.
