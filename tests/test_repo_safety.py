""".env・.cache/・秘密値がコミット対象に入っていないことの確認。"""

import shutil
import subprocess
import sys

import pytest

from conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import check_repo_safety as safety  # noqa: E402

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or not (REPO_ROOT / ".git").exists(), reason="Gitリポジトリではない"
)


def test_tracked_files_are_safe():
    assert safety.check(safety.git_paths(staged=False)) == []


def test_staged_files_are_safe():
    assert safety.check(safety.git_paths(staged=True)) == []


@pytest.mark.parametrize(
    "path",
    [".env", ".env.local", "config/.env", ".cache/body.txt", "data/.cache/x.json",
     "web/node_modules/a.js", ".venv/bin/python", "logs/run.txt", "collector.log"],
)
def test_forbidden_paths(path):
    assert safety.forbidden_reason(path)


@pytest.mark.parametrize("path", [".env.example", "config/site.yaml", "data/state.json", "docs/cache.md"])
def test_allowed_paths(path):
    assert safety.forbidden_reason(path) is None


@pytest.mark.parametrize("path", [".env", ".env.production", ".cache/body.txt", "node_modules/x/index.js",
                                  ".venv/x", "run.log"])
def test_gitignore_covers_forbidden_files(path):
    result = subprocess.run(["git", "check-ignore", "-q", "--no-index", path], cwd=REPO_ROOT)
    assert result.returncode == 0, f"{path} が .gitignore で除外されていません"


def test_env_example_is_not_ignored():
    result = subprocess.run(["git", "check-ignore", "-q", "--no-index", ".env.example"], cwd=REPO_ROOT)
    assert result.returncode == 1


def test_secret_in_file_is_detected(tmp_path, monkeypatch):
    monkeypatch.setattr(safety, "REPO_ROOT", tmp_path)
    (tmp_path / "notes.md").write_text("key: sk-" + "x" * 30, encoding="utf-8")
    (tmp_path / "ok.md").write_text("普通の文章", encoding="utf-8")
    problems = safety.check(["notes.md", "ok.md"])
    assert len(problems) == 1 and problems[0].startswith("notes.md")


def test_pre_commit_hook_blocks_env_file(tmp_path):
    """実際の git commit で .env が止められることを一時リポジトリで確認する。"""
    repo = tmp_path / "repo"
    shutil.copytree(REPO_ROOT, repo, ignore=shutil.ignore_patterns(".git", ".venv", "node_modules", ".pytest_cache"))
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com", "PATH": __import__("os").environ["PATH"]}

    def git(*args):
        return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, env=env)

    git("init", "-q")
    git("config", "core.hooksPath", ".githooks")
    (repo / ".env").write_text("AI_API_KEY=dummy-value-123", encoding="utf-8")
    git("add", "-A")
    git("add", "-f", ".env")
    result = git("commit", "-q", "-m", "test")
    assert result.returncode != 0
    assert ".env" in result.stderr
    git("rm", "-q", "--cached", ".env")
    assert git("commit", "-q", "-m", "test").returncode == 0
