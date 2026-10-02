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
  versions: { version: number; fetched_at: string; change_type: "new" | "content_changed" | "extraction_changed"; extraction_status: string }[];
  attachments: { title: string; url: string; status: "ok" | "failed" | "unsupported" | "skipped"; note: string | null; pages: number | null }[];
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
  stale_after_days: number;
  data_as_of: string | null;
  tags: { id: string; name: string; description: string; retired: boolean }[];
  sources: { id: string; name: string }[];
}

export interface SourceStatus {
  id: string;
  name: string;
  method: string;
  entry_url: string;
  enabled: boolean;
  last_success_at: string | null;
  last_attempt_at: string | null;
  last_attempt_status: string | null;
  consecutive_failures: number;
  explored_range: { oldest: string | null; newest: string | null; pages: number } | null;
  retry_count: number;
  last_run: {
    status: string; error: string | null; warnings: string[];
    new: number; changed: number; unchanged: number; date_unknown: number; fetch_failed: number;
  } | null;
  articles: number;
  date_unknown: number;
}

export interface RunSummary {
  run_id: string;
  started_at: string;
  finished_at: string | null;
  status: string;
  kind: string;
  period: { start: string; end: string } | null;
  totals: Record<"new" | "changed" | "unchanged" | "date_unknown" | "fetch_failed" | "summarized" | "summarize_failed", number>;
  sources: { source_id: string; status: string; new: number; changed: number; date_unknown: number; fetch_failed: number; error: string | null; warnings: string[] }[];
}

export interface Status {
  last_run_at: string | null;
  last_run_status: string | null;
  last_full_success_at: string | null;
  counts: { articles: number; date_unknown: number; content_missing: number; unsummarized: number; summary_outdated: number };
  sources: SourceStatus[];
  runs: RunSummary[];
}

export interface ReportItem {
  id: string;
  title: string;
  url: string;
  source_name: string;
  published: string | null;
  first_seen_at: string;
  version: number | null;
  tags: string[];
  summary_status: string;
}

export interface WeeklyReport {
  id: string;
  from: string;
  to: string;
  counts: { new: number; changed: number; date_unknown: number; unsummarized: number; untagged: number; runs: number };
  new: ReportItem[];
  changed: ReportItem[];
  tag_counts: { id: string; name: string; count: number }[];
  sources: { id: string; name: string; runs: { run_id: string; started_at: string; status: string; new: number; changed: number; error: string | null }[] }[];
  markdown: string;
}

export interface SiteData {
  meta: Meta;
  articles: Article[];
  status: Status;
  reports: WeeklyReport[];
}
