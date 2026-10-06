import { h } from "../dom";
import type { Tag } from "../types";

/** タグの由来の表示（チップの文言）。 */
export const ORIGIN_TEXT: Record<Tag["origin"], string> = { ai: "AI", human: "人が追加", source: "設定" };
const ORIGIN_TITLE: Record<Tag["origin"], string> = { ai: "AIが付与", human: "人が追加したタグ", source: "情報源の設定で付与" };

/** タグ1つ。AI付与・人の追加・情報源の設定を、見た目と文言で区別する。 */
export function tagChip(tag: Tag, withLink = true): HTMLElement {
  const label = [tag.name, tag.retired ? "（廃止）" : ""].join("");
  const originText = ORIGIN_TEXT[tag.origin];
  const content = [h("span", { class: "tag-origin" }, originText), h("span", { class: "tag-name" }, label)];
  const attrs = {
    class: `tag tag-${tag.origin}${tag.retired ? " tag-retired" : ""}`,
    title: tag.origin === "human" ? "人が追加したタグ" : `${ORIGIN_TITLE[tag.origin]}${tag.reason ? `：${tag.reason}` : ""}`,
  };
  return withLink
    ? h("a", { ...attrs, href: `#/search?tag=${encodeURIComponent(tag.id)}` }, ...content)
    : h("span", attrs, ...content);
}

export function tagList(tags: Tag[]): HTMLElement {
  if (!tags.length) return h("span", { class: "muted" }, "タグなし");
  return h("span", { class: "tags" }, ...tags.map((t) => tagChip(t)));
}
