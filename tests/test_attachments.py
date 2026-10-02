"""記事ページにリンクされた添付PDFの読み取りのテスト（架空のサイトのみ）。"""

from datetime import date, datetime

import pytest

from collector import collect as col
from collector import export as ex
from collector.dates import JST
from collector.extract import extract_html
from collector.fetch import FixtureFetcher
from collector.validation import article_id_from_canonical_url, validate_all, validate_config
from conftest import REPO_ROOT, read_json, read_yaml, write_yaml

WEB = REPO_ROOT / "tests" / "fixtures" / "web"
CONFIG_DIR = REPO_ROOT / "config"
OVERLAY = WEB / "attach_config"
P1 = article_id_from_canonical_url("https://attach.example.org/press/p1.html")


@pytest.fixture
def config():
    cfg, report = validate_config(CONFIG_DIR, overlay_dir=OVERLAY)
    assert report.errors == []
    return cfg


@pytest.fixture
def fetcher():
    return FixtureFetcher.from_manifest(WEB / "attach-manifest.yaml")


def run(config, data, fetcher, day, overlay=OVERLAY):
    # 記事の公開日（9/10）を含む期間を指定する（週次の既定期間だと再実行時に範囲外になるため）
    options = col.Options(now=datetime(2026, 10, day, 8, 0, tzinfo=JST), start=date(2026, 9, 1), end=date(2026, 9, 30),
                          cache_dir=data.parent / "cache")
    return col.collect(config, data, fetcher, options, config_dir=CONFIG_DIR, overlay_dir=overlay)


def test_pdf_links_only_in_main_content():
    e = extract_html((WEB / "attach-page.html").read_bytes(), "https://attach.example.org/press/p1.html")
    urls = [u for u, _ in e.pdf_links]
    assert urls == [
        "https://attach.example.org/files/report.pdf",
        "https://attach.example.org/files/scan.pdf",
        "https://other.example.com/x.pdf",
        "https://attach.example.org/files/extra.pdf",
    ], "ナビのPDFは含めず、#page= 付きの重複は1件にまとめる"


def test_attachments_are_read_and_recorded(config, fetcher, tmp_path):
    data = tmp_path / "data"
    run(config, data, fetcher, 2)
    version = read_json(data / "articles" / f"{P1}.json")["versions"][0]
    assert version["extraction_profile"] == "html+pdf(3files,30pages)"
    statuses = [(a["url"].rsplit("/", 1)[1], a["status"]) for a in version["attachments"]]
    assert statuses == [
        ("report.pdf", "ok"),
        ("scan.pdf", "unsupported"),  # 画像PDF
        ("x.pdf", "skipped"),         # 許可ホスト外
        ("extra.pdf", "skipped"),     # 1記事3件の上限を超えた
    ]
    assert version["attachments"][0]["title"] == "【架空】調査結果の概要（PDF／1KB）"
    assert "画像PDF" in version["attachments"][1]["error"]
    assert "上限（3件）" in version["attachments"][3]["error"]
    assert version["attachments"][0]["pages"] == 1
    # PDF の本文は .cache にだけ入る（data/ には入らない）
    cached = (tmp_path / "cache" / "text" / f"{P1}_v1.txt").read_text(encoding="utf-8")
    assert "[添付PDF]【架空】調査結果の概要" in cached  # 全角記号は正規化される and "Fictional survey report" in cached
    assert "Fictional survey report" not in (data / "articles" / f"{P1}.json").read_text(encoding="utf-8")
    assert "https://other.example.com/x.pdf" not in fetcher.requested
    assert validate_all(CONFIG_DIR, data, overlay_dir=OVERLAY).errors == []


def test_rerun_without_changes_keeps_one_version(config, fetcher, tmp_path):
    data = tmp_path / "data"
    run(config, data, fetcher, 2)
    r = run(config, data, fetcher, 3)
    assert r["sources"][0]["changed"] == 0
    assert read_json(data / "articles" / f"{P1}.json")["article"]["latest_version"] == 1


def test_replaced_pdf_adds_content_version(config, fetcher, tmp_path):
    data = tmp_path / "data"
    run(config, data, fetcher, 2)
    replaced = fetcher.override({"https://attach.example.org/files/report.pdf": {"file": "report2.pdf", "type": "application/pdf"}})
    r = run(config, data, replaced, 3)
    assert r["sources"][0]["changed"] == 1
    versions = read_json(data / "articles" / f"{P1}.json")["versions"]
    assert [v["change_type"] for v in versions] == ["new", "content_changed"]


def test_failed_pdf_does_not_create_spurious_version(config, fetcher, tmp_path):
    data = tmp_path / "data"
    run(config, data, fetcher, 2)
    broken = fetcher.override({"https://attach.example.org/files/report.pdf": {"status": 503}})
    r = run(config, data, broken, 3)
    res = r["sources"][0]
    assert res["changed"] == 0 and res["fetch_failed"] == 1
    assert read_json(data / "articles" / f"{P1}.json")["article"]["latest_version"] == 1
    queue = read_json(data / "state.json")["sources"]["fx-attach"]["retry_queue"]
    assert queue[0]["url"] == "https://attach.example.org/press/p1.html" and "添付PDF" in queue[0]["reason"]
    # 回復すると再試行対象から外れ、内容は同じなので版は増えない
    run(config, data, fetcher, 4)
    assert read_json(data / "state.json")["sources"]["fx-attach"]["retry_queue"] == []
    assert read_json(data / "articles" / f"{P1}.json")["article"]["latest_version"] == 1


def test_turning_on_pdf_marks_extraction_change(config, fetcher, tmp_path):
    """添付PDFを読む設定にした後の版は「抽出方法の変更」として記録し、原文の変更として数えない。"""
    data = tmp_path / "data"
    off = tmp_path / "off"
    off.mkdir()
    sources = read_yaml(OVERLAY / "sources.yaml")
    sources["sources"][0].pop("attachments")
    write_yaml(off / "sources.yaml", sources)
    cfg_off, _ = validate_config(CONFIG_DIR, overlay_dir=off)
    run(cfg_off, data, fetcher, 2, overlay=off)
    first = read_json(data / "articles" / f"{P1}.json")["versions"][0]
    assert "attachments" not in first and "extraction_profile" not in first

    r = run(config, data, fetcher, 3)
    res = r["sources"][0]
    assert res["changed"] == 0
    assert any("抽出方法の変更" in w for w in res["warnings"])
    versions = read_json(data / "articles" / f"{P1}.json")["versions"]
    assert [v["change_type"] for v in versions] == ["new", "extraction_changed"]


def test_attachments_flow_to_public_json(config, fetcher, tmp_path):
    data = tmp_path / "data"
    run(config, data, fetcher, 2)
    outputs = ex.build_public_data(config, data, "real", "2026-10-02T09:00:00+09:00")
    assert ex.check_public_data(outputs, environ={}) == []
    article = outputs["articles.json"]["articles"][0]
    assert [(a["status"], a["url"]) for a in article["attachments"]][:2] == [
        ("ok", "https://attach.example.org/files/report.pdf"),
        ("unsupported", "https://attach.example.org/files/scan.pdf"),
    ]
    assert "Fictional survey report" not in str(outputs), "PDFの本文は画面用JSONに出さない"


def test_source_schema_rejects_bad_attachment_settings(tmp_path):
    bad = tmp_path / "bad"
    bad.mkdir()
    sources = read_yaml(OVERLAY / "sources.yaml")
    sources["sources"][0]["attachments"] = {"pdf": True, "max_files": 100}
    write_yaml(bad / "sources.yaml", sources)
    _, report = validate_config(CONFIG_DIR, overlay_dir=bad)
    assert any("max_files" in e for e in report.errors)


def test_excluded_titles_are_not_counted(fetcher, tmp_path):
    custom = tmp_path / "custom"
    custom.mkdir()
    sources = read_yaml(OVERLAY / "sources.yaml")
    sources["sources"][0]["attachments"] = {"pdf": True, "max_files": 1, "exclude_titles": ["概要"]}
    write_yaml(custom / "sources.yaml", sources)
    cfg, report = validate_config(CONFIG_DIR, overlay_dir=custom)
    assert report.errors == []
    data = tmp_path / "data"
    run(cfg, data, fetcher, 2, overlay=custom)
    atts = read_json(data / "articles" / f"{P1}.json")["versions"][0]["attachments"]
    assert [a["status"] for a in atts] == ["skipped", "unsupported", "skipped", "skipped"]
    assert "exclude_titles" in atts[0]["error"]
    assert "上限（1件）" in atts[2]["error"] or "取得対象外" in atts[2]["error"]
