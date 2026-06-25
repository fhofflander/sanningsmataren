import { resolve } from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  publicDir: "extension/public",
  build: {
    outDir: "dist-extension",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        popup: resolve(__dirname, "extension/popup.html"),
        background: resolve(__dirname, "src/extension/background.ts"),
        contentScript: resolve(__dirname, "src/extension/contentScript.ts"),
      },
      output: {
        entryFileNames: (chunk) => {
          if (chunk.name === "background") return "assets/background.js";
          if (chunk.name === "contentScript") return "assets/contentScript.js";
          return "assets/[name]-[hash].js";
        },
        chunkFileNames: "assets/[name]-[hash].js",
        assetFileNames: "assets/[name]-[hash][extname]",
      },
    },
  },
});
