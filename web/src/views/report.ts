// 週次レポート：期間内の新規・変更、タグ別件数、情報源別の取得状況。Markdown でも保存できる。
import { externalLink, h } from "../dom";
import { downloadText } from "../download";
import { formatDateTime, formatPartialDate } from "../format";
import type { ReportItem, SiteData, WeeklyReport } from "../types";

const SOURCE_STATUS: Record<string, string> = { success: "成功", failed: "失敗", skipped: "対象外", unsupported: "未対応" };

export function reportView(data: SiteData, weekId: string | null, navigate: (hash: string) => void): HTMLElement {
  const weeks = data.reports;
  if (!weeks.length) return h("section", {}, h("h1", {}, "週次レポート"), h("p", { class: "empty" }, "まだ収集したデータがありません。"));
  const week = weeks.find((w) => w.id === weekId) ?? weeks[0];

  const select = h(
    "select",
    { id: "report-week" },
    ...weeks.map((w) => h("option", { value: w.id, selected: w.id === week.id }, periodLabel(w))),
  ) as HTMLSelectElement;
  select.addEventListener("change", () => navigate(`#/reports/${select.value}`));

  const mdButton = h("button", { type: "button" }, "Markdownで保存");
  mdButton.addEventListener("click", () => downloadText(`weekly_${week.id}.md`, week.markdown, "text/markdown"));

  const c = week.counts;
  return h(
    "section",
    { class: "report" },
    h("h1", {}, "週次レポート"),
    h("div", { class: "toolbar" }, h("label", { for: "report-week" }, "期間："), select, mdButton),
    h("p", { class: "lead" }, `${periodLabel(week)}：公開日が期間内の記事と、期間内に本文が変わった記事（公開日が日まで分からない記事は数えない）`),
    h(
      "table",
      { class: "kv counts" },
      kv("新規", `${c.new}件`),
      kv("変更", `${c.changed}件`),
      kv("公開日不明のため数えていない記事（この期間に見つけたもの）", `${c.date_unknown}件`),
      kv("うち未要約", `${c.unsummarized}件`),
      kv("期間内の収集実行", `${c.runs}回`),
    ),
    h("h2", {}, `新規（${c.new}件）`),
    itemTable(week.new, false),
    h("h2", {}, `変更（${c.changed}件）`),
    itemTable(week.changed, true),
    h("h2", {}, "タグ別件数（新規＋変更）"),
    week.tag_counts.length
      ? h(
          "table",
          { class: "history" },
          h("thead", {}, h("tr", {}, h("th", {}, "タグ"), h("th", {}, "件数"))),
          h("tbody", {}, ...week.tag_counts.map((t) => h("tr", {}, h("td", {}, h("a", { href: `#/wiki/${encodeURIComponent(t.id)}` }, t.name)), h("td", {}, t.count)))),
        )
      : h("p", { class: "muted" }, "なし"),
    c.untagged ? h("p", { class: "muted" }, `タグのない記事：${c.untagged}件（AI未処理を含む）`) : null,
    h("h2", {}, "情報源別の取得状況"),
    h(
      "table",
      { class: "history" },
      h("thead", {}, h("tr", {}, h("th", {}, "情報源"), h("th", {}, "実行日時"), h("th", {}, "結果"), h("th", {}, "新規"), h("th", {}, "変更"), h("th", {}, "失敗理由"))),
      h(
        "tbody",
        {},
        ...week.sources.flatMap((s) =>
          s.runs.length
            ? s.runs.map((r) =>
                h(
                  "tr",
                  { class: r.status === "failed" ? "row-failed" : null },
                  h("td", {}, s.name),
                  h("td", {}, formatDateTime(r.started_at)),
                  h("td", {}, SOURCE_STATUS[r.status] ?? r.status),
                  h("td", {}, r.new),
                  h("td", {}, r.changed),
                  h("td", {}, r.error ?? ""),
                ),
              )
            : [h("tr", {}, h("td", {}, s.name), h("td", { colspan: 5, class: "muted" }, "期間内の実行なし"))],
        ),
      ),
    ),
  );
}

function periodLabel(w: WeeklyReport): string {
  return `${formatPartialDate(w.from)}〜${formatPartialDate(w.to)}`;
}

function itemTable(items: ReportItem[], changed: boolean): HTMLElement {
  if (!items.length) return h("p", { class: "muted" }, "なし");
  return h(
    "table",
    { class: "history" },
    h("thead", {}, h("tr", {}, h("th", {}, "公開日"), h("th", {}, "機関"), h("th", {}, "タイトル"), h("th", {}, "タグ"))),
    h(
      "tbody",
      {},
      ...items.map((i) =>
        h(
          "tr",
          {},
          h("td", { class: "date" }, i.published ? formatPartialDate(i.published) : "日付不明"),
          h("td", {}, i.source_name),
          h("td", {}, h("a", { href: `#/articles/${encodeURIComponent(i.id)}` }, i.title), changed && i.version ? `（第${i.version}版）` : "", " ", externalLink(i.url, "出典")),
          h("td", {}, i.tags.length ? i.tags.join("、") : i.summary_status === "success" ? "タグなし" : h("span", { class: "muted" }, "AI未処理")),
        ),
      ),
    ),
  );
}

function kv(key: string, value: string): HTMLElement {
  return h("tr", {}, h("th", { class: "k" }, key), h("td", {}, value));
}
