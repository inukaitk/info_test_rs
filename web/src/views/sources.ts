// 情報源：収集している（採用中の）情報源と、候補（未採用）の一覧。取得方式・添付PDFの設定・取得状況・制約を示す。
import { externalLink, h } from "../dom";
import { formatDateTime } from "../format";
import type { SiteData, SourceStatus } from "../types";

const METHOD: Record<string, string> = { rss: "RSS", html: "HTML一覧ページ", sitemap: "サイトマップ", manual: "手動登録" };
const RESULT: Record<string, string> = { success: "成功", failed: "失敗", skipped: "対象外", unsupported: "未対応" };

export function sourcesView(data: SiteData): HTMLElement {
  const sources = data.status.sources;
  const active = sources.filter((s) => s.enabled);
  const candidates = sources.filter((s) => !s.enabled);
  return h(
    "section",
    { class: "sources" },
    h("h1", {}, "情報源"),
    h(
      "p",
      { class: "lead" },
      "記事を集めているページです。公的機関（またはその支援を受けた公式サービスサイト）のほか、特別に認めた民間企業4社を含みます。民間企業は、他の情報源と同じ設定・同じ処理で扱い、優劣や順位は付けていません（五十音順）。「候補」には、公的機関ではない団体・媒体を含みます。ここに載っているページの範囲だけを収集し、Web全体は探していません。",
      "各ページの利用条件と robots.txt を確認したうえで、間隔を空けて少しずつ取得しています。",
    ),
    h("h2", {}, `収集中（${active.length}件）`),
    active.length ? h("div", { class: "source-cards" }, ...active.map((s) => card(s, true))) : h("p", { class: "muted" }, "ありません。"),
    h("h2", {}, `候補（未採用、${candidates.length}件）`),
    h("p", { class: "muted" }, "調査済みで、設定を有効にすれば追加できる情報源です。現在は収集していません。"),
    candidates.length ? h("div", { class: "source-cards" }, ...candidates.map((s) => card(s, false))) : h("p", { class: "muted" }, "ありません。"),
  );
}

function card(s: SourceStatus, active: boolean): HTMLElement {
  const pdf = s.attachments
    ? `添付PDFも読む（1記事${s.attachments.max_files}件・${s.attachments.max_pages}ページまで${
        s.attachments.exclude_titles.length ? `、「${s.attachments.exclude_titles.join("」「")}」を含む資料は除外` : ""
      }）`
    : "添付PDFは読まない";
  return h(
    "article",
    { class: `source-card${active ? "" : " candidate"}` },
    h("h3", {}, s.name, h("span", { class: `badge ${active ? "active" : "candidate"}` }, active ? "収集中" : "候補")),
    h(
      "table",
      { class: "kv" },
      kv("URL", externalLink(s.entry_url, s.entry_url)),
      kv("取得方式", `${METHOD[s.method] ?? s.method}　／　${pdf}`),
      active
        ? kv(
            "取得状況",
            h(
              "span",
              {},
              `前回：${RESULT[s.last_attempt_status ?? ""] ?? "未実行"}　最後の成功：${s.last_success_at ? formatDateTime(s.last_success_at) : "なし"}　記事：${s.articles}件　`,
              h("a", { href: "#/status" }, "取得状況を見る"),
            ),
          )
        : null,
      kv("制約・メモ", s.notes ?? "—"),
    ),
  );
}

function kv(key: string, value: HTMLElement | string): HTMLElement {
  return h("tr", {}, h("th", { class: "k" }, key), h("td", {}, value));
}
