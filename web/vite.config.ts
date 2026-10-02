import { defineConfig } from "vitest/config";

declare const process: { env: Record<string, string | undefined> };

// GitHub Pages ではリポジトリ名のサブパス（https://<user>.github.io/<repo>/）で配信される。
// 既定はリポジトリ名 info_test_rs（仮）。変えるときは環境変数 BASE_PATH で指定する（例 BASE_PATH=/other/）。
// 1ファイル版（npm run build:standalone）は --base ./ で相対パスにして作る。
// 画面の切り替えは hash（#/wiki/... など）で行うため、サブパスでも直リンクが 404 にならない。
const base = process.env.BASE_PATH ?? "/info_test_rs/";

export default defineConfig({
  base,
  server: { port: 5173, strictPort: true },
  preview: { port: 4173, strictPort: true },
  test: { environment: "jsdom", include: ["tests/**/*.test.ts"] },
});
