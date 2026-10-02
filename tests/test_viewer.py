"""1ファイル版（viewer/info_viewer.html）が最新の画面用JSONと一致し、安全に作られていることの確認。"""

import json
import re

from conftest import REPO_ROOT

VIEWER = REPO_ROOT / "viewer" / "info_viewer.html"
PUBLIC_DATA = REPO_ROOT / "web" / "public" / "data"


def _html():
    return VIEWER.read_text(encoding="utf-8")


def _embedded():
    m = re.search(r'<script type="application/json" id="embedded-site-data">(.*?)</script>', _html(), re.S)
    assert m, "埋め込みデータが見つかりません"
    return json.loads(m.group(1))


def test_viewer_matches_public_data():
    """画面用JSONを作り直したら、cd web; npm run build:standalone で1ファイル版も作り直すこと。"""
    data = _embedded()
    for name in ("meta", "articles", "status", "reports"):
        assert data[name] == json.loads((PUBLIC_DATA / f"{name}.json").read_text(encoding="utf-8")), name


def test_viewer_has_no_external_resources():
    html = _html()
    assert not re.search(r'<(script|link|img|iframe)[^>]+(src|href)="(https?:)?//', html)
    assert "<link" not in html


def test_viewer_has_strict_csp():
    m = re.search(r'http-equiv="Content-Security-Policy" content="([^"]+)"', _html())
    assert m
    csp = m.group(1)
    assert "default-src 'none'" in csp
    assert "connect-src 'none'" in csp
    assert "unsafe-inline" not in csp and "unsafe-eval" not in csp
    assert re.search(r"script-src 'sha256-[A-Za-z0-9+/=]+'", csp)


def test_viewer_embeds_only_screen_data():
    """埋め込むのは画面用JSON（meta・articles・status・reports）だけ。タグ候補などは含まない。"""
    data = _embedded()
    assert set(data) == {"meta", "articles", "status", "reports"}
    candidates = json.loads((REPO_ROOT / "demo" / "data" / "tag_candidates.json").read_text(encoding="utf-8"))
    html = _html()
    for c in candidates["candidates"]:
        assert c["name"] not in html


def test_demo_viewer_is_marked_as_fictional():
    data = _embedded()
    if data["meta"]["is_demo"]:
        assert all("【架空】" in a["title"] for a in data["articles"]["articles"])
