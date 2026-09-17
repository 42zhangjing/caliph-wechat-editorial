#!/usr/bin/env python3
"""Render a Caliph editorial report into modern HTML, PNG pages and/or PDF."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from validate_report import validate

DEFAULT_OUTPUT_ROOT = Path("/Users/chengyu/Downloads/微信群报")
PAGE_WIDTH = 1123
PAGE_HEIGHT = 1587


def esc(value: Any) -> str:
    return html.escape(str(value or ""))


def safe_name(value: str, fallback: str = "微信群报") -> str:
    value = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", value).strip().rstrip(".")
    return value or fallback


def resolve_local_path(value: str | None, base_dir: Path) -> Path | None:
    if not value:
        return None
    if value.startswith("file://"):
        parsed = urlparse(value)
        return Path(unquote(parsed.path))
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve()


class AssetManager:
    def __init__(self, directory: Path, href_prefix: str, base_dir: Path) -> None:
        self.directory = directory
        self.href_prefix = href_prefix.rstrip("/")
        self.base_dir = base_dir
        self.cache: dict[str, str] = {}
        directory.mkdir(parents=True, exist_ok=True)

    def import_asset(self, value: str | None, label: str) -> str:
        path = resolve_local_path(value, self.base_dir)
        if path is None or not path.is_file():
            return ""
        key = str(path)
        if key in self.cache:
            return self.cache[key]
        digest = hashlib.sha1(path.read_bytes()).hexdigest()[:10]
        suffix = path.suffix.lower() or ".jpg"
        filename = f"{safe_name(label, 'asset')}-{digest}{suffix}"
        target = self.directory / filename
        if not target.exists():
            shutil.copy2(path, target)
        href = f"{self.href_prefix}/{filename}"
        self.cache[key] = href
        return href


def image_tag(src: str, alt: str = "", class_name: str = "editorial-image") -> str:
    if not src:
        return ""
    return f'<img class="{esc(class_name)}" src="{esc(src)}" alt="{esc(alt)}">'


def quote_html(quotes: list[dict[str, Any]]) -> str:
    if not quotes:
        return ""
    blocks = []
    for quote in quotes:
        cite = " · ".join(x for x in [quote.get("speaker"), quote.get("time")] if x)
        blocks.append(
            '<blockquote class="quote">'
            f'<p>“{esc(quote.get("text"))}”</p>'
            f'<cite>{esc(cite)}</cite>'
            '</blockquote>'
        )
    return '<div class="quotes">' + "".join(blocks) + "</div>"


def section_html(section: dict[str, Any], number: int, assets: AssetManager) -> str:
    tone = section.get("tone", "ink")
    image = assets.import_asset(section.get("image"), f"story-{number:02d}")
    evidence = section.get("evidence", "group_observation")
    return f'''
    <article class="story story-{esc(tone)}">
      <div class="story-index">{number:02d}</div>
      <div class="story-main">
        <div class="story-meta"><span class="eyebrow">{esc(section.get("eyebrow"))}</span><span class="evidence">{esc(evidence.replace("_", " / ").upper())}</span></div>
        <h3>{esc(section.get("title"))}</h3>
        {image_tag(image, section.get("image_alt", ""))}
        <p class="story-body">{esc(section.get("body"))}</p>
        {quote_html(section.get("quotes", []))}
      </div>
    </article>'''


def people_html(report: dict[str, Any], assets: AssetManager, avatars: dict[str, str]) -> str:
    people = report.get("people", [])
    if not people:
        return ""
    cards = []
    for index, person in enumerate(people, start=1):
        name = str(person.get("name", ""))
        count = f'<span class="person-count">{esc(person["count"])}</span>' if person.get("count") is not None else ""
        raw_avatar = person.get("avatar") or avatars.get(name, "")
        avatar_src = assets.import_asset(str(raw_avatar), f"avatar-{index:03d}") if raw_avatar else ""
        avatar = image_tag(avatar_src, name, "person-avatar-image")
        avatar = avatar or f'<div class="person-avatar">{esc(name or "·")[:1]}</div>'
        cards.append(
            '<div class="person">'
            f'{avatar}<div class="person-copy">'
            f'<div class="person-name">{esc(name)} {count}</div>'
            f'<div class="person-role">{esc(person.get("role"))}</div>'
            f'<div class="person-note">{esc(person.get("note"))}</div>'
            '</div></div>'
        )
    return '<section class="people"><div class="section-heading"><span>本期角色</span><span>PEOPLE</span></div><div class="people-grid">' + "".join(cards) + "</div></section>"


def stats_html(stats: list[dict[str, Any]]) -> str:
    if not stats:
        return ""
    items = "".join(
        f'<div class="stat"><div class="stat-value">{esc(item.get("value"))}</div><div class="stat-label">{esc(item.get("label"))}</div></div>'
        for item in stats
    )
    return f'<section class="stats" style="--stat-count:{max(1, len(stats))}">{items}</section>'


def section_weight(section: dict[str, Any]) -> float:
    body = len(str(section.get("body", "")))
    title = len(str(section.get("title", "")))
    quotes = len(section.get("quotes", []))
    weight = 0.8 + body / 360 + title / 80 + quotes * 0.25
    if section.get("image"):
        weight += 0.7
    if section.get("priority", "major") == "major":
        weight += 0.15
    return weight


def auto_pages(report: dict[str, Any]) -> list[dict[str, Any]]:
    sections = report.get("sections", [])
    if not sections:
        return [{"label": "第 1 版", "section_indices": [], "show_extras": True}]
    pages: list[dict[str, Any]] = []
    current: list[int] = []
    current_weight = 0.0
    for index, section in enumerate(sections):
        cap = 3.15 if not pages else 4.35
        weight = section_weight(section)
        if current and current_weight + weight > cap:
            pages.append({"section_indices": current})
            current = []
            current_weight = 0.0
        current.append(index)
        current_weight += weight
    if current:
        pages.append({"section_indices": current})
    for i, page in enumerate(pages, start=1):
        page["label"] = f"第 {i} 版"
        page["show_extras"] = i == len(pages)
    return pages


def resolve_pages(report: dict[str, Any]) -> list[dict[str, Any]]:
    layout = report.get("layout", {})
    if layout.get("page_mode") == "manual" and report.get("pages"):
        pages = [dict(page) for page in report["pages"]]
        for i, page in enumerate(pages, start=1):
            page.setdefault("label", f"第 {i} 版")
            page.setdefault("show_extras", i == len(pages))
        return pages
    return auto_pages(report)


def masthead_html(report: dict[str, Any], page_label: str, group_avatar: str, first_page: bool) -> str:
    masthead = report.get("masthead", {})
    period = report.get("period", {})
    period_text = " — ".join(x for x in [period.get("start"), period.get("end")] if x)
    avatar = image_tag(group_avatar, report.get("group_name", ""), "group-avatar-image")
    compact = "" if first_page else " masthead--compact"
    return f'''
      <header class="masthead{compact}">
        <div class="masthead-brand">{avatar}<div>
          <div class="masthead-kicker">{esc(masthead.get("kicker", "CALIPH GROUP EDITORIAL"))}</div>
          <h1>{esc(masthead.get("title", report.get("group_name", "群聊编辑部")))}</h1>
          <div class="masthead-subtitle">{esc(masthead.get("subtitle", "群聊现场编辑"))}</div>
        </div></div>
        <div class="issue"><div>{esc(report.get("edition", ""))}</div><div>{esc(period_text)}</div><div>{esc(page_label)}</div></div>
      </header>'''


def lead_html(report: dict[str, Any], assets: AssetManager) -> str:
    lead = report.get("lead", {})
    image = assets.import_asset(lead.get("image"), "lead")
    mode = "lead--with-image" if image else "lead--text-only"
    tags = "".join(f'<span>{esc(tag)}</span>' for tag in lead.get("tags", []))
    return f'''
      <section class="lead {mode}">
        <div class="lead-copy">
          <div class="eyebrow">{esc(lead.get("kicker", "THE LEAD"))}</div>
          <h2>{esc(lead.get("title"))}</h2>
          <p class="lead-dek">{esc(lead.get("dek"))}</p>
          <p class="lead-body">{esc(lead.get("body"))}</p>
          <div class="tags">{tags}</div>
        </div>{image_tag(image, lead.get("image_alt", ""))}
      </section>'''


def continuation_strip(report: dict[str, Any], page: dict[str, Any]) -> str:
    label = page.get("kicker") or ("WEEKLY / CONTINUED" if report.get("kind") == "weekly" else "DAILY / CONTINUED")
    return f'<div class="continuation-strip"><span>{esc(label)}</span><span>{esc(page.get("label", ""))}</span></div>'


def build_page_fragments(
    report: dict[str, Any], assets: AssetManager, avatars: dict[str, str], group_avatar_raw: str | None
) -> list[str]:
    sections = report.get("sections", [])
    pages = resolve_pages(report)
    group_avatar = assets.import_asset(group_avatar_raw or report.get("group_avatar"), "group-avatar")
    fragments: list[str] = []
    for page_number, page in enumerate(pages):
        first_page = page_number == 0
        indices = [i for i in page.get("section_indices", []) if isinstance(i, int) and 0 <= i < len(sections)]
        body = "".join(section_html(sections[i], i + 1, assets) for i in indices)
        show_extras = bool(page.get("show_extras", page_number == len(pages) - 1))
        extras = ""
        if show_extras:
            extras += people_html(report, assets, avatars)
            extras += stats_html(report.get("stats", []))
            closing = report.get("closing", {})
            if closing.get("body"):
                extras += f'<section class="closing"><div class="section-heading"><span>{esc(closing.get("title", "留下的问题"))}</span><span>EDITOR\'S NOTE</span></div><p>{esc(closing.get("body"))}</p></section>'
        top = masthead_html(report, page.get("label", ""), group_avatar, first_page)
        feature = lead_html(report, assets) if first_page else continuation_strip(report, page)
        fragments.append(f'''
    <section class="page">
      {top}<div class="rule"></div>
      <main>{feature}<section class="stories">{body}</section>{extras}</main>
      <footer><span>CALIPH WECHAT EDITORIAL</span><span>{esc(report.get("footer", "本地素材编辑 · 群聊原话与编辑判断分离"))}</span></footer>
    </section>''')
    return fragments


CSS = r'''
@page { size: A3 portrait; margin: 0; }
:root { --paper:#f4f0e8; --ink:#111318; --muted:#706f6b; --accent:#a83228; --secondary:#304b63; --line:#cbc5bb; --panel:#e9e4da; --signal:#111318; }
* { box-sizing:border-box; }
html,body { margin:0; padding:0; background:#d7d4ce; color:var(--ink); }
body { font-family:"Songti SC","Noto Serif SC","STSong",serif; }
body.roast { --paper:#f3f0e8; --ink:#101010; --muted:#65615b; --accent:#e33b20; --secondary:#101010; --panel:#f1d94c; --signal:#f1d94c; }
.page { width:1123px; height:1587px; padding:48px 62px 34px; margin:24px auto; background:var(--paper); display:flex; flex-direction:column; page-break-after:always; overflow:hidden; }
.masthead { display:flex; justify-content:space-between; gap:36px; align-items:flex-start; }
.masthead-brand { display:flex; gap:17px; align-items:flex-start; min-width:0; }
.group-avatar-image { width:72px; height:72px; border-radius:3px; object-fit:cover; flex:none; filter:saturate(.86) contrast(1.03); }
.masthead-kicker,.eyebrow,.section-heading,.continuation-strip,.evidence { font-family:"SFMono-Regular","Menlo","Helvetica Neue","PingFang SC",sans-serif; text-transform:uppercase; }
.masthead-kicker { color:var(--accent); font-size:11px; line-height:1.3; letter-spacing:2.5px; font-weight:700; }
.masthead h1 { margin:7px 0 4px; font-family:"PingFang SC","Helvetica Neue",sans-serif; font-size:50px; line-height:1.02; letter-spacing:-1.5px; font-weight:800; }
.masthead-subtitle { color:var(--muted); font-family:"PingFang SC","Helvetica Neue",sans-serif; font-size:13px; letter-spacing:2px; }
.issue { min-width:205px; text-align:right; color:var(--muted); font-family:"SFMono-Regular","Menlo",monospace; font-size:11px; line-height:1.75; }
.masthead--compact .group-avatar-image { width:44px; height:44px; }
.masthead--compact h1 { font-size:29px; margin:4px 0 2px; letter-spacing:-.5px; }
.masthead--compact .masthead-subtitle { display:none; }
.rule { height:4px; background:var(--ink); margin:20px 0 24px; }
.lead { display:grid; padding:4px 0 27px; border-bottom:1px solid var(--ink); }
.lead--with-image { grid-template-columns:minmax(0,7fr) minmax(280px,5fr); gap:34px; }
.lead--text-only { grid-template-columns:1fr; }
.lead--text-only .lead-copy { display:grid; grid-template-columns:minmax(0,7fr) minmax(260px,5fr); column-gap:40px; }
.lead--text-only .eyebrow,.lead--text-only h2,.lead--text-only .tags { grid-column:1 / -1; }
.lead--text-only .lead-dek { grid-column:1; }
.lead--text-only .lead-body { grid-column:2; grid-row:3; }
.eyebrow { color:var(--accent); font-size:11px; letter-spacing:2px; font-weight:700; }
.lead h2 { margin:10px 0 12px; font-family:"PingFang SC","Helvetica Neue",sans-serif; font-size:44px; line-height:1.08; letter-spacing:-1.3px; font-weight:800; }
.lead-dek { margin:0; color:var(--secondary); font-family:"PingFang SC","Helvetica Neue",sans-serif; font-size:19px; line-height:1.46; font-weight:650; }
.lead-body { margin:0; font-size:15.5px; line-height:1.83; text-align:justify; }
.tags { display:flex; flex-wrap:wrap; gap:7px; margin-top:18px; }
.tags span { border:1px solid var(--accent); color:var(--accent); padding:4px 9px; font-family:"SFMono-Regular","Menlo",sans-serif; font-size:9.5px; letter-spacing:.8px; }
.editorial-image { width:100%; max-height:315px; object-fit:cover; display:block; border-radius:2px; filter:saturate(.86) contrast(1.03); }
.lead > .editorial-image { height:315px; align-self:stretch; }
.continuation-strip { display:flex; justify-content:space-between; padding:1px 0 12px; border-bottom:1px solid var(--line); color:var(--accent); font-size:10px; letter-spacing:2px; font-weight:700; }
.stories { display:grid; grid-template-columns:repeat(12,1fr); column-gap:18px; margin-top:18px; }
.story { grid-column:span 6; display:grid; grid-template-columns:42px 1fr; gap:10px; padding:14px 0 18px; border-top:1px solid var(--line); break-inside:avoid; }
.story:nth-child(-n+2) { border-top:0; }
.story-index { color:var(--accent); font-family:"SFMono-Regular","Menlo",sans-serif; font-size:24px; font-weight:800; line-height:1; }
.story-meta { display:flex; align-items:baseline; justify-content:space-between; gap:8px; }
.evidence { color:var(--muted); font-size:7.5px; letter-spacing:.8px; white-space:nowrap; }
.story h3 { margin:6px 0 9px; font-family:"PingFang SC","Helvetica Neue",sans-serif; font-size:22px; line-height:1.27; letter-spacing:-.4px; }
.story-body { margin:0; font-size:14px; line-height:1.72; text-align:justify; }
.story .editorial-image { margin:8px 0 11px; max-height:195px; }
.quotes { margin-top:10px; border-left:2px solid var(--accent); padding-left:11px; }
.quote { margin:0 0 7px; }
.quote p { margin:0; font-family:"PingFang SC","Helvetica Neue",sans-serif; font-size:12.5px; line-height:1.45; font-weight:600; }
.quote cite { color:var(--muted); font-family:"SFMono-Regular","Menlo",sans-serif; font-size:8.5px; font-style:normal; letter-spacing:.5px; }
.section-heading { display:flex; justify-content:space-between; border-bottom:2px solid var(--ink); padding-bottom:6px; font-size:10px; letter-spacing:1.5px; font-weight:700; }
.people { margin-top:auto; padding-top:14px; }
.people-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:14px 18px; margin-top:12px; }
.person { display:flex; gap:10px; min-height:60px; }
.person-avatar,.person-avatar-image { width:50px; height:50px; flex:none; border-radius:50%; }
.person-avatar { background:var(--secondary); color:#fff; display:grid; place-items:center; font-family:"PingFang SC",sans-serif; font-size:19px; }
.person-avatar-image { object-fit:cover; }
.person-name { font-family:"PingFang SC","Helvetica Neue",sans-serif; font-size:14px; font-weight:750; }
.person-count { color:var(--muted); font-family:"SFMono-Regular","Menlo",monospace; font-size:9px; font-weight:500; }
.person-role { margin-top:2px; color:var(--accent); font-family:"SFMono-Regular","Menlo","PingFang SC",sans-serif; font-size:8.5px; letter-spacing:.5px; }
.person-note { margin-top:3px; color:var(--muted); font-size:10.5px; line-height:1.35; }
.stats { display:grid; grid-template-columns:repeat(var(--stat-count),1fr); margin-top:15px; border:1px solid var(--ink); }
.stat { padding:11px 7px 10px; text-align:center; border-right:1px solid var(--line); }
.stat:last-child { border-right:0; }
.stat-value { font-family:"Helvetica Neue","PingFang SC",sans-serif; font-size:23px; font-weight:800; }
.stat-label { margin-top:3px; color:var(--muted); font-family:"SFMono-Regular","Menlo","PingFang SC",sans-serif; font-size:8.5px; letter-spacing:.4px; }
.closing { margin-top:15px; padding:12px 14px 13px; background:var(--panel); }
.closing .section-heading { border-color:currentColor; }
.closing p { margin:8px 0 0; font-size:13px; line-height:1.6; }
body.roast .story h3,body.roast .lead h2 { letter-spacing:-1.8px; }
body.roast .quote { background:var(--signal); padding:8px 10px; margin-left:-11px; }
body.roast .quote cite { color:#423d24; }
footer { display:flex; justify-content:space-between; margin-top:18px; padding-top:8px; border-top:1px solid var(--ink); color:var(--muted); font-family:"SFMono-Regular","Menlo",sans-serif; font-size:8.5px; letter-spacing:.7px; }
@media screen and (max-width:900px) {
  .page { width:100%; height:auto; min-height:100vh; margin:0; padding:28px 22px; overflow:visible; }
  .lead--with-image,.lead--text-only .lead-copy { grid-template-columns:1fr; display:grid; }
  .lead--text-only .lead-body,.lead--text-only .lead-dek { grid-column:1; grid-row:auto; }
  .stories { display:block; }
  .people-grid { grid-template-columns:1fr 1fr; }
  .stats { grid-template-columns:repeat(2,1fr); }
  .masthead h1 { font-size:36px; }
}
@media print { html,body { background:var(--paper); } .page { margin:0; } }
'''

PREFLIGHT_SCRIPT = r'''<script>
window.addEventListener('load', () => {
  document.querySelectorAll('.page').forEach((p) => {
    p.dataset.overflow = p.scrollHeight > p.clientHeight + 2 ? 'true' : 'false';
    p.dataset.scrollHeight = String(p.scrollHeight);
    p.dataset.clientHeight = String(p.clientHeight);
  });
});
</script>'''


def document_html(report: dict[str, Any], fragments: list[str], png_mode: bool = False) -> str:
    style = report.get("style", "normal")
    body_class = "roast" if style == "roast" else "normal"
    extra = "<style>.page{margin:0!important}.page:not(:first-child){display:none!important}</style>" if png_mode else ""
    title = f'{esc(report.get("group_name", "群聊编辑部"))} · {esc(report.get("kind", "daily"))}'
    return f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>{CSS}</style>{extra}</head><body class="{body_class}">{"".join(fragments)}{PREFLIGHT_SCRIPT}</body></html>'


def find_chrome() -> str | None:
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        shutil.which("google-chrome"),
        shutil.which("chromium"),
    ]
    return next((item for item in candidates if item and Path(item).exists()), None)


def browser_preflight(chrome: str, html_path: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="caliph-preflight-") as profile:
        proc = subprocess.run([
            chrome, "--headless=new", "--disable-gpu", "--allow-file-access-from-files",
            "--virtual-time-budget=1000", f"--user-data-dir={profile}", "--dump-dom",
            html_path.resolve().as_uri(),
        ], check=True, capture_output=True, text=True)
    matches = re.findall(r'data-overflow="(true|false)"[^>]*data-scroll-height="(\d+)"[^>]*data-client-height="(\d+)"', proc.stdout)
    overflowing = [(i + 1, scroll, client) for i, (flag, scroll, client) in enumerate(matches) if flag == "true"]
    if overflowing:
        details = ", ".join(f"p{page} {scroll}>{client}" for page, scroll, client in overflowing)
        raise RuntimeError(f"A3 layout overflow detected: {details}. Reduce copy or adjust pagination before publishing.")


def print_pdf(chrome: str, html_path: Path, pdf_path: Path) -> None:
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="caliph-editorial-chrome-") as profile:
        subprocess.run([
            chrome, "--headless=new", "--disable-gpu", "--allow-file-access-from-files",
            "--no-pdf-header-footer", f"--user-data-dir={profile}",
            f"--print-to-pdf={pdf_path}", html_path.resolve().as_uri(),
        ], check=True)
    os.chmod(pdf_path, 0o600)


def print_pngs(chrome: str, report: dict[str, Any], fragments: list[str], work_dir: Path, output_dir: Path, base_name: str) -> list[Path]:
    outputs: list[Path] = []
    for i, fragment in enumerate(fragments, start=1):
        page_html = work_dir / f"page-{i:02d}.html"
        page_html.write_text(document_html(report, [fragment], png_mode=True), encoding="utf-8")
        target = output_dir / f"{base_name}_p{i:02d}.png"
        with tempfile.TemporaryDirectory(prefix="caliph-png-chrome-") as profile:
            subprocess.run([
                chrome, "--headless=new", "--disable-gpu", "--allow-file-access-from-files",
                "--hide-scrollbars", f"--user-data-dir={profile}",
                f"--window-size={PAGE_WIDTH},{PAGE_HEIGHT}", "--force-device-scale-factor=2",
                f"--screenshot={target}", page_html.resolve().as_uri(),
            ], check=True)
        os.chmod(target, 0o600)
        outputs.append(target)
    return outputs


def base_output_name(report: dict[str, Any]) -> str:
    group = safe_name(str(report.get("group_name", "微信群")))
    kind = "日报" if report.get("kind") == "daily" else "周报"
    period = report.get("period", {})
    start, end = str(period.get("start", "")), str(period.get("end", ""))
    span = start if start == end else f"{start}--{end}"
    style = "毒舌版" if report.get("style", "normal") == "roast" else "普通版"
    return safe_name(f"{group}_{kind}_{span}_{style}")


def parse_formats(value: str) -> list[str]:
    formats = [item.strip().lower() for item in value.split(",") if item.strip()]
    invalid = [item for item in formats if item not in {"html", "png", "pdf"}]
    if invalid:
        raise ValueError(f"unsupported formats: {', '.join(invalid)}")
    return list(dict.fromkeys(formats))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("report", type=Path, help="report.json")
    p.add_argument("--source", type=Path, help="source-normalized.json; enables quote audit")
    p.add_argument("--output", type=Path, help="legacy explicit HTML output path")
    p.add_argument("--output-dir", type=Path, help="output root; defaults to /Users/chengyu/Downloads/微信群报")
    p.add_argument("--formats", help="comma-separated: html,png,pdf; default png,pdf (or html with legacy --output)")
    p.add_argument("--avatars", type=Path, help="optional name -> local avatar path JSON")
    p.add_argument("--group-avatar", type=Path, help="optional local group avatar image")
    p.add_argument("--skip-preflight", action="store_true")
    args = p.parse_args()

    report_path = args.report.resolve()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    source = json.loads(args.source.read_text(encoding="utf-8")) if args.source else None
    errors, warnings = validate(report, source)
    for warning in warnings:
        print(f"[WARN] {warning}")
    if errors:
        for error in errors:
            print(f"[ERROR] {error}")
        return 1

    formats = parse_formats(args.formats or ("html" if args.output else "png,pdf"))
    output_root = (args.output_dir or DEFAULT_OUTPUT_ROOT).expanduser()
    group_dir = output_root / safe_name(str(report.get("group_name", "微信群")))
    group_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(group_dir, 0o700)
    name = base_output_name(report)

    avatars = json.loads(args.avatars.read_text(encoding="utf-8")) if args.avatars else {}
    chrome = find_chrome()
    if any(fmt in {"png", "pdf"} for fmt in formats) and not chrome:
        raise RuntimeError("PNG/PDF export requires Google Chrome or Chromium.")

    persistent_html = "html" in formats
    if persistent_html:
        html_path = args.output or (group_dir / f"{name}.html")
        assets_dir = html_path.parent / f"{html_path.stem}_assets"
        href_prefix = assets_dir.name
        work_context = None
        work_dir = html_path.parent
    else:
        work_context = tempfile.TemporaryDirectory(prefix="caliph-editorial-")
        work_dir = Path(work_context.name)
        html_path = work_dir / f"{name}.html"
        assets_dir = work_dir / "assets"
        href_prefix = "assets"

    try:
        assets = AssetManager(assets_dir, href_prefix, report_path.parent)
        fragments = build_page_fragments(
            report,
            assets,
            avatars,
            str(args.group_avatar.resolve()) if args.group_avatar else None,
        )
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(document_html(report, fragments), encoding="utf-8")
        os.chmod(html_path, 0o600)

        if chrome and not args.skip_preflight:
            browser_preflight(chrome, html_path)

        outputs: list[Path] = []
        if persistent_html:
            outputs.append(html_path)
        if "pdf" in formats:
            pdf_path = group_dir / f"{name}.pdf"
            print_pdf(chrome or "", html_path, pdf_path)
            outputs.append(pdf_path)
        if "png" in formats:
            outputs.extend(print_pngs(chrome or "", report, fragments, work_dir, group_dir, name))

        for output in outputs:
            print(f"[OK] wrote {output}")
        return 0
    finally:
        if work_context is not None:
            work_context.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
