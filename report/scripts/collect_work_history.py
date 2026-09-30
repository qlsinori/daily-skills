#!/usr/bin/env python3
"""Collect a date-bounded, deduplicated digest of local Codex sessions."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


BLOCK_PATTERNS = (
    re.compile(r"<environment_context>.*?</environment_context>", re.DOTALL),
    re.compile(r"<recommended_plugins>.*?</recommended_plugins>", re.DOTALL),
    re.compile(r"<turn_aborted>.*?</turn_aborted>", re.DOTALL),
)


@dataclass
class Message:
    timestamp: datetime
    role: str
    phase: str
    text: str


@dataclass
class Session:
    session_id: str
    path: Path
    title: str = ""
    cwd: str = ""
    models: list[str] = field(default_factory=list)
    messages: list[Message] = field(default_factory=list)
    duplicates: list[str] = field(default_factory=list)

    @property
    def user_messages(self) -> list[Message]:
        return [message for message in self.messages if message.role == "user"]

    @property
    def final_messages(self) -> list[Message]:
        return [
            message
            for message in self.messages
            if message.role == "assistant" and message.phase == "final_answer"
        ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True, type=date.fromisoformat)
    parser.add_argument("--end", required=True, type=date.fromisoformat)
    parser.add_argument("--timezone", default="UTC")
    parser.add_argument(
        "--sessions-root", default=str(Path.home() / ".codex" / "sessions")
    )
    parser.add_argument(
        "--index", default=str(Path.home() / ".codex" / "session_index.jsonl")
    )
    parser.add_argument("--session-id", action="append", default=[])
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--detail", choices=("digest", "full"), default="digest")
    parser.add_argument("--output", help="Write output to this file instead of stdout")
    return parser.parse_args()


def parse_timestamp(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def clean_text(text: str) -> str:
    for pattern in BLOCK_PATTERNS:
        text = pattern.sub("", text)
    return text.strip()


def message_text(content: object) -> str:
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") not in {"input_text", "output_text", "text"}:
            continue
        value = item.get("text")
        if isinstance(value, str) and value.strip():
            parts.append(value)
    return clean_text("\n".join(parts))


def read_titles(index_path: Path) -> dict[str, str]:
    titles: dict[str, str] = {}
    if not index_path.is_file():
        return titles
    with index_path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            session_id = item.get("id")
            title = item.get("thread_name")
            if isinstance(session_id, str) and isinstance(title, str):
                titles[session_id] = title
    return titles


def infer_id(path: Path) -> str:
    match = re.search(
        r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
        path.name,
    )
    return match.group(1) if match else path.stem


def read_session(
    path: Path, titles: dict[str, str], start_at: datetime, end_at: datetime
) -> Session | None:
    session = Session(session_id=infer_id(path), path=path)
    try:
        handle = path.open(encoding="utf-8")
    except OSError:
        return None
    with handle:
        for line in handle:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            payload = item.get("payload")
            if item.get("type") == "session_meta" and isinstance(payload, dict):
                session.session_id = str(payload.get("id") or session.session_id)
                session.cwd = str(payload.get("cwd") or session.cwd)
                continue
            if item.get("type") == "turn_context" and isinstance(payload, dict):
                model = payload.get("model") or payload.get("model_provider")
                if isinstance(model, str) and model and model not in session.models:
                    session.models.append(model)
                continue
            if item.get("type") != "response_item" or not isinstance(payload, dict):
                continue
            if payload.get("type") != "message":
                continue
            role = payload.get("role")
            if role not in {"user", "assistant"}:
                continue
            timestamp = parse_timestamp(item.get("timestamp"))
            if timestamp is None:
                continue
            local_timestamp = timestamp.astimezone(start_at.tzinfo)
            if local_timestamp < start_at or local_timestamp > end_at:
                continue
            text_value = message_text(payload.get("content"))
            if not text_value:
                continue
            session.messages.append(
                Message(
                    timestamp=local_timestamp,
                    role=role,
                    phase=str(payload.get("phase") or ""),
                    text=text_value,
                )
            )
    if not session.messages:
        return None
    session.title = titles.get(session.session_id, session.session_id)
    return session


def normalize_for_fingerprint(text: str) -> str:
    return " ".join(text.split()).strip().lower()


def user_sequence(session: Session) -> list[str]:
    return [normalize_for_fingerprint(item.text) for item in session.user_messages]


def shared_prefix_length(left: list[str], right: list[str]) -> int:
    count = 0
    for left_item, right_item in zip(left, right):
        if left_item != right_item:
            break
        count += 1
    return count


def transcripts_overlap(left: Session, right: Session) -> bool:
    left_requests = user_sequence(left)
    right_requests = user_sequence(right)
    if left_requests == right_requests:
        return len(left_requests) >= 3 or sum(map(len, left_requests)) >= 500
    shortest = min(len(left_requests), len(right_requests))
    if shortest < 5:
        return False
    shared = shared_prefix_length(left_requests, right_requests)
    # Forked or resumed conversations contain a long copied prefix followed by a
    # small unique tail. Merge the copied history while preserving both tails.
    return shared >= 20 or shared / shortest >= 0.8


def merge_sessions(left: Session, right: Session) -> Session:
    canonical, secondary = sorted(
        (left, right), key=lambda item: len(item.messages), reverse=True
    )
    seen = {
        (item.role, item.phase, normalize_for_fingerprint(item.text))
        for item in canonical.messages
    }
    merged_messages = list(canonical.messages)
    for item in secondary.messages:
        key = (item.role, item.phase, normalize_for_fingerprint(item.text))
        if key in seen:
            continue
        seen.add(key)
        merged_messages.append(item)
    merged_messages.sort(key=lambda item: item.timestamp)
    merged_ids = [
        *canonical.duplicates,
        secondary.session_id,
        *secondary.duplicates,
    ]
    canonical.messages = merged_messages
    canonical.duplicates = list(dict.fromkeys(merged_ids))
    return canonical


def deduplicate(sessions: Iterable[Session]) -> tuple[list[Session], int]:
    kept: list[Session] = []
    removed = 0
    for session in sessions:
        for index, existing in enumerate(kept):
            if transcripts_overlap(existing, session):
                kept[index] = merge_sessions(existing, session)
                removed += 1
                break
        else:
            kept.append(session)
    kept.sort(key=lambda item: min(message.timestamp for message in item.messages))
    return kept, removed


def shorten(text: str, limit: int) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 1].rstrip() + "…"


def select_messages(messages: list[Message], detail: str, role: str) -> list[Message]:
    if detail == "full":
        return messages
    limit = 1600 if role == "user" else 4000
    return [
        Message(item.timestamp, item.role, item.phase, shorten(item.text, limit))
        for item in messages
    ]


def render_markdown(
    sessions: list[Session], removed: int, args: argparse.Namespace
) -> str:
    lines = [
        "# Codex work-history extract",
        "",
        f"- Date range: `{args.start.isoformat()}` through `{args.end.isoformat()}`",
        f"- Timezone: `{args.timezone}`",
        f"- Included unique sessions: `{len(sessions)}`",
        f"- Duplicate or overlapping transcript histories merged: `{removed}`",
        "",
    ]
    for session in sessions:
        lines.extend(
            [
                f"## {session.title}",
                "",
                f"- Session: `{session.session_id}`",
                f"- Working directory: `{session.cwd or 'unknown'}`",
            ]
        )
        if session.models:
            lines.append("- Models/providers observed: " + ", ".join(f"`{item}`" for item in session.models))
        if session.duplicates:
            lines.append(
                "- Overlapping transcript copies merged: "
                + ", ".join(f"`{item}`" for item in session.duplicates)
            )
        lines.extend(["", "### User requests or reported work", ""])
        for item in select_messages(session.user_messages, args.detail, "user"):
            lines.append(f"- `{item.timestamp.isoformat(timespec='seconds')}` {item.text}")
        lines.extend(["", "### Recorded final outcomes", ""])
        finals = select_messages(session.final_messages, args.detail, "assistant")
        if finals:
            for item in finals:
                lines.append(f"- `{item.timestamp.isoformat(timespec='seconds')}` {item.text}")
        else:
            lines.append("- No final outcome recorded in this date range.")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_json(
    sessions: list[Session], removed: int, args: argparse.Namespace
) -> str:
    def encode_message(item: Message) -> dict[str, str]:
        return {
            "timestamp": item.timestamp.isoformat(timespec="seconds"),
            "text": item.text,
        }

    payload = {
        "date_range": {"start": str(args.start), "end": str(args.end)},
        "timezone": args.timezone,
        "unique_session_count": len(sessions),
        "duplicate_session_count": removed,
        "sessions": [],
    }
    for session in sessions:
        users = select_messages(session.user_messages, args.detail, "user")
        finals = select_messages(session.final_messages, args.detail, "assistant")
        payload["sessions"].append(
            {
                "id": session.session_id,
                "title": session.title,
                "cwd": session.cwd,
                "duplicate_ids": session.duplicates,
                "user_requests_or_reports": [encode_message(item) for item in users],
                "recorded_final_outcomes": [encode_message(item) for item in finals],
            }
        )
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    args = parse_args()
    if args.end < args.start:
        print("error: --end must be on or after --start", file=sys.stderr)
        return 2
    try:
        local_zone = ZoneInfo(args.timezone)
    except ZoneInfoNotFoundError:
        print(f"error: unknown timezone: {args.timezone}", file=sys.stderr)
        return 2
    start_at = datetime.combine(args.start, time.min, local_zone)
    end_at = datetime.combine(args.end, time.max, local_zone)
    root = Path(args.sessions_root).expanduser()
    if not root.is_dir():
        print(f"error: sessions directory not found: {root}", file=sys.stderr)
        return 2
    titles = read_titles(Path(args.index).expanduser())
    filters = tuple(args.session_id)
    sessions: list[Session] = []
    for path in sorted(root.rglob("*.jsonl")):
        if filters and not any(value in path.name for value in filters):
            continue
        session = read_session(path, titles, start_at, end_at)
        if session is not None:
            sessions.append(session)
    sessions, removed = deduplicate(sessions)
    content = (
        render_markdown(sessions, removed, args)
        if args.format == "markdown"
        else render_json(sessions, removed, args)
    )
    if args.output:
        output = Path(args.output).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
    else:
        sys.stdout.write(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
