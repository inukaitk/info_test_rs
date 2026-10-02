"""日付の読み取り（RSS・ISO 8601・和暦・日本語表記）と期間判定。精度も返す。"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime

JST = timezone(timedelta(hours=9))
ERAS = {"令和": 2018, "平成": 1988, "R": 2018, "H": 1988}


@dataclass(frozen=True)
class ParsedDate:
    value: str  # YYYY / YYYY-MM / YYYY-MM-DD / タイムゾーン付き日時
    precision: str  # year / month / day / datetime

    def range(self) -> tuple[date, date]:
        """この日付が表す日本時間の日付範囲（両端を含む）。"""
        if self.precision == "datetime":
            d = datetime.fromisoformat(self.value).astimezone(JST).date()
            return d, d
        parts = [int(x) for x in self.value.split("-")]
        if self.precision == "day":
            d = date(*parts)
            return d, d
        if self.precision == "month":
            y, m = parts
            last = (date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1))
            return date(y, m, 1), last
        return date(parts[0], 1, 1), date(parts[0], 12, 31)


def _nfkc(text: str) -> str:
    return unicodedata.normalize("NFKC", text)


def parse_rfc822(text: str) -> ParsedDate | None:
    try:
        dt = parsedate_to_datetime(text.strip())
    except (TypeError, ValueError, IndexError):
        return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JST)
    return ParsedDate(dt.isoformat(), "datetime")


_ISO = re.compile(r"^(\d{4})-(\d{2})(?:-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?\s*(Z|[+-]\d{2}:?\d{2})?)?)?$")


def parse_iso(text: str) -> ParsedDate | None:
    if re.fullmatch(r"\d{4}", text.strip()):
        return ParsedDate(text.strip(), "year")
    m = _ISO.match(text.strip())
    if not m:
        return None
    y, mo, d, hh, mm, ss, tz = m.groups()
    try:
        if hh is not None:
            if tz is None or tz == "":
                tzinfo = JST  # タイムゾーンのない日時は日本時間とみなす（国内の公的機関のため）
            elif tz == "Z":
                tzinfo = timezone.utc
            else:
                sign = 1 if tz[0] == "+" else -1
                tz = tz[1:].replace(":", "")
                tzinfo = timezone(sign * timedelta(hours=int(tz[:2]), minutes=int(tz[2:])))
            dt = datetime(int(y), int(mo), int(d), int(hh), int(mm), int(ss or 0), tzinfo=tzinfo)
            return ParsedDate(dt.isoformat(), "datetime")
        if d is not None:
            return ParsedDate(date(int(y), int(mo), int(d)).isoformat(), "day")
        date(int(y), int(mo), 1)
        return ParsedDate(f"{y}-{mo}", "month")
    except ValueError:
        return None


_JP_DATE = re.compile(
    r"(?P<era>令和|平成|R|H)?\s*(?P<y>\d{1,4}|元)\s*[年./]\s*(?P<m>\d{1,2})\s*[月./]\s*(?P<d>\d{1,2})\s*日?"
)
_JP_MONTH = re.compile(r"(?P<era>令和|平成)?\s*(?P<y>\d{1,4}|元)\s*年\s*(?P<m>\d{1,2})\s*月(?!\s*\d)")


def _year(era: str | None, y: str) -> int | None:
    n = 1 if y == "元" else int(y)
    if era:
        return ERAS[era] + n
    return n if n >= 1900 else None


def find_japanese_date(text: str) -> tuple[ParsedDate, str] | None:
    """文中の最初の日付（2026年9月1日、令和8年9月1日、2026/09/01 など）と、その根拠の文字列を返す。"""
    normalized = _nfkc(text)
    for m in _JP_DATE.finditer(normalized):
        year = _year(m.group("era"), m.group("y"))
        if year is None:
            continue
        try:
            d = date(year, int(m.group("m")), int(m.group("d")))
        except ValueError:
            continue
        return ParsedDate(d.isoformat(), "day"), m.group(0).strip()
    for m in _JP_MONTH.finditer(normalized):
        year = _year(m.group("era"), m.group("y"))
        month = int(m.group("m"))
        if year is None or not 1 <= month <= 12:
            continue
        return ParsedDate(f"{year:04d}-{month:02d}", "month"), m.group(0).strip()
    return None


def parse_any(text: str) -> ParsedDate | None:
    text = text.strip()
    if not text:
        return None
    return parse_iso(text) or parse_rfc822(text) or (find_japanese_date(text) or (None,))[0]


def jst_day_bounds(start: date, end: date) -> tuple[datetime, datetime]:
    """--start/--end（日本時間、両端を含む）を「開始日0時以上・終了日の翌日0時未満」に変換する。"""
    return datetime.combine(start, time.min, JST), datetime.combine(end + timedelta(days=1), time.min, JST)


def in_period(parsed: ParsedDate | None, start: date | None, end: date | None) -> bool | None:
    """期間内なら True、期間外なら False、日付不明なら None（推定で混ぜない）。
    精度が月・年の日付は、期間と重なれば期間内とする。"""
    if parsed is None:
        return None
    if start is None and end is None:
        return True
    if parsed.precision == "datetime":
        dt = datetime.fromisoformat(parsed.value)
        lo, hi = jst_day_bounds(start or date.min, end or date(9999, 12, 30))
        return lo <= dt < hi
    first, last = parsed.range()
    if start and last < start:
        return False
    if end and first > end:
        return False
    return True
