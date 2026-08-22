import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["test/**/*.test.ts"],
    // Compiling a fixture is not fast, and there are many of them.
    testTimeout: 30_000,
  },
});
