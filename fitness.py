#!/usr/bin/env python3
"""Local, deterministic fitness check-in CLI."""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


def parse_check_in(text: str) -> dict:
    """Conservatively extract only explicit fitness check-in fields."""
    duration = re.search(r"\b(\d{1,3})\s*(?:minutes?|mins?)\b", text, re.I)
    energy = re.search(r"\benergy\s*(?:is|was|:)?\s*([1-5])(?:\s*/\s*5)?\b", text, re.I)
    energy_value = int(energy.group(1)) if energy else None
    if energy_value is None:
        phrase_scores = ((r"\bvery low energy\b", 1), (r"\blow energy\b", 2), (r"\benergy feels high\b", 4), (r"\bvery high energy\b", 5))
        energy_value = next((score for pattern, score in phrase_scores if re.search(pattern, text, re.I)), None)
    soreness = re.search(
        r"\b((?:left|right)\s+)?([a-z]+)\s+soreness\s*(?:is|was|:)?\s*([1-5])(?:\s*/\s*5)?\b",
        text,
        re.I,
    )
    sleep_hours = re.search(r"\b(?:slept|sleep)\s*(\d+(?:\.\d+)?)\s*hours?\b", text, re.I)
    sleep_quality = re.search(r"\bsleep quality\s*(?:is|was|:)?\s*(poor|fair|good|great|excellent)\b", text, re.I)
    sentences = [part.strip() for part in re.findall(r"[^.!?]+[.!?]?", text) if part.strip()]
    activity = next((s for s in sentences if re.search(r"\b(?:ran|run|walked|walk|cycled|bike|swam|swim|workout|trained|lifted|yoga)\b", s, re.I)), "")
    food_hydration = " ".join(s for s in sentences if re.search(r"\b(?:ate|food|meal|water|drank|hydration|liters?|litres?)\b", s, re.I))
    used = {activity, *[s for s in sentences if re.search(r"\b(?:energy|soreness|slept|sleep quality|ate|food|meal|water|drank|hydration|liters?|litres?)\b", s, re.I)]}
    note = " ".join(s for s in sentences if s not in used)
    return {
        "activity": activity,
        "duration_minutes": int(duration.group(1)) if duration else None,
        "energy": energy_value,
        "soreness": ([{"area": f"{soreness.group(1) or ''}{soreness.group(2)}".strip().lower(), "severity": int(soreness.group(3))}] if soreness else []),
        "sleep_hours": float(sleep_hours.group(1)) if sleep_hours else None,
        "sleep_quality": sleep_quality.group(1).lower() if sleep_quality else None,
        "food_hydration": food_hydration,
        "note": note,
    }


def database_path() -> Path:
    return Path(os.environ.get("FITNESS_DB_PATH", "~/.hermes/private/fitness/fitness.sqlite3")).expanduser()


def connect_database(path: Path | None = None) -> sqlite3.Connection:
    path = path or database_path()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        path.parent.chmod(0o700)
    except OSError:
        pass
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=10000")
    connection.execute(
        """CREATE TABLE IF NOT EXISTS entries (
        id TEXT PRIMARY KEY NOT NULL,
        occurred_at TEXT NOT NULL,
        occurred_epoch INTEGER NOT NULL,
        source_text TEXT NOT NULL CHECK(length(trim(source_text)) > 0),
        parsed_json TEXT NOT NULL CHECK(json_valid(parsed_json)),
        urgent INTEGER NOT NULL DEFAULT 0 CHECK(urgent IN (0, 1)),
        created_at TEXT NOT NULL
        ) STRICT"""
    )
    connection.commit()
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return connection


def parse_timestamp(value: str | None) -> datetime:
    if value is None:
        return datetime.now().astimezone()
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("--at must include a UTC or local offset, for example -07:00")
    return parsed


def has_urgent_symptom(text: str) -> bool:
    patterns = (
        r"\bchest pain\b",
        r"\b(?:trouble|difficulty|cannot|can't) breathing\b",
        r"\bfaint(?:ed|ing)?\b",
        r"\bsevere bleeding\b",
        r"\bface droop(?:ing)?\b",
        r"\bslurred speech\b",
        r"\bsudden (?:one-sided )?(?:weakness|numbness)\b",
        r"\bstroke(?:-like)? symptoms?\b",
    )
    return any(re.search(pattern, text, re.I) for pattern in patterns)


def command_log(args: argparse.Namespace) -> int:
    if not args.text.strip():
        raise ValueError("--text must not be empty")
    occurred = parse_timestamp(args.at)
    parsed = parse_check_in(args.text)
    urgent = has_urgent_symptom(args.text)
    entry_id = os.urandom(8).hex()
    with connect_database() as connection:
        connection.execute(
            "INSERT INTO entries (id, occurred_at, occurred_epoch, source_text, parsed_json, urgent, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (entry_id, occurred.isoformat(), int(occurred.timestamp()), args.text, json.dumps(parsed, ensure_ascii=False), int(urgent), datetime.now(timezone.utc).isoformat()),
        )
    print(f"Logged entry {entry_id} at {occurred.isoformat()}")
    if urgent:
        print("URGENT SAFETY WARNING: These words may describe an emergency. Seek emergency help now by contacting local emergency services.")
    return 0


def command_recent(args: argparse.Namespace) -> int:
    cutoff = int((datetime.now(timezone.utc) - timedelta(days=args.days)).timestamp())
    with connect_database() as connection:
        rows = connection.execute(
            "SELECT id, occurred_at, source_text FROM entries WHERE occurred_epoch >= ? ORDER BY occurred_epoch DESC, id DESC",
            (cutoff,),
        ).fetchall()
    if not rows:
        print("No check-ins found for this period.")
        return 0
    for row in rows:
        print(f"Entry {row['id']}\nAt: {row['occurred_at']}\nCheck-in: {row['source_text']}\n")
    return 0


def command_summary(args: argparse.Namespace) -> int:
    cutoff = int((datetime.now(timezone.utc) - timedelta(days=args.days)).timestamp())
    with connect_database() as connection:
        rows = connection.execute(
            "SELECT parsed_json FROM entries WHERE occurred_epoch >= ? ORDER BY occurred_epoch",
            (cutoff,),
        ).fetchall()
    parsed = [json.loads(row["parsed_json"]) for row in rows]
    energies = [item["energy"] for item in parsed if item["energy"] is not None]
    print(f"Observation ({args.days} days): {len(rows)} check-ins recorded.")
    if energies:
        print(f"Observed average energy: {sum(energies) / len(energies):.1f}/5 from {len(energies)} explicit ratings.")
    if len(rows) < 3:
        print("At least 3 check-ins are required before describing directional patterns.")
    elif len(energies) >= 3:
        if all(left < right for left, right in zip(energies, energies[1:])):
            print("Observed directional pattern: explicit energy ratings increased across these check-ins; this does not establish a cause.")
        elif all(left > right for left, right in zip(energies, energies[1:])):
            print("Observed directional pattern: explicit energy ratings decreased across these check-ins; this does not establish a cause.")
        else:
            print("Observed directional pattern: explicit energy ratings varied; this does not establish a cause.")
    print("This is a descriptive record, not a diagnosis or medical advice.")
    return 0


def command_export_json(_args: argparse.Namespace) -> int:
    with connect_database() as connection:
        rows = connection.execute(
            "SELECT id, occurred_at, source_text, parsed_json, urgent, created_at FROM entries ORDER BY occurred_epoch, id"
        ).fetchall()
    entries = [
        {
            "id": row["id"],
            "occurred_at": row["occurred_at"],
            "source_text": row["source_text"],
            "parsed": json.loads(row["parsed_json"]),
            "urgent": bool(row["urgent"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]
    print(json.dumps({"schema_version": 1, "entries": entries}, ensure_ascii=False, indent=2))
    return 0


def command_delete_entry(args: argparse.Namespace) -> int:
    if not args.confirm:
        raise ValueError("deletion requires the literal --confirm flag")
    with connect_database() as connection:
        cursor = connection.execute("DELETE FROM entries WHERE id = ?", (args.id,))
        if cursor.rowcount != 1:
            raise ValueError(f"entry {args.id} not found")
    print(f"Deleted entry {args.id}")
    return 0


def positive_integer(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("days must be at least 1")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Private local fitness check-ins (not medical advice).")
    subparsers = parser.add_subparsers(dest="command", required=True)
    log_parser = subparsers.add_parser("log", help="Log a check-in")
    log_parser.add_argument("--text", required=True)
    log_parser.add_argument("--at")
    log_parser.set_defaults(handler=command_log)
    recent_parser = subparsers.add_parser("recent", help="Show recent check-ins")
    recent_parser.add_argument("--days", type=positive_integer, default=7)
    recent_parser.set_defaults(handler=command_recent)
    summary_parser = subparsers.add_parser("summary", help="Show conservative observations")
    summary_parser.add_argument("--days", type=positive_integer, default=7)
    summary_parser.set_defaults(handler=command_summary)
    export_parser = subparsers.add_parser("export-json", help="Export all entries as JSON")
    export_parser.set_defaults(handler=command_export_json)
    delete_parser = subparsers.add_parser("delete-entry", help="Delete one exact entry by ID")
    delete_parser.add_argument("--id", required=True, help="Exact entry ID from recent or export-json")
    delete_parser.add_argument("--confirm", action="store_true", help="Confirm deletion of this one entry")
    delete_parser.set_defaults(handler=command_delete_entry)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.handler(args)
    except (ValueError, sqlite3.Error) as error:
        parser.error(str(error))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
