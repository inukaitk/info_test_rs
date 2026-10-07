"""週次レポート（画面用 reports.json と Markdown）のテスト。"""

from datetime import date

import pytest

from collector import export as ex
from collector import report as rp
from collector.validation import validate_config
from conftest import REPO_ROOT

DEMO_DATA = REPO_ROOT / "demo" / "data"
GENERATED_AT = "2026-09-29T09:00:00+09:00"


@pytest.fixture(scope="module")
def outputs():
    config, report = validate_config(REPO_ROOT / "config", overlay_dir=REPO_ROOT / "demo" / "config")
    assert report.errors == []
    return ex.build_public_data(config, DEMO_DATA, "demo", GENERATED_AT)


@pytest.fixture(scope="module")
def weeks(outputs):
    return outputs["reports.json"]["weeks"]


def test_reports_match_schema(outputs):
    assert ex.check_public_data(outputs, environ={}) == []


def test_weeks_end_at_last_collection(weeks):
    assert [(w["from"], w["to"]) for w in weeks] == [
        ("2026-09-22", "2026-09-28"), ("2026-09-15", "2026-09-21"),
        ("2026-09-08", "2026-09-14"), ("2026-09-01", "2026-09-07"),
    ]


def test_every_article_is_new_in_exactly_one_week(weeks, outputs):
    ids = [i["id"] for w in weeks for i in w["new"]]
    assert sorted(ids) == sorted(a["id"] for a in outputs["articles.json"]["articles"])


def test_changed_articles(weeks):
    latest, previous = weeks[0], weeks[1]
    assert [(i["title"], i["version"]) for i in latest["changed"]] == [("【架空】低出生体重児の支援に関する手引き（改訂版）", 2)]
    assert [(i["title"], i["version"]) for i in previous["changed"]] == [("【架空】乳幼児健康診査の実施要領を改正しました", 2)]


def test_tag_counts_use_final_tags(weeks):
    previous = weeks[1]
    counts = {t["name"]: t["count"] for t in previous["tag_counts"]}
    # 産後ケアQ&A：AIの「調査・統計」は人が除外、「通知・事務連絡」は人が追加
    assert "調査・統計" not in counts
    assert counts["通知・事務連絡"] == 1
    assert previous["counts"]["untagged"] == 3


def test_source_status_in_report(weeks):
    latest = {s["id"]: s for s in weeks[0]["sources"]}
    failed = latest["demo-jichitai-html"]["runs"]
    assert [r["status"] for r in failed] == ["failed"]
    assert "タイムアウト" in failed[0]["error"]


def test_markdown_contents(weeks):
    text = weeks[1]["markdown"]
    assert text.startswith("# 週次レポート 2026年9月15日〜2026年9月21日")
    assert "**架空データ**" in text
    for heading in ["## 概要", "## 新規（4件）", "## 変更（1件）", "## タグ別件数", "## 情報源別の取得状況"]:
        assert heading in text
    assert "一覧ページがタイムアウト" in text
    assert "タグ：AI未処理" in text


def test_markdown_escapes_titles():
    week = {
        "from": "2026-09-01", "to": "2026-09-07",
        "counts": {"new": 1, "changed": 0, "date_unknown": 0, "unsummarized": 0, "untagged": 0, "runs": 0},
        "new": [{"id": "a_0000000000000001", "title": "<script>x</script> [link](javascript:alert(1)) *強調*",
                 "url": "https://a.example.org/x(1).html", "source_name": "A|B", "published": "2026-09-01",
                 "first_seen_at": "2026-09-01T08:00:00+09:00", "version": None, "tags": ["t"], "summary_status": "success"}],
        "changed": [], "tag_counts": [], "sources": [],
    }
    meta = {"is_demo": False, "site_name": "s", "generated_at": GENERATED_AT}
    text = rp.to_markdown(week, meta)
    assert "<script>" not in text
    assert "](javascript:" not in text
    assert "A\\|B" in text
    assert "x%281%29.html" in text
    assert "架空データ" not in text


def test_basis_date_prefers_published_day():
    seen = "2026-10-05T09:00:00+09:00"
    assert rp.basis_date({"published": {"value": "2026-09-17"}, "first_seen_at": seen}) == date(2026, 9, 17)
    # 日付不明・月のみ・年のみは、取得日で数える
    for value in (None, "2026-09", "2026"):
        assert rp.basis_date({"published": {"value": value}, "first_seen_at": seen}) == date(2026, 10, 5)


def test_published_day_reads_timestamps_as_japan_time_and_ignores_unknown_or_partial():
    assert rp.published_day({"published": {"value": "2026-09-17"}}) == date(2026, 9, 17)
    assert rp.published_day({"published": {"value": "2026-09-01T12:00:02+09:00"}}) == date(2026, 9, 1)
    assert rp.published_day({"published": {"value": "2026-09-21T16:00:00+00:00"}}) == date(2026, 9, 22), "UTCの夕方は日本時間では翌日"
    for value in (None, "2026-09", "2026"):
        assert rp.published_day({"published": {"value": value}}) is None


def test_basis_date_uses_the_published_day_of_timestamp_values_not_the_first_seen_day():
    seen = "2026-10-05T09:00:00+09:00"
    assert rp.basis_date({"published": {"value": "2026-09-01T12:00:02+09:00"}, "first_seen_at": seen}) == date(2026, 9, 1)


def test_backfilled_old_articles_do_not_count_as_new_this_week():
    article = lambda i, pub: {  # noqa: E731
        "id": i, "title": i, "url": "https://a.example.org/" + i, "source_name": "s",
        "published": {"value": pub}, "first_seen_at": "2026-10-05T09:00:00+09:00",
        "versions": [], "tags": [], "summary": {"status": "success"}}
    articles = [article("old", "2026-09-01"), article("recent", "2026-10-02"), article("unknown", None)]
    meta = {"tags": [], "sources": []}
    week = rp.build_week(date(2026, 9, 29), date(2026, 10, 5), meta, articles, {"runs": []})
    assert [i["id"] for i in week["new"]] == ["unknown", "recent"]  # 並びは集計に使う日の新しい順
    assert week["counts"]["new"] == 2 and week["counts"]["date_unknown"] == 1
    # 週の一覧は、公開日が最も古い記事の週まで作られる
    assert rp.week_windows("2026-10-05T09:00:00+09:00", articles)[-1][0] <= date(2026, 9, 1)


def test_week_windows_limit():
    articles = [{"first_seen_at": "2025-01-01T08:00:00+09:00"}]
    assert len(rp.week_windows("2026-09-28T08:00:00+09:00", articles)) == rp.MAX_WEEKS
    assert rp.week_windows(None, articles) == []


def test_jst_date_boundary():
    assert rp.jst_date("2026-09-21T15:30:00Z") == date(2026, 9, 22)


def test_cli_writes_markdown(tmp_path, capsys):
    assert rp.main(["--mode", "demo", "--out", str(tmp_path)]) == 0
    files = list(tmp_path.glob("weekly_*.md"))
    assert [f.name for f in files] == ["weekly_2026-09-22_2026-09-28.md"]
    assert rp.main(["--mode", "demo", "--out", str(tmp_path), "--all"]) == 0
    assert len(list(tmp_path.glob("weekly_*.md"))) == 4


def test_real_mode_without_data(tmp_path, capsys, monkeypatch):
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setattr(ex, "paths_for_mode", lambda mode: (empty, None))
    assert rp.main(["--mode", "real", "--out", str(tmp_path)]) == 1
    assert "収集データがない" in capsys.readouterr().err
