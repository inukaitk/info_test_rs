"""収集処理（IMPLEMENTATION 4章）。

1. 設定を検証し、対象の情報源を確定する
2. RSS または一覧ページから候補URLを列挙する（ページ送りは上限内、探索範囲を記録）
3. URL とリダイレクト先が許可ホストか検証する（localhost・内部IP・非HTTPは拒否）
4. 件数・サイズ・待機時間・timeout を制限して取得する
5. 本文・タイトル・日付・PDFのテキストを抽出する（ナビ等の変化を本文の変更にしない）
6. 公開日・更新日の根拠を保存する（HTTP の Last-Modified だけで公開日を確定しない）
7. 正規化URLと本文hashで新規・変更・既存を判定し、意味のある本文変更は版を追加する
8. 結果を一時フォルダに書いて検証してから置き換える。情報源ごとに成功地点を管理する

使い方（リポジトリのルートで実行）:
    python -m collector.collect --fixtures tests/fixtures/web/manifest.yaml --config-dir tests/fixtures/web --data /tmp/data
    python -m collector.collect --start 2026-09-01 --end 2026-09-30 ...   # 期間指定（日本時間、両端を含む）
    python -m collector.collect --source demo-news ...                     # 情報源を指定
実際のWebへアクセスするには --allow-network が必要（段階2-bで、採用した情報源にだけ使う）。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from collector.dates import JST, ParsedDate, in_period
from dataclasses import replace

from collector.extract import (
    Candidate, DateFound, Extracted, Listing, extract_document, extract_pdf, normalize_text, parse_feed, parse_html_listing,
)
from collector.fetch import FetchError, Fetcher, FixtureFetcher, HttpFetcher
from collector.urls import UrlRejected, check_allowed
from collector.validation import REPO_ROOT, Config, article_id_from_canonical_url, load_json, validate_all, validate_config

OVERLAP_DAYS = 14  # 前回の成功地点からさかのぼって再確認する日数
INITIAL_DAYS = 30  # 初回（成功地点なし）にさかのぼる日数
DROP_RATIO = 0.5  # 候補数が前回のこの割合未満に減ったら警告


@dataclass
class Options:
    now: datetime
    start: date | None = None
    end: date | None = None
    source_ids: list[str] | None = None
    cache_dir: Path | None = None
    trigger: str = "manual_cli"
    max_items: int | None = None  # 1つの情報源から本文を取得する件数の上限（設定より小さくするときだけ使う）


@dataclass
class SourceOutcome:
    result: dict
    failures: list[dict] = field(default_factory=list)
    extraction_changed: int = 0  # 抽出方法の変更で版を追加した件数


def _ts(dt: datetime) -> str:
    return dt.astimezone(JST).isoformat(timespec="seconds")


def _store_date(found: DateFound | None) -> tuple[str | None, dict | None, str]:
    if found is None:
        return None, None, "unknown"
    value = found.value.value
    if found.value.precision == "datetime":
        value = datetime.fromisoformat(value).astimezone(JST).isoformat(timespec="seconds")
    return value, {"method": found.method, "evidence": found.evidence[:200]}, found.value.precision


# ---------------------------------------------------------------- 保存データ


class Store:
    """data/ の読み書き。変更は作業用フォルダに書き、検証後に本来の場所へ置き換える。"""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.articles: dict[str, dict] = {}
        for p in sorted((data_dir / "articles").glob("*.json")):
            f = load_json(p)
            self.articles[f["article"]["article_id"]] = f
        state_path = data_dir / "state.json"
        self.state = load_json(state_path) if state_path.exists() else {"schema_version": 1, "sources": {}}
        runs = sorted((data_dir / "runs").glob("*.json"))
        self.previous_run = load_json(runs[-1])["run"] if runs else None
        self.changed_articles: set[str] = set()

    def source_state(self, source_id: str) -> dict:
        return self.state["sources"].get(source_id) or {
            "source_id": source_id, "last_success_at": None, "last_attempt_at": None, "last_attempt_status": None,
            "explored_range": None, "retry_queue": [], "consecutive_failures": 0,
        }

    def commit(self, run: dict, config_dir: Path, overlay_dir: Path | None) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp) / "data"
            if self.data_dir.exists():
                shutil.copytree(self.data_dir, stage)
            for sub in ("articles", "summaries", "runs"):
                (stage / sub).mkdir(parents=True, exist_ok=True)
            written: list[str] = []
            for article_id in sorted(self.changed_articles):
                rel = f"articles/{article_id}.json"
                _write_json(stage / rel, self.articles[article_id])
                written.append(rel)
            _write_json(stage / "state.json", self.state)
            written.append("state.json")
            rel = f"runs/{run['run_id']}.json"
            _write_json(stage / rel, {"schema_version": 1, "run": run})
            written.append(rel)
            report = validate_all(config_dir, stage, overlay_dir=overlay_dir)
            if not report.ok:
                raise RuntimeError("保存前の検証に失敗したため、data/ は変更していません:\n" + "\n".join(report.errors))
            for rel in written:  # 検証を通ったファイルだけを置き換える
                target = self.data_dir / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                tmp_target = target.with_suffix(".json.tmp")
                shutil.copyfile(stage / rel, tmp_target)
                os.replace(tmp_target, target)


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- 情報源ごとの処理


def collection_window(state: dict, options: Options) -> tuple[date | None, date | None]:
    """期間指定があればそれを使う。なければ前回の成功地点から重複確認期間を設けた範囲（初回は INITIAL_DAYS 日）。"""
    if options.start or options.end:
        return options.start, options.end
    today = options.now.astimezone(JST).date()
    if state["last_success_at"]:
        last = datetime.fromisoformat(state["last_success_at"]).astimezone(JST).date()
        return last - timedelta(days=OVERLAP_DAYS), today
    return today - timedelta(days=INITIAL_DAYS), today


def list_candidates(source: dict, fetcher: Fetcher) -> tuple[list[Candidate], int, str | None, list[str]]:
    """候補を列挙する。戻り値：候補、探索したページ数、失敗理由（失敗時）、除外したリンク。"""
    limits = source["limits"]
    url: str | None = source["entry_url"]
    max_pages = source.get("pagination", {}).get("max_pages", 1) if source["method"] == "html" else 1
    candidates: list[Candidate] = []
    rejected: list[str] = []
    pages = 0
    while url and pages < max_pages:
        try:
            resp = fetcher.get(url, allowed_hosts=source["allowed_hosts"], max_bytes=limits["max_bytes"],
                               timeout=limits["timeout_seconds"])
            if source["method"] == "rss":
                listing: Listing = parse_feed(resp.body, resp.url)
            else:
                listing = parse_html_listing(resp.body, resp.url, source.get("link_rules", {}),
                                             source.get("pagination", {}).get("next_selector"))
        except (FetchError, UrlRejected, ValueError) as e:
            label = "一覧ページ" if pages == 0 else f"一覧の{pages + 1}ページ目"
            return candidates, pages, f"{label}を取得できません：{e}", rejected
        pages += 1
        candidates += listing.candidates
        rejected += listing.rejected
        url = listing.next_url
    return candidates, pages, None, rejected


def choose_dates(candidate: Candidate, extracted: Extracted | None) -> tuple[DateFound | None, DateFound | None]:
    """公開日の根拠の優先順：RSSの日付 > ページのメタ情報 > 本文の記載 > 一覧の記載 > PDFの文書情報。"""
    listing = DateFound(*candidate.listing_date) if candidate.listing_date else None
    listing_updated = DateFound(*candidate.listing_updated) if candidate.listing_updated else None
    page_pub = extracted.published if extracted else None
    page_upd = extracted.updated if extracted else None
    order = [
        listing if listing and listing.method.startswith("rss") else None,
        page_pub if page_pub and page_pub.method != "pdf_metadata" else None,
        listing,
        page_pub,
    ]
    published = next((d for d in order if d is not None), None)
    return published, page_upd or listing_updated


def process_source(source: dict, store: Store, fetcher: Fetcher, options: Options, now_ts: str) -> SourceOutcome:
    source_id = source["id"]
    state = store.source_state(source_id)
    limits = source["limits"]
    result = {"source_id": source_id, "status": "success", "candidates": 0, "new": 0, "changed": 0, "unchanged": 0,
              "date_unknown": 0, "fetch_failed": 0, "warnings": [], "error": None}
    outcome = SourceOutcome(result)

    if source["method"] == "manual":
        result["status"] = "skipped"
        state.update(last_attempt_at=now_ts, last_attempt_status="skipped")
        store.state["sources"][source_id] = state
        return outcome

    start, end = collection_window(state, options)
    candidates, pages, list_error, rejected = list_candidates(source, fetcher)

    # 重複URL（正規化後に同じもの）は1件にまとめる
    unique: dict[str, Candidate] = {}
    for c in candidates:
        unique.setdefault(c.url, c)
    result["candidates"] = len(unique)
    if rejected:
        result["warnings"].append(f"取得対象外のリンク {len(rejected)}件を除外しました（http(s)以外など）")

    # 前回失敗して再試行待ちのもの（本文の取得・抽出）も対象に加える
    retry_queue = {r["url"]: r for r in state["retry_queue"]}
    for url in retry_queue:
        if retry_queue[url]["stage"] in ("fetch", "extract") and url not in unique:
            unique[url] = Candidate(url=url, title=None)

    # 探索できた範囲は、一覧で見えたすべての候補の日付から求める（本文を取得したかどうかによらない）
    explored: list[ParsedDate] = [c.listing_date[0] for c in candidates if c.listing_date]
    processed = 0
    max_items = min(limits["max_items"], options.max_items) if options.max_items else limits["max_items"]
    for cand in unique.values():
        if cand.listing_date:
            if in_period(cand.listing_date[0], start, end) is False and cand.url not in retry_queue:
                continue  # 一覧の日付で期間外と分かるものは取得しない
        if processed >= max_items:
            result["warnings"].append(f"取得上限（{max_items}件）に達したため、残りは次回に回します")
            break
        processed += 1
        try:
            url = check_allowed(cand.url, source["allowed_hosts"])
        except UrlRejected as e:
            result["warnings"].append(f"許可ホスト以外のリンクを除外：{e}")
            continue
        handle_candidate(source, cand, url, store, fetcher, options, now_ts, start, end, state, retry_queue, outcome)

    # 0件・急減の警告（正常か抽出規則の破損かを区別できるように）
    if list_error is None and len(candidates) == 0:
        result["warnings"].append("一覧から記事を1件も抽出できませんでした（抽出規則が壊れている可能性があります）")
    prev = _previous_result(store.previous_run, source_id)
    if list_error is None and prev and prev["candidates"] >= 4 and len(unique) < prev["candidates"] * DROP_RATIO:
        result["warnings"].append(f"候補が前回（{prev['candidates']}件）から{len(unique)}件に大きく減りました")

    if outcome.extraction_changed:
        result["warnings"].append(
            f"抽出方法の変更（添付PDFを読む等）により {outcome.extraction_changed}件に版を追加しました（原文の変更ではありません）")
    state["retry_queue"] = list(retry_queue.values())
    state["last_attempt_at"] = now_ts
    if list_error:
        result["status"] = "failed"
        result["error"] = list_error
        outcome.failures.append({"source_id": source_id, "stage": "list", "reason": list_error})
        state["last_attempt_status"] = "failed"
        state["consecutive_failures"] += 1
        # 失敗した情報源の成功地点（last_success_at）と探索範囲は進めない
    else:
        state["last_attempt_status"] = "success"
        state["last_success_at"] = now_ts
        state["consecutive_failures"] = 0
        ranges = [p.range() for p in explored]
        state["explored_range"] = {
            "oldest": min(r[0] for r in ranges).isoformat() if ranges else None,
            "newest": max(r[1] for r in ranges).isoformat() if ranges else None,
            "pages": pages,
        }
    store.state["sources"][source_id] = state
    return outcome


def _previous_result(run: dict | None, source_id: str) -> dict | None:
    if not run:
        return None
    return next((s for s in run["sources"] if s["source_id"] == source_id and s["status"] == "success"), None)


def _retry(retry_queue: dict, url: str, article_id: str | None, stage: str, reason: str, now_ts: str) -> None:
    item = retry_queue.get(url)
    if item:
        item.update(attempts=item["attempts"] + 1, reason=reason, stage=stage)
    else:
        item = {"url": url, "stage": stage, "reason": reason, "first_failed_at": now_ts, "attempts": 1}
        retry_queue[url] = item
    if article_id:
        item["article_id"] = article_id


# ---------------------------------------------------------------- 添付PDF


ATTACHMENT_DEFAULTS = {"max_files": 3, "max_bytes": 10 * 1024 * 1024, "max_pages": 30}
MAX_ATTACHMENT_RECORDS = 20


def extraction_profile(source: dict, extracted: Extracted | None) -> str:
    """抽出方法を表す文字列。これが変わったときの版は「抽出方法の変更」として記録する。"""
    if extracted is not None and extracted.content_type == "pdf":
        return "pdf"
    conf = source.get("attachments") or {}
    if not conf.get("pdf"):
        return "html"
    c = {**ATTACHMENT_DEFAULTS, **conf}
    excluded = f",exclude:{'|'.join(c['exclude_titles'])}" if c.get("exclude_titles") else ""
    return f"html+pdf({c['max_files']}files,{c['max_pages']}pages{excluded})"


def fetch_attachments(source: dict, extracted: Extracted, fetcher: Fetcher) -> tuple[Extracted, list[dict], list[str]]:
    """記事ページの本文中にある PDF を取得し、本文に加える。戻り値：本文を足した抽出結果、添付の記録、失敗の理由。"""
    conf = source.get("attachments") or {}
    if not conf.get("pdf") or extracted.content_type != "html" or extracted.status != "ok" or not extracted.pdf_links:
        return extracted, [], []
    c = {**ATTACHMENT_DEFAULTS, **conf}
    records: list[dict] = []
    parts: list[str] = [extracted.text]
    failures: list[str] = []
    exclude = [re.compile(p) for p in c.get("exclude_titles", [])]
    taken = 0
    for link, label in extracted.pdf_links[:MAX_ATTACHMENT_RECORDS]:
        record = {"url": link, "title": label[:200], "status": "skipped", "error": None,
                  "text_length": None, "pages": None, "pages_read": None}
        records.append(record)
        if any(p.search(label) for p in exclude):
            record["error"] = "設定（exclude_titles）で除外した資料です"
            continue
        taken += 1
        if taken > c["max_files"]:
            record["error"] = f"1記事あたりの上限（{c['max_files']}件）を超えたため取得していません"
            continue
        try:
            url = check_allowed(link, source["allowed_hosts"])
        except UrlRejected as e:
            record["error"] = f"取得対象外：{e}"
            continue
        try:
            resp = fetcher.get(url, allowed_hosts=source["allowed_hosts"], max_bytes=c["max_bytes"],
                               timeout=source["limits"]["timeout_seconds"])
        except (FetchError, UrlRejected) as e:
            record.update(status="failed", error=str(e))
            failures.append(f"{label[:40]}：{e}")
            continue
        pdf = extract_pdf(resp.body, max_pages=c["max_pages"])
        record.update(status=pdf.status, pages=pdf.page_count, pages_read=pdf.pages_read)
        if pdf.status != "ok":
            record["error"] = pdf.error
            continue
        record["text_length"] = len(pdf.text)
        if pdf.page_count and pdf.pages_read and pdf.pages_read < pdf.page_count:
            record["error"] = f"先頭{pdf.pages_read}ページだけを読み取りました（全{pdf.page_count}ページ）"
        parts.append(f"［添付PDF］{label}\n{pdf.text}")
    combined = replace(extracted, text=normalize_text("\n\n".join(parts)))
    return combined, records, failures


def handle_candidate(source, cand: Candidate, url: str, store: Store, fetcher: Fetcher, options: Options, now_ts: str,
                     start, end, state, retry_queue: dict, outcome: SourceOutcome) -> None:
    result = outcome.result
    limits = source["limits"]
    extracted: Extracted | None = None
    error: str | None = None
    final_url = url
    try:
        resp = fetcher.get(url, allowed_hosts=source["allowed_hosts"], max_bytes=limits["max_bytes"],
                           timeout=limits["timeout_seconds"])
        final_url = resp.url
        extracted = extract_document(resp.body, resp.content_type, resp.url)
    except (FetchError, UrlRejected) as e:
        error = str(e)

    article_id = article_id_from_canonical_url(url)
    existing = store.articles.get(article_id)
    published, updated = choose_dates(cand, extracted)

    # 期間の判定（日付不明は期間内と推定せず、別枠として保存・報告する）
    if existing is None:
        judged = in_period(published.value if published else None, start, end)
        if judged is False:
            retry_queue.pop(url, None)
            return

    if error is not None:
        result["fetch_failed"] += 1
        outcome.failures.append({"source_id": source["id"], "url": url, "stage": "fetch", "reason": error})
        _retry(retry_queue, url, article_id, "fetch", error, now_ts)
        if existing is None:
            _new_article(store, source, article_id, url, cand, None, published, updated, now_ts, error=error)
            result["new"] += 1
            if published is None:
                result["date_unknown"] += 1
        else:
            existing["article"]["last_seen_at"] = now_ts
            store.changed_articles.add(article_id)
            result["unchanged"] += 1
        return

    assert extracted is not None
    profile = extraction_profile(source, extracted)
    extracted, attachments, attachment_failures = fetch_attachments(source, extracted, fetcher)
    if attachment_failures:
        reason = "添付PDFの取得に失敗：" + "／".join(attachment_failures)
        result["fetch_failed"] += 1
        outcome.failures.append({"source_id": source["id"], "url": url, "stage": "fetch", "reason": reason[:300]})
        _retry(retry_queue, url, article_id, "fetch", reason[:300], now_ts)
        if existing is not None:
            # 一時的な失敗で本文が欠けた版を作らない（次回の再試行でまとめて確認する）
            existing["article"]["last_seen_at"] = now_ts
            store.changed_articles.add(article_id)
            result["unchanged"] += 1
            return
    else:
        retry_queue.pop(url, None)

    if existing is None:
        _new_article(store, source, article_id, url, cand, extracted, published, updated, now_ts,
                     attachments=attachments, profile=profile)
        _cache_text(options.cache_dir, article_id, extracted, 1)
        result["new"] += 1
        if published is None:
            result["date_unknown"] += 1
        return

    article, versions = existing["article"], existing["versions"]
    latest = versions[-1]
    article["last_seen_at"] = now_ts
    _update_dates(article, published, updated)
    if extracted.content_type == "html" and extracted.title and extracted.title != article["title"]:
        article["title"] = extracted.title
    new_hash = extracted.content_hash
    if extracted.status == "ok" and new_hash != latest["content_hash"]:
        # 抽出方法（添付PDFを読む等）が前の版と違うときは、原文の変更ではなく「抽出方法の変更」として記録する
        same_method = latest.get("extraction_profile", "html") == profile or latest["extraction_status"] != "ok"
        change_type = "content_changed" if same_method else "extraction_changed"
        versions.append(_version(article_id, len(versions) + 1, extracted, now_ts, change_type,
                                 attachments=attachments, profile=profile))
        article["latest_version"] = len(versions)
        if article["status"] == "unsupported":
            article["status"] = "active"
        _cache_text(options.cache_dir, article_id, extracted, len(versions))
        if change_type == "content_changed":
            result["changed"] += 1
        else:
            result["unchanged"] += 1
            outcome.extraction_changed += 1
    else:
        result["unchanged"] += 1
        # .cache/ はセッションをまたいで残らないため、変化がなくても本文のキャッシュがなければ書き直す（AI要約で使う）
        if extracted.status == "ok" and new_hash == latest["content_hash"]:
            _cache_text(options.cache_dir, article_id, extracted, len(versions), only_if_missing=True)
    store.changed_articles.add(article_id)


def _version(article_id: str, n: int, extracted: Extracted | None, now_ts: str, change_type: str, error: str | None = None,
             attachments: list[dict] | None = None, profile: str | None = None) -> dict:
    if extracted is None:
        return {"article_id": article_id, "version": n, "content_hash": None, "fetched_at": now_ts, "content_type": "none",
                "text_length": None, "extraction_status": "failed", "extraction_error": error, "change_type": change_type}
    ok = extracted.status == "ok"
    extra: dict = {}
    if profile and profile != "html":
        extra["extraction_profile"] = profile
    if attachments:
        extra["attachments"] = attachments
    return {**extra, 
        "article_id": article_id, "version": n, "content_hash": extracted.content_hash, "fetched_at": now_ts,
        "content_type": extracted.content_type, "text_length": len(extracted.text) if ok else None,
        "extraction_status": extracted.status, "extraction_error": None if ok else extracted.error, "change_type": change_type,
    }


def _new_article(store: Store, source, article_id, url, cand: Candidate, extracted: Extracted | None,
                 published: DateFound | None, updated: DateFound | None, now_ts: str, error: str | None = None,
                 attachments: list[dict] | None = None, profile: str | None = None) -> None:
    pub_value, pub_basis, pub_precision = _store_date(published)
    upd_value, upd_basis, upd_precision = _store_date(updated)
    # PDF の文書情報のタイトルは当てにならないことが多いため、PDF は一覧のリンク文字を優先する
    page_title = extracted.title if extracted and extracted.title else None
    if extracted is not None and extracted.content_type == "pdf":
        title = cand.title or page_title or url
    else:
        title = page_title or cand.title or url
    status = "unsupported" if extracted is not None and extracted.status == "unsupported" else "active"
    store.articles[article_id] = {
        "schema_version": 1,
        "article": {
            "article_id": article_id, "source_id": source["id"], "canonical_url": url, "title": title[:300],
            "published_at": pub_value, "updated_at": upd_value,
            "date_basis": {"published": pub_basis, "updated": upd_basis},
            "date_precision": {"published": pub_precision, "updated": upd_precision},
            "first_seen_at": now_ts, "last_seen_at": now_ts, "latest_version": 1, "status": status,
        },
        "versions": [_version(article_id, 1, extracted, now_ts, "new", error, attachments, profile)],
    }
    store.changed_articles.add(article_id)


def _update_dates(article: dict, published: DateFound | None, updated: DateFound | None) -> None:
    if article["published_at"] is None and published is not None:
        value, basis, precision = _store_date(published)
        article.update(published_at=value)
        article["date_basis"]["published"] = basis
        article["date_precision"]["published"] = precision
    if updated is not None:
        value, basis, precision = _store_date(updated)
        if value != article["updated_at"]:
            article["updated_at"] = value
            article["date_basis"]["updated"] = basis
            article["date_precision"]["updated"] = precision


def _cache_text(cache_dir: Path | None, article_id: str, extracted: Extracted, version: int,
                only_if_missing: bool = False) -> None:
    """原文の本文は .cache/ にだけ置く（Git・公開物には入れない）。AI処理（段階3）で使う。"""
    if cache_dir is None or extracted.status != "ok":
        return
    path = cache_dir / "text" / f"{article_id}_v{version}.txt"
    if only_if_missing and path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(extracted.text, encoding="utf-8")


# ---------------------------------------------------------------- 全体


def collect(config: Config, data_dir: Path, fetcher: Fetcher, options: Options,
            config_dir: Path = REPO_ROOT / "config", overlay_dir: Path | None = None) -> dict:
    store = Store(data_dir)
    now = options.now.astimezone(timezone.utc)
    run_id = "run_" + now.strftime("%Y%m%dT%H%M%SZ")
    now_ts = _ts(options.now)
    sources = [s for s in config.sources["sources"] if s["enabled"]]
    if options.source_ids:
        unknown = set(options.source_ids) - {s["id"] for s in config.sources["sources"]}
        if unknown:
            raise ValueError(f"未登録の情報源id: {', '.join(sorted(unknown))}")
        sources = [s for s in config.sources["sources"] if s["id"] in options.source_ids]

    results, failures = [], []
    for source in sources:
        outcome = process_source(source, store, fetcher, options, now_ts)
        results.append(outcome.result)
        failures += outcome.failures

    totals = {k: sum(r[k] for r in results) for k in ("new", "changed", "unchanged", "date_unknown", "fetch_failed")}
    totals.update(summarized=0, summarize_failed=0)
    statuses = {r["status"] for r in results}
    if results and statuses <= {"failed"}:
        status = "failed"
    elif "failed" in statuses or totals["fetch_failed"]:
        status = "partial"
    else:
        status = "success"
    run = {
        "run_id": run_id, "started_at": now_ts, "finished_at": _ts(max(datetime.now(timezone.utc), now)),
        "status": status, "trigger": options.trigger,
        "kind": "collect",
        "period": {"start": options.start.isoformat(), "end": options.end.isoformat()} if options.start and options.end else None,
        "sources": results, "totals": totals, "failures": failures,
        "api_usage": {"requests": 0, "input_tokens": 0, "output_tokens": 0, "estimated_cost_usd": None},
    }
    store.commit(run, config_dir, overlay_dir)
    return run


# ---------------------------------------------------------------- 試し読み（情報源を追加するときの確認用）


def dry_run(config: Config, fetcher: Fetcher, source_ids: list[str] | None, limit: int = 10) -> int:
    """一覧ページだけを読み、抽出規則で取れる候補を表示する。記事本文の取得・保存はしない。"""
    sources = [s for s in config.sources["sources"] if (s["id"] in source_ids if source_ids else s["enabled"])]
    if not sources:
        print("NG: 対象の情報源がありません（--source で id を指定するか、enabled: true にしてください）", file=sys.stderr)
        return 1
    ok = True
    for source in sources:
        if source["method"] == "manual":
            print(f"- {source['id']}: 手動登録のため一覧はありません")
            continue
        source = {**source, "pagination": {**source.get("pagination", {}), "max_pages": 1}}
        candidates, pages, error, rejected = list_candidates(source, fetcher)
        print(f"- {source['id']}（{source['name']}）：候補 {len(candidates)}件" + (f"　NG：{error}" if error else ""))
        if error:
            ok = False
        for c in candidates[:limit]:
            when = f"{c.listing_date[0].value}" if c.listing_date else "日付不明"
            print(f"    {when:<26} {(c.title or '')[:40]}\n      {c.url}")
        if len(candidates) > limit:
            print(f"    …ほか {len(candidates) - limit}件")
        if not candidates and not error:
            print("    警告：候補が0件です。link_rules（css_selector・item_selector・include）を見直してください")
    return 0 if ok else 1


# ---------------------------------------------------------------- CLI


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError("YYYY-MM-DD の形式で指定してください") from e


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="情報源から記事を収集して data/ に保存します")
    parser.add_argument("--start", type=_date, help="開始日（日本時間、この日を含む）YYYY-MM-DD")
    parser.add_argument("--end", type=_date, help="終了日（日本時間、この日を含む）YYYY-MM-DD")
    parser.add_argument("--source", action="append", dest="sources", help="情報源id（複数指定可。省略時は有効なすべて）")
    parser.add_argument("--data", type=Path, default=REPO_ROOT / "data", help="データフォルダ")
    parser.add_argument("--config-dir", type=Path, default=None,
                        help="sources.yaml を置いたフォルダ（tags 等は config/ を使う）。テスト用")
    parser.add_argument("--fixtures", type=Path, help="テスト用：URLとファイルの対応表（実際のWebにはアクセスしない）")
    parser.add_argument("--allow-network", action="store_true", help="実際のWebへアクセスする（採用した情報源のみ）")
    parser.add_argument("--cache", type=Path, default=REPO_ROOT / ".cache", help="原文本文の保存先（Git管理外）")
    parser.add_argument("--max-items", type=int, help="情報源ごとに本文を取得する件数の上限（試しに少数だけ取得するとき）")
    parser.add_argument("--dry-run", action="store_true",
                        help="一覧ページだけを読んで候補（題名・日付・URL）を表示する。記事本文は取得せず、何も保存しない")
    args = parser.parse_args(argv)

    if (args.start is None) != (args.end is None):
        parser.error("--start と --end は両方指定してください")
    if args.start and args.end and args.start > args.end:
        parser.error("--start は --end 以前の日付にしてください")
    if args.fixtures is None and not args.allow_network:
        parser.error("実際のWebへアクセスするには --allow-network を付けてください（テストでは --fixtures を使う）")

    config_dir = REPO_ROOT / "config"
    config, report = validate_config(config_dir, overlay_dir=args.config_dir)
    if config is None:
        print("NG: 設定の検証に失敗しました", file=sys.stderr)
        for e in report.errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    if args.fixtures:
        fetcher: Fetcher = FixtureFetcher.from_manifest(args.fixtures)
    else:
        fetcher = HttpFetcher(wait_seconds=max(s["limits"]["wait_seconds"] for s in config.sources["sources"]))
    if args.dry_run:
        return dry_run(config, fetcher, args.sources)
    options = Options(now=datetime.now(JST), start=args.start, end=args.end, source_ids=args.sources,
                      cache_dir=args.cache, max_items=args.max_items)
    try:
        run = collect(config, args.data, fetcher, options, config_dir=config_dir, overlay_dir=args.config_dir)
    except (ValueError, RuntimeError) as e:
        print(f"NG: {e}", file=sys.stderr)
        return 1

    label = {"success": "成功", "partial": "一部失敗", "failed": "失敗"}[run["status"]]
    t = run["totals"]
    print(f"{'OK' if run['status'] == 'success' else 'NG' if run['status'] == 'failed' else '注意'}: 収集{label}"
          f"（新規 {t['new']}件、変更 {t['changed']}件、変化なし {t['unchanged']}件、日付不明 {t['date_unknown']}件、取得失敗 {t['fetch_failed']}件）")
    for r in run["sources"]:
        line = f"  - {r['source_id']}: {r['status']}（候補 {r['candidates']}件）"
        if r["error"]:
            line += f" 理由：{r['error']}"
        print(line)
        for w in r["warnings"]:
            print(f"      警告：{w}")
    print(f"  実行記録：{args.data / 'runs' / (run['run_id'] + '.json')}")
    return 0 if run["status"] != "failed" else 1


if __name__ == "__main__":
    sys.exit(main())
