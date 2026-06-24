import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Pure client-side SPA. No backend, no server runtime.
export default defineConfig({
  plugins: [react()],
});
