import { describe, expect, it } from "vitest";
import { articlesToCsv, csvCell } from "../src/download";
import { parseHash } from "../src/router";
import type { WeeklyReport } from "../src/types";
import { detailView } from "../src/views/detail";
import { latestView } from "../src/views/latest";
import { layout } from "../src/views/layout";
import { reportView } from "../src/views/report";
import { statusView, statusWarnings } from "../src/views/status";
import { tagChip } from "../src/views/tags";
import { wikiIndexView, wikiTagView } from "../src/views/wiki";
import { article, meta, site, status } from "./fixtures";

const NOW = new Date("2026-09-30T12:00:00+09:00");
const XSS = `<img src=x onerror="window.__xss=1">`;

describe("Wiki", () => {
  const articles = [
    article({ id: "a_0000000000000001", title: "【架空】9月の記事", published: { value: "2026-09-10", precision: "day", basis: null } }),
    article({ id: "a_0000000000000002", title: "【架空】8月の記事", published: { value: "2026-08-20", precision: "day", basis: null } }),
    article({ id: "a_0000000000000003", title: "【架空】日付不明の記事", published: { value: null, precision: "unknown", basis: null } }),
    article({
      id: "a_0000000000000004", title: "【架空】人が追加した記事",
      tags: [{ id: "childcare-support", name: "子育て支援", origin: "human", reason: null, retired: false }],
    }),
  ];

  it("タグの一覧に説明と件数を出す", () => {
    const text = wikiIndexView(site(articles)).textContent!;
    expect(text).toContain("母子保健");
    expect(text).toContain("3件");
    expect(text).toContain("子育て支援");
  });

  it("タグのページは時系列（月ごと、新しい順）で、日付不明は別枠", () => {
    const el = wikiTagView(site(articles), "maternal-child-health");
    const headings = [...el.querySelectorAll("h2")].map((x) => x.textContent);
    expect(headings).toEqual(["2026年9月", "2026年8月", "日付不明"]);
    expect(el.textContent).toContain("9月の記事");
    expect(el.textContent).not.toContain("人が追加した記事");
    expect(el.querySelector('a[href="#/articles/a_0000000000000001"]')).not.toBeNull();
  });

  it("タグの由来（AI・人）を示す", () => {
    const el = wikiTagView(site(articles), "childcare-support");
    expect(el.querySelector(".origin-human")?.textContent).toBe("人が追加");
  });

  it("存在しないタグ", () => {
    expect(wikiTagView(site(articles), "nothing").textContent).toContain("見つかりません");
  });

  it("タイトルをHTMLとして解釈しない", () => {
    const el = wikiTagView(site([article({ title: XSS })]), "maternal-child-health");
    expect(el.querySelector("img")).toBeNull();
  });
});

function week(overrides: Partial<WeeklyReport> = {}): WeeklyReport {
  return {
    id: "2026-09-22_2026-09-28", from: "2026-09-22", to: "2026-09-28",
    counts: { new: 1, changed: 0, date_unknown: 0, unsummarized: 0, untagged: 0, runs: 1 },
    new: [{ id: "a_0000000000000001", title: XSS, url: "https://a.example.org/1", source_name: "架空機関A（デモ）", published: "2026-09-25",
      first_seen_at: "2026-09-28T08:00:00+09:00", version: null, tags: ["母子保健"], summary_status: "success" }],
    changed: [],
    tag_counts: [{ id: "maternal-child-health", name: "母子保健", count: 1 }],
    sources: [
      { id: "demo-a", name: "架空機関A（デモ）", runs: [{ run_id: "r", started_at: "2026-09-28T08:00:00+09:00", status: "failed", new: 0, changed: 0, error: "タイムアウト" }] },
      { id: "demo-b", name: "架空機関B（デモ）", runs: [] },
    ],
    markdown: "# 週次レポート",
    ...overrides,
  };
}

describe("週次レポート", () => {
  it("新規・変更・タグ別件数・情報源別の取得状況を出す", () => {
    const el = reportView(site([], {}, { reports: [week()] }), null, () => {});
    const text = el.textContent!;
    for (const s of ["新規（1件）", "変更（0件）", "タグ別件数", "情報源別の取得状況", "タイムアウト", "期間内の実行なし", "Markdownで保存"]) {
      expect(text).toContain(s);
    }
    expect(el.querySelector("img")).toBeNull();
  });

  it("公開日が日まで分からない記事は数えず、数えていない件数と、数えない旨を出す", () => {
    const w = week();
    const data = site([], {}, { reports: [{ ...w, counts: { ...w.counts, date_unknown: 2 } }] });
    const text = reportView(data, null, () => {}).textContent!;
    expect(text).toContain("公開日が日まで分からない記事は数えない");
    expect(text).toContain("公開日不明のため数えていない記事（この期間に見つけたもの）2件");
    expect(text).not.toContain("うち日付不明");
  });

  it("期間を選べる（指定がなければ最新の週）", () => {
    const older = week({ id: "2026-09-15_2026-09-21", from: "2026-09-15", to: "2026-09-21" });
    const data = site([], {}, { reports: [week(), older] });
    expect((reportView(data, null, () => {}).querySelector("select") as HTMLSelectElement).value).toBe("2026-09-22_2026-09-28");
    expect((reportView(data, "2026-09-15_2026-09-21", () => {}).querySelector("select") as HTMLSelectElement).value).toBe("2026-09-15_2026-09-21");
  });

  it("データがなければその旨", () => {
    expect(reportView(site([]), null, () => {}).textContent).toContain("まだ収集したデータがありません");
  });
});

describe("取得状況", () => {
  it("最終実行・最終全情報源成功・件数を出す", () => {
    const text = statusView(site([]), NOW).textContent!;
    for (const s of ["最終実行", "最終全情報源成功", "日付不明", "未要約", "情報源ごとの状況", "実行履歴", "問題は見つかっていません"]) {
      expect(text).toContain(s);
    }
  });

  it("データが古いと警告する", () => {
    const later = new Date("2026-10-10T12:00:00+09:00");
    expect(statusWarnings(site([]), later).join()).toContain("データが古くなっています");
    expect(statusWarnings(site([]), NOW)).toEqual([]);
  });

  it("失敗が続く情報源と失敗理由を示す", () => {
    const st = status();
    st.sources[0] = { ...st.sources[0], last_attempt_status: "failed", consecutive_failures: 2,
      last_run: { ...st.sources[0].last_run!, status: "failed", error: "一覧ページがタイムアウト" } };
    const data = site([], {}, { status: st });
    expect(statusWarnings(data, NOW).join()).toContain("2回続けて取得に失敗");
    const el = statusView(data, NOW);
    expect(el.textContent).toContain("一覧ページがタイムアウト");
    expect(el.querySelector(".row-failed")).not.toBeNull();
  });

  it("前回の収集で出た警告（抽出0件など）も上部に出す", () => {
    const st = status();
    st.sources[0] = { ...st.sources[0], last_run: { ...st.sources[0].last_run!, warnings: ["一覧から記事を1件も抽出できませんでした"] } };
    expect(statusWarnings(site([], {}, { status: st }), NOW).join()).toContain("1件も抽出できませんでした");
  });

  it("取得が完了していない記事（添付PDFが大きい等）は「問題なし」とせず、理由を示す", () => {
    const st = status();
    st.sources[0] = { ...st.sources[0], retry_count: 1, retry_items: [{
      article_id: "a_0123456789abcdef", title: "【架空】会議資料", url: "https://a.example.org/x", stage: "fetch", kind: "size_limit",
      reason: "添付PDFの取得に失敗：資料（PDF／10.5MB）：サイズ上限（10485760バイト）を超えました", attempts: 1,
      first_failed_at: "2026-09-28T08:00:00+09:00" }] };
    const data = site([], {}, { status: st });
    expect(statusWarnings(data, NOW).join()).toContain("ファイルサイズが上限を超える添付資料があり、取得が完了していません");
    const el = statusView(data, NOW);
    expect(el.textContent).not.toContain("問題は見つかっていません");
    expect(el.textContent).toContain("取得が完了していない記事");
    expect(el.querySelector('a[href="#/articles/a_0123456789abcdef"]')?.textContent).toBe("【架空】会議資料");
  });

  it("再試行待ちがなければ従来どおり「問題は見つかっていません」", () => {
    expect(statusView(site([]), NOW).textContent).toContain("問題は見つかっていません");
    expect(statusView(site([]), NOW).textContent).not.toContain("取得が完了していない記事");
  });

  it("一度も成功していない情報源・未実行", () => {
    const st = status({ last_run_at: null, last_run_status: null, last_full_success_at: null });
    st.sources[0] = { ...st.sources[0], last_success_at: null, last_attempt_status: null, last_run: null };
    const warnings = statusWarnings(site([], {}, { status: st }), NOW).join();
    expect(warnings).toContain("まだ収集を実行していません");
    expect(warnings).toContain("一度も取得に成功していません");
  });
});

describe("修正依頼リンク", () => {
  it("未設定なら「未設定」", () => {
    const page = layout(meta(), "latest", latestView(site([]), NOW));
    expect(page.querySelector(".correction")?.textContent).toBe("修正依頼：未設定");
  });
  it("設定されていればリンク（https のみ）", () => {
    const page = layout(meta({ correction_request_url: "https://forms.example.com/r/abc" }), "latest", document.createElement("div"));
    expect(page.querySelector(".correction a")?.getAttribute("href")).toBe("https://forms.example.com/r/abc");
    const bad = layout(meta({ correction_request_url: "javascript:alert(1)" }), "latest", document.createElement("div"));
    expect(bad.querySelector(".correction a")?.getAttribute("href")).toBe("#");
  });
  it("トップ（最新情報）にも出す", () => {
    expect(latestView(site([]), NOW).querySelector(".correction")).not.toBeNull();
  });
});

describe("CSV", () => {
  it("式として実行されないようにし、区切り文字を含む値を囲む", () => {
    expect(csvCell("=HYPERLINK(\"x\")")).toBe("\"'=HYPERLINK(\"\"x\"\")\"");
    expect(csvCell("+1")).toBe("'+1");
    expect(csvCell("@a")).toBe("'@a");
    expect(csvCell("a,b")).toBe('"a,b"');
    expect(csvCell("改行\nあり")).toBe('"改行\nあり"');
    expect(csvCell(null)).toBe("");
  });

  it("AIタグと人の修正を別の列に出し、BOM付き", () => {
    const a = article({
      tags: [
        { id: "maternal-child-health", name: "母子保健", origin: "ai", reason: "r", retired: false },
        { id: "childcare-support", name: "子育て支援", origin: "human", reason: null, retired: false },
      ],
      removed_tags: [{ id: "survey-statistics", name: "調査・統計" }],
    });
    const csv = articlesToCsv([a]);
    expect(csv.charCodeAt(0)).toBe(0xfeff);
    const [header, row] = csv.slice(1).trim().split("\r\n");
    expect(header.split(",")).toContain("人が追加したタグ");
    expect(row).toContain("母子保健,,,子育て支援,調査・統計"); // AIタグ、設定で付けたタグ（なし）、ルールで付けたタグ（なし）、人が追加、人が除外
  });
});

describe("情報源の設定で付けるタグ（ベンダ動向）", () => {
  const vendor = { id: "vendor-trend", name: "ベンダ動向", origin: "source" as const, reason: "情報源の設定：架空社の記事すべてに付けています", retired: false };

  it("チップは「設定」と表示し、AI・人の追加と区別する。説明は title に出す", () => {
    const chip = tagChip(vendor);
    expect(chip.textContent).toBe("設定ベンダ動向");
    expect(chip.className).toContain("tag-source");
    expect(chip.getAttribute("title")).toContain("情報源の設定で付与");
    expect(tagChip({ ...vendor, origin: "ai" }).textContent).toBe("AIベンダ動向");
    expect(tagChip({ ...vendor, origin: "human" }).textContent).toBe("人が追加ベンダ動向");
  });

  it("記事詳細に「情報源の設定で付与」の欄を出す（AIが未処理でも）。設定のタグがない記事では欄を出さない", () => {
    const withTag = article({ summary: { ...article().summary, status: "not_processed", text: null }, tags: [vendor] });
    const text = detailView(site([withTag]), withTag.id).textContent!;
    expect(text).toContain("情報源の設定で付与");
    expect(text).toContain("架空社の記事すべてに付けています");
    expect(text).toContain("AI未処理のためなし");
    expect(detailView(site([article()]), article().id).textContent).not.toContain("情報源の設定で付与");
  });

  it("ルール（キーワード一致）のタグは「一致」と表示し、記事詳細に「ルールで付与」の欄とその理由を出す", () => {
    const rule = { ...vendor, origin: "rule" as const, reason: "ルール（キーワード一致）：「ミラボ」（本文）が見つかりました" };
    const chip = tagChip(rule);
    expect(chip.textContent).toBe("一致ベンダ動向");
    expect(chip.className).toContain("tag-rule");
    expect(chip.getAttribute("title")).toContain("ルール（キーワード一致）で付与");
    const a = article({ tags: [rule] });
    const text = detailView(site([a]), a.id).textContent!;
    expect(text).toContain("ルールで付与");
    expect(text).toContain("「ミラボ」（本文）が見つかりました");
    expect(text).not.toContain("情報源の設定で付与");
  });

  it("CSVには「設定で付けたタグ」の列を別に出す", () => {
    const csv = articlesToCsv([article({ tags: [vendor, { id: "maternal-child-health", name: "母子保健", origin: "ai", reason: "r", retired: false },
      { id: "childcare-support", name: "子育て支援", origin: "rule", reason: "r", retired: false }] })]);
    const [header, row] = csv.slice(1).trim().split("\r\n");
    const cols = header.split(",");
    const cells = row.split(",");
    expect(cols).toContain("設定で付けたタグ");
    expect(cells[cols.indexOf("AIタグ")]).toBe("母子保健");
    expect(cells[cols.indexOf("設定で付けたタグ")]).toBe("ベンダ動向");
    expect(cells[cols.indexOf("ルールで付けたタグ")]).toBe("子育て支援");
  });
});

describe("ルーティング（直リンク）", () => {
  it("各画面のURLを解釈する", () => {
    expect(parseHash("#/wiki")).toEqual({ name: "wiki" });
    expect(parseHash("#/wiki/maternal-child-health")).toEqual({ name: "wikiTag", tag: "maternal-child-health" });
    expect(parseHash("#/reports")).toEqual({ name: "reports", week: null });
    expect(parseHash("#/reports/2026-09-22_2026-09-28")).toEqual({ name: "reports", week: "2026-09-22_2026-09-28" });
    expect(parseHash("#/status")).toEqual({ name: "status" });
    expect(parseHash("#/wiki/<x>").name).toBe("notfound");
  });
});

describe("情報源", () => {
  it("収集中と候補を分け、URL・取得方式・添付PDF・制約を出す", async () => {
    const { sourcesView } = await import("../src/views/sources");
    const st = status();
    st.sources.push({ ...st.sources[0], id: "demo-b", name: "架空機関B（候補）", enabled: false, attachments: null,
      notes: "規約の確認が必要", entry_url: "javascript:alert(1)" });
    const el = sourcesView(site([], {}, { status: st }));
    const text = el.textContent!;
    expect(text).toContain("収集中（1件）");
    expect(text).toContain("候補（未採用、1件）");
    expect(text).toContain("添付PDFも読む（1記事3件・30ページまで、「座席」を含む資料は除外）");
    expect(text).toContain("添付PDFは読まない");
    expect(text).toContain("規約の確認が必要");
    expect(el.querySelector(".candidate")?.textContent).not.toContain("取得状況");
    for (const a of el.querySelectorAll("a")) expect(a.getAttribute("href")).not.toMatch(/^javascript:/i);
    expect(parseHash("#/sources")).toEqual({ name: "sources" });
  });

  it("メニューに情報源がある", () => {
    const page = layout(meta(), "sources", document.createElement("div"));
    expect(page.querySelector('nav a[aria-current="page"]')?.textContent).toBe("情報源");
  });
});
