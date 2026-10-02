// hash によるルーティング（#/ 最新情報、#/search 記事を探す、#/articles/<id> 記事詳細、
// #/wiki・#/wiki/<tag> Wiki、#/reports・#/reports/<期間> 週次レポート、#/status 取得状況）。サブパスに置いても直リンクが 404 にならない。
import { type Filters, parseFilters } from "./filters";

export type Route =
  | { name: "latest" }
  | { name: "search"; filters: Filters }
  | { name: "detail"; id: string }
  | { name: "wiki" }
  | { name: "wikiTag"; tag: string }
  | { name: "reports"; week: string | null }
  | { name: "status" }
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
  if (path === "/wiki") return { name: "wiki" };
  const w = /^\/wiki\/([a-z0-9][a-z0-9_-]{0,63})$/.exec(path);
  if (w) return { name: "wikiTag", tag: w[1] };
  if (path === "/reports") return { name: "reports", week: null };
  const r = /^\/reports\/(\d{4}-\d{2}-\d{2}_\d{4}-\d{2}-\d{2})$/.exec(path);
  if (r) return { name: "reports", week: r[1] };
  if (path === "/status") return { name: "status" };
  return { name: "notfound" };
}
