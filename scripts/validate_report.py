#!/usr/bin/env python3
"""Validate a Caliph editorial report before rendering or publication."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

ALLOWED_KINDS = {"daily", "weekly"}
ALLOWED_STYLES = {"normal", "roast"}
ALLOWED_TONES = {"ink", "red", "blue", "accent"}
ALLOWED_EVIDENCE = {
    "direct_quote",
    "group_observation",
    "linked_claim",
    "externally_verified",
    "editorial_inference",
}
STYLE_PATTERNS = [
    ("不是……而是……", re.compile(r"不是.{0,80}而是", re.S)),
    ("并非……而是……", re.compile(r"并非.{0,80}而是", re.S)),
]
AI_TICS = [
    "真正值得关注的是",
    "某种意义上",
    "归根结底",
    "值得注意的是",
    "这背后反映了",
]
ROAST_REDFLAGS = [
    ("medical or psychological diagnosis", re.compile(r"ADHD|精神病|人格障碍|心理医生|需要看医生", re.I)),
]


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("report", type=Path, help="report.json")
    p.add_argument("--source", type=Path, help="source-normalized.json for quote verification")
    p.add_argument("--warnings-as-errors", action="store_true")
    return p


def strings_for_style(report: dict[str, Any]) -> Iterable[tuple[str, str]]:
    masthead = report.get("masthead", {})
    lead = report.get("lead", {})
    closing = report.get("closing", {})
    for key in ("title", "subtitle"):
        if masthead.get(key):
            yield f"masthead.{key}", str(masthead[key])
    for key in ("kicker", "title", "dek", "body"):
        if lead.get(key):
            yield f"lead.{key}", str(lead[key])
    for i, section in enumerate(report.get("sections", [])):
        for key in ("eyebrow", "title", "body"):
            if section.get(key):
                yield f"sections[{i}].{key}", str(section[key])
        for j, quote in enumerate(section.get("quotes", [])):
            if isinstance(quote, dict) and quote.get("comment"):
                yield f"sections[{i}].quotes[{j}].comment", str(quote["comment"])
    for i, person in enumerate(report.get("people", [])):
        for key in ("role", "note", "roast_note"):
            if person.get(key):
                yield f"people[{i}].{key}", str(person[key])
    for key in ("title", "body"):
        if closing.get(key):
            yield f"closing.{key}", str(closing[key])


def require_text(obj: dict[str, Any], key: str, path: str, errors: list[str]) -> None:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{path}.{key}: required non-empty string")


def verify_quote(
    quote: dict[str, Any], messages: list[dict[str, Any]], path: str, errors: list[str]
) -> None:
    text = str(quote.get("text", "")).strip()
    speaker = str(quote.get("speaker", "")).strip()
    time = str(quote.get("time", "")).strip()
    if not text or not speaker:
        errors.append(f"{path}: quote requires text + speaker")
        return

    candidates = [m for m in messages if str(m.get("sender", "")) == speaker]
    if time:
        candidates = [
            m for m in candidates if time in str(m.get("time", ""))
        ] or candidates
    if not any(text in str(m.get("content", "")) for m in candidates):
        errors.append(f"{path}: quote not found verbatim for speaker {speaker!r}: {text!r}")


def validate(report: dict[str, Any], source: dict[str, Any] | None = None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    kind = report.get("kind")
    if kind not in ALLOWED_KINDS:
        errors.append(f"kind: expected one of {sorted(ALLOWED_KINDS)}, got {kind!r}")
    style = report.get("style", "normal")
    if style not in ALLOWED_STYLES:
        errors.append(f"style: expected one of {sorted(ALLOWED_STYLES)}, got {style!r}")

    require_text(report, "group_name", "report", errors)
    period = report.get("period")
    if not isinstance(period, dict):
        errors.append("period: required object")
    else:
        require_text(period, "start", "period", errors)
        require_text(period, "end", "period", errors)

    lead = report.get("lead")
    if not isinstance(lead, dict):
        errors.append("lead: required object")
    else:
        for key in ("title", "dek", "body"):
            require_text(lead, key, "lead", errors)
        if len(str(lead.get("body", ""))) > 420:
            warnings.append("lead.body: unusually long (>420 chars); likely to hurt first-page pacing")

    sections = report.get("sections")
    if not isinstance(sections, list) or not sections:
        errors.append("sections: required non-empty array")
        sections = []
    recommended = (3, 6) if kind == "daily" else (4, 7)
    if sections and not (recommended[0] <= len(sections) <= recommended[1]):
        warnings.append(
            f"sections: {len(sections)} items; recommended {recommended[0]}-{recommended[1]} for {kind}"
        )

    messages = list((source or {}).get("messages", []))
    for i, section in enumerate(sections):
        path = f"sections[{i}]"
        if not isinstance(section, dict):
            errors.append(f"{path}: expected object")
            continue
        for key in ("eyebrow", "title", "body"):
            require_text(section, key, path, errors)
        tone = section.get("tone", "ink")
        if tone not in ALLOWED_TONES:
            errors.append(f"{path}.tone: invalid value {tone!r}")
        evidence = section.get("evidence", "group_observation")
        if evidence not in ALLOWED_EVIDENCE:
            errors.append(f"{path}.evidence: invalid value {evidence!r}")
        priority = section.get("priority", "major")
        if priority not in {"major", "minor"}:
            errors.append(f"{path}.priority: expected major/minor")
        body_len = len(str(section.get("body", "")))
        if body_len > 520:
            warnings.append(f"{path}.body: unusually long ({body_len} chars)")
        quotes = section.get("quotes", [])
        if not isinstance(quotes, list):
            errors.append(f"{path}.quotes: expected array")
        else:
            for j, quote in enumerate(quotes):
                if not isinstance(quote, dict):
                    errors.append(f"{path}.quotes[{j}]: expected object")
                else:
                    if source is not None:
                        verify_quote(quote, messages, f"{path}.quotes[{j}]", errors)
                    if "comment" in quote:
                        if not isinstance(quote["comment"], str):
                            errors.append(f"{path}.quotes[{j}].comment: expected string")
                        elif len(quote["comment"]) > 90:
                            warnings.append(f"{path}.quotes[{j}].comment: unusually long (>90 chars)")

    people = report.get("people", [])
    if not isinstance(people, list):
        errors.append("people: expected array")
    elif len(people) > 8:
        warnings.append(f"people: {len(people)} cards; consider <=8 for editorial focus")
    else:
        for i, person in enumerate(people):
            if not isinstance(person, dict):
                errors.append(f"people[{i}]: expected object")
            elif "roast_note" in person and not isinstance(person["roast_note"], str):
                errors.append(f"people[{i}].roast_note: expected string")

    stats = report.get("stats", [])
    if not isinstance(stats, list):
        errors.append("stats: expected array")
    elif len(stats) > 6:
        errors.append("stats: maximum 6 items")

    pages = report.get("pages", [])
    if pages:
        seen: set[int] = set()
        for p, page in enumerate(pages):
            if not isinstance(page, dict):
                errors.append(f"pages[{p}]: expected object")
                continue
            for index in page.get("section_indices", []):
                if not isinstance(index, int) or not 0 <= index < len(sections):
                    errors.append(f"pages[{p}]: invalid section index {index!r}")
                elif index in seen:
                    errors.append(f"pages[{p}]: duplicated section index {index}")
                else:
                    seen.add(index)

    style_strings = list(strings_for_style(report))
    for path, text in style_strings:
        for label, pattern in STYLE_PATTERNS:
            if pattern.search(text):
                errors.append(f"{path}: avoid template contrast pattern {label}")
        for tic in AI_TICS:
            if tic in text:
                warnings.append(f"{path}: generic editorial tic detected: {tic}")
    if style == "roast":
        for path, text in style_strings:
            for label, pattern in ROAST_REDFLAGS:
                if pattern.search(text):
                    errors.append(f"{path}: roast copy must not include {label}")

    if source is not None:
        src_period = source.get("period", {})
        rep_period = report.get("period", {})
        for key in ("start", "end"):
            if src_period.get(key) and rep_period.get(key) and str(src_period[key]) != str(rep_period[key]):
                warnings.append(
                    f"period.{key}: report={rep_period[key]!r} differs from source={src_period[key]!r}"
                )

    return errors, warnings


def main() -> int:
    args = parser().parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    source = json.loads(args.source.read_text(encoding="utf-8")) if args.source else None
    errors, warnings = validate(report, source)
    for item in warnings:
        print(f"[WARN] {item}", file=sys.stderr)
    for item in errors:
        print(f"[ERROR] {item}", file=sys.stderr)
    if errors or (warnings and args.warnings_as_errors):
        return 1
    print(f"[OK] report valid: errors=0 warnings={len(warnings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
