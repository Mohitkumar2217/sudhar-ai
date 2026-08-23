import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#101314",
        panel: "#171b1d",
        panelBorder: "#262b2e",
        ink: "#EDEEE9",
        muted: "#8B9296",
        gold: "#E8A23D",
        goldDim: "#4a3a1f",
        rust: "#C1584B",
        rustDim: "#3a201c",
      },
      fontFamily: {
        display: ["'Space Grotesk'", "sans-serif"],
        body: ["'Inter'", "sans-serif"],
        mono: ["'IBM Plex Mono'", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
