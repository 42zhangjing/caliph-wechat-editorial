#!/usr/bin/env python3
"""Render a Caliph editorial report JSON into local HTML and optional PDF."""

from __future__ import annotations

import argparse
import html
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


def esc(value: Any) -> str:
    return html.escape(str(value or ""))


def image_tag(image: str | None, alt: str = "") -> str:
    if not image:
        return ""
    path = image
    if path.startswith("/"):
        path = Path(path).resolve().as_uri()
    if not path.startswith("file://"):
        return ""
    return f'<img class="editorial-image" src="{esc(path)}" alt="{esc(alt)}">'


def quote_html(quotes: list[dict[str, Any]]) -> str:
    if not quotes:
        return ""
    parts = []
    for quote in quotes:
        cite = " · ".join(x for x in [quote.get("speaker"), quote.get("time")] if x)
        parts.append(
            '<blockquote class="quote">'
            f'<p>“{esc(quote.get("text"))}”</p>'
            f'<cite>{esc(cite)}</cite>'
            '</blockquote>'
        )
    return '<div class="quotes">' + "".join(parts) + "</div>"


def section_html(section: dict[str, Any], number: int) -> str:
    tone = section.get("tone", "ink")
    return f'''
    <article class="story story-{esc(tone)}">
      <div class="story-index">{number:02d}</div>
      <div class="story-main">
        <div class="eyebrow">{esc(section.get("eyebrow"))}</div>
        <h3>{esc(section.get("title"))}</h3>
        {image_tag(section.get("image"), section.get("image_alt", ""))}
        <p class="story-body">{esc(section.get("body"))}</p>
        {quote_html(section.get("quotes", []))}
      </div>
    </article>'''


def people_html(people: list[dict[str, Any]], avatars: dict[str, str] | None = None) -> str:
    if not people:
        return ""
    cards = []
    avatars = avatars or {}
    for person in people:
        count = f'<strong>{esc(person["count"])}</strong>' if person.get("count") is not None else ""
        avatar_path = person.get("avatar") or avatars.get(person.get("name", ""), "")
        avatar = image_tag(str(avatar_path), str(person.get("name", ""))) if avatar_path else ""
        avatar = avatar.replace('class="editorial-image"', 'class="person-avatar-image"') if avatar else ""
        avatar = avatar or f'<div class="person-avatar">{esc(person.get("name", "·"))[:1]}</div>'
        cards.append(
            '<div class="person">'
            f'{avatar}'
            '<div class="person-copy">'
            f'<div class="person-name">{esc(person.get("name"))}</div>'
            f'<div class="person-role">{esc(person.get("role"))} {count}</div>'
            f'<div class="person-note">{esc(person.get("note"))}</div>'
            '</div></div>'
        )
    return '<section class="people"><div class="section-label">本期角色</div><div class="people-grid">' + "".join(cards) + "</div></section>"


def stats_html(stats: list[dict[str, Any]]) -> str:
    if not stats:
        return ""
    items = []
    for stat in stats:
        items.append(
            f'<div class="stat"><div class="stat-value">{esc(stat.get("value"))}</div>'
            f'<div class="stat-label">{esc(stat.get("label"))}</div></div>'
        )
    return '<section class="stats">' + "".join(items) + "</section>"


def page_html(
    report: dict[str, Any],
    sections: list[dict[str, Any]],
    page_label: str = "",
    avatars: dict[str, str] | None = None,
    show_extras: bool = True,
    group_avatar: str | None = None,
) -> str:
    masthead = report.get("masthead", {})
    lead = report.get("lead", {})
    closing = report.get("closing", {})
    period = report.get("period", {})
    period_text = " — ".join(x for x in [period.get("start"), period.get("end")] if x)
    body = "".join(section_html(section, index + 1) for index, section in enumerate(sections))
    lead_image = image_tag(lead.get("image"), lead.get("image_alt", ""))
    group_avatar_path = group_avatar or report.get("group_avatar")
    group_avatar_html = image_tag(group_avatar_path, report.get("group_name", "")) if group_avatar_path else ""
    if group_avatar_html:
        group_avatar_html = group_avatar_html.replace(
            'class="editorial-image"', 'class="group-avatar-image"'
        )
    people = people_html(report.get("people", []), avatars) if show_extras else ""
    stats = stats_html(report.get("stats", [])) if show_extras else ""
    closing_html = ""
    if show_extras:
        closing_html = f'''
        <section class="closing">
          <div class="section-label">{esc(closing.get("title", "编辑手记"))}</div>
          <p>{esc(closing.get("body"))}</p>
        </section>'''
    return f'''
    <section class="page">
      <header class="masthead">
        <div class="masthead-brand">
          {group_avatar_html}
          <div>
            <div class="masthead-kicker">{esc(masthead.get("kicker", "CALIPH EDITORIAL"))}</div>
            <h1>{esc(masthead.get("title", report.get("group_name", "群聊编辑部")))}</h1>
            <div class="masthead-subtitle">{esc(masthead.get("subtitle", "当日现场记录"))}</div>
          </div>
        </div>
        <div class="issue"><div>{esc(report.get("edition", ""))}</div><div>{esc(period_text)}</div><div>{esc(page_label)}</div></div>
      </header>
      <div class="rule"></div>
      <main>
        <section class="lead">
          <div class="lead-copy">
            <div class="eyebrow">{esc(lead.get("kicker", "TODAY'S LEAD"))}</div>
            <h2>{esc(lead.get("title"))}</h2>
            <p class="lead-dek">{esc(lead.get("dek"))}</p>
            <p class="lead-body">{esc(lead.get("body"))}</p>
            <div class="tags">{"".join(f'<span>{esc(tag)}</span>' for tag in lead.get("tags", []))}</div>
          </div>
          {lead_image}
        </section>
        <section class="stories">{body}</section>
        {people}
        {stats}
        {closing_html}
      </main>
      <footer><span>CALIPH WECHAT EDITORIAL</span><span>{esc(report.get("footer", "本地素材编辑 · 未经外部发布"))}</span></footer>
    </section>'''


CSS = r'''
@page { size: A3 portrait; margin: 0; }
:root { --paper:#f7f3eb; --ink:#171717; --muted:#6e6a63; --red:#a83228; --blue:#243a53; --line:#c9c0b2; }
* { box-sizing: border-box; }
html, body { margin:0; padding:0; background:#d9d4cb; color:var(--ink); }
body { font-family:"Songti SC","Noto Serif SC","STSong",serif; }
.page { width:1123px; min-height:1587px; padding:54px 66px 40px; margin:24px auto; background:var(--paper); display:flex; flex-direction:column; page-break-after:always; overflow:hidden; }
.masthead { display:flex; justify-content:space-between; gap:40px; align-items:flex-start; }
.masthead-brand { display:flex; gap:18px; align-items:flex-start; }
.masthead-kicker,.eyebrow,.section-label { color:var(--red); font-family:"Helvetica Neue","PingFang SC",sans-serif; font-size:13px; letter-spacing:3px; font-weight:700; text-transform:uppercase; }
.masthead h1 { margin:10px 0 4px; font-size:58px; line-height:1; letter-spacing:5px; font-weight:900; }
.masthead-subtitle { color:var(--muted); font-family:"Helvetica Neue","PingFang SC",sans-serif; font-size:15px; letter-spacing:4px; }
.issue { min-width:200px; text-align:right; color:var(--muted); font-family:"Helvetica Neue",sans-serif; font-size:13px; line-height:1.8; letter-spacing:1px; }
.group-avatar-image { width:76px; height:76px; margin-top:2px; border:2px solid var(--ink); object-fit:cover; display:block; filter:saturate(.82) contrast(1.03); }
.rule { height:5px; background:var(--ink); margin:24px 0 30px; }
.lead { display:grid; grid-template-columns:1fr 330px; gap:35px; padding-bottom:28px; border-bottom:1px solid var(--ink); }
.lead h2 { margin:13px 0 10px; font-size:42px; line-height:1.13; letter-spacing:1px; }
.lead-dek { margin:0 0 16px; color:var(--blue); font-size:20px; line-height:1.45; font-weight:700; }
.lead-body { margin:0; font-size:17px; line-height:1.8; text-align:justify; }
.tags { display:flex; flex-wrap:wrap; gap:8px; margin-top:18px; }
.tags span { border:1px solid var(--red); color:var(--red); padding:4px 10px; font-family:"Helvetica Neue",sans-serif; font-size:11px; letter-spacing:1px; }
.editorial-image { width:100%; max-height:330px; object-fit:cover; display:block; filter:saturate(.82) contrast(1.03); }
.lead > .editorial-image { align-self:stretch; height:330px; }
.stories { display:grid; grid-template-columns:1fr 1fr; gap:0 34px; margin-top:24px; }
.story { display:grid; grid-template-columns:50px 1fr; gap:12px; padding:16px 0 20px; border-top:1px solid var(--line); break-inside:avoid; }
.story:nth-child(-n+2) { border-top:0; }
.story-index { color:var(--red); font-family:"Helvetica Neue",sans-serif; font-size:30px; font-weight:800; line-height:1; }
.story h3 { margin:7px 0 10px; font-size:25px; line-height:1.25; }
.story-body { margin:0; font-size:15px; line-height:1.72; text-align:justify; }
.story .editorial-image { margin:10px 0 13px; max-height:210px; }
.quotes { margin-top:12px; border-left:3px solid var(--red); padding-left:13px; }
.quote { margin:0 0 9px; }
.quote p { margin:0; font-size:14px; line-height:1.45; }
.quote cite { color:var(--muted); font-family:"Helvetica Neue",sans-serif; font-size:10px; font-style:normal; letter-spacing:1px; }
.people { margin-top:auto; padding-top:18px; border-top:2px solid var(--ink); }
.people-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-top:12px; }
.person { display:flex; gap:9px; min-height:58px; }
.person-avatar { width:38px; height:38px; flex:none; background:var(--blue); color:#fff; display:grid; place-items:center; font-family:"Helvetica Neue",sans-serif; font-size:18px; }
.person-avatar-image { width:38px; height:38px; flex:none; object-fit:cover; display:block; }
.person-name { font-size:16px; font-weight:700; }
.person-role { margin-top:2px; color:var(--red); font-family:"Helvetica Neue",sans-serif; font-size:10px; letter-spacing:1px; }
.person-role strong { margin-left:4px; }
.person-note { margin-top:3px; color:var(--muted); font-size:12px; line-height:1.3; }
.stats { display:grid; grid-template-columns:repeat(6,1fr); gap:0; margin-top:18px; background:var(--blue); color:#fff; padding:15px 12px; }
.stat { text-align:center; border-right:1px solid rgba(255,255,255,.35); }
.stat:last-child { border-right:0; }
.stat-value { font-family:"Helvetica Neue",sans-serif; font-size:25px; font-weight:800; }
.stat-label { margin-top:4px; font-size:11px; letter-spacing:1px; }
.closing { margin-top:18px; padding:14px 18px; background:#e8e0d3; }
.closing p { margin:7px 0 0; font-size:15px; line-height:1.6; }
footer { display:flex; justify-content:space-between; margin-top:22px; padding-top:10px; border-top:1px solid var(--ink); color:var(--muted); font-family:"Helvetica Neue",sans-serif; font-size:10px; letter-spacing:1px; }
@media print { html,body { background:var(--paper); } .page { margin:0; } }
'''


def render(
    report: dict[str, Any],
    avatars: dict[str, str] | None = None,
    group_avatar: str | None = None,
) -> str:
    has_pages = bool(report.get("pages"))
    pages = report.get("pages")
    if not pages:
        pages = [{"label": "", "section_indices": list(range(len(report.get("sections", []))))}]
    sections = report.get("sections", [])
    rendered = []
    for page_number, page in enumerate(pages):
        indices = page.get("section_indices", [])
        selected = [sections[i] for i in indices if isinstance(i, int) and 0 <= i < len(sections)]
        if "show_extras" in page:
            show_extras = bool(page["show_extras"])
        elif "append_people" in page:
            show_extras = bool(page["append_people"])
        else:
            show_extras = not has_pages or page_number == len(pages) - 1
        rendered.append(
            page_html(
                report,
                selected,
                page.get("label", ""),
                avatars,
                show_extras,
                group_avatar,
            )
        )
    title = f'{esc(report.get("group_name", "群聊编辑部"))} · {esc(report.get("kind", "daily"))}'
    return f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>{CSS}</style></head><body>{"".join(rendered)}</body></html>'


def find_chrome() -> str | None:
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        shutil.which("google-chrome"),
        shutil.which("chromium"),
    ]
    return next((item for item in candidates if item and Path(item).exists()), None)


def print_pdf(html_path: Path, pdf_path: Path) -> None:
    chrome = find_chrome()
    if not chrome:
        raise RuntimeError("未找到 Chrome/Chromium，已生成 HTML；请安装浏览器后再生成 PDF。")
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="caliph-editorial-chrome-") as profile:
        subprocess.run([
            chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
            f"--user-data-dir={profile}", f"--print-to-pdf={pdf_path}",
            html_path.resolve().as_uri(),
        ], check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="report.json")
    parser.add_argument("--output", required=True, type=Path, help="HTML output")
    parser.add_argument("--pdf", type=Path, help="optional PDF output")
    parser.add_argument("--avatars", type=Path, help="optional name -> local avatar path JSON")
    parser.add_argument("--group-avatar", type=Path, help="optional local group avatar image")
    args = parser.parse_args()

    report = json.loads(args.report.read_text(encoding="utf-8"))
    avatars = json.loads(args.avatars.read_text(encoding="utf-8")) if args.avatars else {}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(report, avatars, str(args.group_avatar) if args.group_avatar else None), encoding="utf-8")
    os.chmod(args.output, 0o600)
    print(f"[OK] wrote {args.output}")
    if args.pdf:
        print_pdf(args.output, args.pdf)
        os.chmod(args.pdf, 0o600)
        print(f"[OK] wrote {args.pdf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
