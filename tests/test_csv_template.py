"""外部連携用CSVのテンプレート（docs/csv/external_news_template.csv）が、仕様の形式と、画面の列定義に合っていることを確かめる。"""
import csv
import io
import re

from collector.spec_hash import spec_hash
from conftest import REPO_ROOT

TEMPLATE = REPO_ROOT / "docs" / "csv" / "external_news_template.csv"


def _web_columns() -> list[str]:
    source = (REPO_ROOT / "web" / "src" / "externalCsv.ts").read_text(encoding="utf-8")
    block = re.search(r"EXTERNAL_CSV_COLUMNS = \[(.*?)\] as const", source, re.S).group(1)
    return re.findall(r'"([a-z_]+)"', block)


def _rows():
    raw = TEMPLATE.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf"), "UTF-8 BOM付き"
    text = raw.decode("utf-8-sig")
    assert "\r\n" in text and "\n" not in text.replace("\r\n", ""), "改行はCRLF"
    return list(csv.reader(io.StringIO(text, newline="")))


def test_template_header_matches_the_columns_the_site_writes():
    rows = _rows()
    assert rows[0] == _web_columns() and len(rows[0]) == 15
    assert all(len(r) == 15 for r in rows)


def test_template_rows_follow_the_format_rules():
    col = {name: i for i, name in enumerate(_web_columns())}
    for r in _rows()[1:]:
        assert re.fullmatch(r"[A-Z0-9_]+_\d{8}_\d{3}", r[col["record_id"]])
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+09:00", r[col["fetched_at"]])
        assert r[col["url"]].startswith("https://www.example.org/"), "実在のURLを入れない"
        assert r[col["published_date"]] == "" or re.fullmatch(r"\d{4}-\d{2}-\d{2}", r[col["published_date"]])
        if r[col["hash_status"]] == "ok":
            assert re.fullmatch(r"[0-9a-f]{64}", r[col["content_hash"]])
        else:
            assert (r[col["content_hash"]], r[col["hash_scope"]]) == ("", "")


def test_template_hashes_are_reproducible_with_the_documented_method():
    col = {name: i for i, name in enumerate(_web_columns())}
    rows = _rows()[1:]
    assert rows[0][col["content_hash"]] == spec_hash("【架空】サンプルのお知らせ", "【架空】サンプルの本文です。")


def test_template_has_no_internal_information():
    text = TEMPLATE.read_text(encoding="utf-8-sig")
    for word in ("Copilot", "両備", "木下", "犬飼", "重要度", "関連度", "製品"):
        assert word not in text
    assert "【架空】" in text
