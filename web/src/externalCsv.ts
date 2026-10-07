// 外部連携用CSV：週次レポートの1週間分（新規＋変更）の記事を、別のシステムで分析しやすい固定の列で出す。
// 公開情報だけを出す。AI関連度・重要度・製品への影響などの評価や、社内の情報は、列としても持たない。
import { csvCell } from "./download";
import { jstDate, publishedDay } from "./filters";
import type { Article, SiteData, WeeklyReport } from "./types";

/** 列の名前と順序（固定）。docs/csv/external_news_template.csv のヘッダーと同じ。 */
export const EXTERNAL_CSV_COLUMNS = [
  "record_id", "source_id", "publisher", "title", "url", "published_date", "updated_date", "fetched_at", "source_type",
  "content_hash", "category", "excerpt", "source_list_url", "hash_status", "hash_scope",
] as const;

const EXCERPT_MAX = 1000; // 仕様の目安は200〜2,000字。私たちが作った要約と論点なので、長くならない

/** 日本時間のISO 8601（+09:00）。 */
export function toJstIso(timestamp: string): string {
  const t = new Date(timestamp).getTime();
  if (Number.isNaN(t)) return "";
  return new Date(t + 9 * 3600 * 1000).toISOString().replace(/\.\d+Z$/, "+09:00").replace(/Z$/, "+09:00");
}

/** ファイル名用の日本時間（YYYYMMDD_HHmm）。 */
export function jstStamp(timestamp: string): string {
  return toJstIso(timestamp).slice(0, 16).replace(/-/g, "").replace("T", "_").replace(":", "");
}

export function externalCsvFilename(generatedAt: string): string {
  return `external_news_${jstStamp(generatedAt)}.csv`;
}

function sourceCsvId(data: SiteData, a: Article): string {
  return data.meta.sources.find((s) => s.id === a.source_id)?.csv_id ?? a.source_id.toUpperCase().replace(/[^A-Z0-9]+/g, "_");
}

/** 公開日が日まで分かるときだけ日付を返す。推測しない（日付不明・月だけ・年だけは空）。 */
function dayOrEmpty(value: string | null): string {
  if (!value) return "";
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return value;
  if (/^\d{4}-\d{2}-\d{2}T/.test(value)) return jstDate(value);
  return "";
}

/** record_id（CSV内の識別子）：{source_id}_{公開日YYYYMMDD}_{連番3桁}。連番は、全記事の中で同じ情報源・同じ日の記事をID順に並べた順で、週が変わっても同じになる。 */
export function recordIds(data: SiteData): Map<string, string> {
  const groups = new Map<string, Article[]>();
  for (const a of data.articles) {
    const day = publishedDay(a) ?? jstDate(a.first_seen_at);
    const key = `${sourceCsvId(data, a)}_${day.replace(/-/g, "")}`;
    groups.set(key, [...(groups.get(key) ?? []), a]);
  }
  const ids = new Map<string, string>();
  for (const [key, list] of groups) {
    [...list].sort((x, y) => x.id.localeCompare(y.id)).forEach((a, i) => ids.set(a.id, `${key}_${String(i + 1).padStart(3, "0")}`));
  }
  return ids;
}

/** 本文の抜粋ではなく、私たちが作った要約と主な論点（原文を載せない）。要約がない記事は空欄。 */
export function excerptOf(a: Article): string {
  const s = a.summary;
  if (s.status !== "success" || !s.text) return "";
  const points = (s.key_points ?? []).filter(Boolean);
  const text = points.length ? `${s.text} 【主な論点】${points.join(" / ")}` : s.text;
  return text.length > EXCERPT_MAX ? `${text.slice(0, EXCERPT_MAX - 1)}…` : text;
}

export function externalCsvRow(data: SiteData, a: Article, recordId: string): string[] {
  const meta = data.meta.sources.find((s) => s.id === a.source_id);
  return [
    recordId,
    sourceCsvId(data, a),
    meta?.publisher ?? a.source_name,
    a.title,
    a.url,
    dayOrEmpty(a.published.value),
    dayOrEmpty(a.updated.value),
    toJstIso(a.last_seen_at),
    a.csv.source_type,
    a.csv.hash ?? "",
    "", // category：サイト側の公開カテゴリ。今は取得していないため空欄
    excerptOf(a),
    meta?.list_url ?? "",
    a.csv.hash_status,
    a.csv.hash_scope ?? "",
  ];
}

/** 週次レポートの「新規」と「変更」の記事を、公開日の新しい順に並べたCSV（BOM付きUTF-8、CRLF、ヘッダー固定）。 */
export function externalCsvForWeek(week: WeeklyReport, data: SiteData): string {
  const ids = recordIds(data);
  const byId = new Map(data.articles.map((a) => [a.id, a]));
  const wanted = [...new Set([...week.new, ...week.changed].map((i) => i.id))];
  const rows = wanted
    .map((id) => byId.get(id))
    .filter((a): a is Article => a !== undefined)
    .sort((x, y) => (dayOrEmpty(y.published.value) || "0").localeCompare(dayOrEmpty(x.published.value) || "0") || x.id.localeCompare(y.id))
    .map((a) => externalCsvRow(data, a, ids.get(a.id) ?? a.id));
  return "﻿" + [EXTERNAL_CSV_COLUMNS as readonly string[], ...rows].map((r) => r.map(csvCell).join(",")).join("\r\n") + "\r\n";
}
