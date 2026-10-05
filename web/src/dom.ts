// DOM を組み立てる小さな補助関数。
// 取得した文字列は必ず textContent（テキストとして）入れ、innerHTML は使わない。
// これにより記事タイトル等に <script> などが含まれていても HTML として解釈されない（XSS対策）。

type Child = Node | string | number | null | undefined | false;
type Attrs = Record<string, string | number | boolean | null | undefined>;

const SAFE_ATTRS = new Set([
  "class", "id", "href", "title", "type", "name", "value", "placeholder", "for", "role",
  "aria-label", "aria-live", "aria-current", "aria-disabled", "lang", "rel", "target", "min", "max", "datetime", "colspan", "selected",
]);

export function h(tag: string, attrs: Attrs = {}, ...children: Child[]): HTMLElement {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue;
    if (!SAFE_ATTRS.has(key)) throw new Error(`許可していない属性です: ${key}`);
    if (key === "href") {
      el.setAttribute("href", safeHref(String(value)));
    } else {
      el.setAttribute(key, value === true ? "" : String(value));
    }
  }
  append(el, ...children);
  return el;
}

export function append(parent: Node, ...children: Child[]): void {
  for (const child of children) {
    if (child === null || child === undefined || child === false) continue;
    parent.appendChild(typeof child === "string" || typeof child === "number" ? document.createTextNode(String(child)) : child);
  }
}

/** 画面内リンク（#/...）と http(s) のURLだけを許可する。javascript: などは無効なリンクにする。 */
export function safeHref(value: string): string {
  if (value.startsWith("#")) return value;
  try {
    const url = new URL(value);
    if (url.protocol === "http:" || url.protocol === "https:") return url.href;
  } catch {
    // URLとして読めないものは使わない
  }
  return "#";
}

/** 外部サイトへのリンク。新しいタブで開き、遷移元の情報を渡さない。 */
export function externalLink(url: string, text: string): HTMLElement {
  return h("a", { href: url, target: "_blank", rel: "noopener noreferrer external" }, text);
}
