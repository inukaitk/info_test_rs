// 画面からのファイル保存（CSV・JSON・Markdown）。ブラウザ内でファイルを作って保存する（通信なし）。
import type { Article } from "./types";

export function downloadText(filename: string, text: string, mime: string): void {
  const blob = new Blob([text], { type: `${mime};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; // blob: のURL（この画面で作ったファイル）だけを使う
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** CSVの1セル。表計算ソフトで式として実行されないよう、= + - @ などで始まる値の先頭に ' を付ける。 */
export function csvCell(value: string | number | null | undefined): string {
  let s = value === null || value === undefined ? "" : String(value);
  if (/^[=+\-@\t\r]/.test(s)) s = `'${s}`;
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export const CSV_COLUMNS = [
  "記事ID", "公開日", "公開日の精度", "更新日", "取得日時", "機関", "タイトル", "出典URL",
  "概要", "AI処理状態", "AIタグ", "設定で付けたタグ", "ルールで付けたタグ", "人が追加したタグ", "人が除外したタグ", "本文の状態", "最新版",
] as const;

export function articlesToCsv(articles: Article[]): string {
  const rows = articles.map((a) => [
    a.id,
    a.published.value ?? "",
    a.published.precision,
    a.updated.value ?? "",
    a.first_seen_at,
    a.source_name,
    a.title,
    a.url,
    a.summary.text ?? "",
    a.summary.status,
    a.tags.filter((t) => t.origin === "ai").map((t) => t.name).join(";"),
    a.tags.filter((t) => t.origin === "source").map((t) => t.name).join(";"),
    a.tags.filter((t) => t.origin === "rule").map((t) => t.name).join(";"),
    a.tags.filter((t) => t.origin === "human").map((t) => t.name).join(";"),
    a.removed_tags.map((t) => t.name).join(";"),
    a.content_status,
    a.latest_version,
  ]);
  // 先頭の BOM は Excel で文字化けしないため
  return "\uFEFF" + [CSV_COLUMNS, ...rows].map((r) => r.map(csvCell).join(",")).join("\r\n") + "\r\n";
}

export function articlesToJson(articles: Article[], meta: { release_mode: string; generated_at: string }): string {
  return JSON.stringify({ release_mode: meta.release_mode, generated_at: meta.generated_at, articles }, null, 2);
}
