"""公開用変換（画面用JSON）のテスト。"""

import json
import shutil

import pytest

from collector import export as ex
from collector.validation import validate_all, validate_config
from conftest import REPO_ROOT, read_json, write_json

DEMO_DATA = REPO_ROOT / "demo" / "data"
DEMO_CONFIG = REPO_ROOT / "demo" / "config"
GENERATED_AT = "2026-09-29T09:00:00+09:00"


@pytest.fixture
def demo_config():
    config, report = validate_config(REPO_ROOT / "config", overlay_dir=DEMO_CONFIG)
    assert report.errors == []
    return config


@pytest.fixture
def demo_copy(tmp_path):
    target = tmp_path / "data"
    shutil.copytree(DEMO_DATA, target)
    return target


def build(config, data_dir):
    return ex.build_public_data(config, data_dir, "demo", GENERATED_AT)


def by_title(outputs, fragment):
    matches = [a for a in outputs["articles.json"]["articles"] if fragment in a["title"]]
    assert len(matches) == 1, fragment
    return matches[0]


# ---- デモデータ


def test_demo_data_is_valid():
    assert validate_all(REPO_ROOT / "config", DEMO_DATA, overlay_dir=DEMO_CONFIG).errors == []


def test_demo_data_covers_required_cases(demo_config):
    outputs = build(demo_config, DEMO_DATA)
    articles = outputs["articles.json"]["articles"]
    assert 18 <= len(articles) <= 25
    assert all("【架空】" in a["title"] for a in articles)
    assert any(a["published"]["value"] is None for a in articles), "日付不明"
    assert any(a["content_status"] in ("failed", "unsupported") for a in articles), "本文未取得"
    assert any(a["summary"]["status"] != "success" for a in articles), "AI未要約"
    assert any(any(t["origin"] == "human" for t in a["tags"]) or a["removed_tags"] for a in articles), "タグ修正"
    assert any(a["latest_version"] >= 2 for a in articles), "2版"
    status = outputs["status.json"]
    run_statuses = {r["status"] for r in status["runs"]}
    assert {"success", "partial"} <= run_statuses
    assert any(s["last_attempt_status"] == "failed" for s in status["sources"])
    assert any(s["date_unknown"] > 0 for s in status["sources"])


def test_demo_uses_only_fictional_hosts(demo_config):
    for a in build(demo_config, DEMO_DATA)["articles.json"]["articles"]:
        host = a["url"].split("/")[2]
        assert host.endswith((".example.org", ".example.net", ".example.com")), host


def test_outputs_match_public_schemas(demo_config):
    assert ex.check_public_data(build(demo_config, DEMO_DATA), environ={}) == []


def test_meta_marks_demo(demo_config):
    meta = build(demo_config, DEMO_DATA)["meta.json"]
    assert meta["is_demo"] is True and meta["release_mode"] == "demo"
    assert meta["correction_request_url"] is None


def test_meta_has_latest_window(demo_config):
    meta = build(demo_config, DEMO_DATA)["meta.json"]
    assert meta["latest_days"] == 7
    # 最後の収集（2026-09-28 08:00）が最新一覧の基準日時
    assert meta["data_as_of"] == "2026-09-28T08:00:00+09:00"


def test_data_as_of_without_runs():
    files = [{"article": {"first_seen_at": "2026-09-01T08:00:00+09:00"}},
             {"article": {"first_seen_at": "2026-09-05T08:00:00+09:00"}}]
    assert ex.data_as_of([], files) == "2026-09-05T08:00:00+09:00"
    assert ex.data_as_of([], []) is None


# ---- 最終タグ = AIタグ + 追加 - 除外

TAG_DEFS = {
    "a": {"id": "a", "name": "A", "enabled": True},
    "b": {"id": "b", "name": "B", "enabled": True},
    "c": {"id": "c", "name": "C", "enabled": True},
    "old": {"id": "old", "name": "旧", "enabled": False},
}


def ids(tags):
    return [(t["id"], t["origin"]) for t in tags]


def test_final_tags_ai_plus_add_minus_remove():
    ai = [{"tag_id": "a", "reason": "r1"}, {"tag_id": "b", "reason": "r2"}]
    tags = ex.final_tags(ai, {"add": ["c"], "remove": ["b"]}, TAG_DEFS)
    assert ids(tags) == [("a", "ai"), ("c", "human")]
    assert tags[0]["reason"] == "r1" and tags[1]["reason"] is None


def test_final_tags_without_override():
    assert ids(ex.final_tags([{"tag_id": "a", "reason": "r"}], None, TAG_DEFS)) == [("a", "ai")]


def test_final_tags_add_existing_ai_tag_keeps_ai_origin():
    assert ids(ex.final_tags([{"tag_id": "a", "reason": "r"}], {"add": ["a"]}, TAG_DEFS)) == [("a", "ai")]


def test_final_tags_remove_wins_over_add():
    assert ex.final_tags(None, {"add": ["a"], "remove": ["a"]}, TAG_DEFS) == []


def test_final_tags_when_ai_failed_keeps_human_tags():
    assert ids(ex.final_tags(None, {"add": ["c"]}, TAG_DEFS)) == [("c", "human")]


def test_retired_tag_is_flagged():
    tags = ex.final_tags([{"tag_id": "old", "reason": "r"}], None, TAG_DEFS)
    assert tags[0]["retired"] is True


def test_removed_tags_are_listed():
    ai = [{"tag_id": "a", "reason": "r"}, {"tag_id": "b", "reason": "r"}]
    assert ex.removed_tags(ai, {"remove": ["b", "c"]}, TAG_DEFS) == [{"id": "b", "name": "B"}]


def test_demo_override_examples(demo_config):
    outputs = build(demo_config, DEMO_DATA)
    qa = by_title(outputs, "産後ケア事業に関するQ&A")
    assert ids(qa["tags"]) == [("maternal-child-health", "ai"), ("notice-admin-communication", "human")]
    assert qa["removed_tags"] == [{"id": "survey-statistics", "name": "調査・統計"}]
    assert qa["tag_override_reason"]
    accident = by_title(outputs, "事故予防")
    assert ids(accident["tags"]) == [("childcare-support", "human")]


# ---- 失敗・不明を成功に変換しない


def test_unsummarized_article_is_not_shown_as_summary(demo_config):
    outputs = build(demo_config, DEMO_DATA)
    for fragment, status in [("支給要件", "skipped_no_api_key"), ("一括法案", "failed_invalid_output"),
                             ("実施状況（年報）", "failed_api_error")]:
        a = by_title(outputs, fragment)
        assert a["summary"]["status"] == status
        assert a["summary"]["text"] is None and a["tags"] == []


def test_article_without_summary_record(demo_config):
    a = by_title(build(demo_config, DEMO_DATA), "よくある質問")
    assert a["summary"]["status"] == "not_processed"
    assert a["content_status"] == "failed" and a["content_error"]


def test_unknown_date_stays_unknown(demo_config):
    a = by_title(build(demo_config, DEMO_DATA), "メンタルヘルス")
    assert a["published"] == {"value": None, "precision": "unknown", "basis": None}


def test_summary_of_older_version_is_marked_outdated(demo_config, demo_copy):
    path = next(p for p in (demo_copy / "summaries").glob("*.json")
                if any(s["analysis_status"] == "pending" for s in read_json(p)["summaries"]))
    data = read_json(path)
    data["summaries"] = [s for s in data["summaries"] if s["analysis_status"] != "pending"]
    write_json(path, data)
    a = by_title(build(demo_config, demo_copy), "低出生体重児")
    assert a["latest_version"] == 2
    assert a["summary"]["version"] == 1 and a["summary"]["outdated"] is True


# ---- 原文全文・API生応答・タグ候補・秘密値を出さない

SENTINEL = "SENTINEL_MUST_NOT_LEAK_7f3a"


def test_extra_fields_are_not_exported(demo_config, demo_copy):
    """元データに想定外の項目（原文・生応答など）が入っていても画面用JSONに出ない（allowlist）。"""
    for path in (demo_copy / "articles").glob("*.json"):
        data = read_json(path)
        data["article"]["body_text"] = SENTINEL + " 原文全文"
        data["article"]["internal_note"] = SENTINEL
        for v in data["versions"]:
            v["raw_html"] = SENTINEL
        write_json(path, data)
    for path in (demo_copy / "summaries").glob("*.json"):
        data = read_json(path)
        for s in data["summaries"]:
            s["raw_response"] = {"content": SENTINEL}
            s["new_tag_suggestions"] = [{"name": SENTINEL}]
            s["prompt"] = SENTINEL
        write_json(path, data)
    for path in (demo_copy / "runs").glob("*.json"):
        data = read_json(path)
        data["run"]["log"] = SENTINEL
        write_json(path, data)
    text = json.dumps(build(demo_config, demo_copy), ensure_ascii=False)
    assert SENTINEL not in text


def test_tag_candidates_are_not_exported(demo_config):
    candidates = read_json(DEMO_DATA / "tag_candidates.json")["candidates"]
    assert candidates
    text = json.dumps(build(demo_config, DEMO_DATA), ensure_ascii=False)
    for c in candidates:
        assert c["name"] not in text
        assert c["reason"] not in text


def test_cache_directory_is_not_read(demo_config, demo_copy):
    cache = demo_copy / ".cache"
    cache.mkdir()
    (cache / "body.txt").write_text(SENTINEL, encoding="utf-8")
    (cache / "response.json").write_text(json.dumps({"raw": SENTINEL}), encoding="utf-8")
    assert SENTINEL not in json.dumps(build(demo_config, demo_copy), ensure_ascii=False)


def test_environment_secret_is_never_exported(demo_config, monkeypatch):
    monkeypatch.setenv("AI_API_KEY", SENTINEL)
    outputs = build(demo_config, DEMO_DATA)
    assert SENTINEL not in json.dumps(outputs, ensure_ascii=False)
    assert ex.check_public_data(outputs) == []


def test_secret_detection_blocks_export(demo_config, demo_copy, monkeypatch, tmp_path):
    """もし秘密値がデータに紛れ込んでも、出力前の確認で止まる。"""
    monkeypatch.setenv("AI_API_KEY", SENTINEL)
    path = next((demo_copy / "articles").glob("*.json"))
    data = read_json(path)
    data["article"]["title"] = f"【架空】{SENTINEL}"
    write_json(path, data)
    problems = ex.check_public_data(build(demo_config, demo_copy))
    assert any("AI_API_KEY" in p for p in problems)
    assert all(SENTINEL not in p for p in problems), "エラー文に秘密値そのものを出さない"


@pytest.mark.parametrize("value", ["sk-" + "a" * 30, "ghp_" + "b" * 36, "AKIA" + "C" * 16])
def test_secret_patterns_are_detected(value):
    assert ex.find_secrets(f"title {value}", environ={})


def test_short_or_unrelated_env_values_are_ignored():
    assert ex.find_secrets("demo text", environ={"API_KEY": "demo", "HOME": "demo text"}) == []


def test_schema_rejects_unexpected_public_field(demo_config):
    outputs = build(demo_config, DEMO_DATA)
    outputs["articles.json"]["articles"][0]["body_text"] = "x"
    assert any("body_text" in p for p in ex.check_public_data(outputs, environ={}))


# ---- CLI


def test_export_writes_files(tmp_path):
    out = tmp_path / "out"
    outputs = ex.export("demo", out, GENERATED_AT)
    assert sorted(p.name for p in out.iterdir()) == ["articles.json", "meta.json", "reports.json", "status.json"]
    assert read_json(out / "meta.json") == outputs["meta.json"]


def test_export_stops_on_invalid_input(tmp_path, monkeypatch, demo_copy):
    (demo_copy / "state.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(ex, "paths_for_mode", lambda mode: (demo_copy, DEMO_CONFIG))
    out = tmp_path / "out"
    with pytest.raises(ex.ExportError):
        ex.export("demo", out, GENERATED_AT)
    assert not out.exists(), "検証に失敗したら出力しない"


def test_cli(tmp_path, capsys):
    assert ex.main(["--mode", "demo", "--out", str(tmp_path), "--generated-at", GENERATED_AT]) == 0
    assert "記事 20 件" in capsys.readouterr().out


def test_real_mode_with_empty_data(tmp_path, monkeypatch):
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setattr(ex, "paths_for_mode", lambda mode: (empty, None))
    outputs = ex.export("real", tmp_path / "out", GENERATED_AT)
    assert outputs["articles.json"]["articles"] == []
    assert outputs["meta.json"]["is_demo"] is False


def test_plain_text_strips_html_from_date_evidence():
    assert ex._plain_text('<time datetime="2026-10-02">2026年10月2日</time>') == "2026年10月2日"
    assert ex._plain_text("公開日：令和8年9月30日") == "公開日：令和8年9月30日"
    assert ex._plain_text("a &amp; b\n  <b>c</b>") == "a & b c"
    assert ex._plain_text("<br>") == "<br>", "タグだけで空になる場合は元の文字を残す（根拠を空にしない）"


def test_retry_items_are_exposed_with_plain_kind():
    st = {"retry_queue": [
        {"url": "https://a.example.org/x", "stage": "fetch", "article_id": "a_0123456789abcdef", "attempts": 2,
         "first_failed_at": "2026-10-05T10:14:31+09:00",
         "reason": "添付PDFの取得に失敗：資料（PDF／10.5MB）：サイズ上限（10485760バイト）を超えました"},
        {"url": "https://a.example.org/y", "stage": "fetch", "article_id": None, "attempts": 1,
         "first_failed_at": "2026-10-05T10:14:31+09:00", "reason": "HTTP 500"},
    ]}
    items = ex._retry_items(st, [{"id": "a_0123456789abcdef", "title": "会議資料"}])
    assert [i["kind"] for i in items] == ["size_limit", "other"]
    assert items[0]["title"] == "会議資料" and items[1]["title"] is None
    assert ex._retry_items(None, []) == []


# ---- 情報源の設定で付けるタグ（fixed_tags）

FIXED = [{"tag_id": "c", "reason": "情報源の設定：架空社の記事すべてに付けています"}]


def test_final_tags_source_fixed_tag_is_added_even_without_ai_result():
    tags = ex.final_tags(None, None, TAG_DEFS, FIXED)
    assert ids(tags) == [("c", "source")] and "情報源の設定" in tags[0]["reason"]


def test_final_tags_order_ai_then_source_then_human_without_duplicates():
    ai = [{"tag_id": "a", "reason": "r"}, {"tag_id": "c", "reason": "AIも付けた"}]
    tags = ex.final_tags(ai, {"add": ["b"]}, TAG_DEFS, FIXED)
    assert ids(tags) == [("a", "ai"), ("c", "ai"), ("b", "human")], "AIが付けたタグは由来をaiのままにする"
    assert ids(ex.final_tags([{"tag_id": "a", "reason": "r"}], {"add": ["b"]}, TAG_DEFS, FIXED)) == [("a", "ai"), ("c", "source"), ("b", "human")]


def test_final_tags_human_can_remove_a_source_fixed_tag_and_it_is_shown_as_removed():
    override = {"remove": ["c"]}
    assert ex.final_tags(None, override, TAG_DEFS, FIXED) == []
    assert ex.removed_tags(None, override, TAG_DEFS, FIXED) == [{"id": "c", "name": "C"}]


def test_source_fixed_tags_come_from_the_source_config():
    src = {"id": "s", "name": "架空社", "fixed_tags": ["a", "b"]}
    assert [t["tag_id"] for t in ex.source_fixed_tags(src)] == ["a", "b"]
    assert ex.source_fixed_tags({"id": "s", "name": "架空社"}) == []
    assert ex.source_fixed_tags(None) == []


def test_real_vendor_articles_all_have_vendor_trend_and_others_do_not():
    from collector.validation import validate_config
    config, report = validate_config(REPO_ROOT / "config")
    assert report.errors == []
    outputs = ex.build_public_data(config, REPO_ROOT / "data", "real", "2026-10-06T09:00:00+09:00")
    assert ex.check_public_data(outputs, environ={}) == []
    vendors = {"cmic-trust-news", "mchh-prtimes", "milabo-news", "ryobi-neuvola-karte"}
    articles = outputs["articles.json"]["articles"]
    for a in articles:
        has = [t for t in a["tags"] if t["id"] == "vendor-trend"]
        if a["source_id"] in vendors:
            assert len(has) == 1 and has[0]["origin"] == "source", a["title"]
        else:
            assert not has, a["title"]
    assert any(a["source_id"] in vendors for a in articles)
