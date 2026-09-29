import { defineConfig } from "vitest/config";
import { svelte } from "@sveltejs/vite-plugin-svelte";

export default defineConfig({
  plugins: [svelte({ hot: false })],
  test: {
    // jsdom only where a test asks for it via a // @vitest-environment docblock;
    // pure math and store tests run in node, which is ~4x faster to start.
    environment: "node",
    include: ["src/**/__tests__/**/*.test.ts", "mock/__tests__/**/*.test.ts"],
    restoreMocks: true,
    setupFiles: ["./vitest.setup.ts"],
  },
  resolve: {
    // Svelte 5 runes in .svelte.ts modules need the browser condition to resolve
    // to the client runtime rather than the SSR one.
    conditions: ["browser"],
  },
});
