"""AIのAPIキーが使えるかを、課金されない count_tokens で確認する（GitHub Actions の最初の手順で使う）。
キーの値は表示しない。使えなければ終了コード1。"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from collector.ai_provider import MissingApiKey, build_provider  # noqa: E402


def check(ai_config: dict, environ: dict[str, str] | None = None, factory=None) -> tuple[bool, str]:
    try:
        provider = build_provider(ai_config, environ=environ, factory=factory)
    except MissingApiKey:
        return False, "APIキーが設定されていません（環境変数 INFO_AI_API_KEY）。GitHub の Secrets に登録されているか確認してください"
    try:
        provider.count_tokens("確認", "こんにちは")
    except Exception as e:  # noqa: BLE001  詳細（キーを含みうる文字列）は出さず、種類とHTTPの状態だけを出す
        status = getattr(e, "status_code", None)
        hint = "キーが無効、または失効しています" if status in (401, 403) else "APIに接続できません、または一時的なエラーです"
        return False, f"AIのAPIを呼べませんでした（{type(e).__name__}{f'、HTTP {status}' if status else ''}）。{hint}"
    return True, "AIのAPIキーは使えます（課金されない確認）"


def main() -> int:
    config = yaml.safe_load((REPO_ROOT / "config" / "ai.yaml").read_text(encoding="utf-8"))
    ok, message = check(config)
    print(("OK: " if ok else "NG: ") + message)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
