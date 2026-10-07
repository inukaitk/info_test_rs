"""外部連携用CSVの content_hash（SHA-256）。同じURLの本文変更を見つけるための「手がかり」で、変更の確定は受け取る側が行う。

ハッシュの対象は「題名 + 改行 + 本文」。算出の前に、次のとおり正規化する。
  - Unicode は NFC。改行は LF に統一（CRLF・CR → LF）
  - 連続する半角空白・タブ・全角空白は、半角空白1個にまとめ、各行の前後の空白を除く
  - 3行以上続く空行は、2行にまとめる
出力は小文字16進数64桁（先頭の「sha256:」などは付けない）。本文を取得できない（読み取れない・取得失敗）ときは、算出せず、
status を unavailable にする。題名やURLだけから、代わりのハッシュを作らない。

本文は、ナビゲーションやフッターなどを除いて抽出したテキスト。添付PDFを読んだ記事は、その抽出テキストを本文の後ろに足している。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import unicodedata
from pathlib import Path

from collector.validation import REPO_ROOT, load_json

HASH_STATUS_OK = "ok"
HASH_STATUS_UNAVAILABLE = "unavailable"


def normalize_for_hash(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t　]+", " ", line).strip() for line in text.split("\n")]
    text = "\n".join(lines)
    return re.sub(r"\n{4,}", "\n\n\n", text)  # 空行が3行以上続く（改行が4つ以上）ときは、空行2行（改行3つ）にする


def spec_hash(title: str, main_text: str) -> str:
    body = normalize_for_hash(title) + "\n" + normalize_for_hash(main_text)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def hash_scope(content_type: str, attachments: list[dict] | None) -> str:
    """ハッシュの対象を表す文字列。添付PDFを本文に足した記事は、そのことが分かるようにする。"""
    if content_type == "pdf":
        return "title+pdf_text"
    if any(a.get("status") == "ok" for a in attachments or []):
        return "title+main_text+attachments"
    return "title+main_text"


def hash_fields(title: str, text: str | None, content_type: str, extraction_status: str,
                attachments: list[dict] | None) -> dict:
    """版の記録に足す、CSV用ハッシュの3項目。"""
    if extraction_status != "ok" or not text:
        return {"export_hash": None, "export_hash_status": HASH_STATUS_UNAVAILABLE, "export_hash_scope": None}
    return {"export_hash": spec_hash(title, text), "export_hash_status": HASH_STATUS_OK,
            "export_hash_scope": hash_scope(content_type, attachments)}


def backfill(data_dir: Path, cache_dir: Path, dry_run: bool = False) -> dict[str, int]:
    """CSV用ハッシュのない最新版に、本文の控え（.cache/）から算出して足す。本文がなければ、unavailable として記録する。"""
    counts = {"added": 0, "unavailable": 0, "already": 0}
    for path in sorted((data_dir / "articles").glob("*.json")):
        data = load_json(path)
        article, latest = data["article"], data["versions"][-1]
        if "export_hash_status" in latest:
            counts["already"] += 1
            continue
        text = None
        text_path = cache_dir / "text" / f"{article['article_id']}_v{latest['version']}.txt"
        if latest["extraction_status"] == "ok" and text_path.exists():
            text = text_path.read_text(encoding="utf-8")
        fields = hash_fields(article["title"], text, latest["content_type"], latest["extraction_status"], latest.get("attachments"))
        latest.update(fields)
        counts["added" if fields["export_hash_status"] == HASH_STATUS_OK else "unavailable"] += 1
        if not dry_run:
            _write_atomic(path, data)
    return counts


def _write_atomic(path: Path, data: dict) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="外部連携用CSVの content_hash を、ない記事に足す（本文の控え .cache/ が必要）")
    parser.add_argument("--data", type=Path, default=REPO_ROOT / "data")
    parser.add_argument("--cache", type=Path, default=REPO_ROOT / ".cache")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    counts = backfill(args.data, args.cache, args.dry_run)
    print(f"{'確認のみ' if args.dry_run else '更新'}：算出 {counts['added']}件、算出できない {counts['unavailable']}件（本文の控えなし・読み取れない記事）、"
          f"すでにある {counts['already']}件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
