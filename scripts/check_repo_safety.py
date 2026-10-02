"""コミット対象に .env・.cache/・秘密値が入っていないかを確認する。

使い方（リポジトリのルートで実行）:
    python scripts/check_repo_safety.py            # Gitで管理されている全ファイルを確認
    python scripts/check_repo_safety.py --staged   # コミット予定（git add 済み）のファイルを確認

pre-commit フックとして使う場合（一度だけ実行）:
    git config core.hooksPath .githooks
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path, PurePosixPath

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from collector.export import find_secrets  # noqa: E402

ALLOWED_NAMES = {".env.example"}
FORBIDDEN_DIRS = {".cache", "node_modules", ".venv", "logs"}
MAX_SCAN_BYTES = 2_000_000


def forbidden_reason(path: str) -> str | None:
    """コミットしてはいけないパスなら理由を返す。"""
    p = PurePosixPath(path)
    if p.name in ALLOWED_NAMES:
        return None
    if p.name == ".env" or p.name.startswith(".env."):
        return "秘密値のファイル（.env）"
    for part in p.parts[:-1]:
        if part in FORBIDDEN_DIRS:
            return f"{part}/ 以下のファイル"
    if p.suffix == ".log":
        return "ログファイル"
    return None


def secret_findings(path: Path) -> list[str]:
    """ファイルの中身に秘密値の形をした文字列があれば理由を返す。"""
    try:
        data = path.read_bytes()
    except OSError:
        return []
    if len(data) > MAX_SCAN_BYTES or b"\0" in data:
        return []
    return find_secrets(data.decode("utf-8", errors="ignore"), environ={})


def git_paths(staged: bool) -> list[str]:
    if staged:
        cmd = ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"]
    else:
        cmd = ["git", "ls-files"]
    out = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if line]


def check(paths: list[str]) -> list[str]:
    problems = []
    for path in paths:
        reason = forbidden_reason(path)
        if reason:
            problems.append(f"{path}: {reason}はコミットできません")
            continue
        for finding in secret_findings(REPO_ROOT / path):
            problems.append(f"{path}: {finding}らしい文字列があります")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="コミット対象の安全確認")
    parser.add_argument("--staged", action="store_true", help="コミット予定のファイルだけを確認")
    args = parser.parse_args(argv)
    problems = check(git_paths(args.staged))
    if problems:
        print("NG: コミットしてはいけないものがあります", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        print("git restore --staged <ファイル> でコミット対象から外してください", file=sys.stderr)
        return 1
    print("OK: .env・.cache/・秘密値はコミット対象に含まれていません")
    return 0


if __name__ == "__main__":
    sys.exit(main())
