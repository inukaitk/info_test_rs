// 一覧の絞り込みと文字検索（画面用JSONに対してブラウザ内で行う）。
import type { Article } from "./types";

export interface Filters {
  q: string;
  tag: string;
  source: string;
  from: string; // YYYY-MM-DD（日本時間、両端を含む）
  to: string;
  page?: number; // 一覧のページ（1始まり。省略は1ページ目）。絞り込み条件ではない
}

export const EMPTY_FILTERS: Filters = { q: "", tag: "", source: "", from: "", to: "" };

const KEYS = ["q", "tag", "source", "from", "to"] as const;
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

export function parseFilters(params: URLSearchParams): Filters {
  const f = { ...EMPTY_FILTERS };
  for (const key of KEYS) f[key] = (params.get(key) ?? "").slice(0, 200);
  if (!DATE_RE.test(f.from)) f.from = "";
  if (!DATE_RE.test(f.to)) f.to = "";
  const rawPage = params.get("page") ?? "";
  if (/^\d{1,12}$/.test(rawPage) && Number(rawPage) > 1) f.page = Math.min(Number(rawPage), 100000);
  return f;
}

export function filtersToQuery(f: Filters): string {
  const params = new URLSearchParams();
  for (const key of KEYS) if (f[key]) params.set(key, f[key]);
  if (f.page && f.page > 1) params.set("page", String(f.page));
  const s = params.toString();
  return s ? `?${s}` : "";
}

/** 件数と1ページの件数から、ページ数（最低1）と、範囲内に収めた現在のページを返す。 */
export function paginate(total: number, size: number, page: number | undefined): { pages: number; page: number; start: number; end: number } {
  const pages = Math.max(1, Math.ceil(total / Math.max(1, size)));
  const current = Math.min(Math.max(1, page ?? 1), pages);
  return { pages, page: current, start: (current - 1) * size, end: Math.min(total, current * size) };
}

/** ページ送りに並べるページ番号。先頭・末尾・現在の前後2ページを出し、間は null（「…」）にする。 */
export function pageWindow(pages: number, current: number): (number | null)[] {
  const keep = new Set([1, pages]);
  for (let i = current - 2; i <= current + 2; i++) if (i >= 1 && i <= pages) keep.add(i);
  const out: (number | null)[] = [];
  let prev = 0;
  for (const n of [...keep].sort((a, b) => a - b)) {
    if (n - prev > 1) out.push(null);
    out.push(n);
    prev = n;
  }
  return out;
}

/** 全角・半角や大文字・小文字の違いを無視して比較するための正規化。 */
export function normalize(text: string): string {
  return text.normalize("NFKC").toLowerCase();
}

function searchableText(a: Article): string {
  return normalize(
    [
      a.title,
      a.source_name,
      a.summary.text ?? "",
      ...(a.summary.key_points ?? []),
      ...(a.summary.targets ?? []),
      ...a.tags.map((t) => t.name),
    ].join("\n"),
  );
}

/** 精度に応じた日付の範囲（例 2026-09 → 2026-09-01〜2026-09-30）。日付不明は null。 */
export function dateRange(value: string | null): [string, string] | null {
  if (!value) return null;
  const m = /^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?/.exec(value);
  if (!m) return null;
  const [, y, mo, d] = m;
  if (d) return [`${y}-${mo}-${d}`, `${y}-${mo}-${d}`];
  if (mo) {
    const last = new Date(Date.UTC(Number(y), Number(mo), 0)).getUTCDate();
    return [`${y}-${mo}-01`, `${y}-${mo}-${String(last).padStart(2, "0")}`];
  }
  return [`${y}-01-01`, `${y}-12-31`];
}

export function hasPeriod(f: Filters): boolean {
  return Boolean(f.from || f.to);
}

/** 期間との重なりで判定する。日付不明の記事は期間指定時には含めない（推定で混ぜない）。 */
export function inPeriod(a: Article, f: Filters): boolean {
  if (!hasPeriod(f)) return true;
  const range = dateRange(a.published.value);
  if (!range) return false;
  const [start, end] = range;
  if (f.from && end < f.from) return false;
  if (f.to && start > f.to) return false;
  return true;
}

export function applyFilters(articles: Article[], f: Filters): Article[] {
  const terms = normalize(f.q).split(/\s+/).filter(Boolean);
  return articles.filter((a) => {
    if (f.tag && !a.tags.some((t) => t.id === f.tag)) return false;
    if (f.source && a.source_id !== f.source) return false;
    if (!inPeriod(a, f)) return false;
    if (terms.length) {
      const text = searchableText(a);
      if (!terms.every((t) => text.includes(t))) return false;
    }
    return true;
  });
}

/** タイムゾーン付き日時を日本時間の日付（YYYY-MM-DD）にする。 */
export function jstDate(timestamp: string): string {
  const d = new Date(new Date(timestamp).getTime() + 9 * 60 * 60 * 1000);
  return d.toISOString().slice(0, 10);
}

function addDays(date: string, days: number): string {
  const d = new Date(`${date}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

/** 最新一覧の期間：最終収集日（日本時間）を含めて days 日分。基準がなければ null。 */
export function latestWindow(asOf: string | null, days: number): { from: string; to: string } | null {
  if (!asOf) return null;
  const to = jstDate(asOf);
  return { from: addDays(to, -(days - 1)), to };
}

/** 公開日（日本時間の日付）。日まで分かる値と、時刻つきの値（RSSなど）が対象。日付不明・月だけ・年だけは null。 */
export function publishedDay(a: Article): string | null {
  const v = a.published.value;
  if (!v) return null;
  if (/^\d{4}-\d{2}-\d{2}$/.test(v)) return v;
  if (/^\d{4}-\d{2}-\d{2}T/.test(v)) return jstDate(v);
  return null;
}

/** 公開日が最新一覧の期間に入る記事。日付不明・月だけの記事は、取得日などで代用せず、含めない。 */
export function latestArticles(articles: Article[], window: { from: string; to: string } | null): Article[] {
  if (!window) return [];
  return articles.filter((a) => {
    const d = publishedDay(a);
    return d !== null && d >= window.from && d <= window.to;
  });
}

/** 公開日が日まで分からないため、最新一覧に出せない記事の数（画面で別に知らせる）。 */
export function countUndatedForLatest(articles: Article[]): number {
  return articles.filter((a) => publishedDay(a) === null).length;
}

/** 期間指定によって除外された日付不明の記事数（画面で別枠として知らせる）。 */
export function countDateUnknownExcluded(articles: Article[], f: Filters): number {
  if (!hasPeriod(f)) return 0;
  return applyFilters(articles, { ...f, from: "", to: "" }).filter((a) => a.published.value === null).length;
}
