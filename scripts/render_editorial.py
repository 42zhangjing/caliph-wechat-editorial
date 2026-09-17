#!/usr/bin/env python3
"""Render a Caliph editorial report into modern HTML, PNG pages and/or PDF."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import signal
import socket
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote, urlparse

try:
    from .validate_report import validate
except ImportError:  # Script execution keeps the existing direct-import path.
    from validate_report import validate

DEFAULT_OUTPUT_ROOT = Path("/Users/chengyu/Downloads/微信群报")
DEFAULT_BRAND_LOGO = "https://caliph.chengyu.dev/brand/caliph.svg"
PAGE_WIDTH = 1123
PAGE_HEIGHT = 1587
PREFLIGHT_TIMEOUT_SECONDS = 20
EXPORT_TIMEOUT_SECONDS = 45
EXPORT_ARTIFACT_SETTLE_SECONDS = 0.45
MAX_STORIES_ON_FIRST_PAGE = 3
MAX_STORIES_ON_CONTINUATION_PAGE = 4
ROAST_FOOTER = "本简报由一个没有感情的 AI 自动生成，如有冒犯，概不负责。"
PREFLIGHT_PLACEHOLDER = (
    "data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 "
    "width=%2290%22 height=%2216%22%3E%3Crect width=%2290%22 height=%2216%22 "
    "fill=%22%23ddd4c5%22/%3E%3C/svg%3E"
)


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
        if not value:
            return ""
        if value.startswith("https://") or value.startswith("http://"):
            # Public brand assets may remain remote. Private/local images are always localized.
            return value
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


def quote_html(quotes: list[dict[str, Any]], roast: bool = False) -> str:
    if not quotes:
        return ""
    blocks = []
    for quote in quotes:
        cite = " · ".join(x for x in [quote.get("speaker"), quote.get("time")] if x)
        comment = str(quote.get("comment", "")).strip() if roast else ""
        comment_html = f'<p class="quote-comment">编辑点评：{esc(comment)}</p>' if comment else ""
        blocks.append(
            '<blockquote class="quote">'
            f'<p>“{esc(quote.get("text"))}”</p>'
            f'<cite>{esc(cite)}</cite>'
            f'{comment_html}'
            '</blockquote>'
        )
    return '<div class="quotes">' + "".join(blocks) + "</div>"


def section_html(section: dict[str, Any], number: int, assets: AssetManager, roast: bool = False) -> str:
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
        {quote_html(section.get("quotes", []), roast=roast)}
      </div>
    </article>'''


def people_html(report: dict[str, Any], assets: AssetManager, avatars: dict[str, str]) -> str:
    people = report.get("people", [])
    if not people:
        return ""
    roast = report.get("style") == "roast"
    cards = []
    for index, person in enumerate(people, start=1):
        name = str(person.get("name", ""))
        count = f'<span class="person-count">{esc(person["count"])}</span>' if person.get("count") is not None else ""
        raw_avatar = person.get("avatar") or avatars.get(name, "")
        avatar_src = assets.import_asset(str(raw_avatar), f"avatar-{index:03d}") if raw_avatar else ""
        avatar = image_tag(avatar_src, name, "person-avatar-image")
        avatar = avatar or f'<div class="person-avatar">{esc(name or "·")[:1]}</div>'
        note = person.get("roast_note") if roast and person.get("roast_note") else person.get("note")
        cards.append(
            '<div class="person">'
            f'{avatar}<div class="person-copy">'
            f'<div class="person-name">{esc(name)} {count}</div>'
            f'<div class="person-role">{esc(person.get("role"))}</div>'
            f'<div class="person-note">{esc(note)}</div>'
            '</div></div>'
        )
    heading = "本期角色 · 不留情面版" if roast else "本期角色"
    label = "ROAST ROSTER" if roast else "PEOPLE"
    return f'<section class="people"><div class="section-heading"><span>{heading}</span><span>{label}</span></div><div class="people-grid">' + "".join(cards) + "</div></section>"


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


def page_weight(sections: list[dict[str, Any]], indices: list[int]) -> float:
    """Estimate rows, not individual cards: stories render in a two-column grid."""
    return sum(
        max(section_weight(sections[index]) for index in indices[offset:offset + 2])
        for offset in range(0, len(indices), 2)
    )


def label_auto_pages(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for index, page in enumerate(pages, start=1):
        page["label"] = f"第 {index} 版"
        page["show_extras"] = index == len(pages)
    return pages


def auto_pages(report: dict[str, Any]) -> list[dict[str, Any]]:
    sections = report.get("sections", [])
    if not sections:
        return [{"label": "第 1 版", "section_indices": [], "show_extras": True}]
    pages: list[dict[str, Any]] = []
    current: list[int] = []
    for index, section in enumerate(sections):
        cap = 3.15 if not pages else 4.35
        max_stories = MAX_STORIES_ON_FIRST_PAGE if not pages else MAX_STORIES_ON_CONTINUATION_PAGE
        candidate = current + [index]
        if current and (len(candidate) > max_stories or page_weight(sections, candidate) > cap):
            pages.append({"section_indices": current})
            current = []
        current.append(index)
    if current:
        pages.append({"section_indices": current})
    return label_auto_pages(pages)


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
    title = str(masthead.get("title", report.get("group_name", "群聊编辑部")))
    edition = str(report.get("edition", ""))
    if report.get("style") == "roast":
        if "毒舌版" not in title:
            title = f"{title} · 毒舌版"
        if "毒舌版" not in edition:
            edition = f"{edition} · 毒舌版" if edition else "毒舌版"
    return f'''
      <header class="masthead{compact}">
        <div class="masthead-brand">{avatar}<div>
          <div class="masthead-kicker">{esc(masthead.get("kicker", "CALIPH GROUP EDITORIAL"))}</div>
          <h1>{esc(title)}</h1>
          <div class="masthead-subtitle">{esc(masthead.get("subtitle", "群聊现场编辑"))}</div>
        </div></div>
        <div class="issue"><div>{esc(edition)}</div><div>{esc(period_text)}</div><div>{esc(page_label)}</div></div>
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


def build_page_fragment(
    report: dict[str, Any],
    assets: AssetManager,
    avatars: dict[str, str],
    group_avatar: str,
    brand_logo: str,
    page: dict[str, Any],
    page_number: int,
    page_count: int,
) -> str:
    sections = report.get("sections", [])
    first_page = page_number == 0
    indices = [i for i in page.get("section_indices", []) if isinstance(i, int) and 0 <= i < len(sections)]
    roast = report.get("style") == "roast"
    body = "".join(section_html(sections[i], i + 1, assets, roast=roast) for i in indices)
    show_extras = bool(page.get("show_extras", page_number == page_count - 1))
    extras = ""
    if show_extras:
        extras += people_html(report, assets, avatars)
        extras += stats_html(report.get("stats", []))
        closing = report.get("closing", {})
        if closing.get("body"):
            extras += f'<section class="closing"><div class="section-heading"><span>{esc(closing.get("title", "留下的问题"))}</span><span>EDITOR\'S NOTE</span></div><p>{esc(closing.get("body"))}</p></section>'
    top = masthead_html(report, page.get("label", ""), group_avatar, first_page)
    feature = lead_html(report, assets) if first_page else continuation_strip(report, page)
    footer_brand = image_tag(brand_logo, "CALIPH", "brand-logo")
    footer_default = ROAST_FOOTER if roast else "本地素材编辑 · 群聊原话与编辑判断分离"
    footer_text = report.get("footer") or footer_default
    return f'''
    <section class="page">
      {top}<div class="rule"></div>
      <main>{feature}<section class="stories">{body}</section>{extras}</main>
      <footer><span class="footer-brand">{footer_brand}<span>CALIPH WECHAT EDITORIAL</span></span><span>{esc(footer_text)}</span></footer>
    </section>'''


def build_page_fragments(
    report: dict[str, Any],
    assets: AssetManager,
    avatars: dict[str, str],
    group_avatar_raw: str | None,
    pages: list[dict[str, Any]] | None = None,
) -> list[str]:
    pages = pages if pages is not None else resolve_pages(report)
    group_avatar = assets.import_asset(group_avatar_raw or report.get("group_avatar"), "group-avatar")
    brand = report.get("brand", {}) if isinstance(report.get("brand", {}), dict) else {}
    brand_logo = assets.import_asset(str(brand.get("logo", DEFAULT_BRAND_LOGO)), "caliph-brand")
    return [
        build_page_fragment(report, assets, avatars, group_avatar, brand_logo, page, page_number, len(pages))
        for page_number, page in enumerate(pages)
    ]


CSS = r'''
@page { size: A3 portrait; margin: 0; }
:root { --paper:#f4f0e8; --ink:#111318; --muted:#706f6b; --accent:#a83228; --secondary:#304b63; --line:#cbc5bb; --panel:#e9e4da; --signal:#111318; }
* { box-sizing:border-box; }
html,body { margin:0; padding:0; background:#d7d4ce; color:var(--ink); }
body { font-family:"Songti SC","Noto Serif SC","STSong",serif; }
body.roast { --paper:#f3f0e8; --ink:#101010; --muted:#65615b; --accent:#e33b20; --secondary:#101010; --panel:#f1d94c; --signal:#f1d94c; }
.page { width:1123px; height:1587px; padding:48px 62px 34px; margin:24px auto; background:var(--paper); display:flex; flex-direction:column; page-break-after:always; overflow:hidden; }
.page > main { min-height:0; flex:1; display:flex; flex-direction:column; }
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
.stories { display:grid; grid-template-columns:repeat(12,1fr); column-gap:18px; margin-top:18px; flex:1; align-content:space-between; }
.story { grid-column:span 6; display:grid; grid-template-columns:42px 1fr; gap:10px; padding:14px 0 18px; border-top:1px solid var(--line); break-inside:avoid; }
.story:nth-child(-n+2) { border-top:0; }
.story:last-child:nth-child(odd) { grid-column:span 12; }
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
.quote-comment { margin:5px 0 0; color:var(--accent); font-family:"PingFang SC","Helvetica Neue",sans-serif; font-size:10.5px; line-height:1.45; font-weight:700; }
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
body.roast .quote-comment { color:#423d24; }
footer { display:flex; justify-content:space-between; align-items:center; gap:18px; margin-top:18px; padding-top:8px; border-top:1px solid var(--ink); color:var(--muted); font-family:"SFMono-Regular","Menlo",sans-serif; font-size:8.5px; letter-spacing:.7px; }
.footer-brand { display:flex; align-items:center; gap:8px; min-width:0; }
.brand-logo { width:auto; height:16px; max-width:90px; object-fit:contain; display:block; }
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

def document_html(report: dict[str, Any], fragments: list[str], png_mode: bool = False) -> str:
    style = report.get("style", "normal")
    body_class = "roast" if style == "roast" else "normal"
    extra = "<style>.page{margin:0!important}.page:not(:first-child){display:none!important}</style>" if png_mode else ""
    title = f'{esc(report.get("group_name", "群聊编辑部"))} · {esc(report.get("kind", "daily"))}'
    return f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>{CSS}</style>{extra}</head><body class="{body_class}">{"".join(fragments)}</body></html>'


def find_chrome() -> str | None:
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        shutil.which("google-chrome"),
        shutil.which("chromium"),
    ]
    return next((item for item in candidates if item and Path(item).exists()), None)


def prepare_preflight_html(html_path: Path) -> Path:
    """Copy HTML for preflight without network images or page-side scripts."""
    source = html_path.read_text(encoding="utf-8")
    source = re.sub(
        r"(?P<prefix>\bsrc\s*=\s*[\"'])https?://[^\"']+(?P<suffix>[\"'])",
        lambda match: f"{match.group('prefix')}{PREFLIGHT_PLACEHOLDER}{match.group('suffix')}",
        source,
        flags=re.IGNORECASE,
    )
    source = re.sub(r"<script>.*?</script>", "", source, flags=re.IGNORECASE | re.DOTALL)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=html_path.parent,
        prefix=f".{html_path.stem}-",
        suffix=".preflight.html",
        delete=False,
    ) as handle:
        handle.write(source)
        return Path(handle.name)


def terminate_process_group(proc: subprocess.Popen[Any], grace_seconds: float = 2.0) -> None:
    """End one isolated Chrome invocation without touching the user's browser."""
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()


def browser_layout_measurements(chrome: str, html_path: Path) -> list[dict[str, Any]]:
    """Measure pages through CDP without waiting for remote page assets."""
    from websockets.sync.client import connect

    preflight_path = prepare_preflight_html(html_path)
    deadline = time.monotonic() + PREFLIGHT_TIMEOUT_SECONDS

    def remaining() -> float:
        value = deadline - time.monotonic()
        if value <= 0:
            raise TimeoutError
        return value

    try:
        with tempfile.TemporaryDirectory(prefix="caliph-preflight-") as profile:
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
            proc = subprocess.Popen([
                chrome, "--headless=new", "--disable-gpu", "--allow-file-access-from-files",
                f"--remote-debugging-port={port}", f"--user-data-dir={profile}", "about:blank",
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            try:
                endpoint = f"http://127.0.0.1:{port}/json/list"
                targets = None
                while targets is None:
                    try:
                        with urllib.request.urlopen(endpoint, timeout=min(1.0, remaining())) as response:
                            targets = json.load(response)
                    except (OSError, TimeoutError):
                        time.sleep(min(0.05, remaining()))
                page_target = next(item for item in targets if item.get("type") == "page")
                with connect(page_target["webSocketDebuggerUrl"], open_timeout=min(3.0, remaining()), close_timeout=1) as ws:
                    command_id = 0

                    def command(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
                        nonlocal command_id
                        command_id += 1
                        current_id = command_id
                        ws.send(json.dumps({"id": current_id, "method": method, "params": params or {}}))
                        while True:
                            message = json.loads(ws.recv(timeout=remaining()))
                            if message.get("id") == current_id:
                                if "error" in message:
                                    raise RuntimeError(f"Chrome CDP error: {message['error']}")
                                return message

                    command("Page.enable")
                    command("Runtime.enable")
                    command("Page.navigate", {"url": preflight_path.resolve().as_uri()})
                    while True:
                        message = json.loads(ws.recv(timeout=remaining()))
                        if message.get("method") == "Page.domContentEventFired":
                            break
                    result = command(
                        "Runtime.evaluate",
                        {
                            "awaitPromise": True,
                            "returnByValue": True,
                            "expression": """
                            (async () => {
                              const fonts = document.fonts && document.fonts.ready
                                ? document.fonts.ready.catch(() => undefined)
                                : Promise.resolve();
                              const frame = () => new Promise(resolve => requestAnimationFrame(resolve));
                              await Promise.race([
                                Promise.all([fonts, frame(), frame()]),
                                new Promise(resolve => setTimeout(resolve, 400))
                              ]);
                              return Array.from(document.querySelectorAll('.page')).map((p) => {
                                const pageRect = p.getBoundingClientRect();
                                const footer = p.querySelector('footer');
                                const contentBottom = footer
                                  ? footer.getBoundingClientRect().bottom - pageRect.top
                                  : 0;
                                return {
                                  overflow: p.scrollHeight > p.clientHeight + 2,
                                  scrollHeight: p.scrollHeight,
                                  clientHeight: p.clientHeight,
                                  contentBottom: Math.ceil(contentBottom),
                                  utilization: Number((contentBottom / p.clientHeight).toFixed(3))
                                };
                              });
                            })()
                            """,
                        },
                    )
                    measurements = result.get("result", {}).get("result", {}).get("value")
                    if not isinstance(measurements, list):
                        raise RuntimeError("Chrome preflight completed without layout measurements.")
            finally:
                terminate_process_group(proc)
        return measurements
    except TimeoutError as exc:
        raise RuntimeError(
            f"Chrome preflight timed out after {PREFLIGHT_TIMEOUT_SECONDS}s; terminated its process group."
        ) from exc
    finally:
        preflight_path.unlink(missing_ok=True)


def browser_preflight(chrome: str, html_path: Path) -> None:
    measurements = browser_layout_measurements(chrome, html_path)
    overflowing = [
        (i + 1, item["scrollHeight"], item["clientHeight"])
        for i, item in enumerate(measurements)
        if item.get("overflow")
    ]
    if overflowing:
        details = ", ".join(f"p{page} {scroll}>{client}" for page, scroll, client in overflowing)
        raise RuntimeError(f"A3 layout overflow detected: {details}. Reduce copy or adjust pagination before publishing.")


def page_fits(
    chrome: str,
    report: dict[str, Any],
    assets: AssetManager,
    avatars: dict[str, str],
    group_avatar: str,
    brand_logo: str,
    page: dict[str, Any],
    page_number: int,
    page_count: int,
    html_dir: Path,
) -> bool:
    fragment = build_page_fragment(
        report, assets, avatars, group_avatar, brand_logo, page, page_number, page_count
    )
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=html_dir, prefix=".caliph-layout-", suffix=".html", delete=False
    ) as handle:
        handle.write(document_html(report, [fragment]))
        candidate_path = Path(handle.name)
    try:
        measurements = browser_layout_measurements(chrome, candidate_path)
    finally:
        candidate_path.unlink(missing_ok=True)
    if len(measurements) != 1:
        raise RuntimeError("Chrome layout packing completed without exactly one page measurement.")
    return not bool(measurements[0].get("overflow"))


def measured_auto_pages(
    chrome: str,
    report: dict[str, Any],
    assets: AssetManager,
    avatars: dict[str, str],
    group_avatar_raw: str | None,
    html_dir: Path,
) -> list[dict[str, Any]]:
    """Pack story cards against real browser layout, then make room for the last-page extras."""
    sections = report.get("sections", [])
    if not sections:
        return label_auto_pages([{"section_indices": []}])

    group_avatar = assets.import_asset(group_avatar_raw or report.get("group_avatar"), "group-avatar")
    brand = report.get("brand", {}) if isinstance(report.get("brand", {}), dict) else {}
    brand_logo = assets.import_asset(str(brand.get("logo", DEFAULT_BRAND_LOGO)), "caliph-brand")
    pages: list[dict[str, Any]] = []
    current: list[int] = []

    for index in range(len(sections)):
        candidate = current + [index]
        page_number = len(pages)
        max_stories = MAX_STORIES_ON_FIRST_PAGE if page_number == 0 else MAX_STORIES_ON_CONTINUATION_PAGE
        candidate_page = {"section_indices": candidate, "label": f"第 {page_number + 1} 版", "show_extras": False}
        if len(candidate) <= max_stories and page_fits(
            chrome, report, assets, avatars, group_avatar, brand_logo, candidate_page,
            page_number, page_number + 1, html_dir,
        ):
            current = candidate
            continue

        if not current:
            raise RuntimeError(f"A3 layout overflow detected: story {index + 1} cannot fit on its own page.")
        pages.append({"section_indices": current, "show_extras": False})
        current = [index]
        standalone = {"section_indices": current, "label": f"第 {len(pages) + 1} 版", "show_extras": False}
        if not page_fits(
            chrome, report, assets, avatars, group_avatar, brand_logo, standalone,
            len(pages), len(pages) + 1, html_dir,
        ):
            raise RuntimeError(f"A3 layout overflow detected: story {index + 1} cannot fit on its own page.")

    if current:
        pages.append({"section_indices": current, "show_extras": False})

    while True:
        for page_number, page in enumerate(pages, start=1):
            page["label"] = f"第 {page_number} 版"
            page["show_extras"] = False
        last_page = pages[-1]
        last_page["show_extras"] = True
        if page_fits(
            chrome, report, assets, avatars, group_avatar, brand_logo, last_page,
            len(pages) - 1, len(pages), html_dir,
        ):
            return pages

        indices = list(last_page.get("section_indices", []))
        last_page["show_extras"] = False
        if not indices:
            raise RuntimeError("A3 layout overflow detected: people, stats, and closing do not fit on a standalone page.")
        if len(indices) == 1:
            # Keep the story on its own page and let the back matter use a final page.
            pages.append({"section_indices": [], "show_extras": False})
            continue
        carried = indices[-1:]
        last_page["section_indices"] = indices[:-1]
        pages.append({"section_indices": carried, "show_extras": False})


def valid_pdf(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 5 and path.read_bytes()[:5] == b"%PDF-"


def valid_png(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 24 and path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def run_chrome_export(
    chrome: str,
    target: Path,
    label: str,
    artifact_valid: Callable[[Path], bool],
    build_command: Callable[[Path, Path], list[str]],
) -> None:
    """Export atomically and stop Chrome once the requested artifact is complete."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=target.parent, prefix=f".{target.stem}-", suffix=target.suffix, delete=False
    ) as handle:
        staging = Path(handle.name)
    staging.unlink(missing_ok=True)
    proc: subprocess.Popen[Any] | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="caliph-editorial-chrome-") as profile:
            proc = subprocess.Popen(
                build_command(staging, Path(profile)),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            deadline = time.monotonic() + EXPORT_TIMEOUT_SECONDS
            while True:
                if artifact_valid(staging):
                    size = staging.stat().st_size
                    time.sleep(EXPORT_ARTIFACT_SETTLE_SECONDS)
                    if artifact_valid(staging) and staging.stat().st_size == size:
                        break
                return_code = proc.poll()
                if return_code is not None:
                    raise RuntimeError(f"Chrome {label} export exited with code {return_code} before creating a complete artifact.")
                if time.monotonic() >= deadline:
                    raise RuntimeError(f"Chrome {label} export timed out after {EXPORT_TIMEOUT_SECONDS}s before producing a complete artifact.")
                time.sleep(0.05)
            terminate_process_group(proc)
        os.replace(staging, target)
        os.chmod(target, 0o600)
    finally:
        if proc is not None:
            terminate_process_group(proc)
        staging.unlink(missing_ok=True)


def chrome_export_flags(profile: Path) -> list[str]:
    return [
        "--headless=new", "--disable-gpu", "--allow-file-access-from-files",
        "--disable-background-networking", "--disable-component-update", "--disable-sync",
        "--no-default-browser-check", "--no-first-run", f"--user-data-dir={profile}",
    ]


def print_pdf(chrome: str, html_path: Path, pdf_path: Path) -> None:
    run_chrome_export(
        chrome,
        pdf_path,
        "PDF",
        valid_pdf,
        lambda staging, profile: [
            chrome, *chrome_export_flags(profile), "--no-pdf-header-footer",
            f"--print-to-pdf={staging}", html_path.resolve().as_uri(),
        ],
    )


def print_pngs(
    chrome: str,
    report: dict[str, Any],
    fragments: list[str],
    page_dir: Path,
    output_dir: Path,
    base_name: str,
) -> list[Path]:
    outputs: list[Path] = []
    for index, fragment in enumerate(fragments, start=1):
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=page_dir,
            prefix=f".caliph-editorial-page-{index:02d}-", suffix=".html", delete=False,
        ) as handle:
            handle.write(document_html(report, [fragment], png_mode=True))
            page_html = Path(handle.name)
        target = output_dir / f"{base_name}_p{index:02d}.png"
        try:
            run_chrome_export(
                chrome,
                target,
                f"PNG page {index}",
                valid_png,
                lambda staging, profile: [
                    chrome, *chrome_export_flags(profile), "--hide-scrollbars",
                    f"--window-size={PAGE_WIDTH},{PAGE_HEIGHT}", "--force-device-scale-factor=2",
                    f"--screenshot={staging}", page_html.resolve().as_uri(),
                ],
            )
        finally:
            page_html.unlink(missing_ok=True)
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
        layout = report.get("layout", {}) if isinstance(report.get("layout", {}), dict) else {}
        if layout.get("page_mode") == "auto" and chrome and not args.skip_preflight:
            pages = measured_auto_pages(
                chrome,
                report,
                assets,
                avatars,
                str(args.group_avatar.resolve()) if args.group_avatar else None,
                html_path.parent,
            )
        else:
            pages = resolve_pages(report)
        fragments = build_page_fragments(
            report,
            assets,
            avatars,
            str(args.group_avatar.resolve()) if args.group_avatar else None,
            pages=pages,
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
            outputs.extend(print_pngs(chrome or "", report, fragments, html_path.parent, group_dir, name))

        for output in outputs:
            print(f"[OK] wrote {output}")
        return 0
    finally:
        if work_context is not None:
            work_context.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
