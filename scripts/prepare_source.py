#!/usr/bin/env python3
"""Normalize an existing yichen digest-source JSON for editorial work.

The input is a local yichen source package. The output deliberately drops
internal database/table identifiers and sender usernames before the content
is handed to the editorial stage. A synthetic anchor is added so later audit
passes can refer back to a message without exposing WeChat internal IDs.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="yichen digest-source JSON")
    parser.add_argument("--output", required=True, type=Path, help="normalized JSON path")
    parser.add_argument("--start", help="optional inclusive YYYY-MM-DD or ISO datetime")
    parser.add_argument("--end", help="optional exclusive YYYY-MM-DD or ISO datetime")
    return parser.parse_args()


def as_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    if len(value) == 10:
        value += " 00:00:00"
    return datetime.fromisoformat(value.replace("T", " "))


def message_dt(message: dict[str, Any]) -> datetime | None:
    try:
        return as_dt(str(message.get("time", "")))
    except ValueError:
        return None


def main() -> int:
    args = parse_args()
    source = json.loads(args.source.read_text(encoding="utf-8"))
    start = as_dt(args.start)
    end = as_dt(args.end)

    selected: list[dict[str, Any]] = []
    for raw in source.get("messages", []):
        current = message_dt(raw)
        if current is None:
            continue
        if start and current < start:
            continue
        if end and current >= end:
            continue
        # Keep only editorially useful fields. In particular, do not carry
        # sender_username, database names, table names, wxid, or raw IDs.
        selected.append({
            "anchor": f"M{len(selected) + 1:06d}",
            "time": str(raw.get("time", "")),
            "sender": str(raw.get("sender", "未知")),
            "type": str(raw.get("type", "未知")),
            "content": str(raw.get("content", "")),
        })

    sender_counts = Counter(item["sender"] for item in selected)
    type_counts = Counter(item["type"] for item in selected)
    day_counts = Counter(item["time"][:10] for item in selected)
    hour_counts = Counter(item["time"][11:13] for item in selected)

    period = source.get("range", {})
    result = {
        "schema_version": "caliph-editorial-source-2",
        "group_name": source.get("group", {}).get("name", ""),
        "period": {
            "start": args.start or period.get("start", ""),
            "end": args.end or period.get("end", ""),
        },
        "stats": {
            "message_count": len(selected),
            "sender_count": len(sender_counts),
            "sender_counts": [
                {"name": name, "count": count}
                for name, count in sender_counts.most_common()
            ],
            "type_counts": dict(type_counts.most_common()),
            "day_counts": dict(sorted(day_counts.items())),
            "hour_counts": dict(sorted(hour_counts.items())),
        },
        "messages": selected,
        "notes": [
            "本素材由已解密的 yichen vault 生成。",
            "anchor 为本次规范化过程生成的安全定位符，不是微信内部 ID。",
            "图片、视频和文件若只有占位符，不得在成稿中补写不可见内容。",
        ],
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.chmod(args.output, 0o600)
    print(f"[OK] normalized {len(selected)} messages -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
