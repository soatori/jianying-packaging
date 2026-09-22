import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "packaging_tools" / "validators" / "generic_content_impl.py"
SPEC = importlib.util.spec_from_file_location("check_skill_generic_content", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {SCRIPT}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class GenericContentTests(unittest.TestCase):
    def test_generic_text_is_clean(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "generic.md"
            path.write_text("Use semantic-unit IDs and relative slots.", encoding="utf-8")
            self.assertEqual(MODULE.scan([path]), [])

    def test_project_path_is_detected(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bad.md"
            project_path = "E:" + "/JianyingPro/" + "JianyingPro " + "Dra" + "fts/example"
            path.write_text(project_path, encoding="utf-8")
            self.assertTrue(MODULE.scan([path]))

    def test_project_path_in_test_file_is_detected(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "test_bad.py"
            project_path = "E:" + "/JianyingPro/" + "JianyingPro " + "Dra" + "fts/example"
            path.write_text(project_path, encoding="utf-8")
            self.assertTrue(MODULE.scan([path]))

    def test_guid_and_media_references_are_detected(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bad.md"
            guid = "00000000" + "-0000-0000-0000-000000000000"
            media = "clip" + ".mp4"
            path.write_text(guid + " " + media, encoding="utf-8")
            findings = MODULE.scan([path])
            self.assertTrue(any("guid" in item for item in findings))
            self.assertTrue(any("media_filename" in item for item in findings))

    def test_template_like_file_is_checked_without_catalog_exemption(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "template-provenance.json"
            project_path = "E:" + "/JianyingPro/" + "JianyingPro " + "Dra" + "fts/template"
            path.write_text(project_path, encoding="utf-8")
            self.assertTrue(MODULE.scan([path]))

    def test_forbidden_literals_are_runtime_supplied(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "generic.md"
            path.write_text("project marker", encoding="utf-8")
            findings = MODULE.scan([path], forbidden_literals=["project marker"])
            self.assertTrue(any("forbidden_literal" in item for item in findings))


if __name__ == "__main__":
    unittest.main()
