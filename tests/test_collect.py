"""収集処理のテスト（tests/fixtures/web の架空のRSS・HTML・PDFだけを使い、実際のWebにはアクセスしない）。"""

from datetime import date, datetime
from pathlib import Path

import pytest

from collector import collect as col
from collector import export as ex
from collector.dates import JST, find_japanese_date, in_period, parse_any
from collector.extract import content_hash, extract_html, parse_feed, parse_html_listing
from collector.fetch import FetchError, FixtureFetcher, HttpFetcher
from collector.urls import UrlRejected, check_allowed, normalize_url
from collector.validation import article_id_from_canonical_url, validate_all, validate_config
from conftest import REPO_ROOT, read_json

WEB = REPO_ROOT / "tests" / "fixtures" / "web"
CONFIG_DIR = REPO_ROOT / "config"
OVERLAY = WEB / "config"
SEPT = (date(2026, 9, 1), date(2026, 9, 30))


def aid(url: str) -> str:
    return article_id_from_canonical_url(url)


A1 = aid("https://news.example.org/news/a1.html")
A2 = aid("https://news.example.org/news/a2.html")
A3 = aid("https://news.example.org/news/a3.html")
A4 = aid("https://news.example.org/news/a4.html")
A5 = aid("https://news.example.org/news/a5.html")
A6 = aid("https://news.example.org/news/a6.html")
MISSING = aid("https://news.example.org/news/missing.html")
SCAN = aid("https://files.example.net/scan.pdf")
REPORT = aid("https://files.example.net/report.pdf")


@pytest.fixture
def config():
    cfg, report = validate_config(CONFIG_DIR, overlay_dir=OVERLAY)
    assert report.errors == []
    return cfg


@pytest.fixture
def fetcher():
    return FixtureFetcher.from_manifest(WEB / "manifest.yaml")


def run(config, data_dir: Path, fetcher, day: int, *, period=SEPT, sources=None, cache=None) -> dict:
    options = col.Options(
        now=datetime(2026, 10, day, 8, 0, tzinfo=JST),
        start=period[0] if period else None, end=period[1] if period else None,
        source_ids=sources, cache_dir=cache,
    )
    return col.collect(config, data_dir, fetcher, options, config_dir=CONFIG_DIR, overlay_dir=OVERLAY)


def article(data_dir: Path, article_id: str) -> dict:
    return read_json(data_dir / "articles" / f"{article_id}.json")


def result_of(run_record: dict, source_id: str) -> dict:
    return next(s for s in run_record["sources"] if s["source_id"] == source_id)


# ---------------------------------------------------------------- URL


@pytest.mark.parametrize(
    "url, expected",
    [
        ("HTTPS://News.Example.org:443/a.html#top", "https://news.example.org/a.html"),
        ("https://news.example.org/a.html?utm_source=x&id=3&fbclid=y", "https://news.example.org/a.html?id=3"),
        ("https://news.example.org/a.html?page=2&id=3", "https://news.example.org/a.html?page=2&id=3"),
        ("http://news.example.org:8080/a", "http://news.example.org:8080/a"),
        ("https://news.example.org", "https://news.example.org/"),
    ],
)
def test_normalize_url(url, expected):
    assert normalize_url(url) == expected


def test_normalize_relative_url():
    assert normalize_url("../b.html", "https://news.example.org/x/y/a.html") == "https://news.example.org/x/b.html"


@pytest.mark.parametrize(
    "url",
    ["javascript:alert(1)", "file:///etc/passwd", "ftp://news.example.org/a", "https://user:pw@news.example.org/",
     "mailto:a@example.org"],
)
def test_reject_non_http(url):
    with pytest.raises(UrlRejected):
        normalize_url(url)


@pytest.mark.parametrize(
    "url",
    ["https://other.example.org/a", "http://localhost/a", "http://127.0.0.1/a", "http://10.0.0.1/a",
     "http://169.254.169.254/latest/meta-data", "http://[::1]/a", "https://news.example.org.evil.example.com/a"],
)
def test_check_allowed_rejects(url):
    with pytest.raises(UrlRejected):
        check_allowed(url, ["news.example.org", "localhost", "127.0.0.1", "10.0.0.1", "169.254.169.254"])


def test_check_allowed_accepts():
    assert check_allowed("https://NEWS.example.org/a?utm_x=1", ["news.example.org"]) == "https://news.example.org/a"


# ---------------------------------------------------------------- 日付


@pytest.mark.parametrize(
    "text, value, precision",
    [
        ("Tue, 01 Sep 2026 10:00:00 +0900", "2026-09-01T10:00:00+09:00", "datetime"),
        ("2026-09-12", "2026-09-12", "day"),
        ("2026-09", "2026-09", "month"),
        ("2026-09-30T15:30:00Z", "2026-09-30T15:30:00+00:00", "datetime"),
        ("令和8年9月5日", "2026-09-05", "day"),
        ("令和元年5月1日", "2019-05-01", "day"),
        ("平成31年4月30日", "2019-04-30", "day"),
        ("２０２６年９月１５日", "2026-09-15", "day"),
        ("2026/09/15", "2026-09-15", "day"),
        ("2026年9月", "2026-09", "month"),
    ],
)
def test_parse_dates(text, value, precision):
    parsed = parse_any(text)
    assert (parsed.value, parsed.precision) == (value, precision)


@pytest.mark.parametrize("text", ["", "日付なし", "2026年13月40日", "9月5日"])
def test_unparseable_dates(text):
    assert parse_any(text) is None


@pytest.mark.parametrize(
    "text, expected",
    [
        ("2026-09-01T00:00:00+09:00", True),   # 開始日 0時ちょうど（含む）
        ("2026-08-31T23:59:59+09:00", False),  # 開始日の前
        ("2026-09-30T23:59:59+09:00", True),   # 終了日の最後（含む）
        ("2026-10-01T00:00:00+09:00", False),  # 終了日の翌日0時（含まない）
        ("2026-09-30T15:00:00Z", False),       # UTC 15時 = 日本時間 10/1 0時
        ("2026-09-30T14:59:59Z", True),
        ("2026-09-30", True),
        ("2026-08", False),
        ("2026-09", True),
        ("2026", True),                         # 精度が年：期間と重なる
    ],
)
def test_period_boundaries_jst(text, expected):
    assert in_period(parse_any(text), *SEPT) is expected


def test_unknown_date_is_not_in_period():
    assert in_period(None, *SEPT) is None


# ---------------------------------------------------------------- 一覧・本文の抽出


def test_parse_rss_dedup_and_normalize():
    listing = parse_feed((WEB / "rss.xml").read_bytes(), "https://news.example.org/rss.xml")
    urls = [c.url for c in listing.candidates]
    assert urls.count("https://news.example.org/news/a1.html") == 2  # 正規化後に同じURL（収集時に1件にまとめる）
    assert listing.candidates[0].listing_date[1] == "rss_pubdate"


def test_parse_rdf_and_atom():
    rdf = b"""<?xml version="1.0"?><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns="http://purl.org/rss/1.0/" xmlns:dc="http://purl.org/dc/elements/1.1/">
      <item rdf:about="https://news.example.org/r.html"><title>r</title><link>https://news.example.org/r.html</link><dc:date>2026-09-03T10:00:00+09:00</dc:date></item></rdf:RDF>"""
    c = parse_feed(rdf, "https://news.example.org/").candidates[0]
    assert c.listing_date[0].value == "2026-09-03T10:00:00+09:00"
    assert "dc:date" in c.listing_date[2]
    atom = b"""<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>a</title><link href="/at.html"/><published>2026-09-04</published></entry></feed>"""
    c = parse_feed(atom, "https://news.example.org/feed").candidates[0]
    assert c.url == "https://news.example.org/at.html" and c.listing_date[0].value == "2026-09-04"


def test_rss_with_external_entity_is_rejected():
    evil = b"""<?xml version="1.0"?><!DOCTYPE r [<!ENTITY x SYSTEM "file:///etc/passwd">]><rss><channel><item><title>&x;</title><link>https://news.example.org/a</link></item></channel></rss>"""
    with pytest.raises(ValueError):
        parse_feed(evil, "https://news.example.org/")


def test_html_listing_scope_rules_and_next_page():
    listing = parse_html_listing(
        (WEB / "list1.html").read_bytes(), "https://list.example.net/info/index.html",
        {"css_selector": "main .news-list", "include": [r"^https://list\.example\.net/info/\d{8}\.html$", r"^https://files\.example\.net/.+\.pdf$"]},
        "a.next",
    )
    urls = [c.url for c in listing.candidates]
    assert urls == [
        "https://list.example.net/info/20260905.html",
        "https://list.example.net/info/20260912.html",
        "https://files.example.net/report.pdf",
        "https://files.example.net/scan.pdf",
    ]
    dates = {c.url.rsplit("/", 1)[1]: c.listing_date and c.listing_date[0].value for c in listing.candidates}
    assert dates == {"20260905.html": "2026-09-05", "20260912.html": "2026-09-12", "report.pdf": "2026-09-15", "scan.pdf": None}
    assert listing.next_url == "https://list.example.net/info/index2.html"
    assert listing.rejected == ["javascript:void(0)"]


def test_navigation_change_does_not_change_hash():
    base = extract_html((WEB / "a1.html").read_bytes())
    nav = extract_html((WEB / "a1_navchange.html").read_bytes())
    changed = extract_html((WEB / "a1_changed.html").read_bytes())
    assert base.content_hash == nav.content_hash
    assert base.content_hash != changed.content_hash
    assert "メニュー" not in base.text and "トップ" not in base.text


def test_whitespace_only_change_does_not_change_hash():
    assert content_hash("本文 です\n\n次の行") == content_hash("本文　です\n次の行  ")


def test_labeled_dates_in_html():
    e = extract_html((WEB / "a1_changed.html").read_bytes())
    assert (e.published.value.value, e.published.method) == ("2026-09-10", "html_text")
    assert e.published.evidence.startswith("掲載日")
    assert e.updated.value.value == "2026-09-25"


def test_dates_in_body_are_not_used_as_published():
    """本文中の日付（施行日など）を公開日と取り違えない。"""
    e = extract_html("<main><p>令和9年4月1日から適用します。</p></main>".encode())
    assert e.published is None


def test_find_japanese_date_returns_evidence():
    assert find_japanese_date("掲載日：令和8年9月12日（土）")[1] == "令和8年9月12日"


# ---------------------------------------------------------------- 収集：期間・重複・日付不明・PDF


def test_collect_with_period(config, fetcher, tmp_path):
    data = tmp_path / "data"
    r = run(config, data, fetcher, 2, cache=tmp_path / "cache")
    news = result_of(r, "fx-news-rss")
    # a1（重複URLは1件）、a2（9/30 23:59）、a4（9/1 0:00）、a6（日付不明）、missing（取得失敗）
    assert (news["candidates"], news["new"], news["date_unknown"], news["fetch_failed"]) == (8, 5, 1, 1)
    files = {p.stem for p in (data / "articles").glob("*.json")}
    assert {A1, A2, A4, A6, MISSING} <= files
    assert not {A3, A5} & files, "期間外の記事は保存しない（日本時間の日付境界）"
    assert any("evil.example.com" in w for w in news["warnings"])
    assert validate_all(CONFIG_DIR, data, overlay_dir=OVERLAY).errors == []
    # 原文本文は .cache にだけ保存し、data/ には入れない
    assert (tmp_path / "cache" / "text" / f"{A1}_v1.txt").exists()
    assert "問診項目" not in (data / "articles" / f"{A1}.json").read_text(encoding="utf-8")


def test_date_basis_and_precision(config, fetcher, tmp_path):
    data = tmp_path / "data"
    run(config, data, fetcher, 2)
    a1 = article(data, A1)["article"]
    assert a1["published_at"] == "2026-09-10T10:00:00+09:00"
    assert a1["date_basis"]["published"]["method"] == "rss_pubdate"
    assert a1["date_precision"]["published"] == "datetime"
    a6 = article(data, A6)["article"]
    assert a6["published_at"] is None and a6["date_precision"]["published"] == "unknown"
    assert a6["date_basis"]["published"] is None
    meta = article(data, aid("https://list.example.net/info/20260912.html"))["article"]
    assert meta["date_basis"]["published"]["method"] == "html_meta"
    report = article(data, REPORT)
    assert report["article"]["date_basis"]["published"]["method"] == "pdf_text"
    assert report["article"]["title"] == "【架空】調査報告書（PDF）"
    assert report["versions"][0]["content_type"] == "pdf"


def test_image_pdf_is_unsupported(config, fetcher, tmp_path):
    data = tmp_path / "data"
    run(config, data, fetcher, 2)
    scan = article(data, SCAN)
    assert scan["article"]["status"] == "unsupported"
    assert scan["versions"][0]["extraction_status"] == "unsupported"
    assert "画像PDF" in scan["versions"][0]["extraction_error"]
    assert scan["versions"][0]["content_hash"] is None


def test_listing_date_outside_period_is_not_fetched(config, fetcher, tmp_path):
    run(config, tmp_path / "data", fetcher, 2)
    assert "https://list.example.net/info/20260820.html" not in fetcher.requested
    assert "https://news.example.org/news/a5.html" not in fetcher.requested


def test_pagination_reads_second_page(config, fetcher, tmp_path):
    data = tmp_path / "data"
    r = run(config, data, fetcher, 2)
    assert (data / "articles" / f"{aid('https://list.example.net/info/20260918.html')}.json").exists()
    assert read_json(data / "state.json")["sources"]["fx-list-html"]["explored_range"]["pages"] == 2
    assert result_of(r, "fx-list-html")["new"] == 5


# ---------------------------------------------------------------- 再実行：重複しない・版・ナビの変化


def test_rerun_does_not_duplicate(config, fetcher, tmp_path):
    data = tmp_path / "data"
    run(config, data, fetcher, 2)
    before = sorted(p.name for p in (data / "articles").glob("*.json"))
    r = run(config, data, fetcher, 3)
    assert sorted(p.name for p in (data / "articles").glob("*.json")) == before
    news = result_of(r, "fx-news-rss")
    assert news["new"] == 0 and news["changed"] == 0
    assert article(data, A1)["article"]["latest_version"] == 1
    assert article(data, A1)["article"]["first_seen_at"] == "2026-10-02T08:00:00+09:00"
    assert article(data, A1)["article"]["last_seen_at"] == "2026-10-03T08:00:00+09:00"


def test_body_change_adds_version(config, fetcher, tmp_path):
    data = tmp_path / "data"
    run(config, data, fetcher, 2)
    changed = fetcher.override({"https://news.example.org/news/a1.html": {"file": "a1_changed.html"}})
    r = run(config, data, changed, 3, sources=["fx-news-rss"])
    assert result_of(r, "fx-news-rss")["changed"] == 1
    f = article(data, A1)
    assert [v["change_type"] for v in f["versions"]] == ["new", "content_changed"]
    assert f["versions"][0]["content_hash"] != f["versions"][1]["content_hash"]
    assert f["article"]["latest_version"] == 2
    assert f["article"]["updated_at"] == "2026-09-25"
    assert f["article"]["date_basis"]["updated"]["evidence"].startswith("最終更新日")
    assert f["article"]["first_seen_at"] == "2026-10-02T08:00:00+09:00", "初めて見つけた日は変えない"


def test_navigation_only_change_is_not_a_new_version(config, fetcher, tmp_path):
    data = tmp_path / "data"
    run(config, data, fetcher, 2)
    nav = fetcher.override({"https://news.example.org/news/a1.html": {"file": "a1_navchange.html"}})
    r = run(config, data, nav, 3, sources=["fx-news-rss"])
    assert result_of(r, "fx-news-rss")["changed"] == 0
    assert article(data, A1)["article"]["latest_version"] == 1


def test_past_data_is_not_deleted(config, fetcher, tmp_path):
    """一覧から消えた記事も、過去のデータとして残す。"""
    data = tmp_path / "data"
    run(config, data, fetcher, 2)
    gone = fetcher.override({"https://news.example.org/rss.xml": {"file": "empty-rss.xml", "type": "application/rss+xml"}})
    run(config, data, gone, 3, sources=["fx-news-rss"])
    assert (data / "articles" / f"{A1}.json").exists()
    assert len(list((data / "runs").glob("*.json"))) == 2


# ---------------------------------------------------------------- 部分失敗・state・再試行・警告


def test_partial_failure_keeps_success_point(config, fetcher, tmp_path):
    data = tmp_path / "data"
    r1 = run(config, data, fetcher, 2)
    assert r1["status"] == "partial"
    state = read_json(data / "state.json")["sources"]
    assert state["fx-news-rss"]["last_success_at"] == "2026-10-02T08:00:00+09:00"
    assert state["fx-broken"]["last_success_at"] is None
    assert state["fx-broken"]["consecutive_failures"] == 1
    assert "HTTP 500" in result_of(r1, "fx-broken")["error"]

    # 次の回：news は一覧が失敗、broken は回復
    flipped = fetcher.override({
        "https://news.example.org/rss.xml": {"timeout": True},
        "https://broken.example.com/list.html": {"file": "empty-list.html"},
    })
    run(config, data, flipped, 9)
    state = read_json(data / "state.json")["sources"]
    assert state["fx-news-rss"]["last_success_at"] == "2026-10-02T08:00:00+09:00", "失敗した情報源の成功地点は進めない"
    assert state["fx-news-rss"]["last_attempt_status"] == "failed"
    assert state["fx-news-rss"]["consecutive_failures"] == 1
    assert state["fx-broken"]["last_success_at"] == "2026-10-09T08:00:00+09:00"
    assert state["fx-broken"]["consecutive_failures"] == 0
    # 成功した分の記事は保存されている
    assert (data / "articles" / f"{A1}.json").exists()


def test_second_page_failure_marks_source_failed_but_keeps_first_page(config, fetcher, tmp_path):
    data = tmp_path / "data"
    broken = fetcher.override({"https://list.example.net/info/index2.html": {"status": 503}})
    r = run(config, data, broken, 2, sources=["fx-list-html"])
    res = result_of(r, "fx-list-html")
    assert res["status"] == "failed" and "2ページ目" in res["error"]
    assert (data / "articles" / f"{aid('https://list.example.net/info/20260905.html')}.json").exists()
    assert read_json(data / "state.json")["sources"]["fx-list-html"]["last_success_at"] is None


def test_retry_queue(config, fetcher, tmp_path):
    data = tmp_path / "data"
    run(config, data, fetcher, 2, sources=["fx-news-rss"])
    queue = read_json(data / "state.json")["sources"]["fx-news-rss"]["retry_queue"]
    assert [(q["url"], q["stage"], q["attempts"]) for q in queue] == [("https://news.example.org/news/missing.html", "fetch", 1)]
    missing = article(data, MISSING)
    assert missing["versions"][0]["extraction_status"] == "failed"
    assert missing["versions"][0]["extraction_error"] == "HTTP 404"

    # 再び失敗：回数が増える
    run(config, data, fetcher, 3, sources=["fx-news-rss"])
    queue = read_json(data / "state.json")["sources"]["fx-news-rss"]["retry_queue"]
    assert queue[0]["attempts"] == 2 and queue[0]["first_failed_at"] == "2026-10-02T08:00:00+09:00"

    # 回復：本文の版が追加され、再試行対象から外れる
    fixed = fetcher.override({"https://news.example.org/news/missing.html": {"file": "a4.html"}})
    run(config, data, fixed, 4, sources=["fx-news-rss"])
    assert read_json(data / "state.json")["sources"]["fx-news-rss"]["retry_queue"] == []
    versions = article(data, MISSING)["versions"]
    assert [v["extraction_status"] for v in versions] == ["failed", "ok"]


def test_zero_candidates_warning(config, fetcher, tmp_path):
    r = run(config, tmp_path / "data", fetcher, 2, sources=["fx-empty-rss"])
    res = result_of(r, "fx-empty-rss")
    assert res["status"] == "success" and res["candidates"] == 0
    assert any("1件も抽出できません" in w for w in res["warnings"])


def test_sharp_drop_warning(config, fetcher, tmp_path):
    data = tmp_path / "data"
    run(config, data, fetcher, 2, sources=["fx-news-rss"])
    one = fetcher.override({"https://news.example.org/rss.xml": {"file": "rss-one.xml", "type": "application/rss+xml"}})
    r = run(config, data, one, 3, sources=["fx-news-rss"])
    assert any("大きく減りました" in w for w in result_of(r, "fx-news-rss")["warnings"])


def test_redirect_to_disallowed_host_is_rejected(config, fetcher, tmp_path):
    data = tmp_path / "data"
    bad = fetcher.override({"https://news.example.org/news/a2.html": {"redirect": "https://evil.example.com/steal"}})
    r = run(config, data, bad, 2, sources=["fx-news-rss"])
    assert any("転送先" in f["reason"] for f in r["failures"])
    assert "https://evil.example.com/steal" not in bad.requested


def test_weekly_window_uses_success_point_with_overlap():
    state = {"last_success_at": "2026-09-28T08:00:00+09:00"}
    opts = col.Options(now=datetime(2026, 10, 5, 8, 0, tzinfo=JST))
    assert col.collection_window(state, opts) == (date(2026, 9, 14), date(2026, 10, 5))
    assert col.collection_window({"last_success_at": None}, opts) == (date(2026, 9, 5), date(2026, 10, 5))
    opts = col.Options(now=datetime(2026, 10, 5, 8, 0, tzinfo=JST), start=date(2026, 1, 1), end=date(2026, 1, 31))
    assert col.collection_window(state, opts) == (date(2026, 1, 1), date(2026, 1, 31))


def test_invalid_result_is_not_written(config, fetcher, tmp_path, monkeypatch):
    """保存前の検証に失敗したら data/ を変更しない。"""
    data = tmp_path / "data"
    run(config, data, fetcher, 2, sources=["fx-news-rss"])
    before = {p.name: p.read_bytes() for p in (data / "articles").glob("*.json")}
    original = col._new_article

    def broken(store, source, article_id, *args, **kwargs):
        original(store, source, article_id, *args, **kwargs)
        store.articles[article_id]["article"]["published_at"] = "壊れた日付"

    monkeypatch.setattr(col, "_new_article", broken)
    with pytest.raises(RuntimeError):
        run(config, data, fetcher, 3, sources=["fx-list-html"])
    assert {p.name: p.read_bytes() for p in (data / "articles").glob("*.json")} == before
    assert len(list((data / "runs").glob("*.json"))) == 1


# ---------------------------------------------------------------- 取得（実際のWebへは出ない）


def test_fixture_fetcher_never_uses_network(fetcher):
    with pytest.raises(FetchError, match="404"):
        fetcher.get("https://news.example.org/unknown", allowed_hosts=["news.example.org"], max_bytes=1000, timeout=1)


class FakeResponse:
    def __init__(self, status, body=b"", headers=None):
        self.status, self._body, self.headers = status, body, headers or {}

    def read(self, n):
        return self._body[:n]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_http_fetcher_checks_each_redirect_and_robots():
    import urllib.error

    calls = []

    def opener(req, timeout):
        url = req.full_url
        calls.append((url, req.headers.get("User-agent")))
        if url.endswith("/robots.txt"):
            return FakeResponse(200, b"User-agent: *\nDisallow: /private/\n")
        if url.endswith("/old"):
            raise urllib.error.HTTPError(url, 302, "Found", {"Location": "/new"}, None)
        if url.endswith("/away"):
            raise urllib.error.HTTPError(url, 302, "Found", {"Location": "https://evil.example.com/"}, None)
        return FakeResponse(200, b"<html>ok</html>", {"Content-Type": "text/html"})

    f = HttpFetcher(wait_seconds=0, opener=opener, sleep=lambda s: None)
    kw = dict(allowed_hosts=["news.example.org"], max_bytes=10_000, timeout=5)
    assert f.get("https://news.example.org/old", **kw).url == "https://news.example.org/new"
    assert all("info-test-rs-collector" in ua for _, ua in calls)
    with pytest.raises(FetchError, match="転送先"):
        f.get("https://news.example.org/away", **kw)
    with pytest.raises(FetchError, match="robots.txt"):
        f.get("https://news.example.org/private/x", **kw)
    assert not any("evil.example.com" in u for u, _ in calls)


def test_http_fetcher_size_limit():
    f = HttpFetcher(wait_seconds=0, opener=lambda req, timeout: FakeResponse(200, b"x" * 100), sleep=lambda s: None,
                    respect_robots=False)
    with pytest.raises(FetchError, match="サイズ上限"):
        f.get("https://news.example.org/big", allowed_hosts=["news.example.org"], max_bytes=10, timeout=5)


# ---------------------------------------------------------------- 画面用変換へ流れる


def test_collected_data_flows_to_public_json(config, fetcher, tmp_path):
    data = tmp_path / "data"
    run(config, data, fetcher, 2)
    outputs = ex.build_public_data(config, data, "real", "2026-10-02T09:00:00+09:00")
    assert ex.check_public_data(outputs, environ={}) == []
    articles = {a["id"]: a for a in outputs["articles.json"]["articles"]}
    assert len(articles) == 10
    a1 = articles[A1]
    assert a1["published"]["basis"]["method"] == "rss_pubdate"
    assert a1["summary"]["status"] == "not_processed", "AI処理前は未要約"
    assert articles[A6]["published"]["value"] is None
    assert articles[MISSING]["content_status"] == "failed"
    status = outputs["status.json"]
    assert status["counts"]["date_unknown"] == 2
    broken = next(s for s in status["sources"] if s["id"] == "fx-broken")
    assert broken["last_attempt_status"] == "failed" and "HTTP 500" in broken["last_run"]["error"]
    assert outputs["meta.json"]["is_demo"] is False
    week = outputs["reports.json"]["weeks"][0]
    assert week["counts"]["new"] == 10


def test_cli_requires_explicit_network_flag(capsys):
    with pytest.raises(SystemExit):
        col.main(["--data", "/nonexistent"])
    assert "--allow-network" in capsys.readouterr().err


def test_cli_with_fixtures(tmp_path, capsys):
    code = col.main(["--fixtures", str(WEB / "manifest.yaml"), "--config-dir", str(OVERLAY),
                     "--data", str(tmp_path / "data"), "--cache", str(tmp_path / "cache"),
                     "--start", "2026-09-01", "--end", "2026-09-30"])
    out = capsys.readouterr().out
    assert code == 0
    assert "新規 10件" in out and "fx-broken: failed" in out


def test_cli_rejects_bad_period(capsys):
    with pytest.raises(SystemExit):
        col.main(["--fixtures", str(WEB / "manifest.yaml"), "--start", "2026-09-30", "--end", "2026-09-01"])
    with pytest.raises(SystemExit):
        col.main(["--fixtures", str(WEB / "manifest.yaml"), "--start", "2026-09-01"])
