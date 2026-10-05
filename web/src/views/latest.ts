// 最新情報：公開日が直近 latest_days 日（最終収集日を含む）の記事（日付不明・月のみの記事は取得日で数える）。
// それより前の記事は「記事を探す」（全期間の絞り込み・検索）と Wiki で見る。
import { h } from "../dom";
import { latestArticles, latestWindow } from "../filters";
import { formatDateTime, formatPartialDate } from "../format";
import type { SiteData } from "../types";
import { correctionLink } from "./layout";
import { articleTable } from "./list";
import { statusWarnings } from "./status";

export function latestView(data: SiteData, now: Date = new Date()): HTMLElement {
  const { meta } = data;
  const window = latestWindow(meta.data_as_of, meta.latest_days);
  const articles = latestArticles(data.articles, window);

  const period = window
    ? h(
        "p",
        { class: "lead" },
        `${formatPartialDate(window.from)}〜${formatPartialDate(window.to)}に公開された記事（直近${meta.latest_days}日間）：`,
        h("strong", {}, `${articles.length}件`),
      )
    : h("p", { class: "lead" }, "まだ収集したデータがありません。");

  const warnings = statusWarnings(data, now);
  const summary = h(
    "div",
    { class: "top-summary" },
    h("div", {}, "最終収集：", formatDateTime(data.status.last_run_at), "　",
      warnings.length ? h("a", { href: "#/status", class: "warn-link" }, `取得状況に注意が${warnings.length}件あります`) : h("a", { href: "#/status" }, "取得状況")),
    h("div", {}, "今週のまとめ：", h("a", { href: "#/reports" }, "週次レポート"), "　テーマ別：", h("a", { href: "#/wiki" }, "Wiki")),
    h("div", {}, correctionLink(meta), h("span", { class: "muted small" }, "　（タグや要約の誤りに気づいたらお知らせください）")),
  );

  return h(
    "section",
    {},
    h("h1", {}, "最新情報"),
    summary,
    period,
    articles.length ? articleTable(articles) : h("p", { class: "empty" }, "この期間に公開された記事はありません。"),
    h(
      "p",
      { class: "more" },
      "それより前の記事は ",
      h("a", { href: "#/search" }, "記事を探す"),
      " で、期間・タグ・機関の絞り込みや文字検索をして見られます。",
    ),
  );
}
