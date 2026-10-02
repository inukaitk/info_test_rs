// 記事を探す：全期間の記事を、タグ・機関・期間で絞り込み、文字検索する。
import { h } from "../dom";
import { applyFilters, countDateUnknownExcluded, type Filters, filtersToQuery } from "../filters";
import { formatDate, SUMMARY_STATUS_LABEL } from "../format";
import type { Article, SiteData } from "../types";
import { tagList } from "./tags";

export function listView(data: SiteData, filters: Filters, navigate: (hash: string) => void): HTMLElement {
  const results = applyFilters(data.articles, filters);
  const excludedUnknown = countDateUnknownExcluded(data.articles, filters);
  const limit = data.meta.page_size;

  const form = filterForm(data, filters, navigate);
  const summaryLine = h(
    "p",
    { class: "result-count", "aria-live": "polite" },
    `${data.articles.length}件中 ${results.length}件`,
    results.length > limit ? `（新しい順に${limit}件を表示）` : "",
  );
  const notes = h("div", {});
  if (excludedUnknown > 0) {
    notes.append(h("p", { class: "note" }, `日付不明の記事 ${excludedUnknown}件は期間の絞り込みに含めていません。期間を外すと表示されます。`));
  }

  const table = results.length ? articleTable(results.slice(0, limit)) : h("p", { class: "empty" }, "条件に合う記事はありません。");

  return h(
    "section",
    {},
    h("h1", {}, "記事を探す"),
    h("p", { class: "lead" }, "これまでに集めたすべての記事から、タグ・機関・期間（公開日）で絞り込み、文字で検索できます。"),
    form,
    summaryLine,
    notes,
    table,
  );
}

export function articleTable(articles: Article[]): HTMLElement {
  return h(
    "table",
    { class: "article-table" },
    h("thead", {}, h("tr", {}, h("th", {}, "公開日"), h("th", {}, "機関"), h("th", {}, "タイトル・概要"), h("th", {}, "タグ"))),
    h("tbody", {}, ...articles.map(row)),
  );
}

function row(a: Article): HTMLElement {
  const summary =
    a.summary.status === "success"
      ? h("p", { class: "summary" }, a.summary.text)
      : h("p", { class: "summary unsummarized" }, SUMMARY_STATUS_LABEL[a.summary.status] ?? "未要約");
  return h(
    "tr",
    {},
    h("td", { class: "date" }, formatDate(a.published)),
    h("td", { class: "source" }, a.source_name),
    h("td", {}, h("a", { href: `#/articles/${encodeURIComponent(a.id)}`, class: "title" }, a.title), summary),
    h("td", {}, a.tags.length || a.summary.status === "success" ? tagList(a.tags) : h("span", { class: "muted" }, "AI未処理")),
  );
}

function filterForm(data: SiteData, f: Filters, navigate: (hash: string) => void): HTMLElement {
  const usedTags = new Set(data.articles.flatMap((a) => a.tags.map((t) => t.id)));
  const tagOptions = data.meta.tags.filter((t) => usedTags.has(t.id) || t.id === f.tag);
  const option = (value: string, label: string, selected: string) =>
    h("option", { value, ...(value === selected ? { selected: true } : {}) } as Record<string, string | boolean>, label);

  const q = h("input", { type: "search", id: "f-q", name: "q", value: f.q, placeholder: "例：健診 改正" }) as HTMLInputElement;
  const tag = h("select", { id: "f-tag", name: "tag" }, option("", "すべて", f.tag),
    ...tagOptions.map((t) => option(t.id, t.retired ? `${t.name}（廃止）` : t.name, f.tag))) as HTMLSelectElement;
  const source = h("select", { id: "f-source", name: "source" }, option("", "すべて", f.source),
    ...data.meta.sources.map((s) => option(s.id, s.name, f.source))) as HTMLSelectElement;
  const from = h("input", { type: "date", id: "f-from", name: "from", value: f.from }) as HTMLInputElement;
  const to = h("input", { type: "date", id: "f-to", name: "to", value: f.to }) as HTMLInputElement;

  const form = h(
    "form",
    { class: "filters", role: "search" },
    field("f-q", "文字検索", q),
    field("f-tag", "タグ", tag),
    field("f-source", "機関", source),
    h("div", { class: "field period" }, h("span", { class: "label" }, "期間（公開日）"), from, h("span", {}, "〜"), to),
    h("div", { class: "actions" }, h("button", { type: "submit" }, "絞り込む"), h("a", { href: "#/search", class: "reset" }, "条件をクリア")),
  );
  const current = (): Filters => ({ q: q.value.trim(), tag: tag.value, source: source.value, from: from.value, to: to.value });
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    navigate(`#/search${filtersToQuery(current())}`);
  });
  for (const el of [tag, source, from, to]) el.addEventListener("change", () => navigate(`#/search${filtersToQuery(current())}`));
  return form;
}

function field(id: string, label: string, control: HTMLElement): HTMLElement {
  return h("div", { class: "field" }, h("label", { for: id }, label), control);
}
