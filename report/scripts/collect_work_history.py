#!/usr/bin/env python3
"""Collect a date-bounded, deduplicated digest of Codex and Cursor work."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
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
    source: str = "codex"
    source_path: str = ""
    source_labels: list[str] = field(default_factory=list)
    evidence_paths: list[str] = field(default_factory=list)

    @property
    def user_messages(self) -> list[Message]:
        return [message for message in self.messages if message.role == "user"]

    @property
    def final_messages(self) -> list[Message]:
        return [
            message
            for message in self.messages
            if message.role == "assistant"
            and message.phase in {"final_answer", "cursor_outcome"}
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
    parser.add_argument(
        "--include-cursor",
        action="store_true",
        help="Include matching local Cursor transcripts and remote Cursor roots.",
    )
    parser.add_argument(
        "--cursor-root",
        action="append",
        default=[],
        help="Local Cursor project root; may be repeated.",
    )
    parser.add_argument(
        "--remote-host",
        action="append",
        default=[],
        help="SSH host to inspect for Cursor transcripts; may be repeated.",
    )
    parser.add_argument(
        "--all-ssh-hosts",
        action="store_true",
        help="Inspect every concrete host listed in --ssh-config.",
    )
    parser.add_argument(
        "--ssh-config",
        default=str(Path.home() / ".ssh" / "config"),
        help="SSH config used by --all-ssh-hosts and remote collection.",
    )
    parser.add_argument(
        "--remote-cursor-root",
        action="append",
        default=["~/.cursor/projects", "~/.codex/sessions"],
        help="Remote root to inspect; may be repeated.",
    )
    parser.add_argument(
        "--semantic-keyword",
        action="append",
        default=[],
        help="Additional semantic-map keyword; may be repeated.",
    )
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
    session = Session(
        session_id=infer_id(path),
        path=path,
        source_labels=["Codex·本地"],
        evidence_paths=[str(path)],
    )
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


SEMANTIC_KEYWORDS = (
    "语义地图",
    "语义建图",
    "semantic map",
    "semantic_mapping",
    "semantic-mapping",
    "memory_module",
    "hydra_custom",
    "建图服务",
    "mapdb",
)
CURSOR_FILE_SUFFIXES = {".jsonl", ".md", ".txt"}
DATE_MARKER = re.compile(r"(?<!\d)(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})(?!\d)")
NATURAL_DATE_MARKER = re.compile(
    r"<timestamp>[^,]+,\s*([A-Z][a-z]{2})\s+(\d{1,2}),\s*(20\d{2})"
)
MONTHS = {name: index for index, name in enumerate(
    ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
    start=1,
)}


def semantic_keywords(args: argparse.Namespace) -> tuple[str, ...]:
    return tuple(dict.fromkeys((*SEMANTIC_KEYWORDS, *args.semantic_keyword)))


def default_cursor_roots() -> list[Path]:
    candidates = [Path.home() / ".cursor" / "projects"]
    return [path for path in candidates if path.is_dir()]


def marker_dates(text: str) -> list[date]:
    dates: list[date] = []
    for year, month, day in DATE_MARKER.findall(text):
        try:
            dates.append(date(int(year), int(month), int(day)))
        except ValueError:
            continue
    for month, day, year in NATURAL_DATE_MARKER.findall(text):
        try:
            dates.append(date(int(year), MONTHS[month], int(day)))
        except (KeyError, ValueError):
            continue
    return dates


def in_date_range(
    text: str, modified_at: datetime, start_at: datetime, end_at: datetime
) -> bool:
    if start_at <= modified_at <= end_at:
        return True
    return any(start_at.date() <= item <= end_at.date() for item in marker_dates(text))


def cursor_message_timestamp(
    text: str, fallback: datetime, start_at: datetime, end_at: datetime
) -> datetime:
    # Only the message's explicit timestamp dates the work. Dates mentioned in
    # prose may describe a dataset, release, or quoted historical work.
    marker = re.search(r"<timestamp>(.*?)</timestamp>", text, re.DOTALL)
    if marker:
        raw = marker.group(1).strip()
        try:
            parsed = datetime.strptime(raw.split(" (UTC")[0], "%A, %b %d, %Y, %I:%M %p")
            return parsed.replace(tzinfo=fallback.tzinfo)
        except ValueError:
            candidates = marker_dates(marker.group(0))
            if candidates:
                return datetime.combine(candidates[0], time.min, fallback.tzinfo)
    return fallback


def cursor_text_from_item(item: object) -> str:
    if not isinstance(item, dict):
        return ""
    message = item.get("message") if isinstance(item.get("message"), dict) else item
    if not isinstance(message, dict):
        return ""
    return message_text(message.get("content"))


def cursor_project_name(path: str) -> str:
    parts = Path(path).parts
    if "projects" in parts:
        index = parts.index("projects")
        if index + 1 < len(parts):
            return parts[index + 1]
    return Path(path).stem


def cursor_session_id(path: Path, source: str) -> str:
    parts = path.parts
    try:
        index = parts.index("agent-transcripts")
    except ValueError:
        return f"cursor:{source}:{infer_id(path)}"
    # Compaction segments belong to the root transcript. Subagent transcripts
    # keep their own id because they are separate work branches.
    if "subagents" in parts[index + 1 :]:
        identifier = infer_id(path)
    elif index + 1 < len(parts):
        identifier = parts[index + 1]
    else:
        identifier = infer_id(path)
    return f"cursor:{source}:{identifier}"


def read_cursor_file(
    path: Path,
    source: str,
    start_at: datetime,
    end_at: datetime,
    keywords: tuple[str, ...],
    content_override: str | None = None,
    modified_override: float | None = None,
) -> Session | None:
    try:
        content = content_override if content_override is not None else path.read_text(
            encoding="utf-8", errors="ignore"
        )
        modified_at = datetime.fromtimestamp(
            modified_override if modified_override is not None else path.stat().st_mtime,
            tz=start_at.tzinfo,
        )
    except OSError:
        return None
    if not in_date_range(content, modified_at, start_at, end_at):
        return None
    lowered = content.casefold()
    if not any(keyword.casefold() in lowered for keyword in keywords):
        return None

    messages: list[Message] = []
    if path.suffix.casefold() == ".jsonl":
        turn_timestamp = modified_at
        for line in content.splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            role = item.get("role") if isinstance(item, dict) else None
            if role not in {"user", "assistant"}:
                continue
            text_value = cursor_text_from_item(item)
            if not text_value:
                continue
            explicit = parse_timestamp(item.get("timestamp"))
            if explicit is not None:
                turn_timestamp = explicit.astimezone(start_at.tzinfo)
            if role == "user":
                turn_timestamp = cursor_message_timestamp(text_value, turn_timestamp, start_at, end_at)
            timestamp = turn_timestamp
            if not (start_at <= timestamp <= end_at):
                continue
            messages.append(
                Message(
                    timestamp=timestamp,
                    role=role,
                    phase="cursor_outcome" if role == "assistant" else "cursor_request",
                    text=text_value,
                )
            )
    else:
        messages.append(
            Message(
                timestamp=modified_at,
                role="assistant",
                phase="cursor_outcome",
                text=content,
            )
        )
    if not messages:
        return None

    # Preserve every turn. Tail-only selection hides earlier independent tasks.
    kept = messages
    session_id = cursor_session_id(Path(path), source)
    label = "Cursor·本地" if source == "local" else f"Cursor·{source}"
    return Session(
        session_id=session_id,
        path=Path(path),
        title=f"Cursor · {cursor_project_name(path)}",
        cwd=cursor_project_name(path),
        messages=kept,
        source="cursor",
        source_path=str(path),
        source_labels=[label],
        evidence_paths=[str(path)],
    )


def collect_local_cursor(
    roots: Iterable[Path], start_at: datetime, end_at: datetime, keywords: tuple[str, ...]
) -> list[Session]:
    sessions: list[Session] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.casefold() not in CURSOR_FILE_SUFFIXES:
                continue
            if "agent-transcripts" not in path.parts:
                continue
            session = read_cursor_file(path, "local", start_at, end_at, keywords)
            if session is not None:
                sessions.append(session)
    return sessions


REMOTE_CURSOR_SCRIPT = r'''import datetime, json, os, re, sys
payload = json.load(sys.stdin)
start = datetime.date.fromisoformat(payload["start"])
end = datetime.date.fromisoformat(payload["end"])
keywords = [item.casefold() for item in payload["keywords"]]
date_marker = re.compile(r"(?<!\d)(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})(?!\d)")
natural_marker = re.compile(r"<timestamp>[^,]+,\s*([A-Z][a-z]{2})\s+(\d{1,2}),\s*(20\d{2})")
months = {name: index for index, name in enumerate(("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), start=1)}
suffixes = {".jsonl", ".md", ".txt"}
def date_hits(text):
    for year, month, day in date_marker.findall(text):
        try:
            yield datetime.date(int(year), int(month), int(day))
        except ValueError:
            pass
    for month, day, year in natural_marker.findall(text):
        try:
            yield datetime.date(int(year), months[month], int(day))
        except (KeyError, ValueError):
            pass
for raw_root in payload["roots"]:
    root = os.path.expanduser(raw_root)
    if not os.path.isdir(root):
        continue
    for directory, _, names in os.walk(root):
        for name in names:
            path = os.path.join(directory, name)
            if os.path.splitext(name)[1].casefold() not in suffixes:
                continue
            if "agent-transcripts" not in path.split(os.sep):
                continue
            try:
                modified = datetime.datetime.fromtimestamp(os.stat(path).st_mtime).date()
                with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                    text = handle.read()
            except OSError:
                continue
            if not any(keyword in text.casefold() for keyword in keywords):
                continue
            if not (start <= modified <= end or any(start <= item <= end for item in date_hits(text))):
                continue
            print(json.dumps({"path": path, "mtime": os.stat(path).st_mtime, "content": text}, ensure_ascii=False))
'''


def configured_ssh_hosts(config_path: Path) -> list[str]:
    hosts: list[str] = []
    try:
        lines = config_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return hosts
    for line in lines:
        match = re.match(r"\s*Host\s+(.+)", line, re.IGNORECASE)
        if not match:
            continue
        for host in match.group(1).split():
            if "*" not in host and "?" not in host and "!" not in host:
                hosts.append(host)
    return list(dict.fromkeys(hosts))


def collect_remote_cursor(
    hosts: Iterable[str],
    config_path: Path,
    roots: list[str],
    start_at: datetime,
    end_at: datetime,
    keywords: tuple[str, ...],
) -> tuple[list[Session], list[str]]:
    sessions: list[Session] = []
    warnings: list[str] = []
    payload = json.dumps(
        {
            "start": str(start_at.date()),
            "end": str(end_at.date()),
            "keywords": keywords,
            "roots": roots,
        },
        ensure_ascii=False,
    )
    for host in hosts:
        command = [
            "ssh",
            "-F",
            str(config_path),
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=6",
            "-o",
            "ClearAllForwardings=yes",
            host,
            "python3 -c " + shlex.quote(REMOTE_CURSOR_SCRIPT),
        ]
        try:
            result = subprocess.run(
                command,
                input=payload,
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            warnings.append(f"{host}: remote Cursor scan failed ({error})")
            continue
        if result.returncode != 0:
            detail = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "unavailable"
            warnings.append(f"{host}: remote Cursor scan failed ({detail})")
            continue
        for line in result.stdout.splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            path = str(item.get("path") or "")
            content = item.get("content")
            if not path or not isinstance(content, str):
                continue
            session = read_cursor_file(
                Path(path),
                host,
                start_at,
                end_at,
                keywords,
                content_override=content,
                modified_override=float(item.get("mtime") or 0),
            )
            if session is not None:
                sessions.append(session)
    return sessions, warnings


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
    if left.source == right.source and left.session_id == right.session_id:
        return True
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
    canonical.source_labels = list(
        dict.fromkeys([*canonical.source_labels, *secondary.source_labels])
    )
    canonical.evidence_paths = list(
        dict.fromkeys([*canonical.evidence_paths, *secondary.evidence_paths])
    )
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
    warnings = getattr(args, "collection_warnings", [])
    if warnings:
        lines.extend(["- Source access warnings:", *[f"  - {item}" for item in warnings], ""])
    for session in sessions:
        lines.extend(
            [
                f"## {session.title}",
                "",
                f"- Source: `{', '.join(session.source_labels or [session.source])}`",
                f"- Session: `{session.session_id}`",
                f"- Working directory or project: `{session.cwd or 'unknown'}`",
            ]
        )
        if session.source_path:
            lines.append(f"- Transcript path: `{session.source_path}`")
        if session.evidence_paths:
            lines.append("- Evidence paths: " + ", ".join(f"`{path}`" for path in session.evidence_paths))
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
        "source_access_warnings": getattr(args, "collection_warnings", []),
        "sessions": [],
    }
    for session in sessions:
        users = select_messages(session.user_messages, args.detail, "user")
        finals = select_messages(session.final_messages, args.detail, "assistant")
        payload["sessions"].append(
            {
                "id": session.session_id,
                "source": session.source,
                "sources": session.source_labels or [session.source],
                "evidence_paths": session.evidence_paths,
                "source_path": session.source_path,
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
    collection_warnings: list[str] = []
    if args.include_cursor:
        cursor_roots = [Path(item).expanduser() for item in args.cursor_root]
        if not cursor_roots:
            cursor_roots = default_cursor_roots()
        sessions.extend(
            collect_local_cursor(cursor_roots, start_at, end_at, semantic_keywords(args))
        )
        remote_hosts = list(args.remote_host)
        if args.all_ssh_hosts:
            remote_hosts.extend(configured_ssh_hosts(Path(args.ssh_config).expanduser()))
        remote_hosts = list(dict.fromkeys(remote_hosts))
        if remote_hosts:
            remote_sessions, remote_warnings = collect_remote_cursor(
                remote_hosts,
                Path(args.ssh_config).expanduser(),
                args.remote_cursor_root,
                start_at,
                end_at,
                semantic_keywords(args),
            )
            sessions.extend(remote_sessions)
            collection_warnings.extend(remote_warnings)
    args.collection_warnings = collection_warnings
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
