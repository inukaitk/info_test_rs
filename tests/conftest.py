import copy
import json
import shutil
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def config_dir(tmp_path):
    """リポジトリのconfig/を一時フォルダへ複製する（テストで書き換えてよい）。"""
    target = tmp_path / "config"
    shutil.copytree(REPO_ROOT / "config", target)
    return target


@pytest.fixture
def data_dir(tmp_path):
    """架空の正常データ（tests/fixtures/valid_data）を一時フォルダへ複製する。"""
    target = tmp_path / "data"
    shutil.copytree(FIXTURES / "valid_data", target)
    return target


def read_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def write_yaml(path: Path, data) -> None:
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def deep(data):
    return copy.deepcopy(data)
