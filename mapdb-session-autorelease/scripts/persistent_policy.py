#!/usr/bin/env python3
"""Install/remove a project-scoped opt-in without publishing or editing repos."""
import argparse
import fcntl
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import time
from urllib.parse import urlparse

BEGIN = '<!-- mapdb-session-autorelease:begin -->'
END = '<!-- mapdb-session-autorelease:end -->'


def approved_repo(repo):
    remote = subprocess.check_output(['git', '-C', str(repo), 'remote', 'get-url', 'origin'], text=True).strip()
    if '://' in remote:
        parsed = urlparse(remote)
        host, path = parsed.hostname, parsed.path.lstrip('/')
    else:
        match = re.fullmatch(r'(?:[^@/:]+@)?([^/:]+):(.+)', remote)
        host, path = match.groups() if match else (None, None)
    if host != 'gitlab.x2robot.com' or path.removesuffix('.git').rstrip('/') != 'echo/memory_module':
        raise ValueError('origin is not the approved memory_module repository')


def remove_block(text):
    if BEGIN not in text and END not in text:
        return text
    if text.count(BEGIN) != 1 or text.count(END) != 1 or text.index(END) < text.index(BEGIN):
        raise ValueError('malformed/duplicated policy block; existing file preserved')
    a, b = text.index(BEGIN), text.index(END) + len(END)
    return text[:a] + text[b:]


def block():
    skill = Path(__file__).resolve().parents[1] / 'SKILL.md'
    return f'''{BEGIN}
## memory_module 持续发布（用户显式调用 skill 后启用）

仅当当前仓库 origin 指向 gitlab.x2robot.com/echo/memory_module 时适用，包含该仓库各 worktree。每次进入相关代码任务先读取 {skill}。
用户已启用跨会话持续规范：每批完成的代码修改，做相关测试和项目要求的审查，合并最新 origin/develop，维护变更记录，提交并通过 Git SSH 推送 develop 和新 PATCH annotated tag，等待 CI并核验 10.136.29.157:8899 实际版本、健康与相关功能。无需每轮重新询问是否提交、打tag、发布；缺少 GitLab API token不阻止Git SSH tag流水线。
遵守项目数据保护、部署锁、idle等待和CI门禁；不取消其他任务、删除生产数据、改独立Viewer、向机器人部署或立即发群消息。没有代码修改不发版。只推tag或流水线等待不能报告已上线。
更具体的当前用户指令优先：“本次只本地/先不发布”仅暂停本次；“关闭持续发布”用该skill的 disable移除此规则。此规则是用户明确选择的持续授权，不能从普通历史发布请求推断同类授权。
{END}'''


def write_preserving(path, text):
    if path.is_symlink():
        raise ValueError('refusing to replace a symlink instruction file')
    old = path.read_text() if path.exists() else ''
    if old == text:
        return False
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
    if path.exists():
        backups = path.parent / 'mapdb-autorelease-backups'
        backups.mkdir(mode=0o700, exist_ok=True)
        backup = backups / (path.name + '.' + str(time.time_ns()))
        with backup.open('x') as stream:
            stream.write(old)
        backup.chmod(0o600)
    fd, name = tempfile.mkstemp(prefix='.mapdb-policy-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['enable', 'disable', 'status'])
    parser.add_argument('--repo', type=Path)
    parser.add_argument('--codex-home', type=Path, default=Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))))
    args = parser.parse_args()
    if args.action == 'enable':
        if args.repo is None:
            parser.error('enable requires --repo')
        approved_repo(args.repo)
    home = args.codex_home.expanduser().resolve()
    home.mkdir(parents=True, exist_ok=True)
    files = [home / 'AGENTS.override.md', home / 'AGENTS.md']
    with (home / '.mapdb-autorelease.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if any(p.is_symlink() for p in files):
            raise ValueError('instruction symlink requires manual handling')
        texts = {p: p.read_text() if p.exists() else '' for p in files}
        # Validate every managed block before changing either file.
        cleaned = {p: remove_block(t) for p, t in texts.items()}
        effective = files[0] if texts[files[0]].strip() else files[1]
        if args.action == 'status':
            print('enabled' if BEGIN in texts[effective] else 'disabled', effective)
            return
        if args.action == 'disable':
            for path in files:
                if cleaned[path] != texts[path]:
                    write_preserving(path, cleaned[path])
            print('disabled; unrelated instructions preserved')
            return
        # Keep a repeated enable byte-identical when already active.
        desired = block()
        if desired in texts[effective]:
            print('already enabled', effective)
            return
        text = cleaned[effective]
        write_preserving(effective, text + ('\n\n' if text and not text.endswith('\n\n') else '') + desired + '\n')
        print('enabled', effective)


if __name__ == '__main__':
    main()
