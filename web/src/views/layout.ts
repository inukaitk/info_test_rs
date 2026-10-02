// 全画面共通の枠（架空データの表示、ヘッダー、ナビゲーション）。
import { externalLink, h } from "../dom";
import { formatDateTime } from "../format";
import type { Meta } from "../types";

export function demoBanner(meta: Meta): HTMLElement | null {
  if (!meta.is_demo) return null;
  return h(
    "div",
    { class: "demo-banner", role: "note" },
    h("strong", {}, "架空データ"),
    "：この画面に表示している機関名・記事・URLはすべて架空です。実在の情報ではありません。",
  );
}

export type Section = "latest" | "search" | "wiki" | "reports" | "status" | "sources" | "detail";

const MENU: [Section, string, string][] = [
  ["latest", "#/", "最新情報"],
  ["search", "#/search", "記事を探す"],
  ["wiki", "#/wiki", "Wiki"],
  ["reports", "#/reports", "週次レポート"],
  ["status", "#/status", "取得状況"],
  ["sources", "#/sources", "情報源"],
];

/** 修正依頼リンク。URL は site.yaml の correction_request_url。未設定なら「未設定」と表示する。 */
export function correctionLink(meta: Meta): HTMLElement {
  return h(
    "span",
    { class: "correction" },
    "修正依頼：",
    meta.correction_request_url ? externalLink(meta.correction_request_url, "フォームを開く") : h("span", { class: "muted" }, "未設定"),
  );
}

export function layout(meta: Meta, current: Section, main: HTMLElement): HTMLElement {
  const nav = h(
    "nav",
    { "aria-label": "メニュー" },
    ...MENU.map(([key, href, label]) => h("a", { href, "aria-current": current === key ? "page" : null }, label)),
  );
  return h(
    "div",
    { class: "page" },
    demoBanner(meta),
    h(
      "header",
      { class: "site-header" },
      h("div", { class: "site-title" }, h("a", { href: "#/" }, meta.site_name), meta.is_demo ? h("span", { class: "badge demo" }, "架空データ") : null),
      nav,
      correctionLink(meta),
    ),
    h("main", { id: "main" }, main),
    h(
      "footer",
      { class: "site-footer" },
      `データ作成：${formatDateTime(meta.generated_at)}`,
      " ／ 公的機関の公開情報をもとに独自に作成した概要です。内容は必ず出典で確認してください。",
    ),
  );
}

export function errorPage(message: string): HTMLElement {
  return h("div", { class: "page" }, h("main", {}, h("h1", {}, "表示できませんでした"), h("p", { class: "error" }, message)));
}
