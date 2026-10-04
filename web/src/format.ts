// 表示用の文字列に変換する関数（日付、状態の日本語ラベルなど）。
import type { DateInfo, SummaryStatus } from "./types";

/** 精度に応じた日付表示。日付不明は推定せず「日付不明」とする。 */
export function formatDate(info: DateInfo): string {
  if (info.value === null || info.precision === "unknown") return "日付不明";
  return formatPartialDate(info.value);
}

export function formatPartialDate(value: string): string {
  const m = /^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?/.exec(value);
  if (!m) return value;
  const [, y, mo, d] = m;
  if (d) return `${y}年${Number(mo)}月${Number(d)}日`;
  if (mo) return `${y}年${Number(mo)}月（日不明）`;
  return `${y}年（月日不明）`;
}

/** タイムゾーン付き日時を日本時間で表示する。 */
export function formatDateTime(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const jst = new Date(date.getTime() + 9 * 60 * 60 * 1000);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${jst.getUTCFullYear()}年${jst.getUTCMonth() + 1}月${jst.getUTCDate()}日 ${pad(jst.getUTCHours())}:${pad(jst.getUTCMinutes())}`;
}

export const SUMMARY_STATUS_LABEL: Record<SummaryStatus, string> = {
  success: "要約済み",
  pending: "未要約（処理待ち）",
  skipped_no_api_key: "未要約（AI未実行：APIキー未設定）",
  skipped_no_content: "未要約（本文を取得できないため）",
  failed_api_error: "未要約（AI APIエラー）",
  failed_invalid_output: "未要約（AI出力の検証に失敗）",
  failed_limit_exceeded: "未要約（処理上限を超過）",
  failed_refusal: "未要約（AIが応答を拒否）",
  not_processed: "未要約（AI処理なし）",
};

export const CONTENT_STATUS_LABEL: Record<string, string> = {
  ok: "本文取得済み",
  failed: "本文未取得（取得失敗）",
  unsupported: "本文未取得（未対応の形式）",
  not_fetched: "本文未取得",
};

export const ARTICLE_STATUS_LABEL: Record<string, string> = {
  active: "掲載中",
  missing_from_listing: "一覧に見当たらない",
  manual: "手動登録",
  unsupported: "自動取得の対象外",
};

export const DATE_METHOD_LABEL: Record<string, string> = {
  rss_pubdate: "RSSの公開日",
  rss_updated: "RSSの更新日",
  html_meta: "ページのメタ情報",
  html_text: "ページ本文の記載",
  pdf_metadata: "PDFの文書情報",
  pdf_text: "PDF本文の記載",
  listing_text: "一覧ページの記載",
  url_pattern: "URL中の日付",
  manual: "手動登録",
};

export const PRECISION_LABEL: Record<string, string> = {
  datetime: "日時まで",
  day: "日まで",
  month: "月まで",
  year: "年まで",
  unknown: "不明",
};
