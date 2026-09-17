# Caliph WeChat Editorial

An independent personal Codex Skill for turning already decrypted local WeChat material into modern editorial daily reports, weekly reports, high-resolution PNG pages, and printable A3 PDFs.

It supports two presentation modes:

- **normal** — restrained, modern, evidence-aware editorial writing;
- **roast** — the same audited factual skeleton rewritten with sharper headlines and playful commentary, without personal attacks.

This repository is intentionally independent from `mcncarl/yichen-skills`. It may consume a source package produced by `yichen-wechat-local-vault`, but it does not capture keys, decrypt databases, refresh WeChat, control the WeChat UI, or upload chat content.

## Install

```bash
npx skills add 42zhangjing/caliph-wechat-editorial
```

Or copy this repository into a local Skills directory supported by Codex or Claude Code.

## Default behavior

A plain request for a daily or weekly report defaults to:

- normal style;
- group avatar + selected people avatars;
- automatic pagination;
- PNG + PDF output;
- `/Users/chengyu/Downloads/微信群报/<group>/` as the output folder.

HTML is optional and can be requested explicitly.

## Editorial v2 pipeline

```text
source
→ normalize
→ story map
→ write
→ attribution audit
→ style lint
→ layout preflight
→ PNG / PDF / HTML
```

Key guarantees:

- normalized messages receive safe synthetic anchors instead of exposing internal WeChat IDs;
- `validate_report.py` checks structure, exact quotes, page indexes, and editorial style rules;
- generated editorial copy avoids the templated Chinese contrast patterns `不是……而是……` and `并非……而是……` by default; verbatim chat quotes remain untouched;
- roast mode keeps the audited skeleton while adding per-quote editorial comments and “no-mercy” roster notes only for public, period-specific behavior;
- the renderer packs the real two-column story grid, lets a final orphan card span both columns, and keeps the page footer at the bottom rather than creating accidental half-empty pages;
- a missing Lead image triggers a text-only layout rather than an empty image column;
- local images are copied into report-specific asset folders and HTML uses relative URLs;
- Chrome-based A3 preflight uses DOM/layout readiness rather than `window.load`, substitutes remote images only in its measuring copy, detects real overflow, and terminates on a bounded timeout.

## Output naming

Examples:

```text
吃瓜备用_日报_2026-09-17_普通版.pdf
吃瓜备用_日报_2026-09-17_普通版_p01.png
吃瓜备用_周报_2026-09-11--2026-09-17_毒舌版.pdf
```

## Preferences

See `EXTEND.md.example` for the user-level defaults supported by the Skill.

## Privacy boundary

- Generated source packages, reports, avatars, and output files stay in private local folders.
- Internal usernames, database identifiers, keys, and raw databases are not copied into report output.
- `head_image.db` is read-only when group/member avatars are exported.
- Ambiguous duplicate display names are never guessed when resolving avatars; the renderer falls back to an initial placeholder.
- The repository contains no chat exports or private avatars.

## Layout

- `SKILL.md` — routing, defaults, editorial policy, and operational boundaries
- `EXTEND.md.example` — user preference template
- `scripts/prepare_source.py` — strips internal fields and adds safe anchors
- `scripts/validate_report.py` — report, quote, and style validation
- `scripts/extract_avatars.py` — local avatar export with ambiguity protection
- `scripts/render_editorial.py` — modern layout, automatic pagination, HTML/PNG/PDF export and preflight
- `references/` — report schema and editorial workflow
- `tests/` — validator and renderer regression tests
- `agents/openai.yaml` / `assets/` — Codex UI metadata and icon
