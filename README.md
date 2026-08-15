# Imperator Fitness Coach

A dependency-free, local Python CLI for recording fitness check-ins, reviewing recent source text, producing conservative summaries, exporting JSON, and deleting one exact entry with explicit confirmation.

## Safety and privacy boundaries

- This tool is a descriptive personal record, **not a diagnosis, treatment service, or substitute for medical care**.
- It only extracts explicitly stated, narrow fields and does not infer conditions or causes.
- Recognized emergency-language patterns produce an urgent prompt to contact local emergency services; they do not provide treatment advice. Pattern matching is intentionally limited and cannot detect every emergency.
- Health entries remain in a local SQLite database. They are sensitive: do not commit, paste, sync, or share the database or exports unintentionally.
- The database directory is created with mode `0700` and the database with mode `0600`. Host backups, administrator access, malware, and copying an export can bypass these local permissions; full-disk encryption and careful backup handling remain the user's responsibility.

## Requirements

- Python 3.13 is verified. Python 3.11+ with SQLite 3.37+ is expected because the schema uses SQLite `STRICT` tables and JSON validation.
- No third-party packages are required.

Run commands from this repository:

```sh
python3 fitness.py --help
```

## Data path

The default database is:

```text
~/.hermes/private/fitness/fitness.sqlite3
```

For tests, smoke checks, or an alternate private location, set `FITNESS_DB_PATH`:

```sh
FITNESS_DB_PATH=/private/path/fitness.sqlite3 python3 fitness.py recent --days 7
```

The application initializes the strict schema automatically, enables foreign keys, and uses SQLite WAL mode.

## Usage

Log a check-in. `--at` is optional; when supplied, it must be an ISO-8601 timestamp with a UTC or local offset:

```sh
python3 fitness.py log \
  --text "Walked 20 minutes. Energy 3/5." \
  --at "2026-08-14T18:30:00-07:00"
```

Read exact source check-ins from the last seven days:

```sh
python3 fitness.py recent --days 7
```

Produce conservative observations. Directional energy wording requires at least three qualifying check-ins:

```sh
python3 fitness.py summary --days 30
```

Export all entries as parseable JSON:

```sh
python3 fitness.py export-json > fitness-export.json
```

Treat that export as private health data and remove it securely when no longer needed.

Delete exactly one entry. Copy the full ID from `recent` or `export-json`; omission of the literal `--confirm` flag refuses deletion. Unknown and partial IDs are not deleted:

```sh
python3 fitness.py delete-entry --id FULL_ENTRY_ID --confirm
```

There is no bulk-delete command.

## Verification

The governing test command is:

```sh
python3 -m py_compile fitness.py tests/test_fitness.py
python3 -m unittest discover -s tests -v
```

To inspect a database directly without changing it:

```sh
FITNESS_DB_PATH=/private/path/fitness.sqlite3 python3 - <<'PY'
import os, sqlite3
con = sqlite3.connect(f"file:{os.environ['FITNESS_DB_PATH']}?mode=ro", uri=True)
print(con.execute("PRAGMA quick_check").fetchone()[0])
print(con.execute("PRAGMA integrity_check").fetchone()[0])
PY
```

## Backup and rollback

1. Stop commands that are writing to the database.
2. Back up SQLite safely with Python's backup API rather than copying only the main file while WAL mode may be active:

   ```sh
   FITNESS_DB_PATH=/private/path/fitness.sqlite3 FITNESS_BACKUP_PATH=/private/path/fitness-backup.sqlite3 python3 - <<'PY'
   import os, sqlite3
   with sqlite3.connect(os.environ["FITNESS_DB_PATH"]) as source:
       with sqlite3.connect(os.environ["FITNESS_BACKUP_PATH"]) as target:
           source.backup(target)
   PY
   ```

3. To roll back code, revert the relevant Git commit (preferred) or check out a previously reviewed commit.
4. To restore data, preserve the current database first, then replace it with a verified backup while no process is using it. Re-run both SQLite checks above after restoration.

Deletion is permanent unless a backup exists.

## Deferred UI

A graphical user interface is intentionally deferred until Intelligence Hub work resumes. The CLI and its local data contract are the current supported surface.
