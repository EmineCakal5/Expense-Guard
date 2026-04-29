/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        base: "var(--bg-base)",
        surface: "var(--bg-surface)",
        elevated: "var(--bg-elevated)",
        overlay: "var(--bg-overlay)",
        "text-primary": "var(--text-primary)",
        "text-secondary": "var(--text-secondary)",
        "text-muted": "var(--text-muted)",
        "accent-blue": "var(--accent-blue)",
        "accent-cyan": "var(--accent-cyan)",
        "risk-low": "var(--risk-low)",
        "risk-medium": "var(--risk-medium)",
        "risk-high": "var(--risk-high)",
      },
    },
  },
  plugins: [],
};

