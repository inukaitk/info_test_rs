"""設定とデータを検証するCLI。

使い方（リポジトリのルートで実行）:
    python -m collector.validate
    python -m collector.validate --config config --data data
    python -m collector.validate --demo      # 架空データ（demo/）を検証
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from collector.validation import REPO_ROOT, validate_all


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="config/ と data/ をスキーマで検証します")
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "config", help="設定フォルダ")
    parser.add_argument("--data", type=Path, default=REPO_ROOT / "data", help="データフォルダ")
    parser.add_argument("--demo", action="store_true", help="架空データ（demo/data と demo/config）を検証")
    args = parser.parse_args(argv)

    if args.demo:
        report = validate_all(args.config, REPO_ROOT / "demo" / "data", overlay_dir=REPO_ROOT / "demo" / "config")
    else:
        report = validate_all(args.config, args.data)
    if report.ok:
        print("OK: 設定とデータはスキーマ検証を通過しました")
        return 0
    print(f"NG: {len(report.errors)} 件の問題があります", file=sys.stderr)
    for error in report.errors:
        print(f"  - {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
