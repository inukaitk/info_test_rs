import { describe, expect, it } from "vitest";
import { embedJson } from "../scripts/build-standalone.mjs";
import { EMBEDDED_DATA_ID, readEmbeddedData } from "../src/data";
import { article, meta, status } from "./fixtures";

describe("1ファイル版：データの埋め込み", () => {
  it("</script> などで <script> から抜け出せない", () => {
    const text = embedJson({ title: "</script><script>alert(1)</script>& " });
    expect(text).not.toContain("<");
    expect(text).not.toContain(">");
    expect(JSON.parse(text).title).toBe("</script><script>alert(1)</script>& ");
  });

  it("埋め込んだデータを読み込む", () => {
    const doc = document.implementation.createHTMLDocument("t");
    const script = doc.createElement("script");
    script.type = "application/json";
    script.id = EMBEDDED_DATA_ID;
    const title = "【架空】</script><img src=x onerror=alert(1)>";
    script.textContent = embedJson({ meta: meta(), articles: { articles: [article({ title })] }, status: status(), reports: { weeks: [] } });
    doc.body.appendChild(script);
    const data = readEmbeddedData(doc)!;
    expect(data.meta.is_demo).toBe(true);
    expect(data.articles[0].title).toBe(title);
    expect(data.status.sources).toHaveLength(1);
    expect(data.reports).toEqual([]);
    expect(doc.querySelector("img")).toBeNull();
  });

  it("埋め込みがなければ null（通常版は public/data から取得）", () => {
    expect(readEmbeddedData(document.implementation.createHTMLDocument("t"))).toBeNull();
  });
});
