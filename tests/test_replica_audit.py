from __future__ import annotations

import unittest
import sys
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from packaging_tools.replica_audit import classify_replica_errors


class ReplicaAuditTests(unittest.TestCase):
    def test_only_associated_backup_drift_becomes_a_warning(self):
        backup = r"C:\draft\Timelines\T1\draft_content.json.bak"
        template = r"C:\draft\Timelines\T1\template-2.tmp"
        manifest = {
            "replicas": [
                {"path": r"C:\draft\Timelines\T1\draft_content.json", "role": "primary", "primary": True, "associated": True},
                {"path": backup, "role": "writable-backup", "primary": False, "associated": True},
                {"path": template, "role": "writable-template", "primary": False, "associated": True},
            ],
            "errors": [],
        }

        errors, warnings = classify_replica_errors(
            [
                f"Replica differs from primary: {backup}",
                f"Replica differs from primary: {template}",
                "primary content has invalid structure",
            ],
            manifest,
        )

        self.assertEqual(errors, [f"Replica differs from primary: {template}", "primary content has invalid structure"])
        self.assertEqual(warnings, [f"Replica differs from primary: {backup}"])

    def test_unassociated_backup_and_unknown_path_remain_blocking(self):
        backup = r"C:\draft\Timelines\T1\draft_content.json.bak"
        unknown = r"C:\draft\Timelines\T1\other.tmp"
        manifest = {
            "replicas": [
                {"path": backup, "role": "writable-backup", "primary": False, "associated": False},
            ],
            "errors": [f"Unassociated content candidate: {backup}"],
        }

        errors, warnings = classify_replica_errors(
            [f"Replica differs from primary: {backup}", f"Replica differs from primary: {unknown}"],
            manifest,
        )

        self.assertEqual(errors, [f"Replica differs from primary: {backup}", f"Replica differs from primary: {unknown}"])
        self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()
