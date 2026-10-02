// 画面用JSONの読み込み。
// 通常は public/data/ から取得する。1ファイル版（viewer/*.html）では HTML に埋め込んだデータを使う。
import type { Article, Meta, SiteData } from "./types";

export const EMBEDDED_DATA_ID = "embedded-site-data";

async function fetchJson<T>(name: string): Promise<T> {
  const res = await fetch(`${import.meta.env.BASE_URL}data/${name}`, { cache: "no-cache" });
  if (!res.ok) throw new Error(`${name} を読み込めませんでした（HTTP ${res.status}）`);
  return (await res.json()) as T;
}

/** HTML に埋め込まれたデータ（<script type="application/json">）があれば返す。 */
export function readEmbeddedData(doc: Document = document): SiteData | null {
  const el = doc.getElementById(EMBEDDED_DATA_ID);
  if (!el || el.getAttribute("type") !== "application/json") return null;
  const parsed = JSON.parse(el.textContent ?? "") as { meta: Meta; articles: { articles: Article[] } };
  return { meta: parsed.meta, articles: parsed.articles.articles };
}

export async function loadSiteData(): Promise<SiteData> {
  const embedded = readEmbeddedData();
  if (embedded) return embedded;
  const [meta, articles] = await Promise.all([
    fetchJson<Meta>("meta.json"),
    fetchJson<{ articles: Article[] }>("articles.json"),
  ]);
  return { meta, articles: articles.articles };
}
