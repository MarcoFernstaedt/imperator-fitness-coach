import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


class ParsingTests(unittest.TestCase):
    def test_parses_explicit_check_in_fields(self):
        from fitness import parse_check_in

        parsed = parse_check_in(
            "Ran 30 minutes. Energy 4/5. Left knee soreness 2/5. "
            "Slept 7.5 hours, sleep quality good. Drank 2 liters water. "
            "Ate oatmeal. Felt steady."
        )

        self.assertEqual(parsed["duration_minutes"], 30)
        self.assertEqual(parsed["energy"], 4)
        self.assertEqual(parsed["soreness"], [{"area": "left knee", "severity": 2}])
        self.assertEqual(parsed["sleep_hours"], 7.5)
        self.assertEqual(parsed["sleep_quality"], "good")
        self.assertIn("Ran", parsed["activity"])
        self.assertIn("water", parsed["food_hydration"].lower())
        self.assertEqual(parsed["note"], "Felt steady.")

    def test_maps_only_common_explicit_energy_phrases(self):
        from fitness import parse_check_in

        self.assertEqual(parse_check_in("Feeling very low energy.")["energy"], 1)
        self.assertEqual(parse_check_in("Energy feels high today.")["energy"], 4)
        self.assertIsNone(parse_check_in("Had a normal day.")["energy"])


class SafetyTests(unittest.TestCase):
    def test_common_high_risk_breathing_phrases_are_urgent(self):
        from fitness import has_urgent_symptom

        phrases = (
            "I cannot breathe.",
            "I can't breathe.",
            "I can’t breathe.",
            "I have shortness of breath.",
            "I CANNOT BREATHE.",
        )
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                self.assertTrue(has_urgent_symptom(phrase))

    def test_ordinary_nonurgent_breath_references_do_not_trigger(self):
        from fitness import has_urgent_symptom

        phrases = (
            "Breathing exercises helped me relax.",
            "I practiced breath control during yoga.",
            "My breathing felt normal throughout the walk.",
        )
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                self.assertFalse(has_urgent_symptom(phrase))


class PrivacyIgnoreTests(unittest.TestCase):
    def test_sqlite_databases_and_sidecars_are_ignored(self):
        names = (
            "private.sqlite",
            "private.sqlite-wal",
            "private.sqlite-shm",
            "private.sqlite3",
            "private.sqlite3-wal",
            "private.sqlite3-shm",
            "private.db",
            "private.db-wal",
            "private.db-shm",
        )
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "--stdin"],
            cwd=REPO,
            input="\n".join(names) + "\n",
            text=True,
            capture_output=True,
            check=False,
        )

        ignored = set(result.stdout.splitlines())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(ignored, set(names))


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db = Path(self.tempdir.name) / "fitness.sqlite3"
        self.env = {**os.environ, "FITNESS_DB_PATH": str(self.db)}

    def tearDown(self):
        self.tempdir.cleanup()

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(REPO / "fitness.py"), *args],
            env=self.env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_log_then_recent_preserves_exact_source_and_offset_timestamp(self):
        source = "Walked 20 minutes; energy 3/5 — felt okay."
        logged = self.run_cli("log", "--text", source, "--at", "2026-08-14T18:30:00-07:00")
        self.assertEqual(logged.returncode, 0, logged.stderr)
        recent = self.run_cli("recent", "--days", "7")
        self.assertEqual(recent.returncode, 0, recent.stderr)
        self.assertIn(source, recent.stdout)
        self.assertIn("2026-08-14T18:30:00-07:00", recent.stdout)

    def test_rejects_empty_text_naive_timestamp_and_nonpositive_days(self):
        cases = (
            (("log", "--text", "   "), "text"),
            (("log", "--text", "Walked", "--at", "2026-08-14T18:30:00"), "offset"),
            (("recent", "--days", "0"), "days"),
        )
        for arguments, expected in cases:
            with self.subTest(arguments=arguments):
                result = self.run_cli(*arguments)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected, result.stderr.lower())

    def test_sql_metacharacters_are_data_and_database_integrity_is_ok(self):
        source = "Lifted 25 minutes; note: '); DROP TABLE entries; --"
        result = self.run_cli("log", "--text", source)
        self.assertEqual(result.returncode, 0, result.stderr)
        with sqlite3.connect(self.db) as connection:
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(connection.execute("SELECT source_text FROM entries").fetchone()[0], source)
            self.assertEqual(connection.execute("PRAGMA journal_mode").fetchone()[0], "wal")
            sql = connection.execute("SELECT sql FROM sqlite_master WHERE name='entries'").fetchone()[0]
            self.assertIn("CHECK", sql)
        self.assertEqual(self.db.stat().st_mode & 0o777, 0o600)

    def test_summary_below_three_points_uses_observation_without_trend(self):
        now = datetime.now().astimezone()
        for index, energy in enumerate((2, 4)):
            result = self.run_cli(
                "log", "--text", f"Walked 20 minutes. Energy {energy}/5.",
                "--at", (now - timedelta(days=index)).isoformat(),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        summary = self.run_cli("summary", "--days", "7")
        self.assertEqual(summary.returncode, 0, summary.stderr)
        self.assertIn("Observation", summary.stdout)
        self.assertIn("2 check-ins", summary.stdout)
        self.assertNotIn("trend", summary.stdout.lower())
        self.assertNotIn("cause", summary.stdout.lower())

    def test_summary_labels_three_point_energy_pattern_as_observation(self):
        now = datetime.now().astimezone()
        for days_ago, energy in ((2, 2), (1, 3), (0, 4)):
            result = self.run_cli(
                "log", "--text", f"Energy {energy}/5.",
                "--at", (now - timedelta(days=days_ago)).isoformat(),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        summary = self.run_cli("summary", "--days", "7")
        self.assertEqual(summary.returncode, 0, summary.stderr)
        self.assertIn("Observed directional pattern", summary.stdout)
        self.assertIn("increased", summary.stdout)
        self.assertIn("does not establish a cause", summary.stdout)
        self.assertNotIn("diagnosis:", summary.stdout.lower())

    def test_urgent_symptom_warns_to_seek_emergency_help_and_still_logs(self):
        source = "I have chest pain and trouble breathing."
        result = self.run_cli("log", "--text", source)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("URGENT", result.stdout)
        self.assertIn("seek emergency help now", result.stdout.lower())
        self.assertNotIn("treatment", result.stdout.lower())
        with sqlite3.connect(self.db) as connection:
            row = connection.execute("SELECT source_text, urgent FROM entries").fetchone()
        self.assertEqual(row, (source, 1))

    def test_export_json_is_valid_complete_machine_readable_json(self):
        source = "Yoga 40 minutes. Energy 5/5."
        logged = self.run_cli("log", "--text", source)
        self.assertEqual(logged.returncode, 0, logged.stderr)
        exported = self.run_cli("export-json")
        self.assertEqual(exported.returncode, 0, exported.stderr)
        payload = json.loads(exported.stdout)
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(len(payload["entries"]), 1)
        self.assertEqual(payload["entries"][0]["source_text"], source)
        self.assertEqual(payload["entries"][0]["parsed"]["energy"], 5)

    def test_delete_requires_exact_id_and_confirm_flag(self):
        logged = self.run_cli("log", "--text", "Walked 10 minutes.")
        self.assertEqual(logged.returncode, 0, logged.stderr)
        entry_id = re.search(r"Logged entry ([0-9a-f]+)", logged.stdout).group(1)
        refused = self.run_cli("delete-entry", "--id", entry_id)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("--confirm", refused.stderr)
        with sqlite3.connect(self.db) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM entries").fetchone()[0], 1)
        deleted = self.run_cli("delete-entry", "--id", entry_id, "--confirm")
        self.assertEqual(deleted.returncode, 0, deleted.stderr)
        self.assertIn(entry_id, deleted.stdout)
        with sqlite3.connect(self.db) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM entries").fetchone()[0], 0)

    def test_delete_distinguishes_not_found_and_never_matches_partial_id(self):
        first = self.run_cli("log", "--text", "Walked 10 minutes.")
        second = self.run_cli("log", "--text", "Yoga 15 minutes.")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        entry_id = re.search(r"Logged entry ([0-9a-f]+)", first.stdout).group(1)

        missing = self.run_cli("delete-entry", "--id", entry_id[:-1], "--confirm")

        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("not found", missing.stderr.lower())
        with sqlite3.connect(self.db) as connection:
            rows = connection.execute("SELECT id FROM entries ORDER BY id").fetchall()
        self.assertEqual(len(rows), 2)
        self.assertIn((entry_id,), rows)


if __name__ == "__main__":
    unittest.main()
