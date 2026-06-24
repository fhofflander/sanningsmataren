/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Deep blue civic accent + cool-white instrument surfaces.
        accent: {
          DEFAULT: "#1d4ed8",
          deep: "#1e3a8a",
          soft: "#dbeafe",
        },
        surface: {
          DEFAULT: "#ffffff",
          muted: "#f1f5f9",
          page: "#f8fafc",
        },
      },
      fontFamily: {
        mono: [
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Consolas",
          "monospace",
        ],
        sans: [
          "Inter",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
      },
    },
  },
  plugins: [],
};
