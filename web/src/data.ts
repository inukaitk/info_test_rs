// 画面用JSON（public/data/）の読み込み。
import type { Article, Meta, SiteData } from "./types";

async function fetchJson<T>(name: string): Promise<T> {
  const res = await fetch(`${import.meta.env.BASE_URL}data/${name}`, { cache: "no-cache" });
  if (!res.ok) throw new Error(`${name} を読み込めませんでした（HTTP ${res.status}）`);
  return (await res.json()) as T;
}

export async function loadSiteData(): Promise<SiteData> {
  const [meta, articles] = await Promise.all([
    fetchJson<Meta>("meta.json"),
    fetchJson<{ articles: Article[] }>("articles.json"),
  ]);
  return { meta, articles: articles.articles };
}
