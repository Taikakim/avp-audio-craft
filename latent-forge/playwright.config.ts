import { defineConfig, devices } from "@playwright/test";

// 1800x900 is Kim's review viewport (spec §2.5, §11.3) and the size the
// handoff's drawing is compared against side by side. Everything runs against
// `dev:mock`, so no GPU, no render server and no model are needed.
export default defineConfig({
  testDir: "./tests",
  timeout: 30_000,
  expect: { timeout: 5_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    ...devices["Desktop Chrome"],
    baseURL: "http://127.0.0.1:5173",
    viewport: { width: 1800, height: 900 },
    deviceScaleFactor: 1,
  },
  webServer: {
    // --host 127.0.0.1: on this box Node's DNS resolver prefers the IPv6
    // loopback for a bare "localhost", so an unqualified `vite` dev server
    // binds only ::1 and every 127.0.0.1 connection (this config's baseURL)
    // is refused. Explicit host keeps the server on the address the spec
    // actually talks to.
    command: "npm run dev:mock -- --host 127.0.0.1",
    url: "http://127.0.0.1:5173",
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
