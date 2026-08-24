import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Deep-sea instrument panel. ink = surfaces/borders (dark -> light),
        // fg = text (bright -> faint). glow/spark/coral are the three signal
        // colors: glow = positive pole + primary actions, spark = attention /
        // in-progress, coral = negative pole + errors.
        ink: {
          950: "#05070a",
          900: "#0a0f14",
          800: "#111920",
          700: "#1b2731",
          600: "#2a3941",
        },
        fg: {
          DEFAULT: "#eaf3f0",
          muted: "#8fa8a6",
          faint: "#546a6b",
        },
        glow: {
          DEFAULT: "#3FEBB8",
          bright: "#7FFFD9",
          dim: "#173b30",
        },
        spark: {
          DEFAULT: "#FFB343",
          dim: "#3a2a12",
        },
        coral: {
          DEFAULT: "#FF6E5E",
          dim: "#3a1a15",
        },
      },
      fontFamily: {
        display: ["var(--font-display)", "Georgia", "serif"],
        sans: ["var(--font-body)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(63,235,184,0.25), 0 0 24px -4px rgba(63,235,184,0.35)",
        panel: "inset 0 1px 0 0 rgba(255,255,255,0.04), 0 1px 2px rgba(0,0,0,0.4)",
      },
      // Static (non-animated) glow for the bolt icon: paired with
      // animate-bolt-flicker, which only animates opacity now so the
      // flicker stays on the compositor instead of repainting a filter
      // every frame.
      dropShadow: {
        glow: "0 0 3px rgba(63,235,184,0.7)",
      },
      backgroundImage: {
        grain:
          "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.05'/%3E%3C/svg%3E\")",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        // Opacity-only: the old version also animated `filter` (a
        // drop-shadow), which forces a repaint every frame instead of
        // running on the compositor. Opacity alone gives the same flicker
        // read at a fraction of the cost, running forever in the nav bar.
        "bolt-flicker": {
          "0%, 100%": { opacity: "1" },
          "45%": { opacity: "1" },
          "48%": { opacity: "0.4" },
          "50%": { opacity: "1" },
          "52%": { opacity: "0.6" },
          "55%": { opacity: "1" },
        },
        "sweep": {
          "0%": { transform: "translateX(-120%) skewX(-15deg)" },
          "100%": { transform: "translateX(220%) skewX(-15deg)" },
        },
        "value-pop": {
          "0%": { transform: "scale(1.1)", color: "#7FFFD9" },
          "60%": { transform: "scale(1)" },
          "100%": { color: "inherit" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.6s cubic-bezier(0.16,1,0.3,1) both",
        "bolt-flicker": "bolt-flicker 4s ease-in-out infinite",
        sweep: "sweep 1.1s ease-in-out",
        "value-pop": "value-pop 0.4s ease-out",
      },
    },
  },
  plugins: [],
};

export default config;
