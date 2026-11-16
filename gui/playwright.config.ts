import { defineConfig } from "@playwright/test";

// e2e tests start their own `dipm serve` processes (e2e/server.ts); run `npm run build` first.
export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  workers: 1,
  reporter: [["list"]],
  use: {
    viewport: { width: 1440, height: 900 },
    launchOptions: { args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] },
  },
});
