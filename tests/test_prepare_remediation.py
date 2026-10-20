from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

import packaging_tool


class PrepareRemediationTests(unittest.TestCase):
    @staticmethod
    def _temp_root() -> Path:
        root = Path(__file__).resolve().parents[1] / "temp"
        root.mkdir(parents=True, exist_ok=True)
        return root

    @staticmethod
    def _run(argv: list[str]) -> tuple[int, str]:
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            try:
                code = packaging_tool.main(argv)
            except SystemExit as exc:
                code = int(exc.code or 0)
        return code, output.getvalue()

    @staticmethod
    def _plan(*, sound: bool = True, animation: bool = False) -> dict:
        visual = [{"animation": {"resource_id": "text-intro"}}] if animation else []
        return {
            "schema_version": "2.0",
            "source": {"draft_path": "unused", "timeline": "manual"},
            "execution": {"mode": "apply", "phase": "final"},
            "groups": [{
                "id": "g1",
                "visual": visual,
                "audio": {"action": "apply_sfx" if sound else "none"},
            }],
        }

    def _args(self, directory: Path, plan_path: Path, *extra: str) -> list[str]:
        return [
            "prepare", "--draft", str(directory / "draft"), "--timeline", "manual",
            "--plan", str(plan_path), "--prepared", str(directory / "prepared.json"), *extra,
        ]

    def test_prepare_missing_catalog_reports_producer_command(self):
        with tempfile.TemporaryDirectory(dir=self._temp_root()) as directory:
            root = Path(directory)
            plan_path = root / "plan.json"
            pools_path = root / "pools.json"
            plan_path.write_text(json.dumps(self._plan()), encoding="utf-8")
            pools_path.write_text(json.dumps({"pools": []}), encoding="utf-8")

            with patch.object(packaging_tool, "prepare_packaging_plan", return_value={
                "report_type": "packaging_prepare", "ok": True, "status": "ok",
                "errors": [], "input_errors": [], "warnings": [], "data": {},
            }) as prepare:
                code, output = self._run(self._args(root, plan_path, "--pools", str(pools_path)))

            report = json.loads(output)
            message = " ".join(report["input_errors"])
            self.assertEqual(code, 2)
            self.assertIn("--catalog", message)
            self.assertIn("presets", message)
            self.assertIn("python scripts/packaging_tool.py prepare", message)
            self.assertFalse(prepare.called)

    def test_prepare_missing_pools_reports_producer_command(self):
        with tempfile.TemporaryDirectory(dir=self._temp_root()) as directory:
            root = Path(directory)
            plan_path = root / "plan.json"
            catalog_path = root / "catalog.json"
            plan_path.write_text(json.dumps(self._plan()), encoding="utf-8")
            catalog_path.write_text(json.dumps({"presets": []}), encoding="utf-8")

            with patch.object(packaging_tool, "prepare_packaging_plan", return_value={
                "report_type": "packaging_prepare", "ok": True, "status": "ok",
                "errors": [], "input_errors": [], "warnings": [], "data": {},
            }) as prepare:
                code, output = self._run(self._args(root, plan_path, "--catalog", str(catalog_path)))

            report = json.loads(output)
            message = " ".join(report["input_errors"])
            self.assertEqual(code, 2)
            self.assertIn("--pools", message)
            self.assertIn("pools", message)
            self.assertIn("python scripts/packaging_tool.py prepare", message)
            self.assertFalse(prepare.called)

    def test_prepare_missing_dialogue_intervals_reports_existing_audio_command(self):
        with tempfile.TemporaryDirectory(dir=self._temp_root()) as directory:
            root = Path(directory)
            plan_path = root / "plan.json"
            catalog_path = root / "catalog.json"
            pools_path = root / "pools.json"
            plan_path.write_text(json.dumps(self._plan()), encoding="utf-8")
            catalog_path.write_text(json.dumps({"presets": []}), encoding="utf-8")
            pools_path.write_text(json.dumps({"pools": []}), encoding="utf-8")
            blocked = {
                "report_type": "packaging_prepare", "ok": False, "status": "blocked",
                "errors": ["dialogue evidence is required for final sound preparation"],
                "input_errors": [], "warnings": [],
            }

            with patch.object(packaging_tool, "prepare_packaging_plan", return_value=blocked):
                code, output = self._run(self._args(
                    root, plan_path, "--catalog", str(catalog_path), "--pools", str(pools_path),
                ))

            report = json.loads(output)
            message = " ".join(report["input_errors"])
            self.assertEqual(code, 2)
            self.assertIn("--existing-audio", message)
            self.assertIn("dialogue_intervals", message)
            self.assertIn("start_us", message)
            self.assertIn("end_us", message)
            self.assertIn("python scripts/packaging_tool.py prepare", message)

    def test_prepare_missing_catalog_entry_reports_required_fields(self):
        with tempfile.TemporaryDirectory(dir=self._temp_root()) as directory:
            root = Path(directory)
            plan_path = root / "plan.json"
            catalog_path = root / "catalog.json"
            pools_path = root / "pools.json"
            plan_path.write_text(json.dumps(self._plan()), encoding="utf-8")
            catalog_path.write_text(json.dumps({"presets": []}), encoding="utf-8")
            pools_path.write_text(json.dumps({"pools": []}), encoding="utf-8")
            blocked = {
                "report_type": "packaging_prepare", "ok": False, "status": "blocked",
                "errors": ["group g1.audio.catalog_ref: preset is absent from the sound catalog"],
                "input_errors": [], "warnings": [],
            }

            with patch.object(packaging_tool, "prepare_packaging_plan", return_value=blocked):
                code, output = self._run(self._args(
                    root, plan_path, "--catalog", str(catalog_path), "--pools", str(pools_path),
                ))

            report = json.loads(output)
            message = " ".join(report["input_errors"])
            self.assertEqual(code, 2)
            self.assertIn("presets[]", message)
            self.assertIn("preset_id", message)
            self.assertIn("verified", message)
            self.assertIn("python scripts/packaging_tool.py prepare", message)

    def test_prepare_missing_pool_entry_reports_required_fields(self):
        with tempfile.TemporaryDirectory(dir=self._temp_root()) as directory:
            root = Path(directory)
            plan_path = root / "plan.json"
            catalog_path = root / "catalog.json"
            pools_path = root / "pools.json"
            plan_path.write_text(json.dumps(self._plan()), encoding="utf-8")
            catalog_path.write_text(json.dumps({"presets": []}), encoding="utf-8")
            pools_path.write_text(json.dumps({"pools": []}), encoding="utf-8")
            blocked = {
                "report_type": "packaging_prepare", "ok": False, "status": "blocked",
                "errors": ["group g1.audio.candidate_pool_ref: unknown candidate pool 'pool-a'"],
                "input_errors": [], "warnings": [],
            }

            with patch.object(packaging_tool, "prepare_packaging_plan", return_value=blocked):
                code, output = self._run(self._args(
                    root, plan_path, "--catalog", str(catalog_path), "--pools", str(pools_path),
                ))

            report = json.loads(output)
            message = " ".join(report["input_errors"])
            self.assertEqual(code, 2)
            self.assertIn("pools[]", message)
            self.assertIn("pool_id", message)
            self.assertIn("candidates", message)
            self.assertIn("python scripts/packaging_tool.py prepare", message)

    def test_prepare_missing_animation_evidence_reports_required_fields(self):
        with tempfile.TemporaryDirectory(dir=self._temp_root()) as directory:
            root = Path(directory)
            plan_path = root / "plan.json"
            plan_path.write_text(json.dumps(self._plan(sound=False, animation=True)), encoding="utf-8")
            blocked = {
                "report_type": "packaging_prepare", "ok": False, "status": "blocked",
                "errors": [
                    "current Jianying version is unresolved; pass --animation-version",
                    "no Jianying animation cache roots resolved; pass --animation-cache-root",
                    "animation resource 'text-intro' is not visually verified for plain text",
                ],
                "input_errors": [], "warnings": [],
            }

            with patch.object(packaging_tool, "prepare_packaging_plan", return_value=blocked):
                code, output = self._run(self._args(root, plan_path))

            report = json.loads(output)
            message = " ".join(report["input_errors"])
            self.assertEqual(code, 2)
            self.assertIn("--animation-version", message)
            self.assertIn("--animation-cache-root", message)
            self.assertIn("--animation-capabilities", message)
            self.assertIn("jianying_version", message)
            self.assertIn("verified", message)
            self.assertIn("python scripts/packaging_tool.py prepare", message)


if __name__ == "__main__":
    unittest.main()
