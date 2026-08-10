import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Relative base so the built viewer can be served from any static path.
export default defineConfig({
  base: "./",
  plugins: [react()],
});
