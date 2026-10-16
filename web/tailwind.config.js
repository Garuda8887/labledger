/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: "rgb(var(--color-surface) / <alpha-value>)",
          raised: "rgb(var(--color-surface-raised) / <alpha-value>)",
          overlay: "rgb(var(--color-surface-overlay) / <alpha-value>)",
        },
        ink: {
          DEFAULT: "rgb(var(--color-ink) / <alpha-value>)",
          muted: "rgb(var(--color-ink-muted) / <alpha-value>)",
          subtle: "rgb(var(--color-ink-subtle) / <alpha-value>)",
        },
        accent: {
          DEFAULT: "rgb(var(--color-accent) / <alpha-value>)",
          soft: "rgb(var(--color-accent-soft) / <alpha-value>)",
        },
        status: {
          normal: "rgb(var(--color-status-normal) / <alpha-value>)",
          borderline: "rgb(var(--color-status-borderline) / <alpha-value>)",
          out: "rgb(var(--color-status-out) / <alpha-value>)",
          unknown: "rgb(var(--color-status-unknown) / <alpha-value>)",
        },
        hairline: "rgb(var(--color-hairline) / <alpha-value>)",
      },
      fontFamily: {
        sans: ["Inter", "InterVariable", "system-ui", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      borderRadius: {
        card: "1rem",
      },
      boxShadow: {
        soft: "0 8px 32px rgb(0 0 0 / 0.35)",
      },
    },
  },
  plugins: [],
};
