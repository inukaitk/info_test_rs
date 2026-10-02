"""画面用JSON（公開用データ）を作る変換。

allowlist方式：画面に出してよい項目だけを明示的に取り出して新しい辞書を作る。
元データに項目が増えても、ここで指定しない限り画面用JSONには出ない。
原文全文、API生応答、タグ候補（data/tag_candidates.json）、.cache/、秘密値は読み込まない・出力しない。

使い方（リポジトリのルートで実行）:
    python -m collector.export                 # site.yaml の release_mode に従う
    python -m collector.export --mode demo     # 架空データ（demo/）から作る
    python -m collector.export --mode real     # 実データ（data/）から作る
    python -m collector.export --out web/public/data
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from collector.validation import REPO_ROOT, Config, load_json, schema_errors, validate_all, validate_config

DEFAULT_OUT = REPO_ROOT / "web" / "public" / "data"
PUBLIC_SCHEMA_VERSION = 1

# 秘密値らしい環境変数の名前
_SECRET_ENV_NAME = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)", re.IGNORECASE)
# よく使われるAPIキー・トークンの形
_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"AIza[0-9A-Za-z_-]{30,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
]


class ExportError(Exception):
    pass


# ---------------------------------------------------------------- 入力


def paths_for_mode(mode: str) -> tuple[Path, Path | None]:
    """データフォルダと、設定の上書きフォルダ（demoのみ）を返す。"""
    if mode == "demo":
        return REPO_ROOT / "demo" / "data", REPO_ROOT / "demo" / "config"
    if mode == "real":
        return REPO_ROOT / "data", None
    raise ExportError(f"不明なモード: {mode}")


def _load_dir(directory: Path) -> list[Any]:
    return [load_json(p) for p in sorted(directory.glob("*.json"))] if directory.exists() else []


def _latest_summary(summaries: list[dict]) -> dict | None:
    if not summaries:
        return None
    return max(summaries, key=lambda s: (s["article_version"], s["processed_at"]))


# ---------------------------------------------------------------- タグ


def final_tags(ai_tags: list[dict] | None, override: dict | None, tag_defs: dict[str, dict]) -> list[dict]:
    """画面に出すタグ = AIタグ ＋ 追加 － 除外。各タグに由来（ai / human）を付ける。"""
    add = list((override or {}).get("add", []))
    remove = set((override or {}).get("remove", []))
    result = []
    seen = set()
    for tag in ai_tags or []:
        tag_id = tag["tag_id"]
        if tag_id in remove or tag_id in seen:
            continue
        seen.add(tag_id)
        result.append(_tag_entry(tag_id, "ai", tag["reason"], tag_defs))
    for tag_id in add:
        if tag_id in seen or tag_id in remove:
            continue
        seen.add(tag_id)
        result.append(_tag_entry(tag_id, "human", None, tag_defs))
    return result


def _tag_entry(tag_id: str, origin: str, reason: str | None, tag_defs: dict[str, dict]) -> dict:
    definition = tag_defs.get(tag_id)
    return {
        "id": tag_id,
        "name": definition["name"] if definition else tag_id,
        "origin": origin,
        "reason": reason,
        "retired": not definition["enabled"] if definition else True,
    }


def removed_tags(ai_tags: list[dict] | None, override: dict | None, tag_defs: dict[str, dict]) -> list[dict]:
    """AIが付けたが人が除外したタグ（記事詳細で「除外」と表示するため）。"""
    remove = set((override or {}).get("remove", []))
    return [
        {"id": t["tag_id"], "name": tag_defs.get(t["tag_id"], {}).get("name", t["tag_id"])}
        for t in ai_tags or []
        if t["tag_id"] in remove
    ]


# ---------------------------------------------------------------- 変換（allowlist）


def _date_info(article: dict, key: str) -> dict:
    basis = article["date_basis"][key]
    return {
        "value": article[f"{key}_at"],
        "precision": article["date_precision"][key],
        "basis": {"method": basis["method"], "evidence": basis["evidence"]} if basis else None,
    }


def _public_summary(summary: dict | None, latest_version: int) -> dict:
    if summary is None:
        return {"status": "not_processed", "error": None, "version": None, "outdated": False,
                "text": None, "key_points": None, "targets": None, "dates": None, "uncertainties": None,
                "model": None, "processed_at": None}
    success = summary["analysis_status"] == "success"
    return {
        "status": summary["analysis_status"],
        "error": summary["error"],
        "version": summary["article_version"],
        "outdated": summary["article_version"] < latest_version,
        "text": summary["summary"] if success else None,
        "key_points": list(summary["key_points"]) if success else None,
        "targets": list(summary["targets"]) if success else None,
        "dates": [{"label": d["label"], "value": d["value"], "evidence": d["evidence"]} for d in summary["dates"]]
        if success else None,
        "uncertainties": list(summary["uncertainties"]) if success else None,
        "model": summary["model"],
        "processed_at": summary["processed_at"],
    }


def build_articles(article_files: list[dict], summary_files: list[dict], config: Config) -> list[dict]:
    summaries_by_id = {f["article_id"]: f["summaries"] for f in summary_files}
    overrides = {o["article_id"]: o for o in config.tag_overrides["overrides"]}
    tag_defs = {t["id"]: t for t in config.tags["tags"]}
    source_names = {s["id"]: s["name"] for s in config.sources["sources"]}

    result = []
    for file in article_files:
        article, versions = file["article"], file["versions"]
        article_id = article["article_id"]
        summary = _latest_summary(summaries_by_id.get(article_id, []))
        ai_tags = summary["ai_tags"] if summary and summary["analysis_status"] == "success" else None
        override = overrides.get(article_id)
        latest = versions[-1]
        result.append({
            "id": article_id,
            "source_id": article["source_id"],
            "source_name": source_names.get(article["source_id"], article["source_id"]),
            "title": article["title"],
            "url": article["canonical_url"],
            "published": _date_info(article, "published"),
            "updated": _date_info(article, "updated"),
            "first_seen_at": article["first_seen_at"],
            "last_seen_at": article["last_seen_at"],
            "status": article["status"],
            "content_status": latest["extraction_status"],
            "content_error": latest["extraction_error"],
            "latest_version": article["latest_version"],
            "versions": [
                {"version": v["version"], "fetched_at": v["fetched_at"], "change_type": v["change_type"],
                 "extraction_status": v["extraction_status"]}
                for v in versions
            ],
            "summary": _public_summary(summary, article["latest_version"]),
            "tags": final_tags(ai_tags, override, tag_defs),
            "removed_tags": removed_tags(ai_tags, override, tag_defs),
            "tag_override_reason": override.get("reason") if override else None,
        })
    result.sort(key=lambda a: (a["published"]["value"] or "", a["first_seen_at"]), reverse=True)
    return result


def build_status(runs: list[dict], state: dict, articles: list[dict], config: Config) -> dict:
    run_records = sorted((r["run"] for r in runs), key=lambda r: r["started_at"])
    last_run = run_records[-1] if run_records else None
    full_success = [r for r in run_records if r["status"] == "success"]
    last_results = {s["source_id"]: s for s in last_run["sources"]} if last_run else {}
    sources = []
    for source in config.sources["sources"]:
        st = state.get("sources", {}).get(source["id"])
        res = last_results.get(source["id"])
        sources.append({
            "id": source["id"],
            "name": source["name"],
            "method": source["method"],
            "entry_url": source["entry_url"],
            "enabled": source["enabled"],
            "last_success_at": st["last_success_at"] if st else None,
            "last_attempt_at": st["last_attempt_at"] if st else None,
            "last_attempt_status": st["last_attempt_status"] if st else None,
            "consecutive_failures": st["consecutive_failures"] if st else 0,
            "explored_range": dict(st["explored_range"]) if st and st["explored_range"] else None,
            "retry_count": len(st["retry_queue"]) if st else 0,
            "last_run": {
                "status": res["status"], "error": res["error"], "warnings": list(res["warnings"]),
                "new": res["new"], "changed": res["changed"], "unchanged": res["unchanged"],
                "date_unknown": res["date_unknown"], "fetch_failed": res["fetch_failed"],
            } if res else None,
            "articles": sum(1 for a in articles if a["source_id"] == source["id"]),
            "date_unknown": sum(1 for a in articles if a["source_id"] == source["id"]
                                and a["published"]["value"] is None),
        })
    return {
        "last_run_at": last_run["finished_at"] or last_run["started_at"] if last_run else None,
        "last_run_status": last_run["status"] if last_run else None,
        "last_full_success_at": full_success[-1]["finished_at"] if full_success else None,
        "counts": {
            "articles": len(articles),
            "date_unknown": sum(1 for a in articles if a["published"]["value"] is None),
            "content_missing": sum(1 for a in articles if a["content_status"] != "ok"),
            "unsummarized": sum(1 for a in articles if a["summary"]["status"] != "success"),
            "summary_outdated": sum(1 for a in articles if a["summary"]["outdated"]),
        },
        "sources": sources,
        "runs": [
            {"run_id": r["run_id"], "started_at": r["started_at"], "finished_at": r["finished_at"],
             "status": r["status"], "kind": r["kind"],
             "period": dict(r["period"]) if r["period"] else None,
             "totals": dict(r["totals"]),
             "sources": [
                 {"source_id": s["source_id"], "status": s["status"], "new": s["new"], "changed": s["changed"],
                  "date_unknown": s["date_unknown"], "fetch_failed": s["fetch_failed"],
                  "error": s["error"], "warnings": list(s["warnings"])}
                 for s in r["sources"]
             ]}
            for r in reversed(run_records)
        ],
    }


def data_as_of(runs: list[dict], article_files: list[dict]) -> str | None:
    """最新一覧の基準日時：最後の収集の開始日時。実行履歴がなければ最も新しい発見日時。"""
    starts = [r["run"]["started_at"] for r in runs if r["run"]["kind"] in ("collect", "collect_and_summarize")]
    if starts:
        return max(starts)
    seen = [f["article"]["first_seen_at"] for f in article_files]
    return max(seen) if seen else None


def build_meta(config: Config, mode: str, generated_at: str, as_of: str | None = None) -> dict:
    site = config.site
    return {
        "schema_version": PUBLIC_SCHEMA_VERSION,
        "generated_at": generated_at,
        "release_mode": mode,
        "is_demo": mode == "demo",
        "site_name": site["site_name"],
        "correction_request_url": site["correction_request_url"],
        "page_size": site["page_size"],
        "latest_days": site["latest_days"],
        "stale_after_days": site["stale_after_days"],
        "data_as_of": as_of,
        "tags": [
            {"id": t["id"], "name": t["name"], "description": t["description"], "retired": not t["enabled"]}
            for t in config.tags["tags"]
        ],
        "sources": [{"id": s["id"], "name": s["name"]} for s in config.sources["sources"]],
    }


def build_public_data(config: Config, data_dir: Path, mode: str, generated_at: str) -> dict[str, Any]:
    """画面用JSONの内容を作る。tag_candidates.json と .cache/ は読まない。"""
    article_files = _load_dir(data_dir / "articles")
    summary_files = _load_dir(data_dir / "summaries")
    runs = _load_dir(data_dir / "runs")
    state_path = data_dir / "state.json"
    state = load_json(state_path) if state_path.exists() else {"sources": {}}

    articles = build_articles(article_files, summary_files, config)
    outputs = {
        "meta.json": build_meta(config, mode, generated_at, data_as_of(runs, article_files)),
        "articles.json": {"schema_version": PUBLIC_SCHEMA_VERSION, "articles": articles},
        "status.json": {"schema_version": PUBLIC_SCHEMA_VERSION, **build_status(runs, state, articles, config)},
    }
    # 週次レポートは、allowlist を通った画面用JSONだけから作る
    from collector.report import build_reports

    outputs["reports.json"] = build_reports(outputs["meta.json"], outputs["articles.json"], outputs["status.json"])
    return outputs


# ---------------------------------------------------------------- 出力前の確認


PUBLIC_SCHEMAS = {
    "meta.json": "public/meta.schema.json",
    "articles.json": "public/articles.schema.json",
    "status.json": "public/status.schema.json",
    "reports.json": "public/reports.schema.json",
}


def find_secrets(text: str, environ: dict[str, str] | None = None) -> list[str]:
    """出力文字列に秘密値らしいものが含まれていないか調べ、見つかった理由を返す（値そのものは返さない）。"""
    environ = os.environ if environ is None else environ
    found = []
    for name, value in environ.items():
        if _SECRET_ENV_NAME.search(name) and value and len(value) >= 8 and value in text:
            found.append(f"環境変数 {name} の値")
    for pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            found.append(f"秘密値の形式（{pattern.pattern[:12]}…）")
    return found


def check_public_data(outputs: dict[str, Any], environ: dict[str, str] | None = None) -> list[str]:
    problems = []
    for name, data in outputs.items():
        problems += [f"{name}: {e}" for e in schema_errors(data, PUBLIC_SCHEMAS[name])]
        problems += [f"{name}: {s} が含まれています" for s in find_secrets(json.dumps(data, ensure_ascii=False), environ)]
    return problems


def write_outputs(outputs: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, data in outputs.items():
        tmp = out_dir / f".{name}.tmp"
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(out_dir / name)


def export(mode: str, out_dir: Path, generated_at: str, config_dir: Path | None = None) -> dict[str, Any]:
    config_dir = config_dir or REPO_ROOT / "config"
    data_dir, overlay = paths_for_mode(mode)
    report = validate_all(config_dir, data_dir, overlay_dir=overlay)
    if not report.ok:
        raise ExportError("入力データの検証に失敗しました:\n" + "\n".join(f"  - {e}" for e in report.errors))
    config, _ = validate_config(config_dir, overlay_dir=overlay)
    outputs = build_public_data(config, data_dir, mode, generated_at)
    problems = check_public_data(outputs)
    if problems:
        raise ExportError("画面用JSONの確認に失敗しました:\n" + "\n".join(f"  - {p}" for p in problems))
    write_outputs(outputs, out_dir)
    return outputs


def main(argv: list[str] | None = None) -> int:
    from datetime import datetime, timedelta, timezone

    parser = argparse.ArgumentParser(description="画面用JSONを作ります")
    parser.add_argument("--mode", choices=["demo", "real"], help="省略時は config/site.yaml の release_mode")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="出力フォルダ")
    parser.add_argument("--generated-at", help="生成日時（省略時は現在時刻。テスト用）")
    args = parser.parse_args(argv)

    mode = args.mode
    if mode is None:
        config, report = validate_config(REPO_ROOT / "config")
        if config is None:
            print("NG: config/ の検証に失敗しました。python -m collector.validate で確認してください", file=sys.stderr)
            return 1
        mode = config.site["release_mode"]
    generated_at = args.generated_at or datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds")
    try:
        outputs = export(mode, args.out, generated_at)
    except ExportError as e:
        print(f"NG: {e}", file=sys.stderr)
        return 1
    count = len(outputs["articles.json"]["articles"])
    print(f"OK: {mode} モードで記事 {count} 件の画面用JSONを {args.out} に出力しました")
    return 0


if __name__ == "__main__":
    sys.exit(main())
