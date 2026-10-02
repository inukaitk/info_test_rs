import { describe, expect, it } from "vitest";
import { applyFilters, countDateUnknownExcluded, dateRange, EMPTY_FILTERS, filtersToQuery, parseFilters } from "../src/filters";
import { article } from "./fixtures";

const a1 = article({ id: "a_0000000000000001" });
const a2 = article({
  id: "a_0000000000000002", source_id: "demo-b", source_name: "架空機関B（デモ）", title: "【架空】保育の交付金",
  published: { value: "2026-09-30", precision: "day", basis: { method: "html_text", evidence: "x" } },
  summary: { ...a1.summary, text: "交付金の公募" },
  tags: [{ id: "childcare-support", name: "子育て支援", origin: "human", reason: null, retired: false }],
});
const unknown = article({ id: "a_0000000000000003", title: "【架空】日付のない研修", published: { value: null, precision: "unknown", basis: null } });
const month = article({ id: "a_0000000000000004", title: "【架空】月だけ", published: { value: "2026-10", precision: "month", basis: { method: "listing_text", evidence: "2026年10月" } } });
const all = [a1, a2, unknown, month];
const ids = (xs: { id: string }[]) => xs.map((x) => x.id.slice(-1));

describe("絞り込み", () => {
  it("条件なしなら全件", () => expect(applyFilters(all, EMPTY_FILTERS)).toHaveLength(4));
  it("タグ（AI・人の追加どちらでも）", () => {
    expect(ids(applyFilters(all, { ...EMPTY_FILTERS, tag: "childcare-support" }))).toEqual(["2"]);
    expect(ids(applyFilters(all, { ...EMPTY_FILTERS, tag: "maternal-child-health" }))).toEqual(["1", "3", "4"]);
  });
  it("機関", () => expect(ids(applyFilters(all, { ...EMPTY_FILTERS, source: "demo-b" }))).toEqual(["2"]));
  it("期間は両端を含む", () => {
    expect(ids(applyFilters(all, { ...EMPTY_FILTERS, from: "2026-09-10", to: "2026-09-30" }))).toEqual(["1", "2"]);
    expect(ids(applyFilters(all, { ...EMPTY_FILTERS, from: "2026-09-11" }))).toEqual(["2", "4"]);
    expect(ids(applyFilters(all, { ...EMPTY_FILTERS, to: "2026-09-10" }))).toEqual(["1"]);
  });
  it("期間指定時に日付不明を混ぜず、件数を別に数える", () => {
    const f = { ...EMPTY_FILTERS, from: "2026-01-01", to: "2026-12-31" };
    expect(ids(applyFilters(all, f))).not.toContain("3");
    expect(countDateUnknownExcluded(all, f)).toBe(1);
    expect(countDateUnknownExcluded(all, EMPTY_FILTERS)).toBe(0);
  });
  it("月までの日付は期間と重なれば含める", () => {
    expect(ids(applyFilters(all, { ...EMPTY_FILTERS, from: "2026-10-15", to: "2026-10-20" }))).toEqual(["4"]);
  });
});

describe("文字検索", () => {
  it("タイトル・概要・機関名・タグ名を対象に、全角半角と大小文字を区別しない", () => {
    expect(ids(applyFilters(all, { ...EMPTY_FILTERS, q: "交付金" }))).toEqual(["2"]);
    expect(ids(applyFilters(all, { ...EMPTY_FILTERS, q: "機関Ｂ" }))).toEqual(["2"]);
    expect(ids(applyFilters(all, { ...EMPTY_FILTERS, q: "子育て支援" }))).toEqual(["2"]);
  });
  it("空白区切りはすべてを含むもの", () => {
    expect(ids(applyFilters(all, { ...EMPTY_FILTERS, q: "架空 研修" }))).toEqual(["3"]);
    expect(applyFilters(all, { ...EMPTY_FILTERS, q: "架空 存在しない語" })).toEqual([]);
  });
});

describe("URLとの変換", () => {
  it("往復で同じ条件になる", () => {
    const f = { q: "健診", tag: "a", source: "b", from: "2026-09-01", to: "2026-09-30" };
    expect(parseFilters(new URLSearchParams(filtersToQuery(f).slice(1)))).toEqual(f);
  });
  it("不正な日付は無視する", () => {
    expect(parseFilters(new URLSearchParams("from=<script>&to=2026/09/01")).from).toBe("");
  });
  it("dateRange", () => {
    expect(dateRange("2026-02")).toEqual(["2026-02-01", "2026-02-28"]);
    expect(dateRange("2026")).toEqual(["2026-01-01", "2026-12-31"]);
    expect(dateRange(null)).toBeNull();
  });
});
