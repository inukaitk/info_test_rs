import { describe, expect, it } from "vitest";
import { h, safeHref } from "../src/dom";
import { EMPTY_FILTERS } from "../src/filters";
import { formatDate } from "../src/format";
import { parseHash } from "../src/router";
import { detailView } from "../src/views/detail";
import { layout } from "../src/views/layout";
import { listView } from "../src/views/list";
import { article, meta, site } from "./fixtures";

const XSS = `<img src=x onerror="window.__xss=1"><script>window.__xss=1</script>`;

function malicious() {
  return article({
    title: XSS,
    source_name: XSS,
    url: "javascript:alert(1)",
    published: { value: "2026-09-10", precision: "day", basis: { method: "html_text", evidence: XSS } },
    summary: { ...article().summary, text: XSS, key_points: [XSS], targets: [XSS], dates: [{ label: XSS, value: "2026-10-01", evidence: XSS }], uncertainties: [XSS] },
    tags: [{ id: "maternal-child-health", name: XSS, origin: "ai", reason: XSS, retired: false }],
    tag_override_reason: XSS,
  });
}

describe("XSS対策", () => {
  it("一覧で取得文字列をHTMLとして解釈しない", () => {
    const el = listView(site([malicious()]), EMPTY_FILTERS, () => {});
    expect(el.querySelector("img, script")).toBeNull();
    expect(el.textContent).toContain("<script>");
  });
  it("詳細で取得文字列をHTMLとして解釈せず、危険なURLをリンクにしない", () => {
    const a = malicious();
    const el = detailView(site([a]), a.id);
    expect(el.querySelector("img, script")).toBeNull();
    expect(el.textContent).toContain("onerror");
    for (const link of el.querySelectorAll("a")) expect(link.getAttribute("href")).not.toMatch(/^javascript:/i);
  });
  it("safeHref は http(s) と画面内リンクだけを通す", () => {
    expect(safeHref("javascript:alert(1)")).toBe("#");
    expect(safeHref("data:text/html,x")).toBe("#");
    expect(safeHref(" JaVaScRiPt:alert(1)")).toBe("#");
    expect(safeHref("https://a.example.org/x")).toBe("https://a.example.org/x");
    expect(safeHref("#/articles/a_0000000000000001")).toBe("#/articles/a_0000000000000001");
  });
  it("イベント属性などは設定できない", () => {
    expect(() => h("a", { onclick: "x" })).toThrow();
  });
});

describe("架空データの表示", () => {
  it("demo では全画面に「架空データ」を出す", () => {
    for (const main of [listView(site([article()]), EMPTY_FILTERS, () => {}), detailView(site([article()]), article().id)]) {
      const page = layout(meta(), "list", main);
      expect(page.querySelector(".demo-banner")?.textContent).toContain("架空データ");
    }
  });
  it("real では出さない", () => {
    const page = layout(meta({ is_demo: false, release_mode: "real" }), "list", h("div"));
    expect(page.querySelector(".demo-banner")).toBeNull();
    expect(page.textContent).not.toContain("架空データ");
  });
});

describe("一覧", () => {
  it("日付・機関・タイトル・概要・タグを表示し、詳細へリンクする", () => {
    const el = listView(site([article()]), EMPTY_FILTERS, () => {});
    const row = el.querySelector("tbody tr")!;
    expect(row.textContent).toContain("2026年9月10日");
    expect(row.textContent).toContain("架空機関A");
    expect(row.textContent).toContain("問診項目が追加");
    expect(row.textContent).toContain("母子保健");
    expect(row.querySelector("a.title")?.getAttribute("href")).toBe("#/articles/a_0000000000000001");
  });
  it("未要約は概要の代わりに状態を出す", () => {
    const a = article({ summary: { ...article().summary, status: "failed_api_error", text: null } });
    expect(listView(site([a]), EMPTY_FILTERS, () => {}).textContent).toContain("未要約（AI APIエラー）");
  });
  it("表示件数の上限", () => {
    const many = Array.from({ length: 5 }, (_, i) => article({ id: `a_000000000000000${i}` }));
    const el = listView(site(many, { page_size: 3 }), EMPTY_FILTERS, () => {});
    expect(el.querySelectorAll("tbody tr")).toHaveLength(3);
    expect(el.textContent).toContain("5件中 5件");
  });
});

describe("記事詳細", () => {
  it("SPEC 4.5 の項目を表示する", () => {
    const a = article({ updated: { value: "2026-09-20", precision: "day", basis: { method: "html_text", evidence: "更新：9月20日" } } });
    const text = detailView(site([a]), a.id).textContent!;
    for (const s of ["出典", "公開日", "更新日", "取得日", "根拠", "概要", "主要な論点", "対象", "確認できた日付", "タグ", "AI処理", "変更履歴", "更新：9月20日"]) {
      expect(text).toContain(s);
    }
  });
  it("AI付与と人の修正を区別する", () => {
    const a = article({
      tags: [
        { id: "maternal-child-health", name: "母子保健", origin: "ai", reason: "健診のため", retired: false },
        { id: "childcare-support", name: "子育て支援", origin: "human", reason: null, retired: false },
      ],
      removed_tags: [{ id: "survey-statistics", name: "調査・統計" }],
      tag_override_reason: "修正理由の例",
    });
    const el = detailView(site([a]), a.id);
    expect(el.querySelector(".tag-ai")?.textContent).toContain("AI");
    expect(el.querySelector(".tag-human")?.textContent).toContain("人が追加");
    expect(el.querySelector(".tag-removed")?.textContent).toContain("調査・統計");
    expect(el.textContent).toContain("修正理由の例");
    expect(el.textContent).toContain("健診のため");
  });
  it("日付不明・本文未取得・未要約をそのまま示す", () => {
    const a = article({
      published: { value: null, precision: "unknown", basis: null },
      content_status: "failed", content_error: "HTTP 404",
      summary: { ...article().summary, status: "skipped_no_content", text: null, key_points: null, targets: null, dates: null, uncertainties: null },
      tags: [],
    });
    const text = detailView(site([a]), a.id).textContent!;
    expect(text).toContain("日付不明");
    expect(text).toContain("HTTP 404");
    expect(text).toContain("未要約（本文を取得できないため）");
    expect(text).toContain("AI未処理のためなし");
  });
  it("存在しない記事", () => {
    expect(detailView(site([]), "a_ffffffffffffffff").textContent).toContain("見つかりません");
  });
});

describe("ルーティングと表示形式", () => {
  it("hash を解釈する", () => {
    expect(parseHash("").name).toBe("list");
    expect(parseHash("#/?tag=x")).toEqual({ name: "list", filters: { ...EMPTY_FILTERS, tag: "x" } });
    expect(parseHash("#/articles/a_0123456789abcdef")).toEqual({ name: "detail", id: "a_0123456789abcdef" });
    expect(parseHash("#/articles/<script>").name).toBe("notfound");
  });
  it("精度に応じた日付", () => {
    expect(formatDate({ value: "2026-09", precision: "month", basis: null })).toBe("2026年9月（日不明）");
    expect(formatDate({ value: null, precision: "unknown", basis: null })).toBe("日付不明");
  });
});
