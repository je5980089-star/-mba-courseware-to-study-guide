"""Simple tests: run `python -m unittest discover -s tests -v`."""
import importlib.util
from pathlib import Path
import unittest

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "audit_guide.py"
spec = importlib.util.spec_from_file_location("audit_guide", MODULE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def manifest():
    return {
        "schema_version": 1,
        "constraints": {"allow_exam_questions": False},
        "source_units": [{"id": "p1", "status": "reviewed"}],
        "topics": [{"id": "t1", "title": "薪酬体系设计", "required": True, "aliases": ["薪酬体系设计"], "source_refs": ["p1"]}],
        "composites": [{"id": "t1", "title": "薪酬体系设计", "must_have_dedicated_heading": True,
                        "steps": ["岗位价值评价", "薪酬调查", "薪酬现状分析", "薪酬战略", "薪酬结构", "薪酬构成"],
                        "min_chars": 200, "min_chars_per_step": 10}]
    }


def B(s, level=None):
    return {"kind": "paragraph", "text": s, "heading_level": level}


class CoverageAuditTests(unittest.TestCase):
    def test_keywords_scattered_but_no_complete_method_fails(self):
        blocks = [B("岗位价值评价的概念", 2), B("薪酬调查是..."), B("薪酬现状分析"),
                  B("薪酬战略"), B("薪酬结构"), B("薪酬构成"), B("薪酬体系设计只是一个词。")]
        result = audit.check_guide(manifest(), blocks)
        self.assertEqual(result["status"], "fail")
        self.assertTrue(any("NO dedicated heading" in msg for msg in result["failures"]))

    def test_six_unexplained_steps_fail(self):
        blocks = [B("薪酬体系设计", 2), B("岗位价值评价、薪酬调查、薪酬现状分析、薪酬战略、薪酬结构、薪酬构成。")]
        result = audit.check_guide(manifest(), blocks)
        self.assertEqual(result["status"], "fail")
        self.assertTrue(any("too little explanatory text" in msg for msg in result["failures"]))

    def test_full_integrated_process_passes(self):
        s = "这一步需要收集事实并形成下一阶段可运用的结果，同时解释决策依据、组织情境和执行风险。"
        blocks = [B("薪酬体系设计", 2), B("目标是把组织战略、岗位价值、薪酬竞争力和激励机制连接起来。")]
        for step in manifest()["composites"][0]["steps"]:
            blocks.append(B(step + "。" + s * 2))
        result = audit.check_guide(manifest(), blocks)
        self.assertEqual(result["status"], "pass", result["failures"])

    def test_page_cap_requires_pdf_verification(self):
        m = manifest()
        m["constraints"]["max_pages"] = 8
        blocks = [B("薪酬体系设计", 2)] + [B(x + "：" + "背景、具体操作、形成的产出与如何衔接。" * 4)
                                           for x in m["composites"][0]["steps"]]
        result = audit.check_guide(m, blocks)
        self.assertEqual(result["status"], "review_required")


class IndependentScanTests(unittest.TestCase):
    def test_numbered_steps_trigger_review_even_when_manifest_omits_them(self):
        pre_scan = {"units": [{"id": "p1"}], "flow_candidates": [{"id": "flow-1", "unit_ids": ["p1"]}]}
        m = manifest()
        m["composites"] = []
        blocks = [B("薪酬体系设计", 2), B("相关概念很重要。")]
        result = audit.check_guide(m, blocks, source_scan=pre_scan)
        self.assertEqual(result["status"], "fail")
        self.assertTrue(any("no accept/reject decision" in msg for msg in result["failures"]))

    def test_missing_page_from_scan_is_failure(self):
        pre_scan = {"units": [{"id": "p1"}, {"id": "p2"}], "flow_candidates": []}
        m = manifest()
        result = audit.check_guide(m, [B("薪酬体系设计", 2)], source_scan=pre_scan)
        self.assertTrue(any("Missing inspected source pages" in msg for msg in result["failures"]))


if __name__ == "__main__":
    unittest.main()
