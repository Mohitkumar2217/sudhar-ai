import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Cream + deep-maroon theme (matches the reference intake-form screenshot).
        // "gold" stays the primary/positive accent token name so every component
        // that already references text-gold / bg-gold / border-gold rethemes for
        // free — only the hex values changed here.
        bg: "#F6F1EA",
        panel: "#FFFFFF",
        panelBorder: "#E8DFD3",
        ink: "#2E2224",
        muted: "#8C7F76",
        gold: "#7B3B49",
        goldDim: "#F1E1E5",
        rust: "#B0473B",
        rustDim: "#F6E4DF",
      },
      fontFamily: {
        display: ["'Poppins'", "sans-serif"],
        body: ["'Inter'", "sans-serif"],
        mono: ["'IBM Plex Mono'", "monospace"],
      },
      borderRadius: {
        pill: "999px",
      },
    },
  },
  plugins: [],
};

export default config;
