// 取得状況：最終実行、最終全情報源成功、情報源ごとの成否と失敗理由、日付不明・未処理件数、データが古いときの警告。
import { h } from "../dom";
import { formatDateTime, formatPartialDate } from "../format";
import type { SiteData, SourceStatus } from "../types";

const RUN_STATUS: Record<string, string> = { success: "成功", partial: "一部失敗", failed: "失敗", running: "実行中" };
const SOURCE_STATUS: Record<string, string> = { success: "成功", failed: "失敗", skipped: "対象外", unsupported: "未対応" };
const METHOD: Record<string, string> = { rss: "RSS", html: "HTML一覧", manual: "手動登録" };
const DAY = 24 * 60 * 60 * 1000;

function daysSince(ts: string | null, now: Date): number | null {
  if (!ts) return null;
  return Math.floor((now.getTime() - new Date(ts).getTime()) / DAY);
}

/** 画面上部に出す警告（データが古い、失敗が続く情報源など）。 */
export function statusWarnings(data: SiteData, now: Date): string[] {
  const { status, meta } = data;
  const limit = meta.stale_after_days;
  const warnings: string[] = [];
  const sinceRun = daysSince(status.last_run_at, now);
  if (sinceRun === null) warnings.push("まだ収集を実行していません。");
  else if (sinceRun > limit) warnings.push(`データが古くなっています：最後の収集から${sinceRun}日経っています（目安${limit}日）。`);
  for (const s of status.sources.filter((x) => x.enabled)) {
    const since = daysSince(s.last_success_at, now);
    if (s.last_success_at === null) warnings.push(`${s.name}：一度も取得に成功していません。`);
    else if (s.consecutive_failures > 0) {
      warnings.push(`${s.name}：直近${s.consecutive_failures}回続けて取得に失敗しています（最後の成功：${formatDateTime(s.last_success_at)}）。`);
    } else if (since !== null && since > limit) {
      warnings.push(`${s.name}：最後の取得成功から${since}日経っています。`);
    }
  }
  return warnings;
}

export function statusView(data: SiteData, now: Date = new Date()): HTMLElement {
  const { status } = data;
  const warnings = statusWarnings(data, now);
  const c = status.counts;
  return h(
    "section",
    { class: "status" },
    h("h1", {}, "取得状況"),
    warnings.length
      ? h("div", { class: "warn-box", role: "alert" }, h("strong", {}, "注意"), h("ul", {}, ...warnings.map((w) => h("li", {}, w))))
      : h("p", { class: "ok-box" }, "問題は見つかっていません。"),
    h(
      "table",
      { class: "kv" },
      kv("最終実行", `${formatDateTime(status.last_run_at)}（${RUN_STATUS[status.last_run_status ?? ""] ?? "—"}）`),
      kv("最終全情報源成功", status.last_full_success_at ? formatDateTime(status.last_full_success_at) : "まだありません"),
      kv("記事数", `${c.articles}件`),
      kv("日付不明", `${c.date_unknown}件`),
      kv("本文未取得", `${c.content_missing}件`),
      kv("未要約（未処理・失敗を含む）", `${c.unsummarized}件`),
      kv("要約が最新版より古い", `${c.summary_outdated}件`),
    ),
    h("p", { class: "muted" }, "すべての記事を取得できているとは限りません。情報源ごとの成否と探索できた範囲を確認してください。"),
    h("h2", {}, "情報源ごとの状況"),
    h(
      "table",
      { class: "history status-table" },
      h(
        "thead",
        {},
        h("tr", {}, h("th", {}, "情報源"), h("th", {}, "前回の結果"), h("th", {}, "最後の成功"), h("th", {}, "失敗理由・警告"), h("th", {}, "記事"), h("th", {}, "日付不明"), h("th", {}, "再試行待ち"), h("th", {}, "探索できた範囲")),
      ),
      h("tbody", {}, ...status.sources.map(sourceRow)),
    ),
    h("h2", {}, "実行履歴"),
    h(
      "table",
      { class: "history" },
      h("thead", {}, h("tr", {}, h("th", {}, "開始"), h("th", {}, "結果"), h("th", {}, "新規"), h("th", {}, "変更"), h("th", {}, "日付不明"), h("th", {}, "取得失敗"), h("th", {}, "要約"), h("th", {}, "要約失敗"))),
      h(
        "tbody",
        {},
        ...status.runs.map((r) =>
          h(
            "tr",
            { class: r.status === "success" ? null : "row-failed" },
            h("td", {}, formatDateTime(r.started_at)),
            h("td", {}, RUN_STATUS[r.status] ?? r.status),
            h("td", {}, r.totals.new),
            h("td", {}, r.totals.changed),
            h("td", {}, r.totals.date_unknown),
            h("td", {}, r.totals.fetch_failed),
            h("td", {}, r.totals.summarized),
            h("td", {}, r.totals.summarize_failed),
          ),
        ),
      ),
    ),
  );
}

function sourceRow(s: SourceStatus): HTMLElement {
  const lr = s.last_run;
  const problems = [lr?.error, ...(lr?.warnings ?? [])].filter(Boolean) as string[];
  const range = s.explored_range;
  return h(
    "tr",
    { class: s.last_attempt_status === "failed" ? "row-failed" : null },
    h("td", {}, s.name, h("div", { class: "muted small" }, `${METHOD[s.method] ?? s.method}${s.enabled ? "" : "（無効）"}`)),
    h("td", {}, SOURCE_STATUS[s.last_attempt_status ?? ""] ?? "未実行", s.consecutive_failures > 1 ? h("div", { class: "small" }, `${s.consecutive_failures}回連続`) : null),
    h("td", {}, s.last_success_at ? formatDateTime(s.last_success_at) : "なし"),
    h("td", {}, problems.length ? h("ul", { class: "plain" }, ...problems.map((p) => h("li", {}, p))) : "—"),
    h("td", {}, `${s.articles}件`),
    h("td", {}, `${s.date_unknown}件`),
    h("td", {}, `${s.retry_count}件`),
    h("td", {}, range ? `${range.oldest ? formatPartialDate(range.oldest) : "?"}〜${range.newest ? formatPartialDate(range.newest) : "?"}（${range.pages}ページ）` : "—"),
  );
}

function kv(key: string, value: string): HTMLElement {
  return h("tr", {}, h("th", { class: "k" }, key), h("td", {}, value));
}
