export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { 50: "#f6f7fb", 100: "#eceff6", 200: "#d9deeb", 300: "#b9c1d6", 400: "#8a95b3", 500: "#5f6c8f", 600: "#46526f", 700: "#323c55", 800: "#1f2840", 900: "#121a30" },
        brand: { 50: "#eef4ff", 100: "#dbe7ff", 500: "#2f5bea", 600: "#2449cc", 700: "#1d3aa5" },
      },
      fontFamily: { sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "sans-serif"] },
    },
  },
  plugins: [],
};
