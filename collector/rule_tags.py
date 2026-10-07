"""ルール（キーワード一致）によるタグ付け。AIは使わない。費用はかからない。

`config/tags.yaml` の `auto_rules` に書いた言葉（正規表現）が、記事の題名・本文にあれば、そのタグを付ける。
結果は `data/rule_tags.json` に保存する（記事の版・ルールの版つき）。画面用の変換（export）が、AIのタグ・情報源の設定のタグ・
人の修正と合わせて、最終的なタグにする。

- 本文は `.cache/text/` にある場合だけ使う（本文はGitに入れない）。ない記事は題名だけで判定し、`scope: title` と記録する。
  本文が使える環境で実行し直すと、本文で判定し直す。
- 同じ記事の版・同じルールなら、再判定しない（結果を変えない）。ルールを変えたら、本文のある記事を判定し直す。
- 一致した語は、短い引用（80字まで）だけを保存する。原文全文は保存しない。

使い方:
    python -m collector.rule_tags             # data/ と .cache/ から判定して data/rule_tags.json を更新する
    python -m collector.rule_tags --dry-run   # 保存せず、結果の数だけを表示する
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
from dataclasses import dataclass
from pathlib import Path

from collector.validation import REPO_ROOT, Config, load_json, validate_config

SCHEMA_VERSION = 1
MAX_MATCH_CHARS = 80


@dataclass(frozen=True)
class Rule:
    tag_id: str
    label: str
    pattern: re.Pattern[str]
    source: str  # 正規表現の文字列（ルールの版を求めるため）


def load_rules(config: Config) -> list[Rule]:
    """有効なタグの auto_rules を、書かれた順に返す。"""
    rules = []
    for tag in config.tags["tags"]:
        if not tag["enabled"]:
            continue
        for r in tag.get("auto_rules", []):
            rules.append(Rule(tag["id"], r["label"], re.compile(r["pattern"], re.IGNORECASE), r["pattern"]))
    return rules


def rules_version(rules: list[Rule]) -> str:
    body = [{"tag_id": r.tag_id, "label": r.label, "pattern": r.source} for r in rules]
    return "sha256:" + hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _normalize(text: str) -> str:
    """全角・半角の違いを無視して比較するため。"""
    return unicodedata.normalize("NFKC", text)


def match_rules(rules: list[Rule], title: str, body: str | None) -> list[dict]:
    """題名・本文に一致した言葉を返す。同じ（タグ, 名前）は1件。題名で一致すれば、題名を先にする。"""
    title_n = _normalize(title)
    body_n = _normalize(body) if body else ""
    found = []
    for rule in rules:
        for where, text in (("title", title_n), ("body", body_n)):
            m = rule.pattern.search(text) if text else None
            if m:
                found.append({"tag_id": rule.tag_id, "label": rule.label, "matched": m.group(0).strip()[:MAX_MATCH_CHARS] or rule.label,
                              "in": where})
                break
    return found


def _read_text(cache_dir: Path, article_id: str, version: int) -> str | None:
    path = cache_dir / "text" / f"{article_id}_v{version}.txt"
    return path.read_text(encoding="utf-8") if path.exists() else None


@dataclass
class Result:
    updated: int = 0          # 判定し直した記事
    unchanged: int = 0        # 同じ版・同じルールのため、そのままにした記事
    title_only: int = 0       # 本文がなく、題名だけで判定した記事（本文のある環境で実行し直すと、判定し直す）
    stale: int = 0            # ルールが変わったが、本文がないため判定し直せない記事（前の結果を残した）
    tagged: int = 0           # 結果としてタグが付く記事
    changed: bool = False


def apply_rules(config: Config, data_dir: Path, cache_dir: Path) -> tuple[dict, Result]:
    """全記事を判定して、保存する内容（辞書）を返す。ファイルには書かない。"""
    rules = load_rules(config)
    version_now = rules_version(rules)
    path = data_dir / "rule_tags.json"
    previous = load_json(path)["articles"] if path.exists() else {}
    articles: dict[str, dict] = {}
    result = Result()

    for file in sorted((data_dir / "articles").glob("*.json")):
        data = load_json(file)
        article, latest = data["article"], data["versions"][-1]
        article_id, version = article["article_id"], article["latest_version"]
        old = previous.get(article_id)
        text = _read_text(cache_dir, article_id, version) if latest["extraction_status"] == "ok" else None
        fresh = old is not None and old["article_version"] == version and old["rules_version"] == version_now
        if fresh and (old["scope"] == "body" or text is None):
            entry = old
            result.unchanged += 1
        elif old is not None and old["article_version"] == version and text is None and old["scope"] == "body":
            entry = old  # ルールが変わったが、本文がなく判定し直せない（前の結果を残す）
            result.stale += 1
        else:
            scope = "body" if text is not None else "title"
            entry = {"article_version": version, "scope": scope, "rules_version": version_now,
                     "tags": match_rules(rules, article["title"], text)}
            result.updated += 1
        if entry["scope"] == "title" and latest["extraction_status"] == "ok":
            result.title_only += 1
        if entry["tags"]:
            result.tagged += 1
        articles[article_id] = entry
    content = {"schema_version": SCHEMA_VERSION, "articles": dict(sorted(articles.items()))}
    result.changed = (not path.exists()) or load_json(path) != content
    return content, result


def write_atomic(path: Path, content: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(content, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ルール（キーワード一致）でタグを付ける（AIは使わない）")
    parser.add_argument("--data", type=Path, default=REPO_ROOT / "data")
    parser.add_argument("--cache", type=Path, default=REPO_ROOT / ".cache")
    parser.add_argument("--config-dir", type=Path, default=REPO_ROOT / "config")
    parser.add_argument("--dry-run", action="store_true", help="保存せず、結果の数だけを表示する")
    args = parser.parse_args(argv)

    config, report = validate_config(args.config_dir)
    if config is None:
        print("NG: 設定の検証に失敗しました", file=sys.stderr)
        for e in report.errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    rules = load_rules(config)
    if not rules:
        print("ルール（auto_rules）がありません。何もしません。")
        return 0
    content, result = apply_rules(config, args.data, args.cache)
    print(f"{'確認のみ' if args.dry_run else '判定'}：ルール {len(rules)}件、判定し直し {result.updated}件、変更なし {result.unchanged}件、"
          f"タグが付く記事 {result.tagged}件")
    if result.title_only:
        print(f"  注意：本文がなく、題名だけで判定した記事が {result.title_only}件あります（本文のある環境で実行し直すと、本文で判定し直します）")
    if result.stale:
        print(f"  注意：ルールが変わりましたが、本文がなく判定し直せない記事が {result.stale}件あります（前の結果を残しました）")
    if args.dry_run:
        return 0
    if result.changed:
        write_atomic(args.data / "rule_tags.json", content)
        print(f"保存：{args.data / 'rule_tags.json'}")
    else:
        print("変更はありません。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
