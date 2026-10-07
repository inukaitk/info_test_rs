"""ルール（キーワード一致）によるタグ付けのテスト。AIは使わない。実際のWebにも接続しない。"""
import json
import re
import shutil

import pytest

from collector import export as ex
from collector import rule_tags as rt
from collector.validation import validate_all, validate_config
from conftest import REPO_ROOT, read_json, read_yaml, write_yaml

RULES = [
    rt.Rule("vendor-trend", "母子モ", re.compile("母子モ(?!デル)", re.IGNORECASE), "母子モ(?!デル)"),
    rt.Rule("vendor-trend", "CMIC Trust", re.compile(r"CMIC\s?Trust|シミックトラスト", re.IGNORECASE), r"CMIC\s?Trust|シミックトラスト"),
]


def test_match_rules_title_body_width_case_and_exclusion():
    # 題名で一致すれば題名、本文だけなら本文。同じ名前は1件
    found = rt.match_rules(RULES, "【架空】母子モが提供開始", "本文にも母子モがある")
    assert found == [{"tag_id": "vendor-trend", "label": "母子モ", "matched": "母子モ", "in": "title"}]
    assert rt.match_rules(RULES, "題名", "…ＣＭＩＣ　Ｔｒｕｓｔ（全角）と書いてある")[0]["label"] == "CMIC Trust"
    assert rt.match_rules(RULES, "題名", "cmic trust は小文字でも一致する")[0]["in"] == "body"
    assert rt.match_rules(RULES, "母子モデル事業の公募", "母子モデルの説明") == [], "「母子モデル」は除外する"
    assert rt.match_rules(RULES, "題名だけ", None) == []
    assert [m["label"] for m in rt.match_rules(RULES, "x", "母子モとシミックトラスト")] == ["母子モ", "CMIC Trust"]


def test_rules_version_changes_with_the_rules():
    base = rt.rules_version(RULES)
    assert base == rt.rules_version(list(RULES))
    changed = [RULES[0], rt.Rule("vendor-trend", "CMIC Trust", re.compile("x"), "x")]
    assert rt.rules_version(changed) != base
    assert rt.rules_version(RULES[:1]) != base


def _data(tmp_path, version=1, title="【架空】記事", extraction="ok"):
    data = tmp_path / "data"
    (data / "articles").mkdir(parents=True, exist_ok=True)
    aid = "a_0123456789abcdef"
    versions = [{"version": v, "extraction_status": extraction} for v in range(1, version + 1)]
    (data / "articles" / f"{aid}.json").write_text(json.dumps(
        {"article": {"article_id": aid, "title": title, "latest_version": version}, "versions": versions}, ensure_ascii=False), encoding="utf-8")
    return data, aid


class FakeConfig:
    def __init__(self, rules):
        self.tags = {"tags": [{"id": "vendor-trend", "enabled": True, "auto_rules": rules}]}


CFG = FakeConfig([{"label": "母子モ", "pattern": "母子モ(?!デル)"}])


def _cache(tmp_path, aid, version, text):
    (tmp_path / "cache" / "text").mkdir(parents=True, exist_ok=True)
    (tmp_path / "cache" / "text" / f"{aid}_v{version}.txt").write_text(text, encoding="utf-8")


def test_apply_rules_uses_body_when_cached_and_title_only_otherwise(tmp_path):
    data, aid = _data(tmp_path)
    content, result = rt.apply_rules(CFG, data, tmp_path / "cache")
    assert content["articles"][aid]["scope"] == "title" and content["articles"][aid]["tags"] == []
    assert result.title_only == 1 and result.updated == 1
    # 本文が使える環境で実行し直すと、本文で判定し直す
    rt.write_atomic(data / "rule_tags.json", content)
    _cache(tmp_path, aid, 1, "…母子モを導入した自治体の事例…")
    content, result = rt.apply_rules(CFG, data, tmp_path / "cache")
    entry = content["articles"][aid]
    assert entry["scope"] == "body" and entry["tags"][0]["matched"] == "母子モ" and entry["tags"][0]["in"] == "body"
    assert result.updated == 1 and result.title_only == 0 and result.tagged == 1


def test_apply_rules_is_idempotent_and_keeps_results_when_the_body_is_gone(tmp_path):
    data, aid = _data(tmp_path)
    _cache(tmp_path, aid, 1, "母子モ")
    content, _ = rt.apply_rules(CFG, data, tmp_path / "cache")
    rt.write_atomic(data / "rule_tags.json", content)
    again, result = rt.apply_rules(CFG, data, tmp_path / "cache")
    assert again == content and result.unchanged == 1 and result.changed is False
    # 本文のキャッシュがなくなっても（Actions）、同じ版・同じルールなら結果を残す
    shutil.rmtree(tmp_path / "cache")
    kept, result = rt.apply_rules(CFG, data, tmp_path / "cache")
    assert kept == content and result.unchanged == 1


def test_apply_rules_rule_change_without_body_keeps_old_result_and_says_so(tmp_path):
    data, aid = _data(tmp_path)
    _cache(tmp_path, aid, 1, "母子モ")
    content, _ = rt.apply_rules(CFG, data, tmp_path / "cache")
    rt.write_atomic(data / "rule_tags.json", content)
    shutil.rmtree(tmp_path / "cache")
    new_cfg = FakeConfig([{"label": "母子モ", "pattern": "母子モ(?!デル)"}, {"label": "別", "pattern": "別の言葉"}])
    kept, result = rt.apply_rules(new_cfg, data, tmp_path / "cache")
    assert kept["articles"][aid] == content["articles"][aid] and result.stale == 1
    # 本文があれば、新しいルールで判定し直す
    _cache(tmp_path, aid, 1, "母子モ と 別の言葉")
    redone, result = rt.apply_rules(new_cfg, data, tmp_path / "cache")
    assert [t["label"] for t in redone["articles"][aid]["tags"]] == ["母子モ", "別"] and result.updated == 1


def test_apply_rules_new_article_version_is_judged_again_and_unsupported_uses_title(tmp_path):
    data, aid = _data(tmp_path)
    _cache(tmp_path, aid, 1, "関係のない本文")
    content, _ = rt.apply_rules(CFG, data, tmp_path / "cache")
    rt.write_atomic(data / "rule_tags.json", content)
    data, _ = _data(tmp_path, version=2)
    _cache(tmp_path, aid, 2, "第2版で母子モに言及")
    redone, result = rt.apply_rules(CFG, data, tmp_path / "cache")
    assert redone["articles"][aid]["article_version"] == 2 and redone["articles"][aid]["tags"] and result.updated == 1
    data2, aid2 = _data(tmp_path / "b", title="【架空】母子モの会員限定ページ", extraction="unsupported")
    unsupported, _ = rt.apply_rules(CFG, data2, tmp_path / "b" / "cache")
    assert unsupported["articles"][aid2]["scope"] == "title" and unsupported["articles"][aid2]["tags"][0]["in"] == "title"


# ---- 画面用データへの反映

TAG_DEFS = {k: {"id": k, "name": k.upper(), "enabled": True} for k in ("a", "b", "c", "d")}
MATCHES = [{"tag_id": "c", "label": "母子モ", "matched": "母子モ", "in": "title"},
           {"tag_id": "c", "label": "CMIC Trust", "matched": "CMIC Trust", "in": "body"}]


def test_rule_tag_entries_group_by_tag_and_show_label_and_place_only():
    entries = ex.rule_tag_entries(MATCHES)
    assert [e["tag_id"] for e in entries] == ["c"]
    assert entries[0]["reason"] == "ルール（キーワード一致）：「母子モ」（題名）「CMIC Trust」（本文）が見つかりました"
    assert ex.rule_tag_entries(None) == []


def test_final_tags_order_ai_source_rule_human_and_first_origin_wins():
    ai = [{"tag_id": "a", "reason": "r"}]
    fixed = [{"tag_id": "b", "reason": "設定"}]
    rules = ex.rule_tag_entries(MATCHES) + [{"tag_id": "b", "reason": "ルール"}]
    tags = ex.final_tags(ai, {"add": ["d"]}, TAG_DEFS, fixed, rules)
    assert [(t["id"], t["origin"]) for t in tags] == [("a", "ai"), ("b", "source"), ("c", "rule"), ("d", "human")]
    assert [(t["id"], t["origin"]) for t in ex.final_tags(None, None, TAG_DEFS, None, rules)] == [("c", "rule"), ("b", "rule")]


def test_removed_rule_tag_is_shown_as_removed_once():
    override = {"remove": ["c"]}
    rules = ex.rule_tag_entries(MATCHES)
    assert ex.final_tags(None, override, TAG_DEFS, None, rules) == []
    assert ex.removed_tags(None, override, TAG_DEFS, [{"tag_id": "c", "reason": "x"}], rules) == [{"id": "c", "name": "C"}]


def test_real_data_rule_tags_validate_and_vendor_articles_are_tagged_exactly_once():
    report = validate_all(REPO_ROOT / "config", REPO_ROOT / "data")
    assert report.errors == []
    config, _ = validate_config(REPO_ROOT / "config")
    outputs = ex.build_public_data(config, REPO_ROOT / "data", "real", "2026-10-07T09:00:00+09:00")
    assert ex.check_public_data(outputs, environ={}) == []
    for a in outputs["articles.json"]["articles"]:
        assert sum(1 for t in a["tags"] if t["id"] == "vendor-trend") <= 1, a["title"]


# ---- 設定の検証

def _tags_config(tmp_path, mutate):
    shutil.copytree(REPO_ROOT / "config", tmp_path / "config")
    tags = read_yaml(tmp_path / "config" / "tags.yaml")
    mutate(tags["tags"])
    write_yaml(tmp_path / "config" / "tags.yaml", tags)
    return validate_config(tmp_path / "config")[1]


def test_auto_rules_require_rule_only_a_valid_regex_and_unique_labels(tmp_path):
    def not_rule_only(tags):
        next(t for t in tags if t["id"] == "vendor-trend")["rule_only"] = False
    assert any("rule_only: true のタグだけ" in e for e in _tags_config(tmp_path / "a", not_rule_only).errors)

    def bad_regex(tags):
        next(t for t in tags if t["id"] == "vendor-trend")["auto_rules"].append({"label": "壊れた規則", "pattern": "("})
    assert any("正規表現が不正" in e for e in _tags_config(tmp_path / "b", bad_regex).errors)

    def dup_label(tags):
        next(t for t in tags if t["id"] == "vendor-trend")["auto_rules"].append({"label": "母子モ", "pattern": "別"})
    assert any("名前 '母子モ' が重複" in e for e in _tags_config(tmp_path / "c", dup_label).errors)


def test_rule_match_in_a_non_vendor_source_article_shows_as_rule_tag_in_public_data(tmp_path):
    shutil.copytree(REPO_ROOT / "data", tmp_path / "data")
    path = tmp_path / "data" / "rule_tags.json"
    content = read_json(path)
    cfa_id = next(p.stem for p in sorted((tmp_path / "data" / "articles").glob("*.json"))
                  if read_json(p)["article"]["source_id"] == "cfa-news")
    content["articles"][cfa_id]["tags"] = [{"tag_id": "vendor-trend", "label": "ミラボ", "matched": "ミラボ", "in": "body"}]
    path.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
    config, _ = validate_config(REPO_ROOT / "config")
    outputs = ex.build_public_data(config, tmp_path / "data", "real", "2026-10-07T09:00:00+09:00")
    article = next(a for a in outputs["articles.json"]["articles"] if a["id"] == cfa_id)
    tag = next(t for t in article["tags"] if t["id"] == "vendor-trend")
    assert tag["origin"] == "rule" and "「ミラボ」（本文）" in tag["reason"]
    assert ex.check_public_data(outputs, environ={}) == []
