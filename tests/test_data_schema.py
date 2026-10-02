"""data/ の各レコードのスキーマ検証と整合性のテスト。"""

import pytest

from collector.validation import (
    article_id_from_canonical_url,
    schema_errors,
    validate_all,
    validate_config,
)
from conftest import REPO_ROOT, deep, read_json, write_json

ARTICLE = "a_3715ddd7b3d7eab6"
UNKNOWN_DATE_ARTICLE = "a_8e2a26b4d84f3a56"


DEMO_CONFIG = REPO_ROOT / "demo" / "config"


def errors_for(data_dir):
    # テスト用データの情報源（demo-…）は架空データ用の設定にある
    return validate_all(REPO_ROOT / "config", data_dir, overlay_dir=DEMO_CONFIG).errors


def test_repository_data_is_valid():
    assert validate_all(REPO_ROOT / "config", REPO_ROOT / "data").errors == []


def test_fixture_data_is_valid(data_dir):
    assert errors_for(data_dir) == []


def test_article_id_is_deterministic():
    url = "https://kodomo.example.org/news/2026/0901-kenshin.html"
    assert article_id_from_canonical_url(url) == article_id_from_canonical_url(url) == ARTICLE


# ---- 個々のレコード（schemas/records）


@pytest.fixture
def article_file(data_dir):
    return read_json(data_dir / "articles" / f"{ARTICLE}.json")


@pytest.fixture
def summary_file(data_dir):
    return read_json(data_dir / "summaries" / f"{ARTICLE}.json")


@pytest.fixture
def run_file(data_dir):
    return read_json(data_dir / "runs" / "run_20260915T230000Z.json")


@pytest.fixture
def state_file(data_dir):
    return read_json(data_dir / "state.json")


def test_each_record_schema_accepts_fixture(article_file, summary_file, run_file, state_file, data_dir):
    assert schema_errors(article_file["article"], "records/article.schema.json") == []
    for v in article_file["versions"]:
        assert schema_errors(v, "records/article_version.schema.json") == []
    for s in summary_file["summaries"]:
        assert schema_errors(s, "records/summary.schema.json") == []
    assert schema_errors(run_file["run"], "records/run.schema.json") == []
    for s in state_file["sources"].values():
        assert schema_errors(s, "records/source_state.schema.json") == []
    for c in read_json(data_dir / "tag_candidates.json")["candidates"]:
        assert schema_errors(c, "records/tag_candidate.schema.json") == []


# article


@pytest.mark.parametrize(
    "mutation",
    [
        # 日付不明なのに精度が unknown 以外
        lambda a: a.update(published_at=None),
        # 日付があるのに根拠がない
        lambda a: a["date_basis"].update(published=None),
        # 日付があるのに精度が unknown
        lambda a: a["date_precision"].update(published="unknown"),
        # HTTPのLast-Modifiedだけで公開日を確定しない
        lambda a: a["date_basis"]["published"].update(method="http_last_modified"),
        lambda a: a["date_basis"]["published"].update(evidence=""),
        lambda a: a.update(published_at="2026/09/01"),
        lambda a: a.update(first_seen_at="2026-09-02T08:00:00"),  # タイムゾーンなし
        lambda a: a.update(article_id="12345"),
        lambda a: a.update(status="deleted"),
        lambda a: a.update(latest_version=0),
        lambda a: a.update(importance="high"),  # 範囲外の項目（重要度）は持たない
    ],
)
def test_article_schema_rejects_invalid(article_file, mutation):
    article = deep(article_file["article"])
    mutation(article)
    assert schema_errors(article, "records/article.schema.json")


def test_article_with_unknown_date_is_valid(data_dir):
    article = read_json(data_dir / "articles" / f"{UNKNOWN_DATE_ARTICLE}.json")["article"]
    assert article["published_at"] is None
    assert article["date_precision"]["published"] == "unknown"
    assert schema_errors(article, "records/article.schema.json") == []


def test_article_month_precision(article_file):
    article = deep(article_file["article"])
    article["published_at"] = "2026-09"
    article["date_precision"]["published"] = "month"
    assert schema_errors(article, "records/article.schema.json") == []


# article_version


@pytest.mark.parametrize(
    "mutation",
    [
        lambda v: v.update(content_hash=None),  # 抽出成功なのにhashなし
        lambda v: v.update(extraction_status="failed"),  # 失敗なのにhashあり・理由なし
        lambda v: v.update(content_hash="abc"),
        lambda v: v.update(change_type="content_changed"),  # 版1は new
        lambda v: v.update(extraction_error="x"),  # 成功なのにエラーあり
        lambda v: v.update(content_type="none"),  # 成功なのに本文種別なし
    ],
)
def test_article_version_schema_rejects_invalid(article_file, mutation):
    version = deep(article_file["versions"][0])
    mutation(version)
    assert schema_errors(version, "records/article_version.schema.json")


def test_failed_extraction_requires_reason(article_file):
    version = deep(article_file["versions"][0])
    version.update(extraction_status="failed", content_hash=None, extraction_error=None)
    assert schema_errors(version, "records/article_version.schema.json")
    version["extraction_error"] = "HTTP 404"
    assert schema_errors(version, "records/article_version.schema.json") == []


# summary


def _success(summary_file):
    return deep(summary_file["summaries"][1])


def _failed(summary_file):
    return deep(summary_file["summaries"][0])


@pytest.mark.parametrize(
    "mutation",
    [
        lambda s: s.update(summary=None),
        lambda s: s.update(ai_tags=None),
        lambda s: s.update(summary="あ" * 301),
        lambda s: s.update(key_points=["1", "2", "3", "4", "5", "6"]),
        lambda s: s["dates"][0].pop("evidence"),  # 根拠のない日付は出さない
        lambda s: s["dates"][0].update(evidence=""),
        lambda s: s["ai_tags"][0].pop("reason"),
        lambda s: s.update(error="something"),
        lambda s: s.update(model=None),
        lambda s: s.update(analysis_status="done"),
        lambda s: s.update(new_tag_suggestions=[{"name": "x"}]),  # 候補は tag_candidates へ
        lambda s: s.update(raw_response="{...}"),  # API生応答は保存しない
        lambda s: s.update(relevance="high"),
    ],
)
def test_summary_schema_rejects_invalid_success(summary_file, mutation):
    summary = _success(summary_file)
    mutation(summary)
    assert schema_errors(summary, "records/summary.schema.json")


@pytest.mark.parametrize(
    "status",
    ["pending", "skipped_no_api_key", "skipped_no_content", "failed_api_error",
     "failed_invalid_output", "failed_limit_exceeded"],
)
def test_failed_summary_cannot_look_like_no_tags(summary_file, status):
    """失敗を成功や「タグなし」（空配列）として記録できない。"""
    summary = _failed(summary_file)
    summary["analysis_status"] = status
    assert schema_errors(summary, "records/summary.schema.json") == []
    for field, value in [("ai_tags", []), ("summary", "要約"), ("dates", []), ("key_points", [])]:
        broken = deep(summary)
        broken[field] = value
        assert schema_errors(broken, "records/summary.schema.json"), (status, field)


def test_success_summary_may_have_no_tags(summary_file):
    """成功して該当タグがない場合は空配列でよい。"""
    summary = _success(summary_file)
    summary["ai_tags"] = []
    assert schema_errors(summary, "records/summary.schema.json") == []


def test_unregistered_ai_tag_is_rejected(data_dir, summary_file):
    summary_file["summaries"][1]["ai_tags"].append({"tag_id": "sales-opportunity", "reason": "x"})
    write_json(data_dir / "summaries" / f"{ARTICLE}.json", summary_file)
    assert any("未登録のタグid" in e for e in errors_for(data_dir))


def test_summary_for_missing_version_is_rejected(data_dir, summary_file):
    summary_file["summaries"][1]["article_version"] = 3
    write_json(data_dir / "summaries" / f"{ARTICLE}.json", summary_file)
    assert any("存在しない版" in e for e in errors_for(data_dir))


# run


@pytest.mark.parametrize(
    "mutation",
    [
        lambda r: r.update(run_id="run-1"),
        lambda r: r.update(status="running"),  # running なのに finished_at あり
        lambda r: r.update(status="ok"),
        lambda r: r["sources"][1].update(error=None),  # 失敗した情報源には理由が必要
        lambda r: r["sources"][0].update(new=-1),
        lambda r: r["failures"][0].update(stage="unknown"),
        lambda r: r.update(period={"start": "2026-09-01"}),
    ],
)
def test_run_schema_rejects_invalid(run_file, mutation):
    run = deep(run_file["run"])
    mutation(run)
    assert schema_errors(run, "records/run.schema.json")


def test_running_run_has_no_finish_time(run_file):
    run = deep(run_file["run"])
    run.update(status="running", finished_at=None)
    assert schema_errors(run, "records/run.schema.json") == []


def test_run_period_order(data_dir, run_file):
    run_file["run"]["period"] = {"start": "2026-09-30", "end": "2026-09-01"}
    write_json(data_dir / "runs" / "run_20260915T230000Z.json", run_file)
    assert any("start が end より後" in e for e in errors_for(data_dir))


# source_state


@pytest.mark.parametrize(
    "mutation",
    [
        lambda s: s.update(consecutive_failures=-1),
        lambda s: s["retry_queue"][0].update(stage="publish"),
        lambda s: s["retry_queue"][0].update(attempts=0),
        lambda s: s["retry_queue"][0].pop("reason"),
        lambda s: s.update(last_success_at="昨日"),
    ],
)
def test_source_state_schema_rejects_invalid(state_file, mutation):
    state = deep(state_file["sources"]["demo-boshi-html"])
    mutation(state)
    assert schema_errors(state, "records/source_state.schema.json")


def test_state_key_must_match_source_id(data_dir, state_file):
    state_file["sources"]["demo-kodomo-rss"]["source_id"] = "demo-boshi-html"
    write_json(data_dir / "state.json", state_file)
    assert any("キーと一致しません" in e for e in errors_for(data_dir))


# tag_candidate


@pytest.mark.parametrize(
    "candidate",
    [
        {"name": "", "reason": "x", "article_id": ARTICLE, "first_seen_at": "2026-09-16T08:05:00+09:00"},
        {"name": "x", "article_id": ARTICLE, "first_seen_at": "2026-09-16T08:05:00+09:00"},
        {"name": "x", "reason": "x", "article_id": ARTICLE, "first_seen_at": "2026-09-16"},
    ],
)
def test_tag_candidate_schema_rejects_invalid(candidate):
    assert schema_errors(candidate, "records/tag_candidate.schema.json")


def test_tag_candidate_must_reference_existing_article(data_dir):
    path = data_dir / "tag_candidates.json"
    data = read_json(path)
    data["candidates"][0]["article_id"] = "a_0000000000000000"
    write_json(path, data)
    assert any("data/articles にありません" in e for e in errors_for(data_dir))


# ファイル間の整合性


def test_article_filename_must_match_id(data_dir):
    src = data_dir / "articles" / f"{ARTICLE}.json"
    src.rename(data_dir / "articles" / "a_ffffffffffffffff.json")
    errors = errors_for(data_dir)
    assert any("ファイル名と article_id" in e for e in errors)


def test_article_id_must_match_canonical_url(data_dir, article_file):
    article_file["article"]["canonical_url"] = "https://kodomo.example.org/news/other.html"
    write_json(data_dir / "articles" / f"{ARTICLE}.json", article_file)
    assert any("canonical_url から計算した値" in e for e in errors_for(data_dir))


def test_versions_must_be_sequential(data_dir, article_file):
    article_file["versions"][1]["version"] = 3
    article_file["versions"][1]["change_type"] = "content_changed"
    write_json(data_dir / "articles" / f"{ARTICLE}.json", article_file)
    errors = errors_for(data_dir)
    assert any("連番" in e for e in errors)


def test_latest_version_must_match(data_dir, article_file):
    article_file["article"]["latest_version"] = 1
    write_json(data_dir / "articles" / f"{ARTICLE}.json", article_file)
    assert any("latest_version" in e for e in errors_for(data_dir))


def test_unknown_source_is_rejected(data_dir, article_file):
    article_file["article"]["source_id"] = "unknown-source"
    write_json(data_dir / "articles" / f"{ARTICLE}.json", article_file)
    assert any("未登録の情報源id" in e for e in errors_for(data_dir))


def test_broken_json_is_reported(data_dir):
    (data_dir / "runs" / "run_20260915T230000Z.json").write_text("{", encoding="utf-8")
    assert any("JSONとして読めません" in e for e in errors_for(data_dir))


def test_cli_exit_codes(data_dir, config_dir, capsys):
    import shutil

    from collector.validate import main

    shutil.copyfile(DEMO_CONFIG / "sources.yaml", config_dir / "sources.yaml")
    assert main(["--config", str(config_dir), "--data", str(data_dir)]) == 0
    (data_dir / "state.json").write_text("{}", encoding="utf-8")
    assert main(["--config", str(config_dir), "--data", str(data_dir)]) == 1
    assert "NG" in capsys.readouterr().err
