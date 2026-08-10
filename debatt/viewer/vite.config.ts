import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Absolute base: the app uses client-side routing (/debatt/:id) and is
// deployed at the domain root with SPA rewrites.
export default defineConfig({
  base: "/",
  plugins: [react()],
});
