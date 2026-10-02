"""config/ のスキーマ検証とファイル間の整合性のテスト。"""

import pytest

from collector.validation import schema_errors, validate_config
from conftest import REPO_ROOT, read_yaml, write_yaml


def errors_for(config_dir):
    _, report = validate_config(config_dir)
    return report.errors


def test_repository_config_is_valid():
    config, report = validate_config(REPO_ROOT / "config")
    assert report.errors == []
    assert config is not None


def test_example_sources_are_fictional():
    """設定例の情報源は予約済みの例示用ドメインだけを使う。"""
    sources = read_yaml(REPO_ROOT / "config" / "sources.yaml")["sources"]
    for s in sources:
        for host in s["allowed_hosts"]:
            assert host.split(".")[-2:] in (["example", "org"], ["example", "net"], ["example", "com"]), host
        assert "架空" in s["name"]


def test_tags_follow_spec_examples():
    names = {t["name"] for t in read_yaml(REPO_ROOT / "config" / "tags.yaml")["tags"]}
    assert names == {
        "母子保健", "子育て支援", "制度改正", "補助金・交付金",
        "通知・事務連絡", "自治体DX・標準化", "調査・統計", "審議会・検討会",
    }


def test_site_starts_in_demo_mode_without_correction_url():
    site = read_yaml(REPO_ROOT / "config" / "site.yaml")
    assert site["release_mode"] == "demo"
    assert site["correction_request_url"] is None


# ---- sources.yaml


def _mutate(config_dir, filename, fn):
    path = config_dir / filename
    data = read_yaml(path)
    fn(data)
    write_yaml(path, data)


@pytest.mark.parametrize(
    "mutation, expected",
    [
        (lambda d: d["sources"][0].pop("allowed_hosts"), "allowed_hosts"),
        (lambda d: d["sources"][0].update(method="browser"), "method"),
        (lambda d: d["sources"][0].update(id="Bad ID"), "id"),
        (lambda d: d["sources"][0].update(entry_url="file:///etc/passwd"), "entry_url"),
        (lambda d: d["sources"][0].update(timezone="UTC"), "timezone"),
        (lambda d: d["sources"][0]["limits"].update(max_items=0), "max_items"),
        (lambda d: d["sources"][0]["limits"].update(wait_seconds=0), "wait_seconds"),
        (lambda d: d["sources"][0].update(unknown_field=1), "unknown_field"),
        (lambda d: d["sources"][0].update(allowed_hosts=["https://kodomo.example.org/"]), "allowed_hosts"),
    ],
)
def test_sources_schema_rejects_invalid(config_dir, mutation, expected):
    _mutate(config_dir, "sources.yaml", mutation)
    errors = errors_for(config_dir)
    assert errors and any(expected in e for e in errors), errors


def test_sources_duplicate_id(config_dir):
    _mutate(config_dir, "sources.yaml", lambda d: d["sources"].append(dict(d["sources"][0])))
    assert any("重複" in e for e in errors_for(config_dir))


def test_sources_entry_host_must_be_allowed(config_dir):
    _mutate(config_dir, "sources.yaml", lambda d: d["sources"][0].update(allowed_hosts=["other.example.org"]))
    assert any("allowed_hosts にありません" in e for e in errors_for(config_dir))


def test_sources_invalid_regex(config_dir):
    _mutate(config_dir, "sources.yaml", lambda d: d["sources"][0]["link_rules"].update(include=["(unclosed"]))
    assert any("正規表現" in e for e in errors_for(config_dir))


# ---- tags.yaml


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d["tags"][0].pop("description"),
        lambda d: d["tags"][0].update(name=""),
        lambda d: d["tags"][0].update(enabled="yes"),
        lambda d: d["tags"][0].update(priority="high"),
    ],
)
def test_tags_schema_rejects_invalid(config_dir, mutation):
    _mutate(config_dir, "tags.yaml", mutation)
    assert errors_for(config_dir)


def test_tags_duplicate_id_and_name(config_dir):
    _mutate(config_dir, "tags.yaml", lambda d: d["tags"].append(dict(d["tags"][0])))
    errors = errors_for(config_dir)
    assert any("タグid" in e and "重複" in e for e in errors)
    assert any("タグ名" in e and "重複" in e for e in errors)


# ---- tag_overrides.yaml

ARTICLE = "a_3715ddd7b3d7eab6"


def _set_overrides(config_dir, overrides):
    write_yaml(config_dir / "tag_overrides.yaml", {"overrides": overrides})


def test_overrides_valid(config_dir):
    _set_overrides(config_dir, [
        {"article_id": ARTICLE, "add": ["system-revision"], "remove": ["survey-statistics"],
         "updated": "2026-10-01", "reason": "本文が制度改正の通知のため"},
    ])
    assert errors_for(config_dir) == []


def test_overrides_dates_are_read_as_strings(config_dir):
    """YAMLの日付（2026-10-01）が日付型に変換されず、スキーマの文字列パターンで検証される。"""
    (config_dir / "tag_overrides.yaml").write_text(
        f"overrides:\n  - article_id: {ARTICLE}\n    add: [system-revision]\n    updated: 2026-10-01\n",
        encoding="utf-8",
    )
    assert errors_for(config_dir) == []


@pytest.mark.parametrize(
    "override, expected",
    [
        ({"article_id": ARTICLE, "updated": "2026-10-01"}, None),  # add も remove もない
        ({"article_id": ARTICLE, "add": [], "updated": "2026-10-01"}, None),
        ({"article_id": "article-1", "add": ["system-revision"], "updated": "2026-10-01"}, "article_id"),
        ({"article_id": ARTICLE, "add": ["system-revision"], "updated": "2026/10/01"}, "updated"),
        ({"article_id": ARTICLE, "add": ["sales-opportunity"], "updated": "2026-10-01"}, "未登録"),
        ({"article_id": ARTICLE, "add": ["system-revision"], "remove": ["system-revision"], "updated": "2026-10-01"}, "両方"),
    ],
)
def test_overrides_rejects_invalid(config_dir, override, expected):
    _set_overrides(config_dir, [override])
    errors = errors_for(config_dir)
    assert errors
    if expected:
        assert any(expected in e for e in errors), errors


def test_overrides_duplicate_article(config_dir):
    item = {"article_id": ARTICLE, "add": ["system-revision"], "updated": "2026-10-01"}
    _set_overrides(config_dir, [item, dict(item)])
    assert any("重複" in e for e in errors_for(config_dir))


def test_overrides_cannot_add_disabled_tag(config_dir):
    _mutate(config_dir, "tags.yaml", lambda d: d["tags"][0].update(enabled=False))
    disabled = read_yaml(config_dir / "tags.yaml")["tags"][0]["id"]
    _set_overrides(config_dir, [{"article_id": ARTICLE, "add": [disabled], "updated": "2026-10-01"}])
    assert any("廃止済み" in e for e in errors_for(config_dir))


def test_overrides_can_remove_disabled_tag(config_dir):
    _mutate(config_dir, "tags.yaml", lambda d: d["tags"][0].update(enabled=False))
    disabled = read_yaml(config_dir / "tags.yaml")["tags"][0]["id"]
    _set_overrides(config_dir, [{"article_id": ARTICLE, "remove": [disabled], "updated": "2026-10-01"}])
    assert errors_for(config_dir) == []


# ---- site.yaml


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d.update(release_mode="production"),
        lambda d: d.update(correction_request_url="http://forms.example.com/x"),
        lambda d: d.update(correction_request_url=""),
        lambda d: d.update(page_size=0),
        lambda d: d.update(latest_days=0),
        lambda d: d.pop("latest_days"),
        lambda d: d.pop("release_mode"),
    ],
)
def test_site_schema_rejects_invalid(config_dir, mutation):
    _mutate(config_dir, "site.yaml", mutation)
    assert errors_for(config_dir)


def test_site_accepts_https_correction_url():
    assert schema_errors(
        {"site_name": "x", "correction_request_url": "https://forms.example.com/r/abc",
         "release_mode": "real", "page_size": 50, "latest_days": 7, "stale_after_days": 8},
        "config/site.schema.json",
    ) == []


# ---- YAMLの読み込み


def test_duplicate_yaml_key_is_rejected(config_dir):
    (config_dir / "site.yaml").write_text(
        "site_name: a\nsite_name: b\ncorrection_request_url: null\nrelease_mode: demo\npage_size: 50\n",
        encoding="utf-8",
    )
    assert any("重複" in e for e in errors_for(config_dir))


def test_missing_config_file(config_dir):
    (config_dir / "tags.yaml").unlink()
    config, report = validate_config(config_dir)
    assert config is None
    assert any("ファイルがありません" in e for e in report.errors)
