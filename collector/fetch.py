"""Webからの取得。

- HttpFetcher：実際のWeb取得（段階2-bから使う）。User-Agent、timeout、サイズ上限、待機時間、
  robots.txt の確認、リダイレクト先の許可ホスト確認を行う。
- FixtureFetcher：テスト用。URLとローカルファイルの対応表から返す（ネットワークに出ない）。
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request
import urllib.robotparser
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol
from urllib.parse import urljoin, urlsplit

import yaml

from collector.urls import UrlRejected, check_allowed

USER_AGENT = "info-test-rs-collector/0.1 (+https://github.com/inukaitk/info_test_rs; public-info research)"
MAX_REDIRECTS = 5


@dataclass
class Response:
    url: str  # 最終的なURL（リダイレクト後）
    status: int
    content_type: str
    body: bytes
    headers: dict[str, str] = field(default_factory=dict)


class FetchError(Exception):
    """取得に失敗した（理由を日本語で持つ）。"""


class Fetcher(Protocol):
    def get(self, url: str, *, allowed_hosts: list[str], max_bytes: int, timeout: float) -> Response: ...


# ---------------------------------------------------------------- 実際の取得


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None  # リダイレクトは自分で1回ずつ確認して追う


class HttpFetcher:
    def __init__(self, wait_seconds: float = 3.0, opener: Callable | None = None, sleep: Callable = time.sleep,
                 respect_robots: bool = True):
        self.wait_seconds = wait_seconds
        self._opener = opener or urllib.request.build_opener(_NoRedirect).open
        self._sleep = sleep
        self._last: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self.respect_robots = respect_robots

    def _wait(self, host: str) -> None:
        last = self._last.get(host)
        if last is not None:
            remaining = self.wait_seconds - (time.monotonic() - last)
            if remaining > 0:
                self._sleep(remaining)
        self._last[host] = time.monotonic()

    def _raw(self, url: str, max_bytes: int, timeout: float) -> tuple[int, dict[str, str], bytes]:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "ja"})
        try:
            resp = self._opener(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers or {}), b""
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise FetchError(f"接続できません（{getattr(e, 'reason', e)}）。ネットワーク設定またはサイト側の問題の可能性") from e
        with resp:
            body = resp.read(max_bytes + 1)
            if len(body) > max_bytes:
                raise FetchError(f"サイズ上限（{max_bytes}バイト）を超えました")
            return resp.status, dict(resp.headers), body

    def allowed_by_robots(self, url: str, max_bytes: int, timeout: float) -> bool:
        parts = urlsplit(url)
        key = f"{parts.scheme}://{parts.netloc}"
        if key not in self._robots:
            parser = urllib.robotparser.RobotFileParser()
            try:
                self._wait(parts.netloc)
                status, _, body = self._raw(f"{key}/robots.txt", max_bytes, timeout)
            except FetchError:
                status, body = 0, b""
            if status == 200:
                parser.parse(body.decode("utf-8", errors="ignore").splitlines())
                self._robots[key] = parser
            elif status in (401, 403):
                parser.disallow_all = True
                self._robots[key] = parser
            else:
                self._robots[key] = None  # robots.txt なし：制限なし
        parser = self._robots[key]
        return parser is None or parser.can_fetch(USER_AGENT, url)

    def get(self, url: str, *, allowed_hosts: list[str], max_bytes: int, timeout: float) -> Response:
        current = check_allowed(url, allowed_hosts)
        if self.respect_robots and not self.allowed_by_robots(current, max_bytes, timeout):
            raise FetchError("robots.txt で取得が禁止されています")
        for _ in range(MAX_REDIRECTS + 1):
            self._wait(urlsplit(current).netloc)
            status, headers, body = self._raw(current, max_bytes, timeout)
            if status in (301, 302, 303, 307, 308):
                location = headers.get("Location") or headers.get("location")
                if not location:
                    raise FetchError(f"HTTP {status}（転送先なし）")
                try:
                    current = check_allowed(urljoin(current, location), allowed_hosts)
                except UrlRejected as e:
                    raise FetchError(f"許可していない転送先です（{e}）") from e
                continue
            if status != 200:
                raise FetchError(f"HTTP {status}")
            ctype = headers.get("Content-Type") or headers.get("content-type") or ""
            return Response(current, status, ctype, body, headers)
        raise FetchError("転送が多すぎます")


# ---------------------------------------------------------------- テスト用


class FixtureFetcher:
    """URL → ローカルファイルの対応表で応答する。ネットワークには出ない。

    対応表（YAML）の例:
        https://news.example.org/rss.xml: {file: rss.xml, type: application/rss+xml}
        https://news.example.org/broken: {status: 500}
        https://news.example.org/old: {redirect: https://news.example.org/new}
    """

    def __init__(self, root: Path, routes: dict[str, dict]):
        self.root = root
        self.routes = dict(routes)
        self.requested: list[str] = []

    @classmethod
    def from_manifest(cls, manifest: Path) -> "FixtureFetcher":
        routes = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
        return cls(manifest.parent, routes)

    def override(self, routes: dict[str, dict]) -> "FixtureFetcher":
        return FixtureFetcher(self.root, {**self.routes, **routes})

    def get(self, url: str, *, allowed_hosts: list[str], max_bytes: int, timeout: float) -> Response:
        current = check_allowed(url, allowed_hosts)
        for _ in range(MAX_REDIRECTS + 1):
            self.requested.append(current)
            route = self.routes.get(current)
            if route is None:
                raise FetchError("HTTP 404")
            if "redirect" in route:
                try:
                    current = check_allowed(route["redirect"], allowed_hosts)
                except UrlRejected as e:
                    raise FetchError(f"許可していない転送先です（{e}）") from e
                continue
            if route.get("timeout"):
                raise FetchError(f"タイムアウト（{int(timeout)}秒）")
            status = route.get("status", 200)
            if status != 200:
                raise FetchError(f"HTTP {status}")
            body = (self.root / route["file"]).read_bytes()
            if len(body) > max_bytes:
                raise FetchError(f"サイズ上限（{max_bytes}バイト）を超えました")
            return Response(current, 200, route.get("type", "text/html; charset=utf-8"), body)
        raise FetchError("転送が多すぎます")
