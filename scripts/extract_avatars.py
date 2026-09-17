#!/usr/bin/env python3
"""Export a local group avatar and selected member avatars without exposing usernames."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from collections import defaultdict
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="raw yichen digest-source JSON")
    parser.add_argument("--db", required=True, type=Path, help="decrypted head_image.db")
    parser.add_argument("--names", required=True, help="comma-separated display names")
    parser.add_argument("--output", required=True, type=Path, help="private avatar directory")
    parser.add_argument(
        "--without-group-avatar",
        action="store_true",
        help="skip exporting the group avatar",
    )
    args = parser.parse_args()

    raw = json.loads(args.source.read_text(encoding="utf-8"))
    wanted = list(dict.fromkeys(name.strip() for name in args.names.split(",") if name.strip()))

    usernames_by_name: dict[str, set[str]] = defaultdict(set)
    for message in raw.get("messages", []):
        name = str(message.get("sender", ""))
        username = str(message.get("sender_username", ""))
        if name in wanted and username:
            usernames_by_name[name].add(username)

    args.output.mkdir(parents=True, exist_ok=True)
    os.chmod(args.output, 0o700)
    manifest: dict[str, str] = {}
    ambiguous: list[str] = []
    missing: list[str] = []

    connection = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    group_avatar = False
    try:
        group_username = str(raw.get("group", {}).get("username", ""))
        if group_username and not args.without_group_avatar:
            row = connection.execute(
                "select image_buffer from head_image where username = ?",
                (group_username,),
            ).fetchone()
            if row and row[0]:
                group_path = args.output / "group-avatar.jpg"
                group_path.write_bytes(bytes(row[0]))
                os.chmod(group_path, 0o600)
                group_avatar = True

        exported_index = 0
        for name in wanted:
            usernames = usernames_by_name.get(name, set())
            if len(usernames) > 1:
                ambiguous.append(name)
                continue
            if not usernames:
                missing.append(name)
                continue
            username = next(iter(usernames))
            row = connection.execute(
                "select image_buffer from head_image where username = ?",
                (username,),
            ).fetchone()
            if not row or not row[0]:
                missing.append(name)
                continue
            exported_index += 1
            path = args.output / f"avatar-{exported_index:03d}.jpg"
            path.write_bytes(bytes(row[0]))
            os.chmod(path, 0o600)
            manifest[name] = str(path.resolve())
    finally:
        connection.close()

    manifest_path = args.output / "avatars.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(manifest_path, 0o600)

    print(
        f"[OK] exported group_avatar={'yes' if group_avatar else 'no'}, "
        f"members={len(manifest)}/{len(wanted)} -> {args.output}"
    )
    if ambiguous:
        print("[WARN] ambiguous display names skipped (use initial placeholders): " + ", ".join(ambiguous))
    if missing:
        print("[WARN] avatar unavailable (use initial placeholders): " + ", ".join(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
