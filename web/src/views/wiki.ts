// タグ別 Wiki：タグの説明と、該当記事の時系列リンク（全期間）。
import { h } from "../dom";
import { formatDate, formatPartialDate } from "../format";
import type { Article, SiteData } from "../types";
import { ORIGIN_TEXT } from "./tags";

function articlesWithTag(data: SiteData, tagId: string): Article[] {
  return data.articles.filter((a) => a.tags.some((t) => t.id === tagId));
}

function sortKey(a: Article): string {
  return a.published.value ?? "";
}

export function wikiIndexView(data: SiteData): HTMLElement {
  const items = data.meta.tags.map((tag) => {
    const list = articlesWithTag(data, tag.id);
    const latest = list.map(sortKey).filter(Boolean).sort().pop();
    return h(
      "li",
      { class: "wiki-entry" },
      h("a", { href: `#/wiki/${encodeURIComponent(tag.id)}`, class: "wiki-name" }, tag.name),
      tag.retired ? h("span", { class: "badge retired" }, "廃止") : null,
      h("span", { class: "muted" }, `　${list.length}件${latest ? `（最新の公開日：${formatPartialDate(latest)}）` : ""}`),
      h("p", { class: "wiki-desc" }, tag.description),
    );
  });
  return h(
    "section",
    {},
    h("h1", {}, "Wiki（タグ別）"),
    h("p", { class: "lead" }, "タグごとに、説明と該当する記事を時系列で並べています（全期間）。タグはAIが付けたものと人が修正したものを含みます。"),
    h("ul", { class: "wiki-index" }, ...items),
  );
}

export function wikiTagView(data: SiteData, tagId: string): HTMLElement {
  const tag = data.meta.tags.find((t) => t.id === tagId);
  if (!tag) {
    return h("section", {}, h("h1", {}, "タグが見つかりません"), h("p", {}, h("a", { href: "#/wiki" }, "Wiki の一覧へ")));
  }
  const list = articlesWithTag(data, tagId);
  const dated = list.filter((a) => a.published.value !== null).sort((a, b) => sortKey(b).localeCompare(sortKey(a)));
  const unknown = list.filter((a) => a.published.value === null).sort((a, b) => b.first_seen_at.localeCompare(a.first_seen_at));

  // 公開日の年月ごとにまとめる
  const groups = new Map<string, Article[]>();
  for (const a of dated) {
    const ym = a.published.value!.slice(0, 7);
    const key = ym.length === 7 ? ym : a.published.value!.slice(0, 4);
    groups.set(key, [...(groups.get(key) ?? []), a]);
  }

  const item = (a: Article) => {
    const t = a.tags.find((x) => x.id === tagId)!;
    return h(
      "li",
      {},
      h("span", { class: "wiki-date" }, formatDate(a.published)),
      h("a", { href: `#/articles/${encodeURIComponent(a.id)}` }, a.title),
      h("span", { class: "muted" }, `　${a.source_name}`),
      h("span", { class: `origin origin-${t.origin}` }, ORIGIN_TEXT[t.origin]),
    );
  };

  const sections = [...groups.entries()].map(([key, items]) =>
    h("section", { class: "wiki-group" }, h("h2", {}, key.length === 7 ? formatPartialDate(key).replace("（日不明）", "") : `${key}年`), h("ul", { class: "wiki-list" }, ...items.map(item))),
  );
  if (unknown.length) {
    sections.push(
      h(
        "section",
        { class: "wiki-group" },
        h("h2", {}, "日付不明"),
        h("p", { class: "muted" }, "原文で公開日を確認できなかった記事です（見つけた日の新しい順）。"),
        h("ul", { class: "wiki-list" }, ...unknown.map(item)),
      ),
    );
  }

  return h(
    "section",
    {},
    h("p", { class: "back" }, h("a", { href: "#/wiki" }, "← Wiki の一覧へ")),
    h("h1", {}, `${tag.name}${tag.retired ? "（廃止）" : ""}`),
    h("p", { class: "wiki-desc" }, tag.description),
    h(
      "p",
      { class: "lead" },
      `該当する記事：${list.length}件　`,
      h("a", { href: `#/search?tag=${encodeURIComponent(tag.id)}` }, "このタグで絞り込んで探す"),
    ),
    ...(sections.length ? sections : [h("p", { class: "empty" }, "このタグの記事はまだありません。")]),
  );
}
