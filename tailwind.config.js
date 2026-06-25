/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Deep blue civic accent - the only interaction colour.
        accent: {
          DEFAULT: "#1d4ed8",
          deep: "#1e3a8a",
          soft: "#dbeafe",
        },
        // Partner brand colours - quarantined to the logos/attribution only.
        brand: {
          altctrl: "#3b9b62",
          "altctrl-ink": "#0f172a",
          eghed: "#000000",
        },
        ink: {
          DEFAULT: "#0f172a",
          muted: "#475569",
          faint: "#64748b",
        },
        line: {
          DEFAULT: "#e2e8f0",
          strong: "#cbd5e1",
        },
        surface: {
          DEFAULT: "#ffffff",
          muted: "#f1f5f9",
          page: "#f8fafc",
        },
      },
      fontFamily: {
        mono: [
          '"JetBrains Mono"',
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Consolas",
          "monospace",
        ],
        sans: [
          '"Inter"',
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
      },
      borderRadius: {
        lg: "0.625rem",
      },
      boxShadow: {
        sm: "0 1px 2px 0 rgb(15 23 42 / 0.05)",
      },
    },
  },
  plugins: [],
};
