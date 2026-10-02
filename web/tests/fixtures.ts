import type { Article, Meta, SiteData } from "../src/types";

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
    ...overrides,
  };
}

export function meta(overrides: Partial<Meta> = {}): Meta {
  return {
    schema_version: 1, generated_at: "2026-09-29T09:00:00+09:00", release_mode: "demo", is_demo: true,
    site_name: "テスト", correction_request_url: null, page_size: 50,
    latest_days: 7, data_as_of: "2026-09-28T08:00:00+09:00",
    tags: [
      { id: "maternal-child-health", name: "母子保健", description: "d", retired: false },
      { id: "childcare-support", name: "子育て支援", description: "d", retired: false },
    ],
    sources: [{ id: "demo-a", name: "架空機関A（デモ）" }, { id: "demo-b", name: "架空機関B（デモ）" }],
    ...overrides,
  };
}

export function site(articles: Article[], m: Partial<Meta> = {}): SiteData {
  return { meta: meta(m), articles };
}
