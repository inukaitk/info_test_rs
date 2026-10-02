import { defineConfig } from "vitest/config";

export default defineConfig({
  // 相対パスで出力し、どのサブパス（例 /info_test_rs/）に置いても動くようにする。
  // 画面の切り替えは hash（#/articles/...）で行うため、直リンクでも 404 にならない。
  base: "./",
  server: { port: 5173, strictPort: true },
  preview: { port: 4173, strictPort: true },
  test: { environment: "jsdom", include: ["tests/**/*.test.ts"] },
});
