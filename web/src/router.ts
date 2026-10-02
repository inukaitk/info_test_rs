// hash によるルーティング（#/ と #/articles/<id>）。サブパスに置いても直リンクが 404 にならない。
import { type Filters, parseFilters } from "./filters";

export type Route = { name: "list"; filters: Filters } | { name: "detail"; id: string } | { name: "notfound" };

export function parseHash(hash: string): Route {
  const raw = hash.replace(/^#/, "") || "/";
  const [path, query = ""] = raw.split("?", 2);
  if (path === "/" || path === "") return { name: "list", filters: parseFilters(new URLSearchParams(query)) };
  const m = /^\/articles\/(a_[0-9a-f]{16})$/.exec(path);
  if (m) return { name: "detail", id: m[1] };
  return { name: "notfound" };
}
