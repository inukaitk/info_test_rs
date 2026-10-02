// 記事詳細（SPEC 4.5）：出典リンク、公開日、更新日、取得日、日付の根拠、概要、論点、対象、
// 確認できた日付、タグとその由来、AI処理状態、変更履歴。
import { externalLink, h } from "../dom";
import {
  ARTICLE_STATUS_LABEL,
  CONTENT_STATUS_LABEL,
  DATE_METHOD_LABEL,
  formatDate,
  formatDateTime,
  formatPartialDate,
  PRECISION_LABEL,
  SUMMARY_STATUS_LABEL,
} from "../format";
import type { Article, DateInfo, SiteData } from "../types";
import { tagChip } from "./tags";

export function detailView(data: SiteData, id: string): HTMLElement {
  const a = data.articles.find((x) => x.id === id);
  if (!a) {
    return h("section", {}, h("h1", {}, "記事が見つかりません"), h("p", {}, h("a", { href: "#/" }, "最新情報へ戻る")));
  }
  return h(
    "article",
    { class: "detail" },
    h("p", { class: "back" }, h("a", { href: "#/" }, "← 最新情報へ"), "　", h("a", { href: "#/search" }, "記事を探す")),
    h("h1", {}, a.title),
    h("p", { class: "source-line" }, a.source_name, " ／ 出典：", externalLink(a.url, a.url)),
    section("日付", datesTable(a)),
    section("概要", summaryBlock(a)),
    a.attachments.length ? section("添付資料", attachmentsBlock(a)) : null,
    section("タグ", tagsBlock(a)),
    section("処理状態", statusTable(a)),
    section("変更履歴", historyTable(a)),
  );
}

const CHANGE_LABEL: Record<string, string> = {
  new: "新規",
  content_changed: "本文の変更",
  extraction_changed: "抽出方法の変更（原文の変更ではない）",
};

const ATTACHMENT_STATUS: Record<string, string> = {
  ok: "読み取り済み",
  failed: "取得失敗",
  unsupported: "読み取れない形式",
  skipped: "取得していない",
};

function attachmentsBlock(a: Article): HTMLElement {
  return h(
    "div",
    {},
    h("p", { class: "muted" }, "記事ページからリンクされている資料です。「読み取り済み」の資料は概要の材料に含めています（本文は画面に表示しません）。"),
    h(
      "table",
      { class: "history" },
      h("thead", {}, h("tr", {}, h("th", {}, "資料"), h("th", {}, "状態"), h("th", {}, "備考"))),
      h(
        "tbody",
        {},
        ...a.attachments.map((x) =>
          h(
            "tr",
            {},
            h("td", {}, externalLink(x.url, x.title)),
            h("td", {}, ATTACHMENT_STATUS[x.status] ?? x.status, x.pages ? `（${x.pages}ページ）` : ""),
            h("td", {}, x.note ?? ""),
          ),
        ),
      ),
    ),
  );
}

function section(title: string, body: HTMLElement): HTMLElement {
  return h("section", { class: "detail-section" }, h("h2", {}, title), body);
}

function basisText(info: DateInfo): HTMLElement | string {
  if (!info.basis) return info.value === null ? "根拠なし（原文で日付を確認できませんでした）" : "—";
  return h(
    "span",
    {},
    `${DATE_METHOD_LABEL[info.basis.method] ?? info.basis.method}（${PRECISION_LABEL[info.precision]}）：`,
    h("q", { class: "evidence" }, info.basis.evidence),
  );
}

function datesTable(a: Article): HTMLElement {
  const updated = a.updated.value === null ? "記載なし" : formatDate(a.updated);
  return h(
    "table",
    { class: "kv" },
    kv("公開日", formatDate(a.published)),
    kv("公開日の根拠", basisText(a.published)),
    kv("更新日", updated),
    a.updated.value !== null ? kv("更新日の根拠", basisText(a.updated)) : null,
    kv("取得日（最新版）", formatDateTime(a.versions[a.versions.length - 1]?.fetched_at ?? null)),
    kv("初めて見つけた日", formatDateTime(a.first_seen_at)),
  );
}

function summaryBlock(a: Article): HTMLElement {
  const s = a.summary;
  if (s.status !== "success") {
    return h(
      "div",
      { class: "unsummarized-box" },
      h("p", {}, h("strong", {}, SUMMARY_STATUS_LABEL[s.status] ?? "未要約")),
      h("p", { class: "muted" }, "本文やタイトルから内容を推測して補うことはしていません。出典で内容を確認してください。"),
    );
  }
  return h(
    "div",
    {},
    s.outdated ? h("p", { class: "note" }, `この概要は第${s.version}版の本文にもとづいています（最新は第${a.latest_version}版）。`) : null,
    h("p", { class: "summary-text" }, s.text),
    h("h3", {}, "主要な論点"),
    list(s.key_points),
    h("h3", {}, "対象"),
    list(s.targets),
    h("h3", {}, "確認できた日付"),
    s.dates && s.dates.length
      ? h(
          "table",
          { class: "kv" },
          ...s.dates.map((d) => kv(d.label, h("span", {}, formatPartialDate(d.value), " ", h("q", { class: "evidence" }, d.evidence)))),
        )
      : h("p", { class: "muted" }, "原文で確認できた日付はありません。"),
    s.uncertainties && s.uncertainties.length ? h("div", {}, h("h3", {}, "確認できなかった点"), list(s.uncertainties)) : null,
    h("p", { class: "ai-note" }, "この概要はAIが作成したもので、誤りを含む可能性があります。"),
  );
}

function tagsBlock(a: Article): HTMLElement {
  const ai = a.tags.filter((t) => t.origin === "ai");
  const human = a.tags.filter((t) => t.origin === "human");
  return h(
    "div",
    {},
    h(
      "table",
      { class: "kv" },
      kv(
        "AIが付与",
        ai.length
          ? h("ul", { class: "tag-reasons" }, ...ai.map((t) => h("li", {}, tagChip(t), t.reason ? h("span", { class: "reason" }, t.reason) : null)))
          : a.summary.status === "success"
            ? "該当なし"
            : "AI未処理のためなし",
      ),
      kv("人が追加", human.length ? h("span", { class: "tags" }, ...human.map((t) => tagChip(t))) : "なし"),
      kv(
        "人が除外",
        a.removed_tags.length
          ? h("span", { class: "tags" }, ...a.removed_tags.map((t) => h("span", { class: "tag tag-removed" }, h("span", { class: "tag-name" }, t.name))))
          : "なし",
      ),
      a.tag_override_reason ? kv("修正の理由", a.tag_override_reason) : null,
    ),
  );
}

function statusTable(a: Article): HTMLElement {
  return h(
    "table",
    { class: "kv" },
    kv("記事の状態", ARTICLE_STATUS_LABEL[a.status] ?? a.status),
    kv("本文", [CONTENT_STATUS_LABEL[a.content_status] ?? a.content_status, a.content_error ? `：${a.content_error}` : ""].join("")),
    kv("AI処理", SUMMARY_STATUS_LABEL[a.summary.status] ?? a.summary.status),
    a.summary.error && a.summary.status !== "success" ? kv("AI処理の詳細", a.summary.error) : null,
    a.summary.processed_at ? kv("AI処理日時", formatDateTime(a.summary.processed_at)) : null,
    a.summary.model ? kv("モデル", a.summary.model) : null,
  );
}

function historyTable(a: Article): HTMLElement {
  return h(
    "table",
    { class: "history" },
    h("thead", {}, h("tr", {}, h("th", {}, "版"), h("th", {}, "取得日時"), h("th", {}, "内容"), h("th", {}, "本文"))),
    h(
      "tbody",
      {},
      ...a.versions.map((v) =>
        h(
          "tr",
          {},
          h("td", {}, `第${v.version}版`),
          h("td", {}, formatDateTime(v.fetched_at)),
          h("td", {}, CHANGE_LABEL[v.change_type] ?? v.change_type),
          h("td", {}, CONTENT_STATUS_LABEL[v.extraction_status] ?? v.extraction_status),
        ),
      ),
    ),
  );
}

function kv(key: string, value: HTMLElement | string): HTMLElement {
  return h("tr", {}, h("th", { class: "k" }, key), h("td", {}, value));
}

function list(items: string[] | null): HTMLElement {
  if (!items || !items.length) return h("p", { class: "muted" }, "なし");
  return h("ul", {}, ...items.map((i) => h("li", {}, i)));
}
