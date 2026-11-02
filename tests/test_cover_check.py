"""Tests for the covered-original guard (staging step 6b)."""
from __future__ import annotations

import unittest

from packaging_tools.cover_check import check_covered_originals, find_visible_covered_duplicates


def _seg(seg_id, mat_id, start, dur, visible=True):
    segment = {
        "id": seg_id,
        "material_id": mat_id,
        "target_timerange": {"start": start, "duration": dur},
    }
    if visible is not True:
        segment["visible"] = False
    return segment


def _value(tracks, materials):
    return {"tracks": tracks, "materials": {"texts": materials}}


def _track(track_id, segments):
    return {"id": track_id, "type": "text", "segments": segments}


def _mat(mat_id, text):
    import json
    return {"id": mat_id, "content": json.dumps({"text": text}, ensure_ascii=False)}


class FindVisibleCoveredDuplicatesTest(unittest.TestCase):
    def test_exact_copy_over_visible_original_is_flagged(self):
        value = _value(
            [_track("orig", [_seg("s1", "m1", 1_000_000, 2_000_000)]),
             _track("review", [_seg("c1", "m2", 1_000_000, 2_000_000)])],
            [_mat("m1", "主轴压力标准设定在"), _mat("m2", "主轴压力标准设定在")],
        )
        dupes = find_visible_covered_duplicates(value)
        self.assertEqual(len(dupes), 1)
        self.assertTrue(dupes[0]["same_text"])
        self.assertEqual(dupes[0]["lower_track_id"], "orig")
        self.assertEqual(dupes[0]["upper_track_id"], "review")

    def test_disabled_original_clears_the_flag(self):
        value = _value(
            [_track("orig", [_seg("s1", "m1", 1_000_000, 2_000_000, visible=False)]),
             _track("review", [_seg("c1", "m2", 1_000_000, 2_000_000)])],
            [_mat("m1", "主轴压力标准设定在"), _mat("m2", "主轴压力标准设定在")],
        )
        self.assertEqual(find_visible_covered_duplicates(value), [])

    def test_hidden_copy_clears_the_flag(self):
        value = _value(
            [_track("orig", [_seg("s1", "m1", 1_000_000, 2_000_000)]),
             _track("review", [_seg("c1", "m2", 1_000_000, 2_000_000, visible=False)])],
            [_mat("m1", "主轴压力标准设定在"), _mat("m2", "主轴压力标准设定在")],
        )
        self.assertEqual(find_visible_covered_duplicates(value), [])

    def test_non_overlapping_copies_are_not_flagged(self):
        value = _value(
            [_track("orig", [_seg("s1", "m1", 1_000_000, 2_000_000)]),
             _track("review", [_seg("c1", "m2", 3_100_000, 2_000_000)])],
            [_mat("m1", "主轴压力标准设定在"), _mat("m2", "半年更换一次")],
        )
        self.assertEqual(find_visible_covered_duplicates(value), [])

    def test_different_text_but_same_start_is_flagged_without_exact_label(self):
        # Duplicate rules use start-time overlap and do not require identical text.
        value = _value(
            [_track("orig", [_seg("s1", "m1", 1_000_000, 2_000_000)]),
             _track("review", [_seg("c1", "m2", 1_010_000, 2_000_000)])],
            [_mat("m1", "做好每日的润滑与清洁"), _mat("m2", "做好每日的润滑与清洁 ")],
        )
        dupes = find_visible_covered_duplicates(value)
        self.assertEqual(len(dupes), 1)
        self.assertFalse(dupes[0]["same_text"])

    def test_same_track_continuations_are_not_duplicates(self):
        value = _value(
            [_track("orig", [_seg("s1", "m1", 1_000_000, 2_000_000),
                             _seg("s2", "m2", 3_000_000, 2_000_000)])],
            [_mat("m1", "半年更换一次"), _mat("m2", "后续一年换一次即可")],
        )
        self.assertEqual(find_visible_covered_duplicates(value), [])


class CheckCoveredOriginalsReportTest(unittest.TestCase):
    def test_report_surfaces_step_6b_guidance(self):
        value = _value(
            [_track("orig", [_seg("s1", "m1", 1_000_000, 2_000_000)]),
             _track("review", [_seg("c1", "m2", 1_000_000, 2_000_000)])],
            [_mat("m1", "使您的工厂"), _mat("m2", "使您的工厂")],
        )
        report = check_covered_originals("unused", content_value=value, timeline_id="t1")
        self.assertTrue(report["ok"])
        self.assertEqual(report["status"], "review")
        self.assertEqual(report["summary"], {"duplicates": 1, "exact_text_duplicates": 1, "clean": False})
        self.assertIn("6b", report["warnings"][0])

    def test_clean_clone_reports_ok(self):
        value = _value(
            [_track("orig", [_seg("s1", "m1", 1_000_000, 2_000_000, visible=False)]),
             _track("review", [_seg("c1", "m2", 1_000_000, 2_000_000)])],
            [_mat("m1", "使您的工厂"), _mat("m2", "使您的工厂")],
        )
        report = check_covered_originals("unused", content_value=value, timeline_id="t1")
        self.assertEqual(report["status"], "ok")
        self.assertTrue(report["summary"]["clean"])


if __name__ == "__main__":
    unittest.main()
