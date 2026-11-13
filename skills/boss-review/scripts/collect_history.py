#!/usr/bin/env python3
"""Export recent local conversation turns without querying an external service."""
from __future__ import annotations

import argparse
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile

CONTEXT_PREFIXES = (
    "<environment_context>", "<user_instructions>", "<permissions instructions>",
    "<external_codex_apps_open_page>", "# AGENTS.md instructions for ",
)


def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else None


def message_text(content):
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "\n".join(
        part["text"] for part in content
        if isinstance(part, dict) and part.get("type") in ("text", "input_text", "output_text")
        and isinstance(part.get("text"), str)
    )


def merge_events(messages, events):
    # Codex can record the same turn in both representations. Pair nearby
    # matches one-to-one, retaining repeated text from distinct turns.
    candidates = defaultdict(deque)
    for turn in sorted(messages, key=lambda item: item["timestamp"]):
        candidates[(turn["role"], turn["text"])].append(timestamp(turn["timestamp"]))
    tolerance = timedelta(seconds=3)
    for turn in sorted(events, key=lambda item: item["timestamp"]):
        when = timestamp(turn["timestamp"])
        times = candidates[(turn["role"], turn["text"])]
        while times and times[0] < when - tolerance:
            times.popleft()
        if times and times[0] <= when + tolerance:
            times.popleft()
        else:
            messages.append(turn)
    return sorted(messages, key=lambda item: item["timestamp"])


def read_session(path, provider, start, end):
    session_id = path.stem
    messages = []
    events = []
    ignored = 0
    with path.open(encoding="utf-8", errors="replace") as stream:
        has_session_id = False
        for line in stream:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError:
                ignored += 1
                continue
            if not isinstance(row, dict):
                continue
            if provider == "codex" and row.get("type") == "session_meta" and not has_session_id:
                meta = row.get("payload")
                if isinstance(meta, dict) and isinstance(meta.get("id"), str):
                    session_id = meta["id"]
                    has_session_id = True
            when = timestamp(row.get("timestamp"))
            if when is None or not start <= when <= end:
                continue
            kind = row.get("type")
            if provider == "codex":
                payload = row.get("payload")
                if not isinstance(payload, dict):
                    continue
                if kind == "event_msg" and payload.get("type") in ("user_message", "agent_message"):
                    role = "user" if payload["type"] == "user_message" else "assistant"
                    content = payload.get("message")
                    target = events
                elif kind == "response_item" and payload.get("type") == "message":
                    role, content = payload.get("role"), payload.get("content")
                    target = messages
                else:
                    continue
            else:
                if kind not in ("user", "assistant") or row.get("isSidechain") or row.get("isMeta"):
                    continue
                message = row.get("message")
                if not isinstance(message, dict) or message.get("role") != kind:
                    continue
                role, content = kind, message.get("content")
                target = messages
                if isinstance(row.get("sessionId"), str):
                    session_id = row["sessionId"]
            if role not in ("user", "assistant"):
                continue
            value = message_text(content).strip()
            if not value or (role == "user" and value.startswith(CONTEXT_PREFIXES)):
                continue
            target.append({"timestamp": when.isoformat(), "role": role, "text": value})
    if events:
        messages = merge_events(messages, events)
    first_user = next((i for i, turn in enumerate(messages) if turn["role"] == "user"), len(messages))
    return session_id, messages[first_user:], ignored


def default_sources(provider):
    if provider == "codex":
        root = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser()
        return [root / "sessions", root / "archived_sessions"]
    root = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude").expanduser()
    return [root / "projects"]


def log_paths(sources):
    visited = set()
    for source in sources:
        paths = [source] if source.is_file() else sorted(source.rglob("*.jsonl"))
        for path in paths:
            if path.is_symlink() or path.suffix != ".jsonl" or not path.is_file():
                continue
            key = path.resolve()
            if key not in visited:
                visited.add(key)
                yield path


def export(provider, sources, output, start, end):
    output.parent.mkdir(parents=True, exist_ok=True)
    session_ids = set()
    files = bad_files = bad_rows = user_turns = 0
    staged = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent,
                                         prefix=".boss-review-", delete=False) as stream:
            staged = Path(stream.name)
            for path in log_paths(sources):
                files += 1
                try:
                    session_id, messages, ignored = read_session(path, provider, start, end)
                except OSError:
                    bad_files += 1
                    continue
                bad_rows += ignored
                if not messages or session_id in session_ids:
                    continue
                session_ids.add(session_id)
                user_turns += sum(turn["role"] == "user" for turn in messages)
                row = {"session": len(session_ids), "messages": messages}
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        staged.replace(output)
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)
    return {
        "provider": provider, "start": start.isoformat(), "end": end.isoformat(),
        "sessions": len(session_ids), "user_messages": user_turns,
        "files_checked": files, "files_unreadable": bad_files, "invalid_lines": bad_rows,
    }


def required_timestamp(value):
    parsed = timestamp(value)
    if parsed is None:
        raise argparse.ArgumentTypeError("必须包含时区")
    return parsed


def main():
    parser = argparse.ArgumentParser(description="按消息时间收集指定平台近 30 天的本地对话")
    parser.add_argument("--provider", choices=("codex", "claude"), required=True)
    parser.add_argument("--source", type=Path, action="append", help="覆盖默认目录，可指定多次")
    parser.add_argument("--output", type=Path, required=True, help="临时 JSONL 路径")
    parser.add_argument("--now", type=required_timestamp, help="测试用的带时区 ISO 8601 时间")
    args = parser.parse_args()
    sources = [path.expanduser() for path in args.source] if args.source else default_sources(args.provider)
    if args.source and any(not path.exists() for path in sources):
        parser.error("--source 指定的文件或目录不存在")
    output = args.output.expanduser()
    if any(output.resolve() == source.resolve() or
           (source.is_dir() and output.resolve().is_relative_to(source.resolve())) for source in sources):
        parser.error("--output 必须位于记录目录之外")
    end = args.now or datetime.now(timezone.utc)
    summary = export(args.provider, sources, output, end - timedelta(days=30), end)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
