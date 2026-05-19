import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0d1117",
        slab: "#161b22",
        edge: "#30363d",
        text: "#c9d1d9",
        muted: "#8b949e",
        accent: "#58a6ff",
        ok: "#3fb950",
        warn: "#e3b341",
        err: "#f85149",
      },
      fontFamily: { mono: ['"Courier New"', "monospace"] },
    },
  },
} satisfies Config;
