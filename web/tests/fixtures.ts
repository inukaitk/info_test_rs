import type { Article, Meta, SiteData, Status, WeeklyReport } from "../src/types";

export function article(overrides: Partial<Article> = {}): Article {
  return {
    id: "a_0000000000000001",
    source_id: "demo-a",
    source_name: "架空機関A（デモ）",
    title: "【架空】乳幼児健診の改正",
    url: "https://a.example.org/1.html",
    published: { value: "2026-09-10", precision: "day", basis: { method: "rss_pubdate", evidence: "2026-09-10" } },
    updated: { value: null, precision: "unknown", basis: null },
    first_seen_at: "2026-09-11T08:00:00+09:00",
    last_seen_at: "2026-09-11T08:00:00+09:00",
    status: "active",
    content_status: "ok",
    content_error: null,
    latest_version: 1,
    versions: [{ version: 1, fetched_at: "2026-09-11T08:00:00+09:00", change_type: "new", extraction_status: "ok" }],
    summary: {
      status: "success", error: null, version: 1, outdated: false, text: "【架空】健診の問診項目が追加される。",
      key_points: ["問診項目"], targets: ["市区町村"], dates: [], uncertainties: [], model: "demo-model",
      processed_at: "2026-09-11T08:10:00+09:00",
    },
    tags: [{ id: "maternal-child-health", name: "母子保健", origin: "ai", reason: "健診のため", retired: false }],
    removed_tags: [],
    tag_override_reason: null,
    attachments: [],
    ...overrides,
  };
}

export function meta(overrides: Partial<Meta> = {}): Meta {
  return {
    schema_version: 1, generated_at: "2026-09-29T09:00:00+09:00", release_mode: "demo", is_demo: true,
    site_name: "テスト", correction_request_url: null, page_size: 50,
    latest_days: 7, data_as_of: "2026-09-28T08:00:00+09:00", stale_after_days: 8,
    tags: [
      { id: "maternal-child-health", name: "母子保健", description: "d", retired: false },
      { id: "childcare-support", name: "子育て支援", description: "d", retired: false },
    ],
    sources: [{ id: "demo-a", name: "架空機関A（デモ）" }, { id: "demo-b", name: "架空機関B（デモ）" }],
    ...overrides,
  };
}

export function status(overrides: Partial<Status> = {}): Status {
  return {
    last_run_at: "2026-09-28T08:12:00+09:00",
    last_run_status: "success",
    last_full_success_at: "2026-09-28T08:12:00+09:00",
    counts: { articles: 1, date_unknown: 0, content_missing: 0, unsummarized: 0, summary_outdated: 0 },
    sources: [
      {
        id: "demo-a", name: "架空機関A（デモ）", method: "rss", entry_url: "https://a.example.org/rss", enabled: true,
        last_success_at: "2026-09-28T08:01:00+09:00", last_attempt_at: "2026-09-28T08:00:00+09:00", last_attempt_status: "success",
        consecutive_failures: 0, explored_range: { oldest: "2026-09-01", newest: "2026-09-28", pages: 1 }, retry_count: 0, retry_items: [],
        last_run: { status: "success", error: null, warnings: [], new: 1, changed: 0, unchanged: 0, date_unknown: 0, fetch_failed: 0 },
        articles: 1, date_unknown: 0,
        notes: "架空のメモ", attachments: { max_files: 3, max_pages: 30, exclude_titles: ["座席"] },
      },
    ],
    runs: [],
    ...overrides,
  };
}

export function site(articles: Article[], m: Partial<Meta> = {}, extra: { status?: Status; reports?: WeeklyReport[] } = {}): SiteData {
  return { meta: meta(m), articles, status: extra.status ?? status(), reports: extra.reports ?? [] };
}
