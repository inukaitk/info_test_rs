// 最新情報：取得日（見つけた日）が直近 latest_days 日（最終収集日を含む）の記事。
// それより前の記事は「記事を探す」（全期間の絞り込み・検索）と Wiki で見る。
import { h } from "../dom";
import { latestArticles, latestWindow } from "../filters";
import { formatDateTime, formatPartialDate } from "../format";
import type { SiteData } from "../types";
import { articleTable } from "./list";

export function latestView(data: SiteData): HTMLElement {
  const { meta } = data;
  const window = latestWindow(meta.data_as_of, meta.latest_days);
  const articles = latestArticles(data.articles, window);

  const period = window
    ? h(
        "p",
        { class: "lead" },
        `${formatPartialDate(window.from)}〜${formatPartialDate(window.to)}に見つけた記事（直近${meta.latest_days}日間）：`,
        h("strong", {}, `${articles.length}件`),
        h("span", { class: "muted" }, `　最終収集：${formatDateTime(meta.data_as_of)}`),
      )
    : h("p", { class: "lead" }, "まだ収集したデータがありません。");

  return h(
    "section",
    {},
    h("h1", {}, "最新情報"),
    period,
    articles.length ? articleTable(articles) : h("p", { class: "empty" }, "この期間に新しく見つけた記事はありません。"),
    h(
      "p",
      { class: "more" },
      "それより前の記事は ",
      h("a", { href: "#/search" }, "記事を探す"),
      " で、期間・タグ・機関の絞り込みや文字検索をして見られます。",
    ),
  );
}
