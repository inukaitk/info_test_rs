"""外部連携用CSVの content_hash（題名＋本文のSHA-256）の算出ルールのテスト。"""
import hashlib
import json
import unicodedata

import pytest

from collector import collect as col
from collector import spec_hash as sh


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_hash_is_sha256_of_normalized_title_newline_text_in_lowercase_hex_64():
    h = sh.spec_hash("題名", "本文")
    assert h == sha("題名\n本文")
    assert len(h) == 64 and h == h.lower() and not h.startswith("sha256:")


def test_normalization_rules():
    # Unicode は NFC（濁点を分解した形も、合成した形と同じハッシュになる）
    assert sh.spec_hash("が", "x") == sh.spec_hash(unicodedata.normalize("NFD", "が"), "x")
    # 改行は LF に統一
    assert sh.spec_hash("t", "a\r\nb\rc") == sh.spec_hash("t", "a\nb\nc")
    # 連続する半角空白・タブ・全角空白は半角空白1個。行の前後は除く
    assert sh.normalize_for_hash("  a \t　 b  \n\tc　") == "a b\nc"
    # 3行以上続く空行は2行に（空行が1〜2行ならそのまま）
    assert sh.normalize_for_hash("a\n\n\n\n\nb") == "a\n\n\nb"
    assert sh.normalize_for_hash("a\n\nb") == "a\n\nb" and sh.normalize_for_hash("a\n\n\nb") == "a\n\n\nb"
    # 空白だけの行は空行として数える
    assert sh.normalize_for_hash("a\n \n　\n\t\n \nb") == "a\n\n\nb"


def test_url_and_time_do_not_affect_the_hash_but_the_title_does():
    assert sh.spec_hash("t", "x") == sh.spec_hash("t", "x")
    assert sh.spec_hash("t1", "x") != sh.spec_hash("t2", "x")
    assert sh.spec_hash("t", "x") != sh.spec_hash("t", "y")


def test_hash_scope_tells_whether_attachments_were_added():
    assert sh.hash_scope("html", None) == "title+main_text"
    assert sh.hash_scope("html", [{"status": "skipped"}, {"status": "failed"}]) == "title+main_text"
    assert sh.hash_scope("html", [{"status": "ok"}]) == "title+main_text+attachments"
    assert sh.hash_scope("pdf", None) == "title+pdf_text"


def test_unavailable_when_text_is_missing_and_never_made_from_title_or_url():
    for status in ("failed", "unsupported", "not_fetched"):
        f = sh.hash_fields("題名", "", "html", status, None)
        assert f == {"export_hash": None, "export_hash_status": "unavailable", "export_hash_scope": None}
    assert sh.hash_fields("題名", "本文", "html", "unsupported", None)["export_hash"] is None
    ok = sh.hash_fields("題名", "本文", "html", "ok", None)
    assert ok["export_hash_status"] == "ok" and ok["export_hash_scope"] == "title+main_text"


def _article(tmp_path, status="ok", with_cache=True, with_hash=False):
    data = tmp_path / "data"
    (data / "articles").mkdir(parents=True)
    aid = "a_0123456789abcdef"
    version = {"version": 1, "extraction_status": status, "content_type": "html"}
    if with_hash:
        version.update(export_hash_status="ok", export_hash="0" * 64, export_hash_scope="title+main_text")
    (data / "articles" / f"{aid}.json").write_text(json.dumps(
        {"article": {"article_id": aid, "title": "題名", "latest_version": 1}, "versions": [version]}, ensure_ascii=False), encoding="utf-8")
    if with_cache:
        (tmp_path / "cache" / "text").mkdir(parents=True)
        (tmp_path / "cache" / "text" / f"{aid}_v1.txt").write_text("本文", encoding="utf-8")
    return data, tmp_path / "cache", aid


def test_backfill_adds_hash_from_cache_once(tmp_path):
    data, cache, aid = _article(tmp_path)
    assert sh.backfill(data, cache) == {"added": 1, "unavailable": 0, "already": 0}
    v = json.loads((data / "articles" / f"{aid}.json").read_text(encoding="utf-8"))["versions"][-1]
    assert v["export_hash"] == sh.spec_hash("題名", "本文") and v["export_hash_status"] == "ok"
    assert sh.backfill(data, cache) == {"added": 0, "unavailable": 0, "already": 1}, "2回目は変えない"


def test_backfill_marks_unavailable_without_cache_or_for_unsupported(tmp_path):
    data, cache, aid = _article(tmp_path / "a", with_cache=False)
    assert sh.backfill(data, cache) == {"added": 0, "unavailable": 1, "already": 0}
    data2, cache2, _ = _article(tmp_path / "b", status="unsupported")
    assert sh.backfill(data2, cache2)["unavailable"] == 1


def test_backfill_dry_run_does_not_write(tmp_path):
    data, cache, aid = _article(tmp_path)
    before = (data / "articles" / f"{aid}.json").read_text(encoding="utf-8")
    assert sh.backfill(data, cache, dry_run=True)["added"] == 1
    assert (data / "articles" / f"{aid}.json").read_text(encoding="utf-8") == before


def test_new_versions_made_by_the_collector_carry_the_hash(tmp_path):
    ext = col.Extracted("題名", "本文です。", "html")
    v = col._version("a_0123456789abcdef", 1, ext, "2026-10-05T09:00:00+09:00", "new", attachments=None, title="題名")
    assert v["export_hash"] == sh.spec_hash("題名", "本文です。") and v["export_hash_status"] == "ok"
    bad = col.Extracted("題名", "", "html", status="unsupported", error="x")
    assert col._version("a_0123456789abcdef", 1, bad, "2026-10-05T09:00:00+09:00", "new", title="題名")["export_hash_status"] == "unavailable"
    failed = col._version("a_0123456789abcdef", 1, None, "2026-10-05T09:00:00+09:00", "new", "HTTP 500", title="題名")
    assert failed["export_hash"] is None and failed["export_hash_status"] == "unavailable"
