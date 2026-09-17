import os
import stat
import tempfile
import time
import unittest
from pathlib import Path

from scripts.render_editorial import (
    AssetManager,
    PREFLIGHT_PLACEHOLDER,
    ROAST_FOOTER,
    auto_pages,
    build_page_fragments,
    document_html,
    prepare_preflight_html,
    print_pngs,
    run_chrome_export,
    valid_pdf,
)


def report(style="normal"):
    return {
        "kind": "daily",
        "style": style,
        "group_name": "测试群",
        "period": {"start": "2026-09-17", "end": "2026-09-17"},
        "lead": {"title": "当天主线", "dek": "可追溯的副标题", "body": "群里围绕一个具体问题展开讨论。"},
        "sections": [
            {
                "eyebrow": "09:30 · TEST",
                "title": "第一个话题",
                "body": "一段足够短的正文。",
                "quotes": [{"text": "这是一句公开原话", "speaker": "甲", "time": "09:31"}],
            },
            {"eyebrow": "10:00 · TEST", "title": "第二个话题", "body": "第二段足够短的正文。"},
            {"eyebrow": "11:00 · TEST", "title": "第三个话题", "body": "第三段足够短的正文。"},
            {"eyebrow": "12:00 · TEST", "title": "第四个话题", "body": "第四段足够短的正文。"},
            {"eyebrow": "13:00 · TEST", "title": "第五个话题", "body": "第五段足够短的正文。"},
        ],
        "people": [],
        "stats": [],
        "closing": {"title": "留下的问题", "body": "后续仍需观察。"},
        "layout": {"page_mode": "auto"},
    }


def fake_chrome(path: Path) -> Path:
    path.write_text(
        """#!/usr/bin/env python3
import os
import sys
import time
from pathlib import Path

target = None
for argument in sys.argv[1:]:
    if argument.startswith('--output=') or argument.startswith('--screenshot='):
        target = Path(argument.split('=', 1)[1])
    if argument.startswith('--pid-file='):
        Path(argument.split('=', 1)[1]).write_text(str(os.getpid()), encoding='utf-8')
if target is None:
    raise SystemExit(2)
if any(argument.startswith('--screenshot=') for argument in sys.argv[1:]):
    target.write_bytes(b'\\x89PNG\\r\\n\\x1a\\n' + b'fixture-png-' * 3)
else:
    target.write_bytes(b'%PDF-1.4\\nfixture-pdf')
time.sleep(60)
""",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


class RenderEditorialTests(unittest.TestCase):
    def test_auto_pages_respects_the_two_column_story_grid(self):
        pages = auto_pages(report())
        self.assertEqual([page["section_indices"] for page in pages], [[0, 1, 2], [3, 4]])
        self.assertEqual([page["show_extras"] for page in pages], [False, True])

    def test_roast_markup_uses_roster_notes_quote_comments_and_default_footer(self):
        roast_report = report("roast")
        roast_report["sections"] = roast_report["sections"][:1]
        roast_report["sections"][0]["quotes"][0]["comment"] = "一句公开发言，硬是开成了三小时发布会。"
        roast_report["people"] = [
            {"name": "甲", "count": 4, "role": "话题点火器", "roast_note": "每次一句补充，都像给火堆添了根柴。"}
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            assets = AssetManager(root / "assets", "assets", root)
            fragment = build_page_fragments(
                roast_report,
                assets,
                {},
                None,
                pages=[{"section_indices": [0], "show_extras": True}],
            )[0]
        self.assertIn("测试群 · 毒舌版", fragment)
        self.assertIn("本期角色 · 不留情面版", fragment)
        self.assertIn("编辑点评：一句公开发言，硬是开成了三小时发布会。", fragment)
        self.assertIn("每次一句补充，都像给火堆添了根柴。", fragment)
        self.assertIn(ROAST_FOOTER, fragment)

    def test_preflight_html_replaces_remote_images_without_a_window_load_handler(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "report.html"
            source.write_text(
                '<img src="https://caliph.chengyu.dev/brand/caliph.svg"><script>window.addEventListener("load", () => {});</script>',
                encoding="utf-8",
            )
            prepared = prepare_preflight_html(source)
            try:
                content = prepared.read_text(encoding="utf-8")
            finally:
                prepared.unlink(missing_ok=True)
        self.assertIn(PREFLIGHT_PLACEHOLDER, content)
        self.assertNotIn("https://caliph.chengyu.dev/brand/caliph.svg", content)
        self.assertNotIn("window.addEventListener", content)
        self.assertNotIn("window.addEventListener", document_html(report(), ["<section class=\"page\"></section>"]))

    def test_export_finishes_after_a_valid_artifact_without_waiting_for_chrome_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            chrome = fake_chrome(root / "fake-chrome")
            target = root / "report.pdf"
            pid_file = root / "fake-chrome.pid"
            started = time.monotonic()
            run_chrome_export(
                str(chrome),
                target,
                "PDF",
                valid_pdf,
                lambda staging, profile: [str(chrome), f"--output={staging}", f"--pid-file={pid_file}"],
            )
            elapsed = time.monotonic() - started
            self.assertTrue(valid_pdf(target))
            self.assertLess(elapsed, 5)
            pid = int(pid_file.read_text(encoding="utf-8"))
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)

    def test_png_export_removes_its_temporary_page_html(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            chrome = fake_chrome(root / "fake-chrome")
            page_dir = root / "html"
            output_dir = root / "output"
            page_dir.mkdir()
            output_dir.mkdir()
            outputs = print_pngs(
                str(chrome),
                report(),
                ["<section class=\"page\"></section>"],
                page_dir,
                output_dir,
                "fixture",
            )
            self.assertEqual(len(outputs), 1)
            self.assertTrue(outputs[0].is_file())
            self.assertEqual(list(page_dir.glob(".caliph-editorial-page-*.html")), [])


if __name__ == "__main__":
    unittest.main()
