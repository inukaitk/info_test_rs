import { h } from "../dom";
import type { Tag } from "../types";

/** タグ1つ。AI付与と人の追加を見た目と文言で区別する。 */
export function tagChip(tag: Tag, withLink = true): HTMLElement {
  const label = [tag.name, tag.retired ? "（廃止）" : ""].join("");
  const originText = tag.origin === "ai" ? "AI" : "人が追加";
  const content = [h("span", { class: "tag-origin" }, originText), h("span", { class: "tag-name" }, label)];
  const attrs = {
    class: `tag tag-${tag.origin}${tag.retired ? " tag-retired" : ""}`,
    title: tag.origin === "ai" ? `AIが付与${tag.reason ? `：${tag.reason}` : ""}` : "人が追加したタグ",
  };
  return withLink
    ? h("a", { ...attrs, href: `#/?tag=${encodeURIComponent(tag.id)}` }, ...content)
    : h("span", attrs, ...content);
}

export function tagList(tags: Tag[]): HTMLElement {
  if (!tags.length) return h("span", { class: "muted" }, "タグなし");
  return h("span", { class: "tags" }, ...tags.map((t) => tagChip(t)));
}
