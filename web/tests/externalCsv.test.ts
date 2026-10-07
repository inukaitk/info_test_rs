import { describe, expect, it } from "vitest";
import { csvCell } from "../src/download";
import { EXTERNAL_CSV_COLUMNS, categoryOf, excerptOf, externalCsvFilename, externalCsvForWeek, jstStamp, recordIds, toJstIso } from "../src/externalCsv";
import type { Article, WeeklyReport } from "../src/types";
import { reportView } from "../src/views/report";
import { article, site } from "./fixtures";

function parseCsv(csv: string): string[][] {
  // 引用符・改行を含むCSVの読み取り（この仕様の出力を確かめるための最小実装）
  const rows: string[][] = [];
  let row: string[] = [], cell = "", quoted = false;
  const text = csv.replace(/^﻿/, "");
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') { cell += '"'; i++; }
      else if (ch === '"') quoted = false;
      else cell += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ",") { row.push(cell); cell = ""; }
    else if (ch === "\r" && text[i + 1] === "\n") { row.push(cell); rows.push(row); row = []; cell = ""; i++; }
    else cell += ch;
  }
  if (cell || row.length) { row.push(cell); rows.push(row); }
  return rows;
}

const item = (a: Article) => ({ id: a.id, title: a.title, url: a.url, source_name: a.source_name, published: a.published.value, first_seen_at: a.first_seen_at, version: null, tags: [], summary_status: "success" });
const week = (news: Article[], changed: Article[] = []): WeeklyReport => ({
  id: "2026-09-29_2026-10-05", from: "2026-09-29", to: "2026-10-05",
  counts: { new: news.length, changed: changed.length, date_unknown: 0, unsummarized: 0, untagged: 0, runs: 1 },
  new: news.map(item), changed: changed.map(item), tag_counts: [], sources: [], markdown: "# x",
});
const day = (value: string | null, precision: "day" | "datetime" | "month" | "unknown" = "day") =>
  ({ value, precision, basis: null }) as Article["published"];
const A = article({ id: "a_000000000000000a", title: "【架空】記事A", url: "https://a.example.org/news/a", published: day("2026-10-02") });
const B = article({ id: "a_000000000000000b", title: "【架空】記事B", url: "https://a.example.org/files/b.pdf", published: day("2026-10-02T09:30:00+09:00", "datetime"),
  updated: day("2026-10-03"), csv: { source_type: "notice_pdf", hash: "b".repeat(64), hash_status: "ok", hash_scope: "title+pdf_text" } });
const C = article({ id: "a_000000000000000c", title: "【架空】記事C", published: day("2026-09", "month"), source_id: "demo-b", source_name: "架空機関B（デモ）",
  csv: { source_type: "news", hash: null, hash_status: "unavailable", hash_scope: null }, summary: { ...article().summary, status: "not_processed", text: null } });

describe("外部連携用CSV：category", () => {
  const tag = (id: string, name: string, retired = false) => ({ id, name, origin: "ai" as const, reason: null, retired });
  it("タグ名を半角スラッシュでつなぎ、無効なタグは除く。タグがなければ空欄", () => {
    expect(categoryOf(article({ tags: [tag("a", "母子保健"), tag("b", "子育て支援"), tag("c", "旧タグ", true)] }))).toBe("母子保健/子育て支援");
    expect(categoryOf(article({ tags: [] }))).toBe("");
  });
});

describe("外部連携用CSV：形式（仕様の受け入れ条件）", () => {
  const data = site([A, B, C]);
  const csv = externalCsvForWeek(week([A, B, C]), data);

  it("UTF-8 BOM付き、CRLF、末尾も改行。ヘッダーは固定の15列で、記事の数だけ行がある", () => {
    expect(csv.charCodeAt(0)).toBe(0xfeff);
    expect(csv.endsWith("\r\n")).toBe(true);
    expect(csv.replace(/\r\n/g, "").includes("\n")).toBe(false);
    const rows = parseCsv(csv);
    expect(rows[0]).toEqual([...EXTERNAL_CSV_COLUMNS]);
    expect(EXTERNAL_CSV_COLUMNS).toHaveLength(15);
    expect(rows).toHaveLength(1 + 3);
    for (const r of rows) expect(r).toHaveLength(15);
  });

  it("日付：公開日は日本時間のYYYY-MM-DD。月だけ・不明は空欄（推測しない）。取得日時は +09:00", () => {
    const rows = parseCsv(csv).slice(1);
    const col = (name: string) => (EXTERNAL_CSV_COLUMNS as readonly string[]).indexOf(name);
    const byTitle = (t: string) => rows.find((r) => r[col("title")] === t)!;
    expect(byTitle("【架空】記事A")[col("published_date")]).toBe("2026-10-02");
    expect(byTitle("【架空】記事B")[col("published_date")]).toBe("2026-10-02");
    expect(byTitle("【架空】記事B")[col("updated_date")]).toBe("2026-10-03");
    expect(byTitle("【架空】記事A")[col("updated_date")]).toBe("");
    expect(byTitle("【架空】記事C")[col("published_date")]).toBe("");
    for (const r of rows) expect(r[col("fetched_at")]).toBe("2026-09-11T08:00:00+09:00");
    expect(toJstIso("2026-09-21T16:00:00Z")).toBe("2026-09-22T01:00:00+09:00");
  });

  it("content_hash：算出できた記事は64桁。できない記事は空欄で、hash_status=unavailable、hash_scope も空欄", () => {
    const rows = parseCsv(csv).slice(1);
    const col = (name: string) => (EXTERNAL_CSV_COLUMNS as readonly string[]).indexOf(name);
    const b = rows.find((r) => r[col("title")] === "【架空】記事B")!;
    expect([b[col("content_hash")], b[col("hash_status")], b[col("hash_scope")]]).toEqual(["b".repeat(64), "ok", "title+pdf_text"]);
    const c = rows.find((r) => r[col("title")] === "【架空】記事C")!;
    expect([c[col("content_hash")], c[col("hash_status")], c[col("hash_scope")]]).toEqual(["", "unavailable", ""]);
  });

  it("source_id・publisher・source_type・source_list_url は、情報源の設定から。PDFのURLは notice_pdf", () => {
    const rows = parseCsv(csv).slice(1);
    const col = (name: string) => (EXTERNAL_CSV_COLUMNS as readonly string[]).indexOf(name);
    const a = rows.find((r) => r[col("title")] === "【架空】記事A")!;
    expect([a[col("source_id")], a[col("publisher")], a[col("source_type")], a[col("source_list_url")]]).toEqual(["DEMO_A_NEWS", "架空機関A", "news", "https://a.example.org/news/"]);
    expect(rows.find((r) => r[col("title")] === "【架空】記事B")![col("source_type")]).toBe("notice_pdf");
    expect(rows.find((r) => r[col("title")] === "【架空】記事C")![col("source_id")]).toBe("DEMO_B_NEWS");
  });

  it("評価・重要度・製品への影響・社内の情報にあたる列を持たない（公開側は収集だけ）", () => {
    for (const name of EXTERNAL_CSV_COLUMNS) expect(name).not.toMatch(/relevance|importance|priority|impact|memo|owner|rank|score/i);
  });
});

describe("外部連携用CSV：内容", () => {
  it("excerpt は本文の抜粋ではなく、私たちが作った要約と主な論点。要約がない記事は空欄", () => {
    expect(excerptOf(A)).toBe("【架空】健診の問診項目が追加される。 【主な論点】問診項目");
    expect(excerptOf(C)).toBe("");
    const long = article({ summary: { ...A.summary, text: "あ".repeat(3000), key_points: [] } });
    expect(excerptOf(long).length).toBe(1000);
    expect(excerptOf(long).endsWith("…")).toBe(true);
  });

  it("record_id は {source_id}_{公開日YYYYMMDD}_{連番3桁}。連番は全記事の中で決まり、週が変わっても同じ", () => {
    const data = site([A, B, C]);
    const ids = recordIds(data);
    expect(ids.get(A.id)).toBe("DEMO_A_NEWS_20261002_001");
    expect(ids.get(B.id)).toBe("DEMO_A_NEWS_20261002_002");
    expect(ids.get(C.id)).toMatch(/^DEMO_B_NEWS_\d{8}_001$/);
    const onlyB = parseCsv(externalCsvForWeek(week([B]), data))[1];
    expect(onlyB[0]).toBe("DEMO_A_NEWS_20261002_002");
  });

  it("新規と変更の記事を、公開日の新しい順（同じ日はID順、日付不明は最後）に出す。同じ記事は1回だけ。レポートにない記事は出さない", () => {
    const data = site([A, B, C]);
    const csv = externalCsvForWeek(week([A, C], [B, A]), data);
    const titles = parseCsv(csv).slice(1).map((r) => r[3]);
    expect(titles).toEqual(["【架空】記事A", "【架空】記事B", "【架空】記事C"]); // 公開日（日本時間）の新しい順。同じ日はID順。日付不明は最後
    expect(parseCsv(externalCsvForWeek(week([]), data))).toHaveLength(1);
  });

  it("CSVインジェクション対策：先頭の非空白文字が = + - @ の値は、先頭に ' を付ける。引用符・カンマ・改行は囲む", () => {
    expect(csvCell("=SUM(A1)")).toBe("'=SUM(A1)");
    expect(csvCell("  =1+1")).toBe("'  =1+1");
    expect(csvCell("-1")).toBe("'-1");
    expect(csvCell("@x")).toBe("'@x");
    expect(csvCell("+81")).toBe("'+81");
    const evil = article({ id: "a_000000000000000d", title: '=HYPERLINK("http://x")', summary: { ...A.summary, text: '"引用", カンマ\n改行' } });
    const rows = parseCsv(externalCsvForWeek(week([evil]), site([evil])));
    expect(rows[1][3]).toBe(`'=HYPERLINK("http://x")`);
    expect(rows[1][11]).toBe('"引用", カンマ\n改行 【主な論点】問診項目');
  });

  it("ファイル名は external_news_YYYYMMDD_HHmm.csv（日本時間）", () => {
    expect(jstStamp("2026-10-07T00:00:00Z")).toBe("20261007_0900");
    expect(externalCsvFilename("2026-10-06T23:30:00+09:00")).toBe("external_news_20261006_2330.csv");
  });
});

describe("週次レポートの「CSVで保存」ボタン", () => {
  it("「Markdownで保存」の横に、「CSVで保存」のボタンがある", () => {
    const data = site([A], {}, { reports: [week([A])] });
    const buttons = [...reportView(data, null, () => {}).querySelectorAll(".toolbar button")].map((b) => b.textContent);
    expect(buttons).toEqual(["Markdownで保存", "CSVで保存"]);
  });
});
