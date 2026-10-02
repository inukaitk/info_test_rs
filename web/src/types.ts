// 画面用JSON（collector/export.py が出力し、schemas/public/ で検証済み）の型。

export type Precision = "datetime" | "day" | "month" | "year" | "unknown";

export interface DateInfo {
  value: string | null;
  precision: Precision;
  basis: { method: string; evidence: string } | null;
}

export interface Tag {
  id: string;
  name: string;
  origin: "ai" | "human";
  reason: string | null;
  retired: boolean;
}

export type SummaryStatus =
  | "success"
  | "pending"
  | "skipped_no_api_key"
  | "skipped_no_content"
  | "failed_api_error"
  | "failed_invalid_output"
  | "failed_limit_exceeded"
  | "not_processed";

export interface Summary {
  status: SummaryStatus;
  error: string | null;
  version: number | null;
  outdated: boolean;
  text: string | null;
  key_points: string[] | null;
  targets: string[] | null;
  dates: { label: string; value: string; evidence: string }[] | null;
  uncertainties: string[] | null;
  model: string | null;
  processed_at: string | null;
}

export interface Article {
  id: string;
  source_id: string;
  source_name: string;
  title: string;
  url: string;
  published: DateInfo;
  updated: DateInfo;
  first_seen_at: string;
  last_seen_at: string;
  status: "active" | "missing_from_listing" | "manual" | "unsupported";
  content_status: "ok" | "failed" | "unsupported" | "not_fetched";
  content_error: string | null;
  latest_version: number;
  versions: { version: number; fetched_at: string; change_type: "new" | "content_changed"; extraction_status: string }[];
  summary: Summary;
  tags: Tag[];
  removed_tags: { id: string; name: string }[];
  tag_override_reason: string | null;
}

export interface Meta {
  schema_version: number;
  generated_at: string;
  release_mode: "demo" | "real";
  is_demo: boolean;
  site_name: string;
  correction_request_url: string | null;
  page_size: number;
  latest_days: number;
  data_as_of: string | null;
  tags: { id: string; name: string; description: string; retired: boolean }[];
  sources: { id: string; name: string }[];
}

export interface SiteData {
  meta: Meta;
  articles: Article[];
}
