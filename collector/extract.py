"""一覧（RSS・HTML）からの候補URLの列挙と、記事（HTML・テキストPDF）からの本文・タイトル・日付の抽出。"""

from __future__ import annotations

import hashlib
import io
import re
import unicodedata
from dataclasses import dataclass, field

from bs4 import BeautifulSoup
from defusedxml import ElementTree as SafeET

from collector.dates import ParsedDate, find_japanese_date, parse_any
from collector.urls import UrlRejected, normalize_url

# 本文として扱わない要素（ナビゲーション・ヘッダー・フッター等の変化を本文の変更と誤判定しないため）
NON_CONTENT_TAGS = ["script", "style", "noscript", "template", "nav", "header", "footer", "aside", "form", "iframe", "svg", "button"]
NON_CONTENT_SELECTORS = [
    "[role=navigation]", "[role=banner]", "[role=contentinfo]", "[role=search]", "[aria-hidden=true]",
    ".breadcrumb", ".breadcrumbs", "#breadcrumb", ".pankuzu", ".topicpath", ".sns", ".share", ".pagetop", ".page-top",
]
PUBLISHED_LABELS = ("掲載日", "公開日", "公表日", "発表日", "作成日", "登録日", "掲載", "公開", "発出日", "Published")
UPDATED_LABELS = ("最終更新日", "更新日", "最終更新", "更新", "改訂日", "改訂", "Last updated", "Updated")


@dataclass
class Candidate:
    """一覧で見つかった記事の候補。"""

    url: str
    title: str | None
    listing_date: tuple[ParsedDate, str, str] | None = None  # (日付, 方法, 根拠)
    listing_updated: tuple[ParsedDate, str, str] | None = None


@dataclass
class Listing:
    candidates: list[Candidate]
    next_url: str | None = None
    rejected: list[str] = field(default_factory=list)


@dataclass
class DateFound:
    value: ParsedDate
    method: str
    evidence: str


@dataclass
class Extracted:
    title: str | None
    text: str
    content_type: str  # html / pdf
    published: DateFound | None = None
    updated: DateFound | None = None
    status: str = "ok"  # ok / unsupported
    error: str | None = None

    @property
    def content_hash(self) -> str | None:
        return content_hash(self.text) if self.status == "ok" else None


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    lines = [re.sub(r"[ \t　]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def content_hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def _short(text: str, limit: int = 120) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


# ---------------------------------------------------------------- RSS / RDF / Atom


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _child_text(el, *names: str) -> str | None:
    for child in el:
        if _local(child.tag) in names:
            text = (child.text or "").strip()
            if text:
                return text
    return None


def parse_feed(body: bytes, base_url: str) -> Listing:
    """RSS 2.0、RSS 1.0（RDF、dc:date）、Atom に対応。XML は安全なパーサー（外部実体を拒否）で読む。"""
    try:
        root = SafeET.fromstring(body)
    except Exception as e:  # noqa: BLE001  defusedxml・ParseError など
        raise ValueError(f"RSSとして読めません（{type(e).__name__}）") from e
    items = [el for el in root.iter() if _local(el.tag) in ("item", "entry")]
    listing = Listing([])
    for item in items:
        link = _child_text(item, "link")
        if link is None:  # Atom: <link href="...">
            for child in item:
                if _local(child.tag) == "link" and child.get("href") and child.get("rel", "alternate") == "alternate":
                    link = child.get("href")
                    break
        if not link:
            continue
        try:
            url = normalize_url(link, base_url)
        except UrlRejected:
            listing.rejected.append(link)
            continue
        title = _child_text(item, "title")
        pub_raw = _child_text(item, "pubDate", "published", "date", "issued")
        upd_raw = _child_text(item, "updated", "modified")
        pub = parse_any(pub_raw) if pub_raw else None
        upd = parse_any(upd_raw) if upd_raw else None
        tag = "pubDate" if _child_text(item, "pubDate") else ("dc:date" if _child_text(item, "date") else "published")
        listing.candidates.append(
            Candidate(
                url=url,
                title=title,
                listing_date=(pub, "rss_pubdate", f"<{tag}>{pub_raw}</{tag}>") if pub else None,
                listing_updated=(upd, "rss_updated", f"<updated>{upd_raw}</updated>") if upd else None,
            )
        )
    return listing


# ---------------------------------------------------------------- HTML 一覧


def _soup(body: bytes) -> BeautifulSoup:
    return BeautifulSoup(body, "html.parser")


def _date_in(element, date_selector: str | None) -> tuple[ParsedDate, str, str] | None:
    """要素の中から一覧の日付を探す。優先順：date_selector で指定した要素 ＞ <time datetime> ＞ class に date を含む要素。
    タイトル中の日付（例「記者会見（令和8年10月2日）」）を掲載日と取り違えないよう、文中の日付は最後の手段にする。"""
    candidates = []
    if date_selector:
        candidates += element.select(date_selector)
    candidates += element.find_all("time")
    candidates += element.select("[class*=date], [class*=Date]")
    for el in candidates:
        if el.name == "time" and el.get("datetime"):
            parsed = parse_any(el["datetime"])
            if parsed:
                return parsed, "listing_text", f'<time datetime="{el["datetime"]}">{el.get_text(strip=True)}</time>'[:200]
        found = find_japanese_date(el.get_text(" ", strip=True))
        if found:
            return found[0], "listing_text", found[1]
    return None


def parse_html_listing(body: bytes, base_url: str, link_rules: dict, next_selector: str | None = None) -> Listing:
    """一覧ページから候補を列挙する。

    link_rules の項目（すべて任意）:
      css_selector   一覧の範囲（例 "main .news-list"）
      item_selector  1件分の要素（例 "a.card__box"、"div.historical_line"）。指定するとその中からリンク・題名・日付を探す
      title_selector 1件の中の題名の要素（例 ".card__title"）
      date_selector  1件の中の日付の要素（例 ".card__date time"、".h_date"）
      include / exclude  URL の正規表現
    """
    soup = _soup(body)
    scope = soup.select_one(link_rules["css_selector"]) if link_rules.get("css_selector") else soup.body or soup
    listing = Listing([])
    if scope is None:
        return listing
    include = [re.compile(p) for p in link_rules.get("include", [])]
    exclude = [re.compile(p) for p in link_rules.get("exclude", [])]
    item_selector = link_rules.get("item_selector")
    title_selector = link_rules.get("title_selector")
    date_selector = link_rules.get("date_selector")

    if item_selector:
        pairs = []
        for item in scope.select(item_selector):
            a = item if item.name == "a" and item.get("href") else item.find("a", href=True)
            if a is not None:
                pairs.append((a, item))
    else:
        pairs = [(a, None) for a in scope.find_all("a", href=True)]

    seen: set[str] = set()
    for a, item in pairs:
        href = a["href"].strip()
        try:
            url = normalize_url(href, base_url)
        except UrlRejected:
            listing.rejected.append(href)
            continue
        if include and not any(p.search(url) for p in include):
            continue
        if any(p.search(url) for p in exclude):
            continue
        if url in seen:
            continue
        seen.add(url)
        if item is not None:
            title_el = item.select_one(title_selector) if title_selector else None
            title = (title_el or a).get_text(" ", strip=True) or None
            found = _date_in(item, date_selector)
        else:
            title = a.get_text(" ", strip=True) or None
            # リンクを含む行（li・tr・dt/dd など）から日付を探す。日付用の要素があればそれを優先する
            container = a.find_parent(["li", "tr", "dd", "dt", "p", "div"]) or a.parent
            found = _date_in(container, date_selector) if container is not None else None
            if found is None and container is not None:
                text_found = find_japanese_date(container.get_text(" ", strip=True))
                found = (text_found[0], "listing_text", text_found[1]) if text_found else None
        listing.candidates.append(Candidate(url=url, title=title, listing_date=found))
    if next_selector:
        nxt = soup.select_one(next_selector)
        if nxt is not None and nxt.get("href"):
            try:
                listing.next_url = normalize_url(nxt["href"], base_url)
            except UrlRejected:
                listing.next_url = None
    return listing


# ---------------------------------------------------------------- 記事 HTML


def _meta_date(soup: BeautifulSoup, names: tuple[str, ...]) -> DateFound | None:
    for name in names:
        tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            parsed = parse_any(tag["content"])
            if parsed:
                attr = "property" if tag.get("property") else "name"
                return DateFound(parsed, "html_meta", f'<meta {attr}="{name}" content="{tag["content"]}">')
    return None


def _labeled_date(text: str, labels: tuple[str, ...], method: str) -> DateFound | None:
    """「掲載日：2026年9月1日」のように、ラベルの直後にある日付だけを使う（本文中の別の日付と取り違えない）。"""
    normalized = unicodedata.normalize("NFKC", text)
    for line in normalized.splitlines():
        for label in labels:
            idx = line.find(label)
            if idx < 0:
                continue
            tail = line[idx + len(label): idx + len(label) + 40]
            if not re.match(r"^\s*(日)?\s*[:：]?\s*", tail):
                continue
            found = find_japanese_date(tail)
            if found and tail.find(found[1]) <= 6:
                return DateFound(found[0], method, _short(line[idx: idx + len(label) + tail.find(found[1]) + len(found[1])]))
    return None


def extract_html(body: bytes) -> Extracted:
    soup = _soup(body)
    title_tag = soup.find("h1") or soup.find("title")
    title = title_tag.get_text(" ", strip=True) if title_tag else None
    published = _meta_date(soup, ("article:published_time", "dcterms.issued", "DC.date.issued", "date", "DC.date", "pubdate"))
    updated = _meta_date(soup, ("article:modified_time", "dcterms.modified", "DC.date.modified", "last-modified"))

    for tag in soup.find_all(NON_CONTENT_TAGS):
        tag.decompose()
    for selector in NON_CONTENT_SELECTORS:
        for tag in soup.select(selector):
            tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.find(attrs={"role": "main"}) or soup.find(id="main") or soup.body or soup
    text = normalize_text(main.get_text("\n"))

    if published is None:
        published = _labeled_date(text, PUBLISHED_LABELS, "html_text")
    # 「更新日」は「最終更新日」より先に照合すると取り違えるため、長いラベルから順に照合している
    labeled_updated = _labeled_date(text, UPDATED_LABELS, "html_text")
    if updated is None:
        updated = labeled_updated
    if not text:
        return Extracted(title, "", "html", published, updated, status="unsupported", error="本文を抽出できない（動的ページの可能性）")
    return Extracted(title, text, "html", published, updated)


# ---------------------------------------------------------------- PDF


def extract_pdf(body: bytes) -> Extracted:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(body))
        text = normalize_text("\n".join((page.extract_text() or "") for page in reader.pages))
        meta = reader.metadata or {}
    except (PdfReadError, ValueError, KeyError) as e:
        return Extracted(None, "", "pdf", status="unsupported", error=f"PDFを読めない（{type(e).__name__}）")
    title = (meta.get("/Title") or "").strip() or None
    if not text.strip():
        return Extracted(title, "", "pdf", status="unsupported", error="画像PDFのためテキストを抽出できない（OCRは対象外）")
    published = _labeled_date(text, PUBLISHED_LABELS, "pdf_text")
    updated = _labeled_date(text, UPDATED_LABELS, "pdf_text")
    if published is None:
        # 本文に日付の記載がないときだけ、文書情報の作成日を使う（PDFの作成日は公開日と異なることがある）
        raw = str(meta.get("/CreationDate") or "")
        m = re.match(r"D:(\d{4})(\d{2})(\d{2})", raw)
        if m:
            parsed = parse_any(f"{m.group(1)}-{m.group(2)}-{m.group(3)}")
            if parsed:
                published = DateFound(parsed, "pdf_metadata", f"/CreationDate {raw}")
    if title is None:
        first = text.splitlines()[0] if text else ""
        title = _short(first, 80) or None
    return Extracted(title, text, "pdf", published, updated)


def extract_document(body: bytes, content_type: str, url: str) -> Extracted:
    if "pdf" in content_type.lower() or url.lower().endswith(".pdf") or body[:5] == b"%PDF-":
        return extract_pdf(body)
    return extract_html(body)
