"""架空のデモデータ（demo/data/）を作り直すスクリプト。

機関名・URL・内容はすべて架空。URLは予約済みの例示用ドメイン（example.org等）だけを使う。
同じ内容が毎回出力されるよう、日時はすべて固定値にしている。

使い方（リポジトリのルートで実行）:
    python scripts/make_demo_data.py
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from collector.validation import article_id_from_canonical_url  # noqa: E402

DEMO_DATA = REPO_ROOT / "demo" / "data"
TAGS_VERSION = "sha256:" + hashlib.sha256(b"demo-tags-v1").hexdigest()
PROMPT_VERSION = "demo-p1"
PROVIDER = "demo"
MODEL = "demo-model"

SOURCES = {
    "demo-kodomo-rss": "https://kodomo.example.org/news/",
    "demo-boshi-html": "https://boshi.example.net/info/",
    "demo-jichitai-html": "https://hyojunka.example.com/topics/",
    "demo-tokei-rss": "https://tokei.example.org/release/",
}


def h(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def ts(date: str, time: str = "08:00:00") -> str:
    return f"{date}T{time}+09:00"


# 記事の定義。各項目の意味:
#   source, path: 情報源と URL のパス
#   title: タイトル（すべて【架空】を付ける）
#   published: (値, 精度, 根拠の方法, 根拠) または None（日付不明）
#   updated: 同上（明示された更新日がなければ None）
#   seen: 発見日
#   versions: 版ごとの (取得日, 抽出状態, エラー)。抽出状態は ok / failed / unsupported
#   status: article.status
#   summaries: 要約の一覧。("success", 版, 要約, 論点, 対象, 日付, タグ, 不確実な点) か (失敗状態, 版, エラー)
ARTICLES = [
    dict(
        source="demo-kodomo-rss", path="2026/0901-kenshin.html",
        title="【架空】乳幼児健康診査の実施要領を改正しました",
        published=("2026-09-01", "day", "rss_pubdate", "<pubDate>Tue, 01 Sep 2026 10:00:00 +0900</pubDate>"),
        updated=("2026-09-18", "day", "html_text", "最終更新日：2026年9月18日"),
        seen="2026-09-07",
        versions=[("2026-09-07", "ok", None), ("2026-09-21", "ok", None)],
        status="active",
        summaries=[
            ("success", 1, "【架空】乳幼児健康診査の実施要領が改正され、令和9年4月から問診項目が追加される。",
             ["問診項目の追加", "記録様式の変更"], ["市区町村"],
             [("施行日", "2027-04-01", "令和9年4月1日から適用する")],
             [("maternal-child-health", "乳幼児健診に関する内容のため"), ("system-revision", "実施要領の改正のため")], []),
            ("success", 2, "【架空】乳幼児健康診査の実施要領が改正され、令和9年4月から問診項目が追加される。9月18日に記録様式の例が追加された。",
             ["問診項目の追加", "記録様式の変更", "様式例の追加"], ["市区町村"],
             [("施行日", "2027-04-01", "令和9年4月1日から適用する")],
             [("maternal-child-health", "乳幼児健診に関する内容のため"), ("system-revision", "実施要領の改正のため")], []),
        ],
    ),
    dict(
        source="demo-kodomo-rss", path="2026/0903-hoiku-kofukin.html",
        title="【架空】保育環境改善交付金の公募を開始します",
        published=("2026-09-03", "day", "rss_pubdate", "<pubDate>Thu, 03 Sep 2026 14:00:00 +0900</pubDate>"),
        updated=None, seen="2026-09-07",
        versions=[("2026-09-07", "ok", None)], status="active",
        summaries=[
            ("success", 1, "【架空】保育所の環境改善を対象とする交付金の公募が開始された。申請締切は10月30日。",
             ["対象経費は設備整備", "補助率は2分の1"], ["都道府県", "市区町村", "保育所設置者"],
             [("申請締切", "2026-10-30", "令和8年10月30日（金）必着")],
             [("subsidy-grant", "交付金の公募のため"), ("childcare-support", "保育に関する支援のため")], []),
        ],
    ),
    dict(
        source="demo-kodomo-rss", path="2026/0908-jimurenraku.html",
        title="【架空】妊婦健康診査の費用助成に関する事務連絡",
        published=("2026-09-08", "day", "rss_pubdate", "<pubDate>Tue, 08 Sep 2026 09:30:00 +0900</pubDate>"),
        updated=None, seen="2026-09-14",
        versions=[("2026-09-14", "ok", None)], status="active",
        summaries=[
            ("success", 1, "【架空】妊婦健康診査の費用助成について、対象となる検査項目の解釈を示す事務連絡が発出された。",
             ["検査項目の解釈", "問い合わせ先の変更"], ["都道府県", "市区町村"], [],
             [("notice-admin-communication", "事務連絡のため"), ("maternal-child-health", "妊婦健診に関する内容のため")],
             ["適用開始日は本文で確認できなかった"]),
        ],
    ),
    dict(
        source="demo-kodomo-rss", path="2026/0910-shingikai.html",
        title="【架空】第5回こども健やか検討会の資料を掲載しました",
        published=("2026-09-10", "day", "rss_pubdate", "<pubDate>Thu, 10 Sep 2026 17:00:00 +0900</pubDate>"),
        updated=None, seen="2026-09-14",
        versions=[("2026-09-14", "ok", None)], status="active",
        summaries=[
            ("success", 1, "【架空】第5回こども健やか検討会の資料が掲載された。産後ケアの提供体制が議題となった。",
             ["産後ケアの提供体制", "次回は報告書案を議論"], ["検討会委員"],
             [("開催日", "2026-09-09", "令和8年9月9日（水）10時から")],
             [("council-committee", "検討会の資料のため"), ("maternal-child-health", "産後ケアが議題のため")], []),
        ],
    ),
    dict(
        source="demo-kodomo-rss", path="2026/0915-teate.html",
        title="【架空】子育て世帯応援手当の支給要件を見直します",
        published=("2026-09-15", "day", "rss_pubdate", "<pubDate>Tue, 15 Sep 2026 11:00:00 +0900</pubDate>"),
        updated=None, seen="2026-09-21",
        versions=[("2026-09-21", "ok", None)], status="active",
        # AI未要約（APIキーなし）
        summaries=[("skipped_no_api_key", 1, "APIキーが設定されていないため未実行")],
    ),
    dict(
        source="demo-kodomo-rss", path="2026/0917-qa.html",
        title="【架空】産後ケア事業に関するQ&Aを更新しました",
        published=("2026-09-17", "day", "rss_pubdate", "<pubDate>Thu, 17 Sep 2026 15:00:00 +0900</pubDate>"),
        updated=None, seen="2026-09-21",
        versions=[("2026-09-21", "ok", None)], status="active",
        # タグ修正あり：AIが付けた「調査・統計」を人が除外し、「通知・事務連絡」を追加
        summaries=[
            ("success", 1, "【架空】産後ケア事業のQ&Aが更新され、利用者負担の軽減に関する回答が追加された。",
             ["利用者負担の軽減", "委託先の要件"], ["市区町村"], [],
             [("maternal-child-health", "産後ケアに関する内容のため"), ("survey-statistics", "利用状況の数値が含まれるため")], []),
        ],
    ),
    dict(
        source="demo-kodomo-rss", path="2026/0924-dx.html",
        title="【架空】母子保健情報のデジタル化に関する工程表を公表しました",
        published=("2026-09-24", "day", "rss_pubdate", "<pubDate>Thu, 24 Sep 2026 10:00:00 +0900</pubDate>"),
        updated=None, seen="2026-09-28",
        versions=[("2026-09-28", "ok", None)], status="active",
        summaries=[
            ("success", 1, "【架空】母子保健情報のデジタル化に向けた工程表が公表された。令和10年度までの段階的な移行を示す。",
             ["電子版母子健康手帳の普及", "自治体システムとの連携"], ["市区町村", "医療機関"],
             [("移行完了目標", "2028", "令和10年度末までに移行を完了する")],
             [("municipal-dx-standardization", "自治体のデジタル化に関する内容のため"), ("maternal-child-health", "母子保健情報が対象のため")], []),
        ],
    ),
    dict(
        source="demo-kodomo-rss", path="2026/0925-ikkatsu.html",
        title="【架空】こども政策に関する一括法案の概要",
        published=("2026-09-25", "day", "rss_pubdate", "<pubDate>Fri, 25 Sep 2026 18:00:00 +0900</pubDate>"),
        updated=None, seen="2026-09-28",
        versions=[("2026-09-28", "ok", None)], status="active",
        # AI失敗（出力がスキーマ検証に失敗）
        summaries=[("failed_invalid_output", 1, "出力JSONの検証に失敗（登録外のタグid）")],
    ),
    dict(
        source="demo-boshi-html", path="20260902.html",
        title="【架空】母子健康手帳の様式改定に関する研究報告",
        published=("2026-09-02", "day", "html_text", "掲載日：2026年9月2日"),
        updated=None, seen="2026-09-07",
        versions=[("2026-09-07", "ok", None)], status="active",
        summaries=[
            ("success", 1, "【架空】母子健康手帳の様式改定に向けた研究報告が公開された。記入欄の簡素化が提案されている。",
             ["記入欄の簡素化", "多言語版の拡充"], ["研究者", "自治体の母子保健担当"], [],
             [("maternal-child-health", "母子健康手帳に関する内容のため")], ["改定時期は示されていない"]),
        ],
    ),
    dict(
        source="demo-boshi-html", path="20260911.html",
        title="【架空】研修会「妊産婦のメンタルヘルス支援」開催のお知らせ",
        published=None,  # 日付不明（一覧・本文とも日付の記載なし）
        updated=None, seen="2026-09-14",
        versions=[("2026-09-14", "ok", None)], status="active",
        summaries=[
            ("success", 1, "【架空】妊産婦のメンタルヘルス支援に関する研修会の開催案内。対象は保健師等。",
             ["オンライン開催", "事前申込制"], ["保健師", "助産師"], [],
             [("maternal-child-health", "妊産婦支援に関する内容のため")], ["掲載日・開催日が本文で確認できない"]),
        ],
    ),
    dict(
        source="demo-boshi-html", path="files/report-2026.pdf", host="files.boshi.example.net",
        title="【架空】乳幼児の発育に関する調査報告書（PDF）",
        published=None,  # 日付不明かつ画像PDF
        updated=None, seen="2026-09-14",
        versions=[("2026-09-14", "unsupported", "画像PDFのためテキストを抽出できない（OCRは対象外）")],
        status="unsupported",
        summaries=[("skipped_no_content", 1, "本文を取得できないため要約しない")],
    ),
    dict(
        source="demo-boshi-html", path="20260916.html",
        title="【架空】低出生体重児の支援に関する手引き（改訂版）",
        published=("2026-09-16", "day", "html_text", "掲載日：2026年9月16日"),
        updated=("2026-09-25", "day", "html_text", "改訂：2026年9月25日"),
        seen="2026-09-21",
        versions=[("2026-09-21", "ok", None), ("2026-09-28", "ok", None)], status="active",
        # 2版あり。要約は版1のみ（版2は未要約＝要約が古い）
        summaries=[
            ("success", 1, "【架空】低出生体重児の家庭への支援手順をまとめた手引きの改訂版が公開された。",
             ["退院後の訪問支援", "関係機関との連携"], ["市区町村", "医療機関"], [],
             [("maternal-child-health", "低出生体重児の支援に関する内容のため")], []),
            ("pending", 2, None),
        ],
    ),
    dict(
        source="demo-boshi-html", path="20260922.html",
        title="【架空】こどもの事故予防に関する啓発資料",
        published=("2026-09", "month", "listing_text", "2026年9月"),
        updated=None, seen="2026-09-28",
        versions=[("2026-09-28", "ok", None)], status="active",
        # タグ修正あり：AIタグなしのところに人が「子育て支援」を追加
        summaries=[
            ("success", 1, "【架空】家庭内でのこどもの事故を防ぐための啓発資料が公開された。",
             ["誤飲・転落の予防", "年齢別の注意点"], ["保護者", "保育施設"], [], [], []),
        ],
    ),
    dict(
        source="demo-jichitai-html", path="2026/0904.html",
        title="【架空】母子保健システムの標準仕様書（第2版）を公表",
        published=("2026-09-04", "day", "html_meta", '<meta name="date" content="2026-09-04">'),
        updated=None, seen="2026-09-07",
        versions=[("2026-09-07", "ok", None)], status="active",
        # タグ修正あり：AIの「制度改正」を除外
        summaries=[
            ("success", 1, "【架空】母子保健システムの標準仕様書第2版が公表された。帳票要件と連携項目が更新された。",
             ["帳票要件の更新", "データ連携項目の追加"], ["市区町村", "システム事業者"],
             [("適合期限", "2028-03-31", "令和10年3月31日までに標準仕様に適合")],
             [("municipal-dx-standardization", "システム標準化に関する内容のため"),
              ("maternal-child-health", "母子保健システムが対象のため"),
              ("system-revision", "仕様の改定のため")], []),
        ],
    ),
    dict(
        source="demo-jichitai-html", path="2026/0911.html",
        title="【架空】標準化移行に関する説明会の資料",
        published=("2026-09-11", "day", "html_meta", '<meta name="date" content="2026-09-11">'),
        updated=None, seen="2026-09-14",
        versions=[("2026-09-14", "failed", "HTTP 404（本文ページが見つからない）")],
        status="active",
        # 本文未取得
        summaries=[("skipped_no_content", 1, "本文を取得できないため要約しない")],
    ),
    dict(
        source="demo-jichitai-html", path="2026/0912-faq.html",
        title="【架空】標準化に関するよくある質問（更新）",
        published=("2026-09-12", "day", "html_meta", '<meta name="date" content="2026-09-12">'),
        updated=None, seen="2026-09-14",
        versions=[("2026-09-14", "failed", "タイムアウト（30秒）")],
        status="active",
        # 本文未取得・AI処理なし（要約レコードなし）
        summaries=[],
    ),
    dict(
        source="demo-tokei-rss", path="2026/0905-shussho.html",
        title="【架空】令和7年 出生に関する統計（速報）",
        published=("2026-09-05", "day", "rss_pubdate", "<pubDate>Sat, 05 Sep 2026 10:00:00 +0900</pubDate>"),
        updated=None, seen="2026-09-07",
        versions=[("2026-09-07", "ok", None)], status="active",
        summaries=[
            ("success", 1, "【架空】令和7年の出生に関する速報値が公表された。",
             ["出生数の推移", "都道府県別の集計"], ["一般"], [],
             [("survey-statistics", "統計の公表のため")], []),
        ],
    ),
    dict(
        source="demo-tokei-rss", path="2026/0912-hoiku-chosa.html",
        title="【架空】保育所等の利用状況調査の結果",
        published=("2026-09-12", "day", "rss_pubdate", "<pubDate>Sat, 12 Sep 2026 10:00:00 +0900</pubDate>"),
        updated=None, seen="2026-09-14",
        versions=[("2026-09-14", "ok", None)], status="active",
        summaries=[
            ("success", 1, "【架空】保育所等の利用状況に関する調査結果が公表された。待機児童数は前年から減少した。",
             ["利用率の上昇", "待機児童数の減少"], ["一般", "自治体"], [],
             [("survey-statistics", "調査結果の公表のため"), ("childcare-support", "保育の利用状況のため")], []),
        ],
    ),
    dict(
        source="demo-tokei-rss", path="2026/0919-kenshin-jisshi.html",
        title="【架空】乳幼児健診の実施状況（年報）",
        published=("2026-09-19", "day", "rss_pubdate", "<pubDate>Sat, 19 Sep 2026 10:00:00 +0900</pubDate>"),
        updated=None, seen="2026-09-21",
        versions=[("2026-09-21", "ok", None)], status="active",
        # API失敗後に再試行待ち
        summaries=[("failed_api_error", 1, "HTTP 529（APIが混雑）。再試行対象に登録")],
    ),
    dict(
        source="demo-tokei-rss", path="2026/0926-kosodate-ishiki.html",
        title="【架空】子育てに関する意識調査の結果",
        published=("2026", "year", "rss_pubdate", "<dc:date>2026</dc:date>"),
        updated=None, seen="2026-09-28",
        versions=[("2026-09-28", "ok", None)], status="active",
        summaries=[
            ("success", 1, "【架空】子育てに関する意識調査の結果が公表された。相談先の認知度が課題とされた。",
             ["相談先の認知度", "利用したい支援"], ["一般"], [],
             [("survey-statistics", "調査結果の公表のため"), ("childcare-support", "子育て支援に関する内容のため")], []),
        ],
    ),
]

TAG_OVERRIDES = {
    "2026/0917-qa.html": dict(add=["notice-admin-communication"], remove=["survey-statistics"],
                              reason="Q&Aは事務連絡として扱い、数値は付随的な情報のため（架空の修正例）"),
    "20260922.html": dict(add=["childcare-support"], reason="AIが該当タグなしとしたため追加（架空の修正例）"),
    "2026/0904.html": dict(remove=["system-revision"], reason="法令改正ではないため（架空の修正例）"),
}


def article_url(spec: dict) -> str:
    if "host" in spec:
        return f"https://{spec['host']}/{spec['path'].removeprefix('files/')}"
    return SOURCES[spec["source"]] + spec["path"]


def basis(entry):
    if entry is None:
        return None, None, "unknown"
    value, precision, method, evidence = entry
    return value, {"method": method, "evidence": evidence}, precision


def build_article(spec: dict) -> tuple[dict, dict | None, str]:
    url = article_url(spec)
    article_id = article_id_from_canonical_url(url)
    pub, pub_basis, pub_precision = basis(spec["published"])
    upd, upd_basis, upd_precision = basis(spec["updated"])
    versions = []
    for i, (date, status, error) in enumerate(spec["versions"], start=1):
        ok = status == "ok"
        versions.append({
            "article_id": article_id,
            "version": i,
            "content_hash": h(f"{url}#v{i}") if ok else None,
            "fetched_at": ts(date, "08:00:30"),
            "content_type": ("pdf" if url.endswith(".pdf") else "html") if status != "failed" else "none",
            "text_length": 800 + 150 * i if ok else None,
            "extraction_status": status,
            "extraction_error": error,
            "change_type": "new" if i == 1 else "content_changed",
        })
    article = {
        "article_id": article_id,
        "source_id": spec["source"],
        "canonical_url": url,
        "title": spec["title"],
        "published_at": pub,
        "updated_at": upd,
        "date_basis": {"published": pub_basis, "updated": upd_basis},
        "date_precision": {"published": pub_precision, "updated": upd_precision},
        "first_seen_at": ts(spec["seen"]),
        "last_seen_at": ts(spec["versions"][-1][0]),
        "latest_version": len(versions),
        "status": spec["status"],
    }
    summaries = []
    for entry in spec["summaries"]:
        version = entry[1]
        processed = ts(spec["versions"][version - 1][0], "08:10:00")
        record = {
            "article_id": article_id, "article_version": version,
            "provider": PROVIDER, "model": MODEL, "prompt_version": PROMPT_VERSION, "tags_version": TAGS_VERSION,
            "processed_at": processed,
        }
        if entry[0] == "success":
            _, _, summary, points, targets, dates, tags, unc = entry
            record.update(
                analysis_status="success", error=None, summary=summary, key_points=points, targets=targets,
                dates=[{"label": l, "value": v, "evidence": e} for l, v, e in dates],
                ai_tags=[{"tag_id": t, "reason": r} for t, r in tags], uncertainties=unc,
                usage={"input_tokens": 1800, "output_tokens": 320, "retries": 0, "estimated_cost_usd": 0.005},
            )
        else:
            status, _, error = entry
            record.update(
                analysis_status=status, error=error, summary=None, key_points=None, targets=None,
                dates=None, ai_tags=None, uncertainties=None,
                usage={"input_tokens": None, "output_tokens": None,
                       "retries": 2 if status == "failed_api_error" else 0, "estimated_cost_usd": None},
            )
            if status in ("skipped_no_api_key", "skipped_no_content", "pending"):
                record.update(provider=None if status == "skipped_no_api_key" else PROVIDER)
        summaries.append(dict(sorted(record.items(), key=lambda kv: SUMMARY_ORDER.index(kv[0]))))
    summary_file = {"schema_version": 1, "article_id": article_id, "summaries": summaries} if summaries else None
    return {"schema_version": 1, "article": article, "versions": versions}, summary_file, article_id


SUMMARY_ORDER = [
    "article_id", "article_version", "analysis_status", "error", "summary", "key_points", "targets", "dates",
    "ai_tags", "uncertainties", "provider", "model", "prompt_version", "tags_version", "usage", "processed_at",
]


def source_result(source_id, status, candidates, new, changed, unchanged, date_unknown=0, fetch_failed=0,
                  warnings=(), error=None):
    return {"source_id": source_id, "status": status, "candidates": candidates, "new": new, "changed": changed,
            "unchanged": unchanged, "date_unknown": date_unknown, "fetch_failed": fetch_failed,
            "warnings": list(warnings), "error": error}


def build_runs() -> list[dict]:
    runs = []

    def run(run_id, date, status, period, sources, summarized, summarize_failed, failures, requests, cost):
        totals = {k: sum(s[k] for s in sources) for k in ("new", "changed", "unchanged", "date_unknown", "fetch_failed")}
        totals.update(summarized=summarized, summarize_failed=summarize_failed)
        runs.append({"schema_version": 1, "run": {
            "run_id": run_id, "started_at": ts(date, "08:00:00"), "finished_at": ts(date, "08:12:00"),
            "status": status, "trigger": "manual_cli", "kind": "collect_and_summarize", "period": period,
            "sources": sources, "totals": totals, "failures": failures,
            "api_usage": {"requests": requests, "input_tokens": requests * 1800, "output_tokens": requests * 320,
                          "estimated_cost_usd": cost},
        }})

    run("run_20260906T230000Z", "2026-09-07", "success", {"start": "2026-08-24", "end": "2026-09-07"}, [
        source_result("demo-kodomo-rss", "success", 12, 2, 0, 10),
        source_result("demo-boshi-html", "success", 8, 1, 0, 7),
        source_result("demo-jichitai-html", "success", 6, 1, 0, 5),
        source_result("demo-tokei-rss", "success", 9, 1, 0, 8),
    ], 5, 0, [], 5, 0.025)
    run("run_20260913T230000Z", "2026-09-14", "partial", None, [
        source_result("demo-kodomo-rss", "success", 12, 2, 0, 10),
        source_result("demo-boshi-html", "success", 9, 2, 0, 7, date_unknown=2),
        source_result("demo-jichitai-html", "success", 7, 2, 0, 5, fetch_failed=2),
        source_result("demo-tokei-rss", "success", 9, 1, 0, 8),
    ], 5, 0, [
        {"source_id": "demo-jichitai-html", "url": "https://hyojunka.example.com/topics/2026/0911.html",
         "stage": "fetch", "reason": "HTTP 404"},
        {"source_id": "demo-jichitai-html", "url": "https://hyojunka.example.com/topics/2026/0912-faq.html",
         "stage": "fetch", "reason": "タイムアウト（30秒）"},
    ], 5, 0.025)
    run("run_20260920T230000Z", "2026-09-21", "partial", None, [
        source_result("demo-kodomo-rss", "success", 12, 2, 1, 9),
        source_result("demo-boshi-html", "success", 9, 1, 0, 8),
        source_result("demo-jichitai-html", "failed", 0, 0, 0, 0, error="一覧ページがタイムアウト（30秒）"),
        source_result("demo-tokei-rss", "success", 9, 1, 0, 8),
    ], 3, 2, [
        {"source_id": "demo-jichitai-html", "url": "https://hyojunka.example.com/topics/", "stage": "list",
         "reason": "タイムアウト（30秒）"},
        {"article_id": article_id_from_canonical_url(SOURCES["demo-tokei-rss"] + "2026/0919-kenshin-jisshi.html"),
         "stage": "summarize", "reason": "HTTP 529（APIが混雑）"},
    ], 5, 0.02)
    run("run_20260927T230000Z", "2026-09-28", "partial", None, [
        source_result("demo-kodomo-rss", "success", 12, 2, 0, 10),
        source_result("demo-boshi-html", "success", 10, 1, 1, 8),
        source_result("demo-jichitai-html", "failed", 0, 0, 0, 0, error="一覧ページがタイムアウト（30秒）"),
        source_result("demo-tokei-rss", "success", 9, 1, 0, 8, warnings=["新着が前回より大きく減少（架空の警告例）"]),
    ], 3, 1, [
        {"source_id": "demo-jichitai-html", "url": "https://hyojunka.example.com/topics/", "stage": "list",
         "reason": "タイムアウト（30秒）"},
    ], 4, 0.02)
    return runs


def build_state() -> dict:
    def state(source_id, last_success, last_attempt, status, oldest, newest, pages, retry=(), failures=0):
        return {
            "source_id": source_id, "last_success_at": last_success, "last_attempt_at": last_attempt,
            "last_attempt_status": status,
            "explored_range": {"oldest": oldest, "newest": newest, "pages": pages},
            "retry_queue": list(retry), "consecutive_failures": failures,
        }

    last = ts("2026-09-28", "08:00:00")
    return {"schema_version": 1, "sources": {
        "demo-kodomo-rss": state("demo-kodomo-rss", ts("2026-09-28", "08:01:00"), last, "success",
                                 "2026-08-20", "2026-09-25", 1),
        "demo-boshi-html": state("demo-boshi-html", ts("2026-09-28", "08:03:00"), last, "success",
                                 "2026-07-01", "2026-09-22", 3),
        # 失敗が続いている情報源：成功地点（last_success_at）は最後に成功した 9/14 のまま
        "demo-jichitai-html": state(
            "demo-jichitai-html", ts("2026-09-14", "08:05:00"), last, "failed", "2026-08-01", "2026-09-12", 2,
            retry=[
                {"url": "https://hyojunka.example.com/topics/2026/0912-faq.html",
                 "article_id": article_id_from_canonical_url(SOURCES["demo-jichitai-html"] + "2026/0912-faq.html"),
                 "stage": "fetch", "reason": "タイムアウト（30秒）",
                 "first_failed_at": ts("2026-09-14", "08:04:00"), "attempts": 1},
            ],
            failures=2),
        "demo-tokei-rss": state("demo-tokei-rss", ts("2026-09-28", "08:06:00"), last, "success",
                                "2026-06-01", "2026-09-26", 1,
                                retry=[
                                    {"url": SOURCES["demo-tokei-rss"] + "2026/0919-kenshin-jisshi.html",
                                     "article_id": article_id_from_canonical_url(
                                         SOURCES["demo-tokei-rss"] + "2026/0919-kenshin-jisshi.html"),
                                     "stage": "summarize", "reason": "HTTP 529（APIが混雑）",
                                     "first_failed_at": ts("2026-09-21", "08:10:00"), "attempts": 3},
                                ]),
    }}


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    if DEMO_DATA.exists():
        shutil.rmtree(DEMO_DATA)
    ids_by_path = {}
    for spec in ARTICLES:
        article_file, summary_file, article_id = build_article(spec)
        ids_by_path[spec["path"]] = article_id
        write_json(DEMO_DATA / "articles" / f"{article_id}.json", article_file)
        if summary_file:
            write_json(DEMO_DATA / "summaries" / f"{article_id}.json", summary_file)
    for run in build_runs():
        write_json(DEMO_DATA / "runs" / f"{run['run']['run_id']}.json", run)
    write_json(DEMO_DATA / "state.json", build_state())
    # タグ候補：記録するだけで画面には出さない（公開用変換のテストで確認する）
    write_json(DEMO_DATA / "tag_candidates.json", {"schema_version": 1, "candidates": [
        {"name": "【架空候補】産後ケア", "reason": "産後ケアに関する記事が複数あるため",
         "article_id": ids_by_path["2026/0917-qa.html"], "first_seen_at": ts("2026-09-21", "08:10:00")},
        {"name": "【架空候補】事故予防", "reason": "既存タグに該当がないため",
         "article_id": ids_by_path["20260922.html"], "first_seen_at": ts("2026-09-28", "08:10:00")},
    ]})

    overrides = [
        {"article_id": ids_by_path[path], **{k: v for k, v in o.items() if k != "reason"},
         "updated": "2026-09-29", "reason": o["reason"]}
        for path, o in TAG_OVERRIDES.items()
    ]
    lines = [
        "# 架空データ用のタグ修正（demo/data の記事に対応）。scripts/make_demo_data.py が生成する。",
        "overrides:",
    ]
    for o in overrides:
        lines.append(f"  - article_id: {o['article_id']}")
        for key in ("add", "remove"):
            if key in o:
                lines.append(f"    {key}: [{', '.join(o[key])}]")
        lines.append(f"    updated: {o['updated']}")
        lines.append(f"    reason: {o['reason']}")
    (REPO_ROOT / "demo" / "config" / "tag_overrides.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"demo/data に記事 {len(ARTICLES)} 件を作成しました")


if __name__ == "__main__":
    main()
