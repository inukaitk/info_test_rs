"""設定（config/）とデータ（data/）のスキーマ検証。

JSON Schema（schemas/）による形式の検証に加えて、スキーマだけでは書けない
ファイル間の整合性（タグidの存在、IDとファイル名の一致など）を確認する。
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = REPO_ROOT / "schemas"
SCHEMA_BASE = "https://info-test-rs.local/schemas/"

CONFIG_FILES = {
    "sources.yaml": "config/sources.schema.json",
    "tags.yaml": "config/tags.schema.json",
    "tag_overrides.yaml": "config/tag_overrides.schema.json",
    "site.yaml": "config/site.schema.json",
    "ai.yaml": "config/ai.schema.json",
}


def article_id_from_canonical_url(canonical_url: str) -> str:
    """正規化URLから決定的にarticle_idを作る。"""
    digest = hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()
    return f"a_{digest[:16]}"


# ---------------------------------------------------------------- YAML


class _StrictLoader(yaml.SafeLoader):
    """重複キーを拒否し、日付を文字列のまま読むYAMLローダー。"""


_StrictLoader.yaml_implicit_resolvers = {
    key: [(tag, regexp) for tag, regexp in resolvers if tag != "tag:yaml.org,2002:timestamp"]
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def _construct_mapping(loader: _StrictLoader, node: yaml.MappingNode) -> dict:
    mapping: dict = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                None, None, f"キー {key!r} が重複しています", key_node.start_mark
            )
        mapping[key] = loader.construct_object(value_node, deep=True)
    return mapping


_StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)


def load_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return yaml.load(f, Loader=_StrictLoader)


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- スキーマ


def _build_registry() -> Registry:
    resources = []
    for path in sorted(SCHEMA_DIR.rglob("*.schema.json")):
        schema = load_json(path)
        resources.append((schema["$id"], Resource.from_contents(schema)))
    return Registry().with_resources(resources)


_REGISTRY = _build_registry()


def schema_errors(instance: Any, schema_name: str) -> list[str]:
    """schemas/からの相対パスで指定したスキーマで検証し、エラー文の一覧を返す。"""
    schema = _REGISTRY.contents(SCHEMA_BASE + schema_name)
    validator = Draft202012Validator(schema, registry=_REGISTRY)
    messages = []
    for error in sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path)):
        location = "/".join(str(p) for p in error.absolute_path) or "(ルート)"
        messages.append(f"{location}: {error.message}")
    return messages


# ---------------------------------------------------------------- 検証結果


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)

    def add(self, where: str, messages: list[str]) -> None:
        self.errors.extend(f"{where}: {m}" for m in messages)

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass
class Config:
    sources: dict
    tags: dict
    tag_overrides: dict
    site: dict
    ai: dict

    @property
    def source_ids(self) -> set[str]:
        return {s["id"] for s in self.sources.get("sources", [])}

    @property
    def tag_ids(self) -> set[str]:
        return {t["id"] for t in self.tags.get("tags", [])}

    @property
    def enabled_tag_ids(self) -> set[str]:
        return {t["id"] for t in self.tags.get("tags", []) if t.get("enabled")}

    @property
    def ai_tags(self) -> list[dict]:
        """AIが選べるタグ（有効で、情報源の設定でだけ付ける `rule_only` ではないもの）。"""
        return [t for t in self.tags.get("tags", []) if t.get("enabled") and not t.get("rule_only")]


def _duplicates(values: list) -> list:
    seen, dups = set(), []
    for v in values:
        if v in seen and v not in dups:
            dups.append(v)
        seen.add(v)
    return dups


# ---------------------------------------------------------------- config/


def validate_config(
    config_dir: Path, report: Report | None = None, overlay_dir: Path | None = None
) -> tuple[Config | None, Report]:
    """config_dir の設定を検証する。overlay_dir に同名ファイルがあればそちらを使う（demo/config 用）。"""
    report = report or Report()
    loaded: dict[str, Any] = {}
    for filename, schema_name in CONFIG_FILES.items():
        path = config_dir / filename
        where = f"config/{filename}"
        if overlay_dir is not None and (overlay_dir / filename).exists():
            path = overlay_dir / filename
            where = f"{overlay_dir.parent.name}/{overlay_dir.name}/{filename}"
        if not path.exists():
            report.add(where, ["ファイルがありません"])
            continue
        try:
            data = load_yaml(path)
        except yaml.YAMLError as e:
            report.add(where, [f"YAMLとして読めません: {e}"])
            continue
        errors = schema_errors(data, schema_name)
        report.add(where, errors)
        if not errors:
            loaded[filename] = data

    if len(loaded) != len(CONFIG_FILES):
        return None, report

    config = Config(
        sources=loaded["sources.yaml"],
        tags=loaded["tags.yaml"],
        tag_overrides=loaded["tag_overrides.yaml"],
        site=loaded["site.yaml"],
        ai=loaded["ai.yaml"],
    )
    _check_sources(config, report)
    _check_csv_fields(config, report)
    _check_tags(config, report)
    _check_source_fixed_tags(config, report)
    _check_overrides(config, report)
    return config, report


def _check_sources(config: Config, report: Report) -> None:
    where = "config/sources.yaml"
    sources = config.sources["sources"]
    for dup in _duplicates([s["id"] for s in sources]):
        report.add(where, [f"情報源id {dup!r} が重複しています"])
    for s in sources:
        host = urlsplit(s["entry_url"]).hostname
        if host not in s["allowed_hosts"]:
            report.add(where, [f"{s['id']}: 入口URLのホスト {host!r} が allowed_hosts にありません"])
        for kind in ("include", "exclude"):
            for pattern in s.get("link_rules", {}).get(kind, []):
                try:
                    re.compile(pattern)
                except re.error as e:
                    report.add(where, [f"{s['id']}: link_rules.{kind} の正規表現 {pattern!r} が不正です（{e}）"])


def _check_csv_fields(config: Config, report: Report) -> None:
    where = "config/sources.yaml"
    sources = config.sources["sources"]
    for s in sources:
        if s["enabled"]:
            for key in ("csv_id", "publisher", "source_type"):
                if not s.get(key):
                    report.add(where, [f"{s['id']}: 収集中の情報源には、外部連携用CSVの {key} が必要です"])
    for dup in _duplicates([s["csv_id"] for s in sources if s.get("csv_id")]):
        report.add(where, [f"csv_id {dup!r} が重複しています"])


def _check_tags(config: Config, report: Report) -> None:
    where = "config/tags.yaml"
    tags = config.tags["tags"]
    for dup in _duplicates([t["id"] for t in tags]):
        report.add(where, [f"タグid {dup!r} が重複しています"])
    for dup in _duplicates([t["name"] for t in tags]):
        report.add(where, [f"タグ名 {dup!r} が重複しています"])
    for t in tags:
        rules = t.get("auto_rules", [])
        if rules and not t.get("rule_only"):
            report.add(where, [f"{t['id']}: auto_rules は rule_only: true のタグだけに指定できます（AIとルールの二重判定を避けるため）"])
        for dup in _duplicates([r["label"] for r in rules]):
            report.add(where, [f"{t['id']}: auto_rules の名前 {dup!r} が重複しています"])
        for r in rules:
            try:
                re.compile(r["pattern"])
            except re.error as e:
                report.add(where, [f"{t['id']}: auto_rules {r['label']!r} の正規表現が不正です（{e}）"])


def _check_source_fixed_tags(config: Config, report: Report) -> None:
    where = "config/sources.yaml"
    for s in config.sources["sources"]:
        for tag_id in s.get("fixed_tags", []):
            if tag_id not in config.tag_ids:
                report.add(where, [f"{s['id']}: fixed_tags の未登録のタグid {tag_id!r} です"])
            elif tag_id not in config.enabled_tag_ids:
                report.add(where, [f"{s['id']}: fixed_tags の廃止済みのタグ {tag_id!r} は指定できません"])


def _check_overrides(config: Config, report: Report) -> None:
    where = "config/tag_overrides.yaml"
    overrides = config.tag_overrides["overrides"]
    for dup in _duplicates([o["article_id"] for o in overrides]):
        report.add(where, [f"article_id {dup!r} の修正が重複しています（1記事1項目にまとめる）"])
    for o in overrides:
        add, remove = set(o.get("add", [])), set(o.get("remove", []))
        for tag_id in sorted((add | remove) - config.tag_ids):
            report.add(where, [f"{o['article_id']}: 未登録のタグid {tag_id!r} です"])
        for tag_id in sorted(add & (config.tag_ids - config.enabled_tag_ids)):
            report.add(where, [f"{o['article_id']}: 廃止済みのタグ {tag_id!r} は追加できません"])
        for tag_id in sorted(add & remove):
            report.add(where, [f"{o['article_id']}: タグ {tag_id!r} が add と remove の両方にあります"])


# ---------------------------------------------------------------- data/


def validate_data(data_dir: Path, config: Config, report: Report | None = None) -> Report:
    report = report or Report()
    latest_versions = _check_articles(data_dir, config, report)
    _check_summaries(data_dir, config, latest_versions, report)
    _check_runs(data_dir, config, report)
    _check_state(data_dir, config, report)
    _check_tag_candidates(data_dir, latest_versions, report)
    _check_rule_tags(data_dir, config, latest_versions, report)
    return report


def _load_and_check(path: Path, schema_name: str, where: str, report: Report) -> Any | None:
    try:
        data = load_json(path)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        report.add(where, [f"JSONとして読めません: {e}"])
        return None
    errors = schema_errors(data, schema_name)
    report.add(where, errors)
    return None if errors else data


def _check_articles(data_dir: Path, config: Config, report: Report) -> dict[str, int]:
    latest_versions: dict[str, int] = {}
    for path in sorted((data_dir / "articles").glob("*.json")):
        where = f"data/articles/{path.name}"
        data = _load_and_check(path, "files/article_file.schema.json", where, report)
        if data is None:
            continue
        article, versions = data["article"], data["versions"]
        article_id = article["article_id"]
        problems = []
        if path.stem != article_id:
            problems.append(f"ファイル名と article_id {article_id!r} が一致しません")
        if article_id_from_canonical_url(article["canonical_url"]) != article_id:
            problems.append("article_id が canonical_url から計算した値と一致しません")
        if article["source_id"] not in config.source_ids:
            problems.append(f"未登録の情報源id {article['source_id']!r} です")
        if [v["version"] for v in versions] != list(range(1, len(versions) + 1)):
            problems.append("versions の version が 1 からの連番になっていません")
        if article["latest_version"] != len(versions):
            problems.append("latest_version が版の数と一致しません")
        if any(v["article_id"] != article_id for v in versions):
            problems.append("versions に別の article_id が含まれています")
        report.add(where, problems)
        latest_versions[article_id] = article["latest_version"]
    return latest_versions


def _check_summaries(data_dir: Path, config: Config, latest_versions: dict[str, int], report: Report) -> None:
    for path in sorted((data_dir / "summaries").glob("*.json")):
        where = f"data/summaries/{path.name}"
        data = _load_and_check(path, "files/summary_file.schema.json", where, report)
        if data is None:
            continue
        article_id = data["article_id"]
        problems = []
        if path.stem != article_id:
            problems.append(f"ファイル名と article_id {article_id!r} が一致しません")
        if article_id not in latest_versions:
            problems.append(f"記事 {article_id!r} が data/articles にありません")
        for i, s in enumerate(data["summaries"]):
            if s["article_id"] != article_id:
                problems.append(f"summaries/{i}: 別の article_id が含まれています")
            latest = latest_versions.get(article_id)
            if latest is not None and s["article_version"] > latest:
                problems.append(f"summaries/{i}: 存在しない版 {s['article_version']} を参照しています")
            for tag in s["ai_tags"] or []:
                if tag["tag_id"] not in config.tag_ids:
                    problems.append(f"summaries/{i}: 未登録のタグid {tag['tag_id']!r} です")
        report.add(where, problems)


def _check_runs(data_dir: Path, config: Config, report: Report) -> None:
    for path in sorted((data_dir / "runs").glob("*.json")):
        where = f"data/runs/{path.name}"
        data = _load_and_check(path, "files/run_file.schema.json", where, report)
        if data is None:
            continue
        run = data["run"]
        problems = []
        if path.stem != run["run_id"]:
            problems.append(f"ファイル名と run_id {run['run_id']!r} が一致しません")
        if run["period"] and run["period"]["start"] > run["period"]["end"]:
            problems.append("period の start が end より後です")
        report.add(where, problems)


def _check_state(data_dir: Path, config: Config, report: Report) -> None:
    path = data_dir / "state.json"
    if not path.exists():
        return
    data = _load_and_check(path, "files/state_file.schema.json", "data/state.json", report)
    if data is None:
        return
    problems = []
    for key, state in data["sources"].items():
        if state["source_id"] != key:
            problems.append(f"sources/{key}: source_id {state['source_id']!r} がキーと一致しません")
        if key not in config.source_ids:
            problems.append(f"sources/{key}: 未登録の情報源idです")
    report.add("data/state.json", problems)


def _check_rule_tags(data_dir: Path, config: Config, latest_versions: dict[str, int], report: Report) -> None:
    path = data_dir / "rule_tags.json"
    if not path.exists():
        return
    where = "data/rule_tags.json"
    data = _load_and_check(path, "files/rule_tags_file.schema.json", where, report)
    if data is None:
        return
    problems = []
    for article_id, entry in data["articles"].items():
        if article_id not in latest_versions:
            problems.append(f"{article_id}: 記事がありません")
            continue
        if entry["article_version"] > latest_versions[article_id]:
            problems.append(f"{article_id}: article_version が記事の最新版より新しくなっています")
        for t in entry["tags"]:
            if t["tag_id"] not in config.tag_ids:
                problems.append(f"{article_id}: 未登録のタグid {t['tag_id']!r} です")
    report.add(where, problems)


def _check_tag_candidates(data_dir: Path, latest_versions: dict[str, int], report: Report) -> None:
    path = data_dir / "tag_candidates.json"
    if not path.exists():
        return
    data = _load_and_check(path, "files/tag_candidates_file.schema.json", "data/tag_candidates.json", report)
    if data is None:
        return
    problems = [
        f"candidates/{i}: 記事 {c['article_id']!r} が data/articles にありません"
        for i, c in enumerate(data["candidates"])
        if c["article_id"] not in latest_versions
    ]
    report.add("data/tag_candidates.json", problems)


def validate_all(config_dir: Path, data_dir: Path, overlay_dir: Path | None = None) -> Report:
    config, report = validate_config(config_dir, overlay_dir=overlay_dir)
    if config is not None:
        validate_data(data_dir, config, report)
    return report
