"""週次レポート（期間内の新規・変更、タグ別件数、情報源別の取得状況）。

allowlist を通った画面用JSON（meta / articles / status）だけから作る。
同じ内容を、画面用（reports.json）と Markdown ファイルの両方に出す。

使い方（リポジトリのルートで実行）:
    python -m collector.report                  # 最新の週を reports/ に Markdown で出力
    python -m collector.report --all            # 記録のあるすべての週を出力
    python -m collector.report --mode demo      # 架空データ（出力先は reports/demo/）
    python -m collector.report --out reports/x  # 出力先を指定
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

JST = timezone(timedelta(hours=9))
MAX_WEEKS = 12
REPORT_SCHEMA_VERSION = 1

SOURCE_STATUS_LABEL = {"success": "成功", "failed": "失敗", "skipped": "対象外", "unsupported": "未対応"}
RUN_STATUS_LABEL = {"success": "成功", "partial": "一部失敗", "failed": "失敗", "running": "実行中"}


# ---------------------------------------------------------------- 日付


def jst_date(timestamp: str) -> date:
    return datetime.fromisoformat(timestamp).astimezone(JST).date()


def published_day(article: dict) -> date | None:
    """公開日（日本時間の日付）。日まで分かる値と、時刻つきの値（RSSなど）が対象。日付不明・月だけ・年だけは None。"""
    value = (article.get("published") or {}).get("value")
    if not value:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return date.fromisoformat(value)
    if re.match(r"\d{4}-\d{2}-\d{2}T", value):
        return jst_date(value)
    return None


def week_windows(as_of: str | None, articles: list[dict], days: int = 7) -> list[tuple[date, date]]:
    """最終収集日を最後の日とする7日ごとの期間を、新しい順に返す（記事が見つかった最初の週まで）。"""
    if not as_of:
        return []
    end = jst_date(as_of)
    seen = [d for d in (published_day(a) for a in articles) if d is not None]  # 公開日が日まで分からない記事は数えない
    earliest = min(seen) if seen else end
    windows = []
    while len(windows) < MAX_WEEKS:
        start = end - timedelta(days=days - 1)
        windows.append((start, end))
        if start <= earliest:
            break
        end = start - timedelta(days=1)
    return windows


def format_date(d: date) -> str:
    return f"{d.year}年{d.month}月{d.day}日"


def format_partial(value: str | None) -> str:
    if not value:
        return "日付不明"
    m = re.match(r"^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?", value)
    if not m:
        return value
    y, mo, d = m.groups()
    if d:
        return f"{y}年{int(mo)}月{int(d)}日"
    if mo:
        return f"{y}年{int(mo)}月（日不明）"
    return f"{y}年（月日不明）"


def format_timestamp(ts: str | None) -> str:
    if not ts:
        return "—"
    t = datetime.fromisoformat(ts).astimezone(JST)
    return f"{t.year}年{t.month}月{t.day}日 {t.hour:02d}:{t.minute:02d}"


# ---------------------------------------------------------------- レポート本体


def _item(a: dict, version: int | None = None) -> dict:
    return {
        "id": a["id"],
        "title": a["title"],
        "url": a["url"],
        "source_name": a["source_name"],
        "published": a["published"]["value"],
        "first_seen_at": a["first_seen_at"],
        "version": version,
        "tags": [t["name"] for t in a["tags"]],
        "summary_status": a["summary"]["status"],
    }


def build_week(start: date, end: date, meta: dict, articles: list[dict], status: dict) -> dict:
    inside = lambda ts: start <= jst_date(ts) <= end  # noqa: E731

    # 公開日（日本時間）が期間内の記事だけを数える。公開日が日まで分からない記事（日付不明・月だけ・年だけ）は、
    # 取得日などで代用せず、新規にも変更にも数えない（この期間に見つけた件数だけを date_unknown に出す）
    new = [a for a in articles if (d := published_day(a)) is not None and start <= d <= end]
    new_ids = {a["id"] for a in new}
    undated = [a for a in articles if published_day(a) is None]
    changed = []
    for a in articles:
        if a["id"] in new_ids or published_day(a) is None:
            continue
        versions = [v for v in a["versions"] if v["change_type"] == "content_changed" and inside(v["fetched_at"])]
        if versions:
            changed.append((a, max(v["version"] for v in versions)))

    targets = new + [a for a, _ in changed]
    tag_names = {t["id"]: t["name"] for t in meta["tags"]}
    counts: dict[str, int] = {}
    for a in targets:
        for t in a["tags"]:
            counts[t["id"]] = counts.get(t["id"], 0) + 1
    tag_counts = [
        {"id": tag_id, "name": tag_names.get(tag_id, tag_id), "count": n}
        for tag_id, n in sorted(counts.items(), key=lambda kv: (-kv[1], list(tag_names).index(kv[0]) if kv[0] in tag_names else 99))
    ]

    source_names = {s["id"]: s["name"] for s in meta["sources"]}
    runs = [r for r in status["runs"] if inside(r["started_at"])]
    sources = []
    for source_id, name in source_names.items():
        results = [
            {"run_id": r["run_id"], "started_at": r["started_at"], **{k: s[k] for k in ("status", "new", "changed", "error")}}
            for r in sorted(runs, key=lambda r: r["started_at"])
            for s in r["sources"]
            if s["source_id"] == source_id
        ]
        sources.append({"id": source_id, "name": name, "runs": results})

    return {
        "id": f"{start.isoformat()}_{end.isoformat()}",
        "from": start.isoformat(),
        "to": end.isoformat(),
        "counts": {
            "new": len(new),
            "changed": len(changed),
            "date_unknown": sum(1 for a in undated if inside(a["first_seen_at"])),
            "unsummarized": sum(1 for a in targets if a["summary"]["status"] != "success"),
            "untagged": sum(1 for a in targets if not a["tags"]),
            "runs": len(runs),
        },
        "new": [_item(a) for a in sorted(new, key=lambda a: (published_day(a), a["first_seen_at"]), reverse=True)],
        "changed": [_item(a, v) for a, v in changed],
        "tag_counts": tag_counts,
        "sources": sources,
    }


def build_reports(meta: dict, articles_file: dict, status: dict) -> dict:
    articles = articles_file["articles"]
    weeks = []
    for start, end in week_windows(meta["data_as_of"], articles, meta.get("latest_days", 7)):
        week = build_week(start, end, meta, articles, status)
        week["markdown"] = to_markdown(week, meta)
        weeks.append(week)
    return {"schema_version": REPORT_SCHEMA_VERSION, "weeks": weeks}


# ---------------------------------------------------------------- Markdown


_MD_SPECIAL = re.compile(r"([\\`*_{}\[\]()#+\-.!|<>~])")


def md(text: str) -> str:
    """Markdown・HTMLとして解釈されないよう記号をエスケープする。"""
    return _MD_SPECIAL.sub(r"\\\1", text.replace("\n", " "))


def md_url(url: str) -> str:
    return url.replace("(", "%28").replace(")", "%29").replace(" ", "%20").replace("<", "%3C").replace(">", "%3E")


def to_markdown(week: dict, meta: dict) -> str:
    start, end = date.fromisoformat(week["from"]), date.fromisoformat(week["to"])
    c = week["counts"]
    lines = [f"# 週次レポート {format_date(start)}〜{format_date(end)}", ""]
    if meta["is_demo"]:
        lines += ["> **架空データ**：このレポートの機関名・記事・URLはすべて架空です。実在の情報ではありません。", ""]
    lines += [
        f"- サイト：{md(meta['site_name'])}",
        f"- 対象：公開日が期間内の記事と、期間内に本文が変わった記事（公開日が日まで分からない記事は数えない）",
        f"- データ作成：{format_timestamp(meta['generated_at'])}",
        "",
        "## 概要",
        "",
        "| 項目 | 件数 |",
        "|---|---:|",
        f"| 新規 | {c['new']} |",
        f"| 変更 | {c['changed']} |",
        f"| 公開日不明のため数えていない記事（この期間に見つけたもの） | {c['date_unknown']} |",
        f"| うち未要約 | {c['unsummarized']} |",
        f"| 期間内の収集実行 | {c['runs']} |",
        "",
    ]

    def article_lines(items: list[dict], changed: bool) -> list[str]:
        if not items:
            return ["なし", ""]
        out = []
        for i in items:
            tags = "、".join(md(t) for t in i["tags"]) or ("AI未処理" if i["summary_status"] != "success" else "タグなし")
            version = f"（第{i['version']}版）" if changed and i["version"] else ""
            out.append(
                f"- {format_partial(i['published'])}　{md(i['source_name'])}　"
                f"[{md(i['title'])}]({md_url(i['url'])}){version}　タグ：{tags}"
            )
        return out + [""]

    lines += [f"## 新規（{c['new']}件）", ""] + article_lines(week["new"], False)
    lines += [f"## 変更（{c['changed']}件）", ""] + article_lines(week["changed"], True)

    lines += ["## タグ別件数（新規＋変更）", ""]
    if week["tag_counts"]:
        lines += ["| タグ | 件数 |", "|---|---:|"] + [f"| {md(t['name'])} | {t['count']} |" for t in week["tag_counts"]]
    else:
        lines += ["なし"]
    if c["untagged"]:
        lines += ["", f"タグのない記事：{c['untagged']}件（AI未処理を含む）"]
    lines += ["", "## 情報源別の取得状況", ""]
    lines += ["| 情報源 | 実行日時 | 結果 | 新規 | 変更 | 失敗理由 |", "|---|---|---|---:|---:|---|"]
    for s in week["sources"]:
        if not s["runs"]:
            lines.append(f"| {md(s['name'])} | 期間内の実行なし | — | — | — | — |")
        for r in s["runs"]:
            lines.append(
                f"| {md(s['name'])} | {format_timestamp(r['started_at'])} | {SOURCE_STATUS_LABEL.get(r['status'], md(r['status']))} "
                f"| {r['new']} | {r['changed']} | {md(r['error']) if r['error'] else ''} |"
            )
    lines += [
        "",
        "---",
        "公的機関の公開情報をもとに独自に作成した概要です。AIによる要約は誤りを含む可能性があるため、内容は必ず出典で確認してください。",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> int:
    from collector.export import ExportError, build_public_data, paths_for_mode
    from collector.validation import REPO_ROOT, validate_all, validate_config

    parser = argparse.ArgumentParser(description="週次レポートを Markdown で出力します")
    parser.add_argument("--mode", choices=["demo", "real"], help="省略時は config/site.yaml の release_mode")
    parser.add_argument("--out", type=Path, help="出力フォルダ（省略時は real: reports/、demo: reports/demo/）")
    parser.add_argument("--all", action="store_true", help="最新の週だけでなく、記録のあるすべての週を出力")
    args = parser.parse_args(argv)

    config_dir = REPO_ROOT / "config"
    mode = args.mode
    if mode is None:
        config, _ = validate_config(config_dir)
        if config is None:
            print("NG: config/ の検証に失敗しました", file=sys.stderr)
            return 1
        mode = config.site["release_mode"]
    try:
        data_dir, overlay = paths_for_mode(mode)
    except ExportError as e:
        print(f"NG: {e}", file=sys.stderr)
        return 1
    report = validate_all(config_dir, data_dir, overlay_dir=overlay)
    if not report.ok:
        print("NG: 入力データの検証に失敗しました。python -m collector.validate で確認してください", file=sys.stderr)
        return 1
    config, _ = validate_config(config_dir, overlay_dir=overlay)
    generated_at = datetime.now(JST).isoformat(timespec="seconds")
    reports = build_public_data(config, data_dir, mode, generated_at)["reports.json"]["weeks"]
    if not reports:
        print("NG: 収集データがないためレポートを作れません", file=sys.stderr)
        return 1

    out = args.out or (REPO_ROOT / "reports" / ("demo" if mode == "demo" else ""))
    out.mkdir(parents=True, exist_ok=True)
    for week in reports if args.all else reports[:1]:
        path = out / f"weekly_{week['id']}.md"
        path.write_text(week["markdown"], encoding="utf-8")
        print(f"OK: {path} を出力しました（新規 {week['counts']['new']}件、変更 {week['counts']['changed']}件）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
