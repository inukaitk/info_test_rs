// hash によるルーティング（#/ 最新情報、#/search 記事を探す、#/articles/<id> 記事詳細）。サブパスに置いても直リンクが 404 にならない。
import { type Filters, parseFilters } from "./filters";

export type Route =
  | { name: "latest" }
  | { name: "search"; filters: Filters }
  | { name: "detail"; id: string }
  | { name: "notfound" };

export function parseHash(hash: string): Route {
  const raw = hash.replace(/^#/, "") || "/";
  const [path, query = ""] = raw.split("?", 2);
  if (path === "/" || path === "") {
    // 以前の形式（#/?tag=...）の絞り込みリンクは「記事を探す」で開く
    return query ? { name: "search", filters: parseFilters(new URLSearchParams(query)) } : { name: "latest" };
  }
  if (path === "/search") return { name: "search", filters: parseFilters(new URLSearchParams(query)) };
  const m = /^\/articles\/(a_[0-9a-f]{16})$/.exec(path);
  if (m) return { name: "detail", id: m[1] };
  return { name: "notfound" };
}
