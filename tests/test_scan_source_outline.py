"""Regression case for source numbering detection."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "scan_source_outline.py"
spec = importlib.util.spec_from_file_location("scan_source_outline", MODULE)
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)


class OutlineTests(unittest.TestCase):
    def test_chinese_step_numbers_above_ten(self):
        self.assertEqual(scan.step_number("第十二步"), 12)
        self.assertEqual(scan.step_number("第十步"), 10)
        self.assertEqual(scan.step_number("第二十三阶段"), 23)

    def test_detects_numbered_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lecture.txt"
            path.write_text("第1步 岗位价值评价\n第2步 薪酬调查\n第3步 现状诊断\n"
                            "第4步 薪酬战略\n第5步 薪酬结构\n第6步 薪酬构成\n", encoding="utf-8")
            result = scan.scan_files([path])
            self.assertEqual(len(result["units"]), 1)
            self.assertEqual(len(result["flow_candidates"]), 1)
            self.assertEqual(result["flow_candidates"][0]["step_numbers"], [1,2,3,4,5,6])


if __name__ == "__main__":
    unittest.main()
