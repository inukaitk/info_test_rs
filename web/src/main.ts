import { loadSiteData } from "./data";
import { h } from "./dom";
import { parseHash } from "./router";
import type { SiteData } from "./types";
import { detailView } from "./views/detail";
import { errorPage, layout } from "./views/layout";
import { listView } from "./views/list";

const app = document.getElementById("app")!;

function navigate(hash: string): void {
  if (location.hash === hash) render(current!);
  else location.hash = hash;
}

let current: SiteData | null = null;

export function render(data: SiteData): void {
  const route = parseHash(location.hash);
  let main: HTMLElement;
  let title = data.meta.site_name;
  if (route.name === "list") {
    main = listView(data, route.filters, navigate);
  } else if (route.name === "detail") {
    main = detailView(data, route.id);
    const article = data.articles.find((a) => a.id === route.id);
    if (article) title = `${article.title} - ${title}`;
  } else {
    main = h("section", {}, h("h1", {}, "ページが見つかりません"), h("p", {}, h("a", { href: "#/" }, "最新一覧へ戻る")));
  }
  document.title = data.meta.is_demo ? `【架空データ】${title}` : title;
  app.replaceChildren(layout(data.meta, route.name === "list" ? "list" : "detail", main));
  if (route.name === "detail") window.scrollTo(0, 0);
}

loadSiteData()
  .then((data) => {
    current = data;
    render(data);
    window.addEventListener("hashchange", () => render(data));
  })
  .catch((err: unknown) => {
    app.replaceChildren(errorPage(err instanceof Error ? err.message : String(err)));
  });
