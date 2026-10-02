"""URL の正規化と、取得してよいURLかの確認。"""

from __future__ import annotations

import ipaddress
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

# 意味を持たない既知の追跡パラメーター（これ以外のクエリーは残す）
TRACKING_PARAMS = {
    "fbclid", "gclid", "dclid", "msclkid", "yclid", "mc_cid", "mc_eid", "_ga", "_gl", "igshid", "spm",
}
TRACKING_PREFIXES = ("utm_",)


class UrlRejected(ValueError):
    """取得してはいけないURL。"""


def normalize_url(url: str, base: str | None = None) -> str:
    """正規化URL：相対URLの解決、スキーム・ホストの小文字化、既定ポートとフラグメントの削除、追跡パラメーターの削除。"""
    url = url.strip()
    if base:
        url = urljoin(base, url)
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    if scheme not in ("http", "https"):
        raise UrlRejected(f"http(s) 以外のURLです: {scheme or '(なし)'}")
    host = (parts.hostname or "").lower().rstrip(".")
    if not host:
        raise UrlRejected("ホストがありません")
    port = parts.port
    netloc = host if port is None or (scheme, port) in (("http", 80), ("https", 443)) else f"{host}:{port}"
    if parts.username or parts.password:
        raise UrlRejected("認証情報を含むURLは扱いません")
    query = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in TRACKING_PARAMS and not k.lower().startswith(TRACKING_PREFIXES)
    ]
    path = parts.path or "/"
    return urlunsplit((scheme, netloc, path, urlencode(query, doseq=True), ""))


def _is_private_host(host: str) -> bool:
    if host in ("localhost",) or host.endswith((".localhost", ".local", ".internal")):
        return True
    try:
        ip = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified


def check_allowed(url: str, allowed_hosts: list[str]) -> str:
    """許可ホストのURLか確認し、正規化したURLを返す。localhost・内部IP・非HTTPは拒否する。"""
    normalized = normalize_url(url)
    host = urlsplit(normalized).hostname or ""
    if _is_private_host(host):
        raise UrlRejected(f"内部アドレスへのアクセスは拒否します: {host}")
    if host not in {h.lower() for h in allowed_hosts}:
        raise UrlRejected(f"許可ホスト以外です: {host}")
    return normalized
