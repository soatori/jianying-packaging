from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from packaging_tool import _parser as packaging_parser
from packaging_tool import main as packaging_main


def observation() -> dict:
    subtitle = {
        "id": "S1", "segment_id": "S1", "track_id": "T1", "text": "Synthetic subtitle",
        "start_us": 0, "duration_us": 1_000_000,
    }
    segment = {
        "id": "S1", "material_id": "M1", "track_id": "T1", "track_order": 0,
        "target_start_us": 0, "target_duration_us": 1_000_000,
        "source_start_us": 0, "source_duration_us": 1_000_000,
        "text": "Synthetic subtitle",
    }
    return {
        "schema_version": "jianying_timeline_observation@1",
        "source": {
            "timeline_id": "T1", "name": "synthetic", "duration_us": 1_000_000,
            "primary_sha256": "sha256:synthetic-source",
        },
        "tracks": [{
            "id": "T1", "name": "Subtitle", "type": "text", "order": 0,
            "role": "baseline", "segments": [segment],
        }],
        "segments": [segment],
        "subtitle_units": [subtitle],
        "materials": [{"id": "M1", "bucket": "texts"}],
        "templates": [],
        "fonts": [],
        "motion_events": [{"id": "M1", "start_us": 0, "duration_us": 500_000, "motion_family": "fade"}],
        "audio_events": [{"id": "A1", "start_us": 0, "duration_us": 200_000, "role": "sfx"}],
        "evidence_status": {
            "segments": "available", "materials": "available", "templates": "available",
            "fonts": "available", "motion_events": "available", "audio_events": "available",
        },
    }


class AuditBundleTests(unittest.TestCase):
    @staticmethod
    def _temp_root() -> Path:
        root = Path(__file__).resolve().parents[1] / "temp"
        root.mkdir(parents=True, exist_ok=True)
        return root

    @staticmethod
    def _run(argv: list[str]) -> tuple[int, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                code = packaging_main(argv)
            except SystemExit as exc:
                code = int(exc.code or 0)
        return code, stdout.getvalue() + stderr.getvalue()

    def test_audit_bundle_runs_five_checks_from_one_observation(self):
        with tempfile.TemporaryDirectory(dir=self._temp_root()) as directory:
            observation_path = Path(directory) / "observation.json"
            report_path = Path(directory) / "audit.json"
            observation_path.write_text(json.dumps(observation()), encoding="utf-8")

            code, output = self._run([
                "audit-bundle", "--observation", str(observation_path),
                "--format", "text", "--out", str(report_path),
            ])

            self.assertEqual(code, 0, output)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["report_type"], "packaging_audit_bundle")
            self.assertEqual(report["data"]["schema_version"], "packaging_audit_bundle@1")
            self.assertEqual(set(report["data"]["checks"]), {
                "snapshot", "inventory", "layers", "motion_check", "audio_audit",
            })
            self.assertIn("packaging_audit_bundle: ok", output)
            self.assertNotIn('"checks"', output)
            self.assertTrue(all(check["ok"] for check in report["data"]["checks"].values()))

    def test_audit_bundle_preserves_source_fingerprint(self):
        with tempfile.TemporaryDirectory(dir=self._temp_root()) as directory:
            observation_path = Path(directory) / "observation.json"
            observation_path.write_text(json.dumps(observation()), encoding="utf-8")

            code, output = self._run(["audit-bundle", "--observation", str(observation_path)])

            self.assertEqual(code, 0, output)
            report = json.loads(output)
            self.assertEqual(report["data"]["source_fingerprint"], "sha256:synthetic-source")

    def test_audit_bundle_does_not_call_unavailable_motion_evidence_empty(self):
        with tempfile.TemporaryDirectory(dir=self._temp_root()) as directory:
            payload = observation()
            payload["motion_events"] = []
            payload["evidence_status"]["motion_events"] = "unavailable"
            observation_path = Path(directory) / "observation.json"
            observation_path.write_text(json.dumps(payload), encoding="utf-8")

            code, output = self._run(["audit-bundle", "--observation", str(observation_path)])

            self.assertEqual(code, 2)
            self.assertIn("packaging_audit_bundle", output)
            report = json.loads(output)
            self.assertFalse(report["ok"])
            self.assertTrue(any("motion_events" in item for item in report["input_errors"]))
            self.assertTrue(report["data"]["checks"]["motion_check"]["input_errors"])

    def test_audit_bundle_blocks_each_missing_observation_array(self):
        for field in ("tracks", "segments", "subtitle_units", "materials", "templates", "fonts", "motion_events", "audio_events"):
            for malformed in ("missing", "wrong_type"):
                with self.subTest(field=field, malformed=malformed), tempfile.TemporaryDirectory(dir=self._temp_root()) as directory:
                    payload = observation()
                    if malformed == "missing":
                        payload.pop(field)
                    else:
                        payload[field] = None
                    observation_path = Path(directory) / "observation.json"
                    observation_path.write_text(json.dumps(payload), encoding="utf-8")

                    code, output = self._run(["audit-bundle", "--observation", str(observation_path)])

                    self.assertEqual(code, 2)
                    report = json.loads(output)
                    self.assertFalse(report["ok"])
                    self.assertTrue(any(field in error and "array" in error for error in report["input_errors"]))

    def test_cli_exposes_audit_bundle(self):
        choices = packaging_parser()._subparsers._group_actions[0].choices

        self.assertIn("audit-bundle", choices)
        self.assertIn("--observation", choices["audit-bundle"]._option_string_actions)

    def test_audit_bundle_out_cannot_alias_observation(self):
        with tempfile.TemporaryDirectory(dir=self._temp_root()) as directory:
            observation_path = Path(directory) / "observation.json"
            original = json.dumps(observation())
            observation_path.write_text(original, encoding="utf-8")

            code, output = self._run([
                "audit-bundle", "--observation", str(observation_path), "--out", str(observation_path),
            ])

            self.assertNotEqual(code, 0)
            self.assertIn("conflicts with observation", output)
            report = json.loads(output)
            self.assertTrue(any("conflicts with observation" in item for item in report["input_errors"]))
            self.assertEqual(observation_path.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
