import unittest

from scripts.validate_report import validate


class ValidateReportTests(unittest.TestCase):
    def base_report(self):
        return {
            "kind": "daily",
            "style": "normal",
            "group_name": "测试群",
            "period": {"start": "2026-09-17", "end": "2026-09-17"},
            "lead": {"title": "今天的主线", "dek": "一个具体副标题", "body": "当天讨论围绕一个明确问题展开。"},
            "sections": [
                {
                    "eyebrow": "09:30 · TEST",
                    "title": "一次可追溯的讨论",
                    "body": "甲提出问题，乙给出回应，讨论随后收束。",
                    "tone": "ink",
                    "priority": "major",
                    "evidence": "direct_quote",
                    "quotes": [{"text": "这是一句原话", "speaker": "甲", "time": "09:31"}],
                },
                {"eyebrow": "11:00 · TEST", "title": "第二个节点", "body": "补充背景。"},
                {"eyebrow": "15:00 · TEST", "title": "第三个节点", "body": "完成收束。"},
            ],
            "people": [],
            "stats": [],
            "closing": {"title": "留下的问题", "body": "明天继续观察结果。"},
        }

    def source(self):
        return {
            "period": {"start": "2026-09-17", "end": "2026-09-17"},
            "messages": [
                {"anchor": "M000001", "time": "2026-09-17 09:31:00", "sender": "甲", "type": "文本", "content": "这是一句原话"}
            ],
        }

    def test_valid_quote_passes(self):
        errors, _ = validate(self.base_report(), self.source())
        self.assertEqual(errors, [])

    def test_missing_quote_fails(self):
        report = self.base_report()
        report["sections"][0]["quotes"][0]["text"] = "素材里没有这句话"
        errors, _ = validate(report, self.source())
        self.assertTrue(any("quote not found verbatim" in item for item in errors))

    def test_not_but_pattern_is_style_error(self):
        report = self.base_report()
        report["closing"]["body"] = "明天关注的不是热度，而是后续执行。"
        errors, _ = validate(report, self.source())
        self.assertTrue(any("不是……而是……" in item for item in errors))

    def test_direct_quote_may_contain_not_but_pattern(self):
        report = self.base_report()
        report["sections"][0]["quotes"][0]["text"] = "这不是效率问题，而是成本问题"
        source = self.source()
        source["messages"][0]["content"] = "这不是效率问题，而是成本问题"
        errors, _ = validate(report, source)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
