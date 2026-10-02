// ビルド結果（dist/）と画面用JSON（public/data/）から、1ファイルで開ける HTML を作る。
// できたファイルはダブルクリックでブラウザに開ける（Node.js やサーバーは不要）。
//
// 使い方（web フォルダで）: npm run build:standalone
//   出力: ../viewer/info_viewer.html
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const webDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const distDir = join(webDir, "dist-standalone");
// 確認用に別のデータ・出力先を使うとき：DATA_DIR=... OUT_FILE=... npm run build:standalone
const dataDir = process.env.DATA_DIR ? resolve(process.env.DATA_DIR) : join(webDir, "public", "data");
const outFile = process.env.OUT_FILE ? resolve(process.env.OUT_FILE) : resolve(webDir, "..", "viewer", "info_viewer.html");

const read = (p) => readFileSync(p, "utf-8");
const sha256 = (text) => `'sha256-${createHash("sha256").update(text, "utf-8").digest("base64")}'`;

/** JSON を <script> 内に安全に埋め込む（</script> 等で抜け出せないよう < > & をエスケープ）。 */
export function embedJson(value) {
  return JSON.stringify(value)
    .replace(/</g, "\\u003c")
    .replace(/>/g, "\\u003e")
    .replace(/&/g, "\\u0026")
    .replace(new RegExp(String.fromCharCode(0x2028), "g"), "\\u2028")
    .replace(new RegExp(String.fromCharCode(0x2029), "g"), "\\u2029");
}

function main() {
  let html = read(join(distDir, "index.html"));

  const cssMatch = html.match(/<link rel="stylesheet"[^>]*href="\.\/(assets\/[^"]+\.css)"[^>]*>/);
  const jsMatch = html.match(/<script type="module"[^>]*src="\.\/(assets\/[^"]+\.js)"[^>]*><\/script>/);
  if (!cssMatch || !jsMatch) throw new Error("dist/index.html から CSS/JS を見つけられません。npm run build:standalone で実行してください");

  const css = read(join(distDir, cssMatch[1]));
  const js = read(join(distDir, jsMatch[1]));
  if (js.includes("</script")) throw new Error("JS に </script が含まれるため埋め込めません");

  const data = {
    meta: JSON.parse(read(join(dataDir, "meta.json"))),
    articles: JSON.parse(read(join(dataDir, "articles.json"))),
    status: JSON.parse(read(join(dataDir, "status.json"))),
    reports: JSON.parse(read(join(dataDir, "reports.json"))),
  };

  // インラインのスクリプトとスタイルは、ハッシュで指定したものだけを許可する（それ以外は実行しない）
  const csp = [
    "default-src 'none'",
    `script-src ${sha256(js)}`,
    `style-src ${sha256(css)}`,
    "img-src data:",
    "connect-src 'none'",
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'none'",
  ].join("; ");

  html = html
    .replace(/<meta http-equiv="Content-Security-Policy"[\s\S]*?\/>/, `<meta http-equiv="Content-Security-Policy" content="${csp}" />`)
    .replace(cssMatch[0], () => `<style>${css}</style>`)
    .replace(jsMatch[0], () => "")
    .replace(
      "</body>",
      () =>
        `<script type="application/json" id="embedded-site-data">${embedJson(data)}</script>\n` +
        `<script type="module">${js}</script>\n</body>`,
    );

  mkdirSync(dirname(outFile), { recursive: true });
  writeFileSync(outFile, html, "utf-8");
  const kb = Math.round(Buffer.byteLength(html) / 1024);
  console.log(`OK: ${outFile} を作成しました（${kb} KB、記事 ${data.articles.articles.length} 件、${data.meta.is_demo ? "架空データ" : "実データ"}）`);
}

// テストから embedJson だけを読み込めるよう、直接実行されたときだけ作成する
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) main();
