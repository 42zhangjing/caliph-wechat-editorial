# Caliph WeChat Editorial

An independent personal Codex Skill for turning already decrypted local WeChat material into editorial daily reports, weekly reports, and printable A3 group newspapers.

This repository is intentionally independent from `mcncarl/yichen-skills`. It may consume a local source package produced by `yichen-wechat-local-vault`, but it does not vendor that Skill, share its Git history, capture keys, decrypt databases, refresh WeChat, control the WeChat UI, or upload chat content.

## Install

Install the repository as a standalone Skill:

```bash
npx skills add 42zhangjing/caliph-wechat-editorial
```

Or copy this repository into a local Skills directory supported by Codex or Claude Code.

## Use

```text
$caliph-wechat-editorial
生成“吃瓜备用”今天的群聊日报，加入群头像和人物头像。
```

```text
$caliph-wechat-editorial
生成“吃瓜备用”最近完整 7 天的群聊周报，突出话题变化、转折、人物角色和未决问题。
```

The Skill uses existing local source material. If the report must include the newest messages, run the authorized incremental refresh through the separate local-vault workflow first, then ask this Skill to write the report.

## Privacy boundary

- Generated source packages, reports, avatars, HTML, and PDFs stay in a private local output directory.
- Internal usernames, database identifiers, keys, and raw databases are not copied into the report package.
- `head_image.db` is read-only when optional group/member avatars are exported.
- The repository contains only Skill code, documentation, and a generic UI icon; it contains no chat export or private avatar.

## Layout

- `SKILL.md` — routing, editorial policy, and operational boundaries
- `scripts/prepare_source.py` — strips internal fields from an existing source package
- `scripts/extract_avatars.py` — exports optional local group/member avatars
- `scripts/render_editorial.py` — renders HTML and optional A3 PDF
- `references/` — workflow and report schema
- `agents/openai.yaml` / `assets/` — Codex UI metadata and icon
