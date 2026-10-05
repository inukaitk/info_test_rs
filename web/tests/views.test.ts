import { describe, expect, it } from "vitest";
import { h, safeHref } from "../src/dom";
import { EMPTY_FILTERS } from "../src/filters";
import { formatDate } from "../src/format";
import { parseHash } from "../src/router";
import { detailView } from "../src/views/detail";
import { layout } from "../src/views/layout";
import { latestView } from "../src/views/latest";
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
      const page = layout(meta(), "search", main);
      expect(page.querySelector(".demo-banner")?.textContent).toContain("架空データ");
    }
  });
  it("real では出さない", () => {
    const page = layout(meta({ is_demo: false, release_mode: "real" }), "latest", h("div"));
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
    const a2 = { ...a, tags: [] };
    const text = listView(site([a2]), EMPTY_FILTERS, () => {}).textContent!;
    expect(text).toContain("未要約（AI APIエラー）");
    expect(text).toContain("AI未処理");
    expect(text).not.toContain("タグなし");
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
    expect(parseHash("")).toEqual({ name: "latest" });
    expect(parseHash("#/")).toEqual({ name: "latest" });
    expect(parseHash("#/search")).toEqual({ name: "search", filters: EMPTY_FILTERS });
    expect(parseHash("#/search?tag=x")).toEqual({ name: "search", filters: { ...EMPTY_FILTERS, tag: "x" } });
    expect(parseHash("#/?tag=x")).toEqual({ name: "search", filters: { ...EMPTY_FILTERS, tag: "x" } });
    expect(parseHash("#/articles/a_0123456789abcdef")).toEqual({ name: "detail", id: "a_0123456789abcdef" });
    expect(parseHash("#/articles/<script>").name).toBe("notfound");
  });
  it("精度に応じた日付", () => {
    expect(formatDate({ value: "2026-09", precision: "month", basis: null })).toBe("2026年9月（日不明）");
    expect(formatDate({ value: null, precision: "unknown", basis: null })).toBe("日付不明");
  });
});

describe("最新情報（直近の公開日）", () => {
  const pub = (id: string, published: string | null, title: string, firstSeen = "2026-09-28T08:00:00+09:00") =>
    article({ id, first_seen_at: firstSeen, title,
      published: published ? { value: published, precision: "day", basis: null } : { value: null, precision: "unknown", basis: null } });
  const articles = [
    pub("a_0000000000000001", "2026-09-28", "【架空】当日に公開"),
    pub("a_0000000000000002", "2026-09-22", "【架空】7日前（範囲の初日）"),
    pub("a_0000000000000003", "2026-09-21", "【架空】8日前（範囲外）"),
    pub("a_0000000000000004", null, "【架空】日付不明だが最近見つけた", "2026-09-27T08:00:00+09:00"),
    pub("a_0000000000000005", null, "【架空】日付不明で古い取得", "2026-09-10T08:00:00+09:00"),
    pub("a_0000000000000006", "2026-08-01", "【架空】古い公開日だが今週初めて取得", "2026-09-28T08:00:00+09:00"),
  ];

  it("最終収集日を含む直近7日間に公開された記事だけを出す（取得日ではなく公開日で判定）", () => {
    const el = latestView(site(articles));
    const text = el.textContent!;
    expect(text).toContain("当日に公開");
    expect(text).toContain("7日前（範囲の初日）");
    expect(text).not.toContain("8日前（範囲外）");
    expect(text).not.toContain("古い公開日だが今週初めて取得");
    expect(text).toContain("日付不明だが最近見つけた");
    expect(text).not.toContain("日付不明で古い取得");
    expect(text).toContain("2026年9月22日〜2026年9月28日");
    expect(text).toContain("3件");
    expect(el.querySelector('a[href="#/search"]')).not.toBeNull();
  });

  it("日数は設定で変えられる", () => {
    const text = latestView(site(articles, { latest_days: 1 })).textContent!;
    expect(text).toContain("当日に公開");
    expect(text).not.toContain("7日前（範囲の初日）");
  });

  it("収集データがなければその旨を出す", () => {
    expect(latestView(site([], { data_as_of: null })).textContent).toContain("まだ収集したデータがありません");
  });

  it("タグのリンクは「記事を探す」の絞り込みを開く", () => {
    const el = latestView(site(articles));
    expect(el.querySelector("a.tag")?.getAttribute("href")).toBe("#/search?tag=maternal-child-health");
  });
});

describe("添付資料", () => {
  it("資料ごとの状態を出し、危険なURLはリンクにしない", () => {
    const a = article({
      attachments: [
        { title: "【架空】概要（PDF）", url: "https://a.example.org/a.pdf", status: "ok", note: null, pages: 4 },
        { title: "【架空】スキャン（PDF）", url: "https://a.example.org/s.pdf", status: "unsupported", note: "画像PDFのため", pages: 1 },
        { title: XSS, url: "javascript:alert(1)", status: "skipped", note: "上限超過", pages: null },
      ],
      versions: [
        { version: 1, fetched_at: "2026-09-11T08:00:00+09:00", change_type: "new", extraction_status: "ok" },
        { version: 2, fetched_at: "2026-09-12T08:00:00+09:00", change_type: "extraction_changed", extraction_status: "ok" },
      ],
      latest_version: 2,
    });
    const el = detailView(site([a]), a.id);
    const text = el.textContent!;
    expect(text).toContain("添付資料");
    expect(text).toContain("読み取り済み（4ページ）");
    expect(text).toContain("読み取れない形式");
    expect(text).toContain("抽出方法の変更（原文の変更ではない）");
    expect(el.querySelector("img")).toBeNull();
    for (const link of el.querySelectorAll("a")) expect(link.getAttribute("href")).not.toMatch(/^javascript:/i);
  });

  it("添付がなければ欄を出さない", () => {
    expect(detailView(site([article()]), article().id).textContent).not.toContain("添付資料");
  });
});


describe("記事を探す：ページ送り", () => {
  const many = Array.from({ length: 120 }, (_, i) => {
    const n = i + 1;
    return article({
      id: `a_${String(n).padStart(16, "0")}`, title: `【架空】記事${String(n).padStart(3, "0")}`,
      published: { value: `2026-${n <= 60 ? "09" : "10"}-${String((n % 28) + 1).padStart(2, "0")}`, precision: "day", basis: null },
    });
  });
  const titles = (el: HTMLElement) => [...el.querySelectorAll("a.title")].map((a) => a.textContent!);

  it("50件ごとに表示し、すべて保存の案内と件数の範囲を出す", () => {
    const first = listView(site(many), EMPTY_FILTERS, () => {});
    expect(titles(first)).toHaveLength(50);
    expect(first.textContent).toContain("120件中 120件（新しい順に1〜50件目を表示。保存はすべて）");
    const third = listView(site(many), { ...EMPTY_FILTERS, page: 3 }, () => {});
    expect(titles(third)).toHaveLength(20);
    expect(third.textContent).toContain("101〜120件目");
  });

  it("どのページでも、すべての記事がちょうど1回ずつ見え、抜けも重なりもない", () => {
    const seen: string[] = [];
    for (const page of [1, 2, 3]) seen.push(...titles(listView(site(many), { ...EMPTY_FILTERS, page }, () => {})));
    expect(new Set(seen).size).toBe(120);
    expect(seen).toHaveLength(120);
  });

  it("ページ送りのリンクは、絞り込み条件を引き継いでページだけを変える。上下に出し、現在のページは印を付ける", () => {
    const el = listView(site(many), { ...EMPTY_FILTERS, source: "demo-a", page: 2 }, () => {});
    expect(el.querySelectorAll("nav.pager")).toHaveLength(2);
    const nav = el.querySelector("nav.pager")!;
    expect(nav.querySelector('[aria-current="page"]')?.textContent).toBe("2");
    const hrefs = [...nav.querySelectorAll("a.pager-item")].map((a) => a.getAttribute("href"));
    expect(hrefs).toContain("#/search?source=demo-a");
    expect(hrefs).toContain("#/search?source=demo-a&page=3");
    expect(nav.textContent).toContain("2 / 3ページ");
  });

  it("最初のページでは「前へ」、最後のページでは「次へ」を押せない", () => {
    const first = listView(site(many), EMPTY_FILTERS, () => {}).querySelector("nav.pager")!;
    expect(first.querySelector("span.disabled")?.textContent).toBe("前へ");
    const last = listView(site(many), { ...EMPTY_FILTERS, page: 3 }, () => {}).querySelector("nav.pager")!;
    expect(last.querySelector("span.disabled")?.textContent).toBe("次へ");
    expect(last.querySelector('a[aria-label="2ページ目へ（前へ）"]')).not.toBeNull();
  });

  it("範囲外のページ番号は最後のページに収める。1ページに収まるときはページ送りを出さない", () => {
    const beyond = listView(site(many), { ...EMPTY_FILTERS, page: 99 }, () => {});
    expect(titles(beyond)).toHaveLength(20);
    const few = listView(site(many.slice(0, 30)), EMPTY_FILTERS, () => {});
    expect(few.querySelector("nav.pager")).toBeNull();
    expect(few.textContent).not.toContain("件目を表示");
  });
});
